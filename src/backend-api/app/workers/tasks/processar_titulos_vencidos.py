"""Motor `processar_titulos_vencidos` (Epic 13, Story 13.8).

Processa títulos vencidos por contrato. Para cada contrato com pelo menos
um título em atraso (após carência):

1. Calcula encargos (multa + juros) em todos os títulos vencidos do contrato.
2. Atualiza `status` dos títulos: `em_aberto` → `em_atraso`.
3. Decide a ação no nível do contrato com base em `max(dias_atraso)`:
   - `dias_atraso > limite_dias_encerramento`: encerra contrato com pendência
     (passivo inoperante fica como débito futuro — Story 13.11).
   - `dias_atraso > limite_dias_suspensao`: suspende contrato.
   - Senão: envia mensagem de cobrança (respeitando régua de tentativas).
4. Tracker em `motor.execucoes_motor`.

Idempotência:
- Encargos sobrescrevem (recalculados a cada execução baseado em `hoje`).
- Envio de mensagem: 1 por contrato por dia via `lembretes_enviados`.
- Transição de contrato é idempotente pelo `ServicoSituacaoContrato`
  (grafo rejeita transição inválida — ex.: tentar suspender contrato já
  suspenso lança `TransicaoInvalidaError`, que tratamos como no-op).
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.servico_configuracao import ServicoConfiguracao
from app.application.services.servico_situacao_contrato import (
    ServicoSituacaoContrato,
)
from app.core.channels.registry import channel_registry
from app.core.tenant_context import reset_empresa_id, set_empresa_id
from app.domain.contracts.state_machine import (
    SituacaoContrato,
    TransicaoInvalidaError,
)
from app.domain.finance.calculos_encargos import calcular_encargos
from app.infrastructure.db import models  # noqa: F401
from app.infrastructure.db.models.cadastro import Cliente
from app.infrastructure.db.models.contrato import Contrato, EventoContrato
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

NOME_TAREFA = "processar_titulos_vencidos"
TIPO_LEMBRETE = "cobranca_vencida"


async def _carregar_configs(servico: ServicoConfiguracao) -> dict:
    return {
        "dias_carencia": await servico.obter_inteiro("dias_carencia", "financeiro", padrao=0),
        "percentual_multa": await servico.obter_decimal(
            "percentual_multa", "financeiro", padrao=Decimal("2.00")
        ),
        "percentual_juros_dia": await servico.obter_decimal(
            "percentual_juros_dia", "financeiro", padrao=Decimal("0.0333")
        ),
        "limite_tentativas": await servico.obter_inteiro(
            "limite_tentativas_cobranca", "financeiro", padrao=3
        ),
        "intervalo_horas": await servico.obter_inteiro(
            "intervalo_tentativas_horas", "financeiro", padrao=24
        ),
        "limite_dias_suspensao": await servico.obter_inteiro(
            "limite_dias_suspensao", "financeiro", padrao=15
        ),
        "limite_dias_encerramento": await servico.obter_inteiro(
            "limite_dias_encerramento", "financeiro", padrao=60
        ),
        "canal_principal": await servico.obter_string(
            "canal_cobranca_principal", "comunicacao", padrao="whatsapp"
        ),
    }


async def _carregar_contexto_render(
    session: AsyncSession,
    contrato: Contrato,
    titulo: TituloReceber,
    valor_atualizado: Decimal,
    dias_atraso: int,
) -> dict | None:
    cliente = (await session.execute(
        select(Cliente).where(Cliente.id == contrato.cliente_id)
    )).scalar_one_or_none()
    if cliente is None:
        return None
    veiculo = (await session.execute(
        select(Veiculo).where(Veiculo.id == contrato.veiculo_id)
    )).scalar_one_or_none()

    nome_completo = cliente.nome_completo or ""
    primeiro = nome_completo.split(" ")[0] if nome_completo else ""

    return {
        "cliente": {
            "nome": nome_completo,
            "primeiro_nome": primeiro,
            "telefone": cliente.telefone or "",
        },
        "titulo": {
            "valor": f"R$ {titulo.valor:.2f}".replace(".", ","),
            "valor_atualizado": f"R$ {valor_atualizado:.2f}".replace(".", ","),
            "data_vencimento": titulo.data_vencimento.strftime("%d/%m/%Y"),
            "dias_atraso": dias_atraso,
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
        "empresa": {"nome": "", "telefone": ""},
    }


async def _ja_enviou_hoje(
    session: AsyncSession, titulo_id: UUID, tipo: str
) -> bool:
    hoje = datetime.now(timezone.utc).date()
    result = await session.execute(text("""
        SELECT 1 FROM financeiro.lembretes_enviados
        WHERE titulo_id = :tid AND tipo = :tipo
          AND (enviado_em AT TIME ZONE 'UTC')::date = :hoje
        LIMIT 1
    """), {"tid": str(titulo_id), "tipo": tipo, "hoje": hoje})
    return result.first() is not None


async def _enviar_cobranca(canal_tipo: str, telefone: str, mensagem: str) -> tuple[bool, str | None]:
    canais = channel_registry.get_channels_by_type(canal_tipo)
    if not canais:
        return False, f"Nenhum canal '{canal_tipo}' registrado"
    canal = canais[0]
    try:
        await canal.send_text(telefone, mensagem)
        return True, None
    except Exception as exc:
        return False, str(exc)


async def _processar_contrato(
    session: AsyncSession,
    contrato: Contrato,
    titulos_vencidos: list[TituloReceber],
    configs: dict,
    renderizador: RenderizadorTemplate,
    empresa_id: UUID,
    hoje: date,
    redis,
    tracker: ExecucaoMotorTracker,
) -> None:
    """Processa todos os títulos vencidos de UM contrato + decide ação.

    Aplica encargos em cada título, escolhe o "título de referência" (o mais
    antigo) pra mensagem e contagem de tentativas, e transita o contrato se
    o atraso atingiu limites de suspensão/encerramento.
    """
    async with LockOperacao(redis, "processar_vencidos", str(contrato.id)) as lock:
        if not lock.adquirido:
            log.info("contrato_em_processamento_por_outro_worker", contrato_id=str(contrato.id))
            return

        # Encargos em todos os títulos
        titulo_mais_antigo = min(titulos_vencidos, key=lambda t: t.data_vencimento)
        encargos_referencia = calcular_encargos(
            titulo_mais_antigo.valor,
            titulo_mais_antigo.data_vencimento,
            hoje,
            configs["dias_carencia"],
            configs["percentual_multa"],
            configs["percentual_juros_dia"],
        )
        max_dias_atraso = encargos_referencia.dias_atraso

        # Atualiza status dos títulos pra 'em_atraso' (mantém em_atraso se já)
        for t in titulos_vencidos:
            if t.status == "em_aberto":
                t.status = "em_atraso"

        # Evento de auditoria com snapshot dos encargos do título referência
        session.add(EventoContrato(
            empresa_id=empresa_id,
            contrato_id=contrato.id,
            tipo="titulos_vencidos_processados",
            payload={
                "data_processamento": hoje.isoformat(),
                "qtd_titulos_vencidos": len(titulos_vencidos),
                "titulo_referencia": {
                    "id": str(titulo_mais_antigo.id),
                    "valor_base": str(encargos_referencia.valor_base),
                    "multa": str(encargos_referencia.multa),
                    "juros": str(encargos_referencia.juros),
                    "valor_atualizado": str(encargos_referencia.valor_atualizado),
                    "dias_atraso": encargos_referencia.dias_atraso,
                },
            },
        ))

        servico_situacao = ServicoSituacaoContrato(session, empresa_id)

        # Decide ação a nível de contrato
        if max_dias_atraso > configs["limite_dias_encerramento"]:
            try:
                await servico_situacao.transicionar(
                    contrato.id,
                    SituacaoContrato.ENCERRADO_COM_PENDENCIA,
                    motivo=f"Inadimplência crônica ({max_dias_atraso} dias)",
                )
                tracker.registrar_sucesso()
                log.warning(
                    "contrato_encerrado_por_inadimplencia",
                    contrato_id=str(contrato.id),
                    dias_atraso=max_dias_atraso,
                )
            except TransicaoInvalidaError:
                # Já está em estado terminal ou suspenso de forma incompatível — no-op
                tracker.registrar_sucesso()
            return

        if max_dias_atraso > configs["limite_dias_suspensao"]:
            try:
                await servico_situacao.transicionar(
                    contrato.id,
                    SituacaoContrato.SUSPENSO,
                    motivo=f"Inadimplência {max_dias_atraso} dias — suspensão automática",
                )
                tracker.registrar_sucesso()
                log.warning(
                    "contrato_suspenso_por_inadimplencia",
                    contrato_id=str(contrato.id),
                    dias_atraso=max_dias_atraso,
                )
            except TransicaoInvalidaError:
                # Já está suspenso ou em estado incompatível — no-op
                pass
            # NÃO envia mensagem de cobrança quando suspende (já é uma ação forte)
            tracker.registrar_sucesso()
            return

        # Mensagem de cobrança (régua respeitada)
        if titulo_mais_antigo.acoes_de_cobranca >= configs["limite_tentativas"]:
            log.info(
                "limite_tentativas_atingido",
                contrato_id=str(contrato.id),
                titulo_id=str(titulo_mais_antigo.id),
            )
            tracker.registrar_sucesso()
            return

        agora = datetime.now(timezone.utc)
        if (
            titulo_mais_antigo.proxima_acao_em is not None
            and titulo_mais_antigo.proxima_acao_em > agora
        ):
            log.info(
                "intervalo_tentativas_nao_decorreu",
                contrato_id=str(contrato.id),
                proxima_em=titulo_mais_antigo.proxima_acao_em.isoformat(),
            )
            tracker.registrar_sucesso()
            return

        if await _ja_enviou_hoje(session, titulo_mais_antigo.id, TIPO_LEMBRETE):
            tracker.registrar_sucesso()
            return

        contexto = await _carregar_contexto_render(
            session, contrato, titulo_mais_antigo, encargos_referencia.valor_atualizado, max_dias_atraso
        )
        if contexto is None or not contexto["cliente"]["telefone"]:
            tracker.registrar_erro({
                "contrato_id": str(contrato.id),
                "erro": "contexto sem cliente/telefone",
            })
            return

        try:
            mensagem = await renderizador.renderizar(
                "cobranca_vencida", contexto, canal="whatsapp"
            )
        except (TemplateNaoEncontradoError, TemplateRenderError) as exc:
            tracker.registrar_erro({
                "contrato_id": str(contrato.id),
                "erro_template": str(exc),
            })
            return

        sucesso, erro = await _enviar_cobranca(
            configs["canal_principal"], contexto["cliente"]["telefone"], mensagem
        )

        session.add(LembreteEnviado(
            empresa_id=empresa_id,
            titulo_id=titulo_mais_antigo.id,
            tipo=TIPO_LEMBRETE,
            canal=configs["canal_principal"],
            sucesso=sucesso,
            erro=erro,
        ))

        if sucesso:
            titulo_mais_antigo.acoes_de_cobranca += 1
            from datetime import timedelta
            titulo_mais_antigo.proxima_acao_em = agora + timedelta(
                hours=configs["intervalo_horas"]
            )
            tracker.registrar_sucesso()
        else:
            tracker.registrar_erro({"contrato_id": str(contrato.id), "erro_envio": erro})


async def _run(empresa_id: UUID) -> dict[str, int]:
    from app.infrastructure.db.session import get_sessionmaker
    from app.infrastructure.settings import get_settings
    from redis.asyncio import Redis

    settings = get_settings()
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    session_factory = get_sessionmaker()
    hoje = date.today()

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
            configs = await _carregar_configs(servico_config)
            renderizador = RenderizadorTemplate(session, empresa_id)

            # Títulos parcela vencidos após carência
            from datetime import timedelta
            corte = hoje - timedelta(days=configs["dias_carencia"])
            stmt = select(TituloReceber).where(
                TituloReceber.empresa_id == empresa_id,
                TituloReceber.tipo == "parcela",
                TituloReceber.status.in_(("em_aberto", "em_atraso")),
                TituloReceber.data_vencimento < corte,
            ).order_by(TituloReceber.data_vencimento)
            vencidos = list((await session.execute(stmt)).scalars().all())

            # Agrupa por contrato
            por_contrato: dict[UUID, list[TituloReceber]] = defaultdict(list)
            for t in vencidos:
                por_contrato[t.contrato_id].append(t)

            for contrato_id, titulos in por_contrato.items():
                contrato = (await session.execute(
                    select(Contrato).where(Contrato.id == contrato_id)
                )).scalar_one_or_none()
                if contrato is None:
                    continue
                # Só processa contratos vigentes — outros estados são ignorados
                if contrato.status != SituacaoContrato.VIGENTE.value:
                    continue
                try:
                    await _processar_contrato(
                        session, contrato, titulos, configs,
                        renderizador, empresa_id, hoje, redis, tracker,
                    )
                except Exception as exc:
                    log.exception("contrato_processamento_falhou", contrato_id=str(contrato_id))
                    tracker.registrar_erro({"contrato_id": str(contrato_id), "erro": str(exc)})

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


@celery_app.task(name="app.workers.tasks.processar_titulos_vencidos.executar")
def executar(empresa_id: str) -> dict[str, int]:
    eid = UUID(empresa_id)
    set_empresa_id(eid)
    try:
        return asyncio.run(_run(eid))
    finally:
        reset_empresa_id()
