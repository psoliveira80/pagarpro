"""Celery task: process inbound WhatsApp messages."""

from __future__ import annotations

import asyncio

import structlog

from app.workers import celery_app

log = structlog.get_logger()


@celery_app.task(
    name="app.workers.tasks.process_inbound_whatsapp.process_inbound_whatsapp",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    queue="whatsapp_inbound",
)
def process_inbound_whatsapp(self, event_id: str, provider: str) -> dict:
    """Process an inbound WhatsApp message.

    Steps:
    1. Load raw event from webhook_events_raw
    2. Parse payload via provider adapter
    3. Find or create conversation by phone number
    4. Persist message
    5. Enqueue agent turn (if agent is active on conversation)
    """
    return asyncio.run(_process(event_id, provider))


async def _process(event_id: str, provider: str) -> dict:
    from uuid import UUID

    from sqlalchemy import select

    from app.core.agent.conversation_store import ConversationStore
    from app.infrastructure.adapters.whatsapp.whatsapp_factory import (
        get_evolution_go_por_instance_id,
        get_whatsapp_gateway,
    )
    from app.infrastructure.db.models.customer import Customer
    from app.infrastructure.db.models.payable import WebhookEventRaw
    from app.infrastructure.db.session import get_sessionmaker

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        # Load raw event
        stmt = select(WebhookEventRaw).where(WebhookEventRaw.id == UUID(event_id))
        result = await session.execute(stmt)
        event = result.scalar_one_or_none()

        if event is None:
            log.error("webhook_event_not_found", event_id=event_id)
            return {"status": "error", "reason": "event_not_found"}

        payload = event.payload or {}
        headers = payload.pop("headers", {})

        # Story 13.21 — para Evolution Go, identifica a credencial específica
        # pelo `instanceId` no payload. Isso traz contexto multi-tenant +
        # numero_origem_id pra timeline unificada.
        numero_origem_id = None
        if provider == "evolution_go":
            instance_id = payload.get("instanceId") or payload.get("instance_id")
            if not instance_id:
                log.warning(
                    "evolution_go_webhook_sem_instance_id",
                    event_id=event_id,
                )
                event.processed = True
                await session.commit()
                return {"status": "skipped", "reason": "missing_instance_id"}

            adapter, cred = await get_evolution_go_por_instance_id(session, instance_id)
            if adapter is None or cred is None:
                log.error(
                    "evolution_go_instance_nao_cadastrada",
                    instance_id=instance_id,
                    event_id=event_id,
                )
                event.processed = True
                await session.commit()
                return {"status": "error", "reason": "instance_not_registered"}

            # Tenant context vem da credencial
            if event.empresa_id is None:
                event.empresa_id = cred.empresa_id
            numero_origem_id = cred.id
        else:
            # Fallback: providers legados (zapi/uazapi/evolution_api).
            # `get_whatsapp_gateway` busca o primeiro ativo na tabela.
            adapter = await get_whatsapp_gateway(session)

        if adapter is None:
            log.error("no_whatsapp_adapter", provider=provider)
            event.processed = True
            await session.commit()
            return {"status": "error", "reason": "no_adapter"}

        try:
            parsed = await adapter.parse_webhook(headers, payload)
        except ValueError as exc:
            log.warning("webhook_parse_failed", error=str(exc))
            event.processed = True
            await session.commit()
            return {"status": "error", "reason": "parse_failed"}

        if parsed is None:
            event.processed = True
            await session.commit()
            return {"status": "skipped", "reason": "irrelevant_event"}

        from app.domain.ports.whatsapp_gateway import ReceivedMessage, MessageStatusUpdate

        if isinstance(parsed, MessageStatusUpdate):
            event.processed = True
            await session.commit()
            return {"status": "status_update", "external_id": parsed.external_id}

        # It's a ReceivedMessage
        msg: ReceivedMessage = parsed

        # WhatsApp messages without a sender phone cannot be attributed to a
        # conversation. Skip and mark processed so retries don't pile up.
        if not msg.sender_phone:
            log.warning("inbound_whatsapp_missing_phone", event_id=event_id)
            event.processed = True
            await session.commit()
            return {"status": "skipped", "reason": "missing_sender_phone"}

        # Find customer by phone (only within the same tenant as the webhook).
        # If event.empresa_id is NULL (system-level webhook), there is no tenant
        # context — skip persisting since Conversa requires empresa_id NOT NULL.
        if event.empresa_id is None:
            log.warning("inbound_whatsapp_no_tenant", event_id=event_id)
            event.processed = True
            await session.commit()
            return {"status": "skipped", "reason": "no_tenant_context"}

        empresa_id = event.empresa_id

        # Match exato pelo número normalizado para evitar falsos positivos
        # (dois clientes com sufixos coincidentes). Cobre as variações comuns:
        # +5511987654321, 5511987654321, 11987654321, 987654321.
        customer_id = None
        digits_only = "".join(c for c in msg.sender_phone if c.isdigit())
        candidates = {
            digits_only,
            f"+{digits_only}",
            digits_only[-11:],
            digits_only[-10:],
            digits_only[-9:],
        }
        cust_stmt = (
            select(Customer)
            .where(
                Customer.empresa_id == empresa_id,
                Customer.phone.in_(candidates),
            )
            .limit(2)
        )
        cust_result = await session.execute(cust_stmt)
        matches = cust_result.scalars().all()
        if len(matches) == 1:
            customer_id = matches[0].id
        elif len(matches) > 1:
            log.warning(
                "inbound_whatsapp_ambiguous_customer",
                empresa_id=str(empresa_id),
                phone=msg.sender_phone,
                match_count=len(matches),
            )
            # Conversa fica sem customer_id; operador decide manualmente.

        # Get or create conversation
        store = ConversationStore(session, empresa_id)
        conv = await store.get_or_create_conversation(
            channel="whatsapp",
            phone_e164=msg.sender_phone,
            customer_id=customer_id,
        )

        # Persist message
        content = msg.text
        if msg.is_audio:
            content = "[audio message - pending transcription]"

        await store.append_message(
            conv.id,
            role="user",
            content_text=content,
            media_url=msg.media_url,
            media_mime=msg.media_mime,
            external_id=msg.external_id,
            sent_by="customer",
            numero_origem_id=numero_origem_id,
        )

        # Story 13.21 — atribui o número ao cliente se for o primeiro contato.
        # Idempotente: ServicoRoteamentoNumeros respeita atribuição estável.
        if numero_origem_id is not None and customer_id is not None:
            try:
                from app.application.services.servico_roteamento_numeros import (
                    ServicoRoteamentoNumeros,
                )
                # Carrega cliente atualizado pra checar se já tem número
                from app.infrastructure.db.models.cadastro import Cliente
                cliente = (await session.execute(
                    select(Cliente).where(Cliente.id == customer_id)
                )).scalar_one_or_none()
                if cliente is not None and cliente.numero_origem_id is None:
                    cliente.numero_origem_id = numero_origem_id
                    log.info(
                        "cliente_recebeu_numero_origem",
                        cliente_id=str(customer_id),
                        numero_origem_id=str(numero_origem_id),
                    )
            except Exception:
                log.warning("atribuir_numero_origem_falhou", exc_info=True)

        # Story 13.22 — handler do menu rígido do Evolution Go.
        # Só roda quando: (a) provider é evolution_go, (b) cliente identificado,
        # (c) agente automático está ativo (operadora não puxou takeover).
        # Quando humano assume (`agent_active=False`), state machine fica em
        # silêncio para não atropelar a conversa manual.
        if provider == "evolution_go" and customer_id is not None and conv.agent_active:
            try:
                await _processar_state_machine(
                    session=session,
                    empresa_id=empresa_id,
                    cliente_id=customer_id,
                    conversa=conv,
                    msg=msg,
                    adapter=adapter,
                )
            except Exception:
                log.exception("state_machine_falhou")

        event.processed = True
        await session.commit()

        # Enqueue agent turn if agent is active AND provider is legacy.
        # Pro Evolution Go a state machine já cuidou (e só repassa pra IA se
        # ia_atendente_ativa via tool — Story 13.26).
        if conv.agent_active and provider != "evolution_go":
            try:
                from app.workers import celery_app as celery

                celery.send_task(
                    "app.workers.tasks.run_agent_turn.run_agent_turn",
                    args=[str(conv.id), content or ""],
                    queue="agent",
                )
            except Exception:
                log.warning("agent_turn_enqueue_failed", exc_info=True)

        return {"status": "processed", "conversation_id": str(conv.id)}


