"""Motor `alertar_vencimentos_proximos` (Epic 13, Story 13.7).

Lembrete proativo de vencimento via canal de cobrança. Reduz inadimplência
sem mensagem de cobrança formal.

Schedule: diário às 08:00 UTC, fan-out por empresa via `dispatch_por_empresa`.

Fluxo por empresa:

1. Lê config `dias_antecedencia_lembrete` (default 3) e `canal_cobranca_principal`
   (default `whatsapp`).
2. Busca títulos `tipo='parcela'`, `status='em_aberto'`, com
   `data_vencimento` entre `hoje+1` e `hoje + N`.
3. Para cada título:
   - Skip se já enviado lembrete hoje (`lembretes_enviados` UNIQUE day-based).
   - Renderiza template `lembrete_vencimento` com contexto do cliente/título/veículo.
   - Envia via canal (tenta principal; fallback se config tem fallback).
   - Persiste resultado em `lembretes_enviados`.
4. Tracker em `motor.execucoes_motor`.

Idempotência (3 camadas, Story 13.5):
- `LockOperacao` por título (Redis lock).
- Unique index `(titulo_id, tipo, DATE(enviado_em))` no banco.
- Skip explícito por `SELECT` antes de enviar.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.servico_configuracao import ServicoConfiguracao
from app.core.channels.registry import channel_registry
from app.core.tenant_context import reset_empresa_id, set_empresa_id
from app.infrastructure.db import models  # noqa: F401 — registra metadata
from app.infrastructure.db.models.cadastro import Cliente
from app.infrastructure.db.models.contrato import Contrato
from app.infrastructure.db.models.financeiro import TituloReceber
from app.infrastructure.db.models.lembrete_enviado import LembreteEnviado
from app.infrastructure.db.models.veiculos import Veiculo
from app.infrastructure.mensageria.renderizador_template import (
    RenderizadorTemplate,
    TemplateNaoEncontradoError,
    TemplateRenderError,
)
from app.workers import celery_app
from app.workers.base_motor import ExecucaoMotorTracker
from app.workers.idempotencia import LockOperacao


log = structlog.get_logger()

NOME_TAREFA = "alertar_vencimentos_proximos"
TIPO_LEMBRETE = "lembrete_vencimento"


async def _ja_enviado_hoje(
    session: AsyncSession, titulo_id: UUID, tipo: str
) -> bool:
    """Checa se um lembrete do mesmo tipo já foi enviado hoje (UTC)."""
    hoje = datetime.now(timezone.utc).date()
    result = await session.execute(text("""
        SELECT 1 FROM financeiro.lembretes_enviados
        WHERE titulo_id = :tid
          AND tipo = :tipo
          AND (enviado_em AT TIME ZONE 'UTC')::date = :hoje
        LIMIT 1
    """), {"tid": str(titulo_id), "tipo": tipo, "hoje": hoje})
    return result.first() is not None


async def _montar_contexto(
    session: AsyncSession, titulo: TituloReceber
) -> dict | None:
    """Carrega cliente + contrato + veículo + empresa para o template."""
    contrato = (await session.execute(
        select(Contrato).where(Contrato.id == titulo.contrato_id)
    )).scalar_one_or_none()
    if contrato is None:
        return None

    cliente = (await session.execute(
        select(Cliente).where(Cliente.id == contrato.cliente_id)
    )).scalar_one_or_none()
    if cliente is None:
        return None

    veiculo = (await session.execute(
        select(Veiculo).where(Veiculo.id == contrato.veiculo_id)
    )).scalar_one_or_none()

    nome_completo = cliente.nome_completo or ""
    primeiro_nome = nome_completo.split(" ")[0] if nome_completo else ""

    return {
        "cliente": {
            "nome": nome_completo,
            "primeiro_nome": primeiro_nome,
            "telefone": cliente.telefone or "",
        },
        "titulo": {
            "valor": f"R$ {titulo.valor:.2f}".replace(".", ","),
            "valor_atualizado": f"R$ {titulo.valor:.2f}".replace(".", ","),
            "data_vencimento": titulo.data_vencimento.strftime("%d/%m/%Y"),
            "dias_atraso": 0,
            "numero_parcela": titulo.numero_parcela or titulo.sequencia,
        },
        "veiculo": {
            "placa": veiculo.placa if veiculo else "",
            "modelo": (veiculo.fipe_modelo if veiculo else "") or "",
        },
        "contrato": {
            "id": str(contrato.id)[:8],
            "data_inicio": contrato.data_inicio.strftime("%d/%m/%Y"),
        },
        "empresa": {
            "nome": "",
            "telefone": "",
        },
    }


async def _enviar_via_canal(
    canal_tipo: str, telefone: str, mensagem: str
) -> tuple[bool, str | None]:
    """Tenta enviar via o primeiro adapter registrado do tipo do canal.

    Retorna (sucesso, erro_msg). Não levanta exceção — empacota tudo no return.
    """
    canais = channel_registry.get_channels_by_type(canal_tipo)
    if not canais:
        return False, f"Nenhum canal '{canal_tipo}' registrado"

    canal = canais[0]
    try:
        await canal.send_text(telefone, mensagem)
        return True, None
    except Exception as exc:
        return False, str(exc)


async def _enviar_lembrete_whatsapp_com_botao(
    session: AsyncSession,
    empresa_id: UUID,
    telefone: str,
    mensagem: str,
    titulo_id: UUID,
) -> tuple[bool, str | None]:
    """Story 13.25 — Envia o lembrete via Evolution Go com botão
    'Confirmo recebimento'. O id do botão carrega o `titulo_id` para
    o state machine processar quando o cliente clicar.

    Se não há Evolution Go ativo para o tenant, retorna (False, motivo) e
    o caller faz fallback pra `_enviar_via_canal` (texto puro).
    """
    from app.domain.comunicacao.maquina_numero_rigido import PREFIXO_RECEBIMENTO
    from app.infrastructure.adapters.whatsapp.evolution_go_adapter import (
        BotaoReply,
        EvolutionGoAdapter,
    )
    from app.infrastructure.adapters.whatsapp.whatsapp_factory import (
        get_evolution_go_por_credencial_telefone,
    )

    adapter = await get_evolution_go_por_credencial_telefone(
        session, empresa_id, telefone
    )
    if not isinstance(adapter, EvolutionGoAdapter):
        return False, "sem_evolution_go"

    try:
        await adapter.send_buttons_reply(
            telefone,
            descricao=mensagem,
            botoes=[
                BotaoReply(
                    id=f"{PREFIXO_RECEBIMENTO}{titulo_id}",
                    titulo="✓ Confirmo recebimento",
                ),
            ],
        )
        return True, None
    except Exception as exc:
        return False, str(exc)


async def _processar_titulo(
    session: AsyncSession,
    titulo: TituloReceber,
    empresa_id: UUID,
    canal_principal: str,
    canal_fallback: str,
    renderizador: RenderizadorTemplate,
    tracker: ExecucaoMotorTracker,
    redis,
) -> None:
    async with LockOperacao(redis, "alertar_vencimento", str(titulo.id)) as lock:
        if not lock.adquirido:
            log.info("titulo_em_processamento_por_outro_worker", titulo_id=str(titulo.id))
            return

        if await _ja_enviado_hoje(session, titulo.id, TIPO_LEMBRETE):
            log.info("lembrete_ja_enviado_hoje", titulo_id=str(titulo.id))
            return

        contexto = await _montar_contexto(session, titulo)
        if contexto is None:
            tracker.registrar_erro({"titulo_id": str(titulo.id), "erro": "contexto incompleto (cliente/contrato/veiculo)"})
            return
        telefone = contexto["cliente"]["telefone"]
        if not telefone:
            tracker.registrar_erro({"titulo_id": str(titulo.id), "erro": "cliente sem telefone"})
            return

        try:
            mensagem = await renderizador.renderizar(
                "lembrete_vencimento", contexto, canal="whatsapp"
            )
        except (TemplateNaoEncontradoError, TemplateRenderError) as exc:
            tracker.registrar_erro({"titulo_id": str(titulo.id), "erro_template": str(exc)})
            return

        # Envio com fallback. Quando o canal principal é WhatsApp, tenta primeiro
        # via Evolution Go com botão "Confirmo recebimento" (Story 13.25). Se
        # não houver Evolution Go ativo, cai pra _enviar_via_canal (texto puro).
        canal_usado = canal_principal
        sucesso, erro = False, None
        if canal_principal == "whatsapp":
            sucesso, erro = await _enviar_lembrete_whatsapp_com_botao(
                session, empresa_id, telefone, mensagem, titulo.id
            )
        if not sucesso:
            sucesso, erro = await _enviar_via_canal(canal_principal, telefone, mensagem)
        if not sucesso and canal_fallback:
            log.warning(
                "canal_principal_falhou_tentando_fallback",
                titulo_id=str(titulo.id),
                canal_principal=canal_principal,
                canal_fallback=canal_fallback,
                erro_principal=erro,
            )
            canal_usado = canal_fallback
            sucesso, erro = await _enviar_via_canal(canal_fallback, telefone, mensagem)

        session.add(LembreteEnviado(
            empresa_id=empresa_id,
            titulo_id=titulo.id,
            tipo=TIPO_LEMBRETE,
            canal=canal_usado,
            sucesso=sucesso,
            erro=erro,
        ))
        if sucesso:
            tracker.registrar_sucesso()
        else:
            tracker.registrar_erro({"titulo_id": str(titulo.id), "canal": canal_usado, "erro": erro})


async def _run(empresa_id: UUID) -> dict[str, int]:
    from app.infrastructure.db.session import get_sessionmaker
    from app.infrastructure.settings import get_settings
    from redis.asyncio import Redis

    settings = get_settings()
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    session_factory = get_sessionmaker()

    # Tracker em session separada
    tracker_session = session_factory()
    await tracker_session.execute(
        text("SELECT set_config('app.empresa_id', :eid, true)"),
        {"eid": str(empresa_id)},
    )
    tracker = ExecucaoMotorTracker(tracker_session, NOME_TAREFA, empresa_id)
    await tracker.__aenter__()
    await tracker_session.commit()

    try:
        async with session_factory() as session:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(empresa_id)},
            )

            servico_config = ServicoConfiguracao(session, empresa_id, redis=redis)
            dias = await servico_config.obter_inteiro(
                "dias_antecedencia_lembrete", "financeiro", padrao=3
            )
            canal_principal = await servico_config.obter_string(
                "canal_cobranca_principal", "comunicacao", padrao="whatsapp"
            )
            canal_fallback = await servico_config.obter_string(
                "canal_cobranca_fallback", "comunicacao", padrao=""
            )

            hoje = date.today()
            limite = date.fromordinal(hoje.toordinal() + dias)
            renderizador = RenderizadorTemplate(session, empresa_id)

            stmt = select(TituloReceber).where(
                TituloReceber.empresa_id == empresa_id,
                TituloReceber.tipo == "parcela",
                TituloReceber.status == "em_aberto",
                TituloReceber.data_vencimento > hoje,
                TituloReceber.data_vencimento <= limite,
            )
            titulos = list((await session.execute(stmt)).scalars().all())

            for titulo in titulos:
                try:
                    await _processar_titulo(
                        session,
                        titulo,
                        empresa_id,
                        canal_principal,
                        canal_fallback,
                        renderizador,
                        tracker,
                        redis,
                    )
                except Exception as exc:
                    log.exception("titulo_processamento_falhou", titulo_id=str(titulo.id))
                    tracker.registrar_erro({"titulo_id": str(titulo.id), "erro": str(exc)})

            await session.commit()

        await tracker.__aexit__(None, None, None)
        await tracker_session.commit()
        return {
            "total_processados": tracker.total_registros,
            "total_erros": tracker.total_erros,
        }
    except Exception as exc:
        try:
            await tracker.__aexit__(type(exc), exc, exc.__traceback__)
            await tracker_session.commit()
        except Exception:
            log.exception("tracker_finalize_falhou")
        raise
    finally:
        await tracker_session.close()
        await redis.aclose()


@celery_app.task(name="app.workers.tasks.alertar_vencimentos_proximos.executar")
def executar(empresa_id: str) -> dict[str, int]:
    """Entry point Celery — recebe `empresa_id` do `dispatch_por_empresa`."""
    eid = UUID(empresa_id)
    set_empresa_id(eid)
    try:
        return asyncio.run(_run(eid))
    finally:
        reset_empresa_id()
