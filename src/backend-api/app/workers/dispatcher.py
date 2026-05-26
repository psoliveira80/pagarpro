"""Orquestrador `dispatch_por_empresa` (Story 12-6).

Workers que operam por tenant (gerar títulos, gerar despesas, recalcular scores,
verificar saúde de canais) NÃO podem rodar globalmente — cada execução precisa
estar no contexto de uma empresa específica para que o RLS (story 12-5) filtre
o que cada query enxerga.

A solução é um orquestrador único:

  1. Celery Beat dispara `dispatch_por_empresa` para um `task_name` específico.
  2. O orquestrador lê `comercial.empresas` (apenas empresas ativas e não-deletadas).
  3. Para cada empresa, manda um `send_task(task_name, args=[str(empresa.id)])`.

**Resiliência:** falha em `send_task` de uma empresa NÃO mata o orquestrador —
seguimos pras próximas. Sem isso, broker hiccup numa empresa abortaria todas
as outras na mesma rodada do beat.

**Sem retry no orquestrador:** broker fora do ar é melhor resolvido pela
próxima execução do beat (5min/1h depois) do que por replay do dispatcher,
que reduplicaria todas as N empresas em uma janela curta.

Mantém o pattern "uma infra global filtrando por estado" documentado em
[[single-infra-architecture]]. O orquestrador usa sessão async (asyncpg)
para alinhar com o restante da suíte de workers — psycopg2/sync não está
instalado no container.
"""

from __future__ import annotations

import asyncio

import structlog
from sqlalchemy import select, text

from app.infrastructure.db import models  # noqa: F401 — registra modelos
from app.infrastructure.db.models.comercial import Empresa
from app.infrastructure.db.session import get_sessionmaker
from app.workers import celery_app

log = structlog.get_logger()


async def _listar_empresas_ativas() -> list[str]:
    """Retorna ids (como string) de empresas ativas E não soft-deletadas."""
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        # Orquestrador roda fora de contexto tenant — desabilita RLS pra ler
        # `comercial.empresas` completa. `is_local=true` garante que expira
        # ao fim da transação. Autobegin abre a transação no primeiro execute().
        await session.execute(text("SET LOCAL row_security = off"))
        rows = (
            await session.execute(
                select(Empresa.id).where(
                    Empresa.ativo.is_(True),
                    Empresa.excluido_em.is_(None),
                )
            )
        ).scalars().all()
        return [str(eid) for eid in rows]


@celery_app.task(
    name="app.workers.dispatcher.dispatch_por_empresa",
    bind=True,
    max_retries=0,
    queue="default",
)
def dispatch_por_empresa(self, task_name: str) -> dict[str, int]:
    """Dispara `task_name` uma vez para cada empresa ativa.

    Args:
        task_name: nome registrado da task filho (ex.:
            `"app.workers.tasks.gerar_titulos_mensais.executar"`).

    Returns:
        Dicionário com `dispatched`, `failed` para observabilidade.
    """
    empresa_ids = asyncio.run(_listar_empresas_ativas())

    dispatched = 0
    failed = 0
    for empresa_id in empresa_ids:
        try:
            celery_app.send_task(task_name, args=[empresa_id])
            dispatched += 1
        except Exception as exc:
            failed += 1
            log.error(
                "dispatch_send_task_failed",
                task_name=task_name,
                empresa_id=empresa_id,
                error=str(exc),
            )

    log.info(
        "dispatch_por_empresa_complete",
        task_name=task_name,
        dispatched=dispatched,
        failed=failed,
    )
    return {"dispatched": dispatched, "failed": failed, "skipped": 0}
