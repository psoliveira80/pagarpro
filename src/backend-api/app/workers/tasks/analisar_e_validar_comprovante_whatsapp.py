"""Task Celery — Story 13.23.

Fluxo (assíncrono, fora do webhook):
1. Baixa a mídia do Evolution Go (URL temporária).
2. Roda `ServicoAnaliseComprovante.analisar()` sobre os bytes.
3. Decide auto-homologar:
   - cliente NÃO está em blacklist
   - `score_confianca >= score_minimo_auto_homologar`
   - tem `titulo_match_id` válido + `valor_detectado`
4. Se auto-homologa:
   - dispara `ServicoTituloPago.registrar_pagamento`
   - se `desbloqueio_automatico_apos_validacao` e contrato está suspenso:
     reativa contrato via `ServicoSituacaoContrato`
   - responde WhatsApp: "✓ Pagamento confirmado! Veículo liberado."
5. Se NÃO auto-homologa:
   - responde WhatsApp: "Recebido, em análise. Avisaremos em breve."
   - registro fica `status='analisado'` aguardando gestor.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import httpx
import structlog

from app.workers import celery_app


log = structlog.get_logger()


@celery_app.task(
    name="app.workers.tasks.analisar_e_validar_comprovante_whatsapp.executar",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
    queue="default",
)
def executar(
    self,
    empresa_id: str,
    cliente_id: str,
    media_url: str | None,
    telefone_remetente: str,
) -> dict:
    return asyncio.run(
        _executar(empresa_id, cliente_id, media_url, telefone_remetente)
    )


async def _executar(
    empresa_id: str,
    cliente_id: str,
    media_url: str | None,
    telefone_remetente: str,
) -> dict:
    from sqlalchemy import select

    from app.application.services.servico_analise_comprovante import (
        ComprovanteJaAnalisadoError,
        ServicoAnaliseComprovante,
    )
    from app.application.services.servico_configuracao import ServicoConfiguracao
    from app.application.services.servico_titulo_pago import ServicoTituloPago
    from app.infrastructure.db.models.cadastro import Cliente
    from app.infrastructure.db.models.contrato import Contrato
    from app.infrastructure.db.session import get_sessionmaker

    if not media_url:
        return {"status": "skipped", "reason": "no_media_url"}

    empresa_uuid = UUID(empresa_id)
    cliente_uuid = UUID(cliente_id)

    # 1. Baixa o arquivo
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(media_url)
            resp.raise_for_status()
            bytes_arquivo = resp.content
            mime = resp.headers.get("content-type", "application/octet-stream").split(";")[0].strip()
    except Exception:
        log.exception("falha_download_midia", url=media_url)
        return {"status": "error", "reason": "download_failed"}

    # 2. Analisa
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        cliente = (await session.execute(
            select(Cliente).where(
                Cliente.id == cliente_uuid,
                Cliente.empresa_id == empresa_uuid,
            )
        )).scalar_one_or_none()
        if cliente is None:
            return {"status": "error", "reason": "cliente_nao_encontrado"}

        servico = ServicoAnaliseComprovante(session, empresa_uuid)
        try:
            comprovante = await servico.analisar(
                bytes_arquivo=bytes_arquivo,
                tipo_mime=mime,
                arquivo_url=media_url,
                cliente_id=cliente_uuid,
                origem="whatsapp_menu",
                telefone_remetente=telefone_remetente,
            )
        except ComprovanteJaAnalisadoError as ja:
            await _responder_template(
                session, empresa_uuid, telefone_remetente,
                "comprovante_ja_enviado", {},
                fallback="📎 Esse comprovante já tinha sido enviado antes — verificamos o histórico.",
            )
            await session.commit()
            return {
                "status": "already_analyzed",
                "comprovante_id": str(ja.comprovante_existente.id),
            }

        # 3. Decisão de auto-homologação delegada ao ServicoValidacaoAutomatica
        # (Story 13.23 AC 3 — refactor hexagonal). Service é puro, devolve
        # decisão + motivo. Worker só orquestra os efeitos.
        from app.application.services.servico_validacao_automatica import (
            ServicoValidacaoAutomatica,
        )
        servico_validacao = ServicoValidacaoAutomatica(session, empresa_uuid)
        decisao = await servico_validacao.avaliar(comprovante.id)

        config = ServicoConfiguracao(session, empresa_uuid, redis=None)
        desbloqueio_auto = await config.obter_booleano(
            "desbloqueio_automatico_apos_validacao", "comprovantes", padrao=True
        )

        if not decisao.pode_auto:
            # Cliente em blacklist recebe template específico (não revela
            # a flag) — demais casos recebem o template "aguardando análise".
            nome_template = (
                "comprovante_rejeitado_blacklist"
                if decisao.blacklist
                else "comprovante_aguardando_validacao_manual"
            )
            await _responder_template(
                session, empresa_uuid, telefone_remetente,
                nome_template, {"motivo": decisao.motivo},
                fallback=(
                    f"📎 Recebi seu comprovante! Está em análise.\n"
                    f"Vou te avisar assim que confirmar. 🙂\n\n"
                    f"(motivo: {decisao.motivo})"
                ),
            )
            await session.commit()
            return {
                "status": "manual_review",
                "comprovante_id": str(comprovante.id),
                "motivo": decisao.motivo,
            }

        # 4. Auto-homologa
        try:
            servico_titulo = ServicoTituloPago(session, empresa_uuid)
            resultado_pagamento = await servico_titulo.registrar_pagamento(
                titulo_id=comprovante.titulo_id,
                valor_pago=comprovante.valor_detectado,
                data_pagamento=(
                    comprovante.data_detectada.date()
                    if comprovante.data_detectada
                    else None
                ),
                forma_pagamento="pix",
                ator_id=None,  # sistema
            )
        except Exception:
            log.exception("falha_registrar_pagamento_auto",
                          comprovante_id=str(comprovante.id))
            await _responder_template(
                session, empresa_uuid, telefone_remetente,
                "comprovante_erro_homologacao", {},
                fallback=(
                    "📎 Recebi seu comprovante. Houve um problema no processamento "
                    "automático — um humano vai revisar e te confirmar em breve."
                ),
            )
            await session.commit()
            return {"status": "auto_homologate_failed"}

        from datetime import datetime, timezone
        comprovante.status = "homologado"
        comprovante.homologado_em = datetime.now(timezone.utc)

        decisao_pagamento = (resultado_pagamento or {}).get("decisao", "integral")
        # Pagamento PARCIAL (fundido/separado) — sobrou saldo; não reativa
        # contrato automaticamente. Cliente precisa saber que ainda deve algo.
        pagamento_parcial = decisao_pagamento in ("fundido", "separado")

        # 5. Desbloqueio do contrato (só quando pagamento integral/excedente
        # quitou a parcela) — pagamento parcial deixa contrato como está.
        contrato_reativado = False
        if desbloqueio_auto and not pagamento_parcial:
            contrato = (await session.execute(
                select(Contrato).where(
                    Contrato.cliente_id == cliente_uuid,
                    Contrato.empresa_id == empresa_uuid,
                    Contrato.status == "suspenso",
                )
                .order_by(Contrato.data_inicio.desc())
                .limit(1)
            )).scalar_one_or_none()
            if contrato is not None:
                try:
                    from app.application.services.servico_situacao_contrato import (
                        ServicoSituacaoContrato,
                    )
                    from app.domain.contracts.state_machine import SituacaoContrato
                    svc_sit = ServicoSituacaoContrato(session, empresa_uuid)
                    await svc_sit.transicionar(
                        contrato.id,
                        SituacaoContrato.VIGENTE,
                        motivo="Reativação automática — pagamento via WhatsApp confirmado",
                        ator_id=None,
                    )
                    contrato_reativado = True
                except Exception:
                    log.exception("falha_reativar_contrato")

        # 6. Confirma com o cliente via template (parcial vs integral).
        if pagamento_parcial:
            await _responder_template(
                session, empresa_uuid, telefone_remetente,
                "comprovante_validado_parcial", {},
                fallback=(
                    "✓ Pagamento parcial recebido! O restante foi adicionado à "
                    "próxima parcela. Veículo continua na situação anterior."
                ),
            )
        else:
            await _responder_template(
                session, empresa_uuid, telefone_remetente,
                "comprovante_validado_automatico",
                {"contrato_reativado": contrato_reativado},
                fallback=(
                    "✓ Pagamento confirmado! Veículo liberado. Boa rodagem 🚗💨"
                    if contrato_reativado
                    else "✓ Pagamento confirmado! Valeu 🙏"
                ),
            )
        await session.commit()
        return {
            "status": "auto_homologated",
            "comprovante_id": str(comprovante.id),
            "titulo_id": str(comprovante.titulo_id),
            "contrato_reativado": contrato_reativado,
        }


async def _responder(session, empresa_id: UUID, telefone: str, texto: str) -> None:
    """Envia mensagem usando o adapter Evolution Go atribuído ao cliente.

    Se não encontrar, usa o primeiro número da empresa (fallback). Falhas
    são logadas mas não propagam — a homologação não pode rolar back por
    causa de erro de envio.
    """
    try:
        from app.infrastructure.adapters.whatsapp.whatsapp_factory import (
            get_evolution_go_por_credencial_telefone,
        )
        adapter = await get_evolution_go_por_credencial_telefone(
            session, empresa_id, telefone
        )
        if adapter is None:
            log.warning("sem_adapter_para_resposta", telefone=telefone)
            return
        await adapter.send_text(telefone, texto)
    except Exception:
        log.exception("falha_enviar_resposta_whatsapp", telefone=telefone)


async def _responder_template(
    session,
    empresa_id: UUID,
    telefone: str,
    nome_template: str,
    contexto: dict,
    *,
    fallback: str,
) -> None:
    """Renderiza `nome_template` via RenderizadorTemplate e envia ao cliente.

    Se template não estiver seedado ou render falhar, usa `fallback` (texto
    puro). Isso garante que o cliente NUNCA fica sem resposta por causa de
    template ausente — mas o sistema continua funcional enquanto o seed
    propaga em todos os tenants.
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
    await _responder(session, empresa_id, telefone, texto)