# ───────────────────── Story 13.22 — handler da state machine ─────────────────


async def _processar_state_machine(
    *,
    session,
    empresa_id,
    cliente_id,
    conversa,
    msg,
    adapter,
):
    """Aplica a state machine do número rígido sobre a mensagem inbound.

    Estados são persistidos em `conversa.estado_maquina` e nos campos
    auxiliares (`aguardando_comprovante_ate`, etc.). Cada ação é despachada
    para o `ServicoAcoesCliente`, e a resposta sai pelo `adapter` (Evolution Go).
    """
    from datetime import datetime, timedelta, timezone

    from app.application.services.servico_acoes_cliente import (
        AcaoNaoPermitidaError,
        ServicoAcoesCliente,
    )
    from app.application.services.servico_configuracao import ServicoConfiguracao
    from app.application.services.servico_menu_adaptativo import (
        ServicoMenuAdaptativo,
    )
    from app.domain.comunicacao.maquina_numero_rigido import (
        AcaoMaquina,
        EntradaEvento,
        EstadoMaquina,
        decidir,
    )
    from app.infrastructure.adapters.whatsapp.evolution_go_adapter import (
        BotaoPix,
        BotaoReply,
        SecaoLista,
    )

    # ── Monta entrada da máquina ──────────────────────────────────────
    if msg.text and msg.text.startswith("__btn__:"):
        evento = EntradaEvento(tipo="botao", botao_id=msg.text[len("__btn__:"):])
    elif msg.text and msg.text.startswith("__row__:"):
        evento = EntradaEvento(tipo="botao", botao_id=msg.text[len("__row__:"):])
    elif msg.media_url:
        evento = EntradaEvento(
            tipo="midia",
            tem_midia=True,
            midia_url=msg.media_url,
        )
    elif msg.text:
        evento = EntradaEvento(tipo="texto", texto=msg.text)
    else:
        return  # nada a fazer

    # ── Estado atual + configurações ──────────────────────────────────
    try:
        estado_atual = EstadoMaquina(conversa.estado_maquina or "idle")
    except ValueError:
        estado_atual = EstadoMaquina.IDLE

    aguardando_valido = False
    if (
        conversa.aguardando_comprovante_ate is not None
        and conversa.aguardando_comprovante_ate > datetime.now(timezone.utc)
    ):
        aguardando_valido = True

    config = ServicoConfiguracao(session, empresa_id, redis=None)
    ia_ativa = await config.obter_booleano(
        "ia_atendente_ativa", "comunicacao", padrao=False
    )

    decisao = decidir(
        estado_atual=estado_atual,
        evento=evento,
        ia_atendente_ativa=ia_ativa,
        aguardando_comprovante_valido=aguardando_valido,
    )

    # ── Aplica efeitos ────────────────────────────────────────────────
    servico_menu = ServicoMenuAdaptativo(session, empresa_id)
    servico_acoes = ServicoAcoesCliente(session, empresa_id)
    telefone = msg.sender_phone

    async def _enviar_menu(prefixo: str | None = None):
        menu = await servico_menu.montar_menu(cliente_id)
        descricao = (prefixo + "\n\n" + menu.descricao) if prefixo else menu.descricao
        if menu.eh_lista:
            secao = SecaoLista(
                titulo="Opções",
                linhas=[{"id": o.id, "title": o.titulo[:24], "description": ""} for o in menu.opcoes],
            )
            await adapter.send_list(
                telefone,
                descricao=descricao,
                secoes=[secao],
                texto_botao="Ver opções",
            )
        else:
            await adapter.send_buttons_reply(
                telefone,
                descricao=descricao,
                botoes=[BotaoReply(id=o.id, titulo=o.titulo) for o in menu.opcoes],
            )

    if decisao.acao == AcaoMaquina.ENVIAR_MENU:
        prefixo = (decisao.parametros or {}).get("explicacao")
        await _enviar_menu(prefixo)

    elif decisao.acao == AcaoMaquina.NAO_ENTENDEU:
        await _enviar_menu(
            "Use os botões abaixo para continuar. 🙂"
        )

    elif decisao.acao == AcaoMaquina.ENVIAR_EXTRATO:
        texto = await servico_acoes.montar_extrato_saldo(cliente_id)
        await adapter.send_text(telefone, texto)
        await _enviar_menu()

    elif decisao.acao == AcaoMaquina.ENVIAR_QR_PIX:
        try:
            dados = await servico_acoes.gerar_pix_para_proximo_titulo(cliente_id)
            await adapter.send_button_pix(
                telefone,
                descricao=(
                    f"{dados.descricao}\n\n"
                    f"💰 Valor: R$ {dados.valor:.2f}\n"
                    f"Toque no botão abaixo para pagar via PIX:"
                ),
                botao_pix=BotaoPix(
                    nome_recebedor=dados.nome_recebedor,
                    chave_pix=dados.chave_pix,
                    tipo_chave=dados.tipo_chave,
                ),
            )
        except AcaoNaoPermitidaError as exc:
            await adapter.send_text(telefone, f"⚠️ {exc}")
            await _enviar_menu()

    elif decisao.acao == AcaoMaquina.INICIAR_CAPTURA_COMPROVANTE:
        timeout_min = await config.obter_inteiro(
            "timeout_aguardar_comprovante_min", "comunicacao", padrao=5
        )
        conversa.aguardando_comprovante_ate = datetime.now(timezone.utc) + timedelta(
            minutes=timeout_min
        )
        await _enviar_template(
            session, empresa_id, telefone, adapter,
            "iniciar_captura_comprovante", {"timeout_min": timeout_min},
            fallback=(
                f"📎 Pode mandar a foto/PDF do comprovante agora.\n"
                f"Vou processar automaticamente quando chegar! 🙂\n\n"
                f"(Aguardo até {timeout_min} minutos.)"
            ),
        )

    elif decisao.acao == AcaoMaquina.PROCESSAR_COMPROVANTE:
        # Story 13.23 AC 8: cliente pode mandar 2+ fotos em sequência dentro
        # do timeout. Mantemos o flag `aguardando_comprovante_ate` válido até
        # expirar naturalmente — cada mídia que chegar nessa janela vira
        # comprovante. Idempotência fica por conta do hash SHA-256 no
        # ServicoAnaliseComprovante (mídia idêntica reenviada não é reanalisada).
        log.info(
            "comprovante_recebido_via_menu",
            cliente_id=str(cliente_id),
            midia_url=(decisao.parametros or {}).get("midia_url"),
        )
        await _enviar_template(
            session, empresa_id, telefone, adapter,
            "comprovante_recebido_inicial", {},
            fallback="📎 Recebi seu comprovante! Vou analisar e te aviso em instantes. 🙂",
        )
        # 13.23 dispara tarefa Celery a partir daqui.
        try:
            from app.workers import celery_app as celery
            celery.send_task(
                "app.workers.tasks.analisar_e_validar_comprovante_whatsapp.executar",
                args=[
                    str(empresa_id),
                    str(cliente_id),
                    (decisao.parametros or {}).get("midia_url"),
                    telefone,
                ],
                queue="default",
            )
        except Exception:
            log.exception("nao_conseguiu_disparar_analise_comprovante")

    elif decisao.acao == AcaoMaquina.PEDIR_CONFIRMACAO_ADIAMENTO:
        from app.domain.comunicacao.maquina_numero_rigido import (
            ID_CONFIRMA_ADIAR_SIM,
            ID_CONFIRMA_ADIAR_NAO,
        )
        dias = await config.obter_inteiro(
            "dias_maximos_adiamento", "cobranca", padrao=5
        )
        await adapter.send_buttons_reply(
            telefone,
            descricao=(
                f"Confirma adiar a próxima parcela em {dias} dias?\n"
                f"(Você só pode usar essa opção uma vez no período.)"
            ),
            botoes=[
                BotaoReply(id=ID_CONFIRMA_ADIAR_SIM, titulo="✓ Sim, adiar"),
                BotaoReply(id=ID_CONFIRMA_ADIAR_NAO, titulo="✗ Cancelar"),
            ],
        )

    elif decisao.acao == AcaoMaquina.APLICAR_ADIAMENTO:
        try:
            resultado = await servico_acoes.aplicar_adiamento(cliente_id)
            await adapter.send_text(
                telefone,
                f"✓ Adiamento aplicado! Nova data de vencimento: "
                f"{resultado['vencimento_novo']}.\n"
                f"Continuamos contando contigo. 🙏",
            )
        except AcaoNaoPermitidaError as exc:
            await adapter.send_text(telefone, f"⚠️ Não foi possível adiar: {exc}")
            await _enviar_menu()

    elif decisao.acao == AcaoMaquina.PEDIR_CONFIRMACAO_DESBLOQUEIO:
        from app.domain.comunicacao.maquina_numero_rigido import (
            ID_CONFIRMA_DESBLOQUEIO_SIM,
            ID_CONFIRMA_DESBLOQUEIO_NAO,
        )
        dias = await config.obter_inteiro(
            "desbloqueio_confianca_dias", "frota", padrao=3
        )
        await adapter.send_buttons_reply(
            telefone,
            descricao=(
                f"Confirma desbloqueio em confiança por {dias} dias?\n"
                f"Você compromete-se a pagar nesse período."
            ),
            botoes=[
                BotaoReply(id=ID_CONFIRMA_DESBLOQUEIO_SIM, titulo="✓ Sim, libera"),
                BotaoReply(id=ID_CONFIRMA_DESBLOQUEIO_NAO, titulo="✗ Cancelar"),
            ],
        )

    elif decisao.acao == AcaoMaquina.APLICAR_DESBLOQUEIO_CONFIANCA:
        try:
            resultado = await servico_acoes.aplicar_desbloqueio_confianca(cliente_id)
            await adapter.send_text(
                telefone,
                f"🔓 Veículo liberado por {resultado['dias_desbloqueio']} dias "
                f"(até {resultado['validade_ate']}).\nValeu a confiança! 🙏",
            )
        except AcaoNaoPermitidaError as exc:
            await adapter.send_text(telefone, f"⚠️ {exc}")
            await _enviar_menu()

    elif decisao.acao == AcaoMaquina.PEDIR_VALOR_PARCIAL:
        await adapter.send_text(
            telefone,
            "💸 Digite o valor que você quer pagar agora (ex.: 250,00):",
        )

    elif decisao.acao == AcaoMaquina.APLICAR_PAGAMENTO_PARCIAL:
        try:
            dados = await servico_acoes.gerar_pix_parcial(
                cliente_id,
                (decisao.parametros or {}).get("texto_valor", ""),
            )
            await adapter.send_button_pix(
                telefone,
                descricao=(
                    f"{dados.descricao}\n💰 Valor parcial: R$ {dados.valor:.2f}"
                ),
                botao_pix=BotaoPix(
                    nome_recebedor=dados.nome_recebedor,
                    chave_pix=dados.chave_pix,
                    tipo_chave=dados.tipo_chave,
                ),
            )
        except AcaoNaoPermitidaError as exc:
            await adapter.send_text(telefone, f"⚠️ {exc}")
            await _enviar_menu()

    elif decisao.acao == AcaoMaquina.REGISTRAR_CONFIRMACAO_RECEBIMENTO:
        # Story 13.25 AC 4 — delega para ServicoConfirmacaoRecebimento
        # (validação multi-tenant + audit + UPDATE da conversa).
        from uuid import UUID as _UUID
        from app.application.services.servico_confirmacao_recebimento import (
            ServicoConfirmacaoRecebimento,
        )

        titulo_id_str = (decisao.parametros or {}).get("titulo_id")
        tit_id = None
        try:
            tit_id = _UUID(titulo_id_str) if titulo_id_str else None
        except (ValueError, TypeError):
            log.warning(
                "confirmacao_recebimento_titulo_id_invalido",
                valor=titulo_id_str,
            )

        try:
            servico_conf = ServicoConfirmacaoRecebimento(session, empresa_id)
            await servico_conf.registrar(
                conversa_id=conversa.id,
                titulo_id=tit_id,
                ator="cliente",
            )
        except Exception:
            log.exception("falha_registrar_confirmacao")

        await _enviar_template(
            session, empresa_id, telefone, adapter,
            "agradecimento_confirmacao_recebimento", {},
            fallback="Obrigado! Avisaremos novamente próximo do vencimento. 🙂",
        )

    elif decisao.acao == AcaoMaquina.INICIAR_ATENDIMENTO_IA:
        # Story 13.26 (V2) — encaminhar para AgentOrchestrator existente.
        # V1: só responde mensagem padrão até a IA ser totalmente plugada.
        await adapter.send_text(
            telefone,
            "🤖 IA atendente em ativação. Em breve disponível! Use os botões por enquanto.",
        )
        await _enviar_menu()

    # ── Persiste novo estado ──────────────────────────────────────────
    if decisao.proximo_estado.value != conversa.estado_maquina:
        conversa.estado_maquina = decisao.proximo_estado.value

    await session.flush()


async def _enviar_template(
    session,
    empresa_id,
    telefone: str,
    adapter,
    nome_template: str,
    contexto: dict,
    *,
    fallback: str,
) -> None:
    """Renderiza template via RenderizadorTemplate e envia ao cliente.

    Se template ausente (não seedado pra esse tenant nem global) ou render
    falhar, usa `fallback` (texto puro) — cliente nunca fica sem resposta.
    """
    from app.infrastructure.mensageria.renderizador_template import (
        RenderizadorTemplate,
        TemplateNaoEncontradoError,
        TemplateRenderError,
    )

    texto = fallback
    try:
        renderizador = RenderizadorTemplate(session, empresa_id)
        texto = await renderizador.renderizar(nome_template, contexto, canal="whatsapp")
    except TemplateNaoEncontradoError:
        log.info(
            "template_nao_encontrado_usando_fallback",
            template=nome_template,
            empresa_id=str(empresa_id),
        )
    except TemplateRenderError:
        log.exception("template_render_falhou", template=nome_template)
    try:
        await adapter.send_text(telefone, texto)
    except Exception:
        log.exception("falha_enviar_template", template=nome_template)
