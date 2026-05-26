"""Celery task: recalcular score dos clientes da empresa (refatorada em 12-6).

Executa diariamente às 02:00 UTC via Celery Beat, **uma vez por empresa ativa**
(orquestrado por `dispatch_por_empresa`). Para cada `Cliente` ativo da empresa,
chama `compute_and_save_score` para atualizar o score em `cobranca.scores_clientes`.

Isolamento tenant: a task recebe `empresa_id` como primeiro argumento, seta
contexto Python + `app.empresa_id` no Postgres para RLS.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import structlog
from sqlalchemy import select, text

from app.core.tenant_context import reset_empresa_id, set_empresa_id
from app.infrastructure.db import models  # noqa: F401
from app.workers import celery_app

log = structlog.get_logger()


async def _run(empresa_id: UUID) -> dict:
    from app.application.agent.score_calculator import compute_and_save_score
    from app.infrastructure.db.models.cadastro import Cliente
    from app.infrastructure.db.session import get_sessionmaker

    session_factory = get_sessionmaker()
    processados = 0
    erros = 0

    async with session_factory() as session:
        await session.execute(
            text("SELECT set_config('app.empresa_id', :eid, true)"),
            {"eid": str(empresa_id)},
        )

        stmt = select(Cliente.id).where(
            Cliente.empresa_id == empresa_id,
            Cliente.status == "ativo",
            Cliente.excluido_em.is_(None),
        )
        cliente_ids = [row[0] for row in (await session.execute(stmt)).all()]

        # Per-cliente savepoint: erro em UM cliente não deve abortar a transação
        # inteira (que perderia todos os scores recalculados antes). Cada cliente
        # tem seu próprio nested begin (SAVEPOINT) que pode dar rollback isolado.
        for cid in cliente_ids:
            try:
                async with session.begin_nested():
                    await compute_and_save_score(session, cid)
                processados += 1
            except Exception:
                log.warning(
                    "score_recalculo_falhou",
                    cliente_id=str(cid),
                    empresa_id=str(empresa_id),
                    exc_info=True,
                )
                erros += 1

        await session.commit()

    log.info(
        "recalcular_scores_clientes_complete",
        empresa_id=str(empresa_id),
        processados=processados,
        erros=erros,
        total=len(cliente_ids),
    )
    return {
        "processados": processados,
        "erros": erros,
        "total": len(cliente_ids),
    }


@celery_app.task(
    name="app.workers.tasks.recalcular_scores_clientes.executar",
    bind=True,
    max_retries=1,
    queue="default",
)
def executar(self, empresa_id: str) -> dict:
    eid = UUID(empresa_id)
    set_empresa_id(eid)
    try:
        return asyncio.run(_run(eid))
    finally:
        reset_empresa_id()
