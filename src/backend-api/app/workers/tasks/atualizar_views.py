"""Celery task: atualizar materialized views de dashboard (system-wide).

Executa a cada hora via Celery Beat — **sistema-wide, sem empresa_id**.
As MVs incluem `empresa_id` como coluna; o filtro tenant acontece nas
queries do dashboard, não no refresh.

Detalhes críticos:

- `REFRESH MATERIALIZED VIEW CONCURRENTLY` **não pode** rodar dentro de uma
  transação explícita (limitação do Postgres). Usamos uma conexão async
  com `isolation_level='AUTOCOMMIT'` — cada `execute` virá já-commitado.

- RLS (story 12-5): a role `app` enxerga o universo via policies tenant.
  Como o refresh é cross-tenant, setamos `row_security = off` antes de
  cada refresh — em AUTOCOMMIT, isso vira um SET session-wide que dura
  enquanto a conexão estiver aberta (basta resetar ao final ou descartar
  a conexão; usamos a segunda).

- A versão pré-12-6 usava `get_sync_sessionmaker()` (psycopg2) — driver
  não instalado no container. Convertido pra `asyncpg` em conexão direta.
"""

from __future__ import annotations

import asyncio
import time

import structlog
from sqlalchemy import text

from app.infrastructure.db.session import get_engine
from app.workers import celery_app

log = structlog.get_logger()

VIEWS = (
    "mv_receivables_summary",
    "mv_customer_metrics",
    "mv_vehicle_metrics",
)


async def _run() -> dict[str, str]:
    """Atualiza todas as materialized views de dashboard concorrentemente."""
    resultados: dict[str, str] = {}
    engine = get_engine()

    # Conexão dedicada em AUTOCOMMIT — REFRESH MV CONCURRENTLY exige autocommit.
    async with engine.connect() as conn:
        ac_conn = await conn.execution_options(isolation_level="AUTOCOMMIT")

        # row_security off vale enquanto essa conexão estiver aberta.
        # Sem o `LOCAL` porque não há transação para escopar.
        await ac_conn.execute(text("SET row_security = off"))

        for view in VIEWS:
            inicio = time.monotonic()
            try:
                await ac_conn.execute(
                    text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}")
                )
                decorrido = round(time.monotonic() - inicio, 3)
                resultados[view] = f"ok ({decorrido}s)"
                log.info("mv_refresh_ok", view=view, elapsed_s=decorrido)
            except Exception as exc:
                decorrido = round(time.monotonic() - inicio, 3)
                resultados[view] = f"error: {exc}"
                log.error(
                    "mv_refresh_failed",
                    view=view,
                    elapsed_s=decorrido,
                    error=str(exc),
                )

    return resultados


@celery_app.task(name="app.workers.tasks.atualizar_views.executar")
def executar() -> dict[str, str]:
    return asyncio.run(_run())
