"""Task Celery — Story 13.22 A1 (code review).

Varre todos os clientes com `desbloqueio_confianca_ate < hoje` que ainda
têm título em atraso. Re-suspende o contrato vigente desses clientes e
limpa o campo. Logs audit como `desbloqueio_confianca_expirado`.

Cobre o gap: sem isso, o cliente desbloqueado em confiança burlava o
bloqueio indefinidamente porque o serviço só transicionava `suspenso →
vigente` sem agendar a volta.

Roda system-wide (não tenant-scoped) — varre toda a base. Schedule via
beat: 4× ao dia (a cada 6h) para garantir reação rápida quando expira.
"""

from __future__ import annotations

import asyncio
from datetime import date

import structlog

from app.workers import celery_app


log = structlog.get_logger()


@celery_app.task(
    name="app.workers.tasks.expirar_desbloqueios_confianca.executar",
    bind=True,
    max_retries=1,
    queue="default",
)
def executar(self) -> dict:
    return asyncio.run(_executar())


async def _executar() -> dict:
    from sqlalchemy import select
    from app.application.services.servico_situacao_contrato import (
        ServicoSituacaoContrato,
    )
    from app.application.shared.audit_logger import AuditLogger
    from app.domain.contracts.state_machine import SituacaoContrato
    from app.infrastructure.db.models.cadastro import Cliente
    from app.infrastructure.db.models.contrato import Contrato
    from app.infrastructure.db.models.financeiro import TituloReceber
    from app.infrastructure.db.session import get_sessionmaker

    hoje = date.today()
    session_factory = get_sessionmaker()
    expirados_total = 0
    re_suspensos_total = 0

    async with session_factory() as session:
        clientes = (await session.execute(
            select(Cliente).where(
                Cliente.desbloqueio_confianca_ate.is_not(None),
                Cliente.desbloqueio_confianca_ate < hoje,
            )
        )).scalars().all()

        for cliente in clientes:
            expirados_total += 1
            # Só re-suspende se ainda houver título em atraso.
            tem_atraso = (await session.execute(
                select(TituloReceber.id)
                .join(Contrato, Contrato.id == TituloReceber.contrato_id)
                .where(
                    Contrato.cliente_id == cliente.id,
                    Contrato.empresa_id == cliente.empresa_id,
                    TituloReceber.empresa_id == cliente.empresa_id,
                    TituloReceber.status == "em_atraso",
                )
                .limit(1)
            )).scalar_one_or_none()

            data_validade = cliente.desbloqueio_confianca_ate
            cliente.desbloqueio_confianca_ate = None

            audit = AuditLogger(session)
            await audit.record(
                action="cliente.desbloqueio_confianca_expirado",
                user_id=None,
                entity="clientes",
                entity_id=str(cliente.id),
                payload_after={
                    "expirou_em": data_validade.isoformat() if data_validade else None,
                    "re_suspendido": tem_atraso is not None,
                },
                module="cobranca",
                category="security",
            )

            if tem_atraso is None:
                # Cliente quitou — não precisa re-suspender.
                continue

            contrato = (await session.execute(
                select(Contrato).where(
                    Contrato.cliente_id == cliente.id,
                    Contrato.empresa_id == cliente.empresa_id,
                    Contrato.status == "vigente",
                )
                .order_by(Contrato.data_inicio.desc())
                .limit(1)
            )).scalar_one_or_none()
            if contrato is None:
                continue
            try:
                svc = ServicoSituacaoContrato(session, cliente.empresa_id)
                await svc.transicionar(
                    contrato.id,
                    SituacaoContrato.SUSPENSO,
                    motivo="Desbloqueio em confiança expirou e cliente ainda tem título em atraso",
                    ator_id=None,
                )
                re_suspensos_total += 1
            except Exception:
                log.exception(
                    "falha_re_suspender_contrato",
                    contrato_id=str(contrato.id),
                )

        await session.commit()

    log.info(
        "expirar_desbloqueios_confianca.concluido",
        expirados=expirados_total,
        re_suspensos=re_suspensos_total,
    )
    return {"expirados": expirados_total, "re_suspensos": re_suspensos_total}
