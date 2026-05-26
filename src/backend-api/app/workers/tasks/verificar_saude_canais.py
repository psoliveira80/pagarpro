"""Celery task: verificar saúde dos canais de mensageria da empresa (story 12-6, scaffolding).

Executa a cada 5 minutos via Celery Beat, **uma vez por empresa ativa**
(orquestrado por `dispatch_por_empresa`). Para cada `CredencialIntegracao`
ativa da empresa na categoria `whatsapp`, faz uma verificação leve de
configuração (presença de credenciais não-vazias) e atualiza
`status` + `ultimo_health_check`.

**Limitação consciente (Epic 11):** esta versão NÃO chama
`adapter.health_check()` porque:

1. `get_whatsapp_gateway(session)` na arquitetura atual retorna o primeiro
   gateway ativo cacheado processo-wide (`_adapter_cache` em
   `whatsapp_factory.py`) — não é tenant-aware, então chamá-lo dentro de
   uma task per-tenant traria adapter de OUTRA empresa.
2. Health check real precisa de timeout + concorrência (gather + wait_for)
   para não bloquear a fila a cada credencial lenta.

Esta task é o scaffolding — mantém `ultimo_health_check` atualizado para
o painel de Integrações ver "última verificação há X minutos" e marca
credenciais com config faltando. O Epic 11 (Channel Health Monitoring)
substitui o stub por uma chamada real com adapter tenant-scoped.

Isolamento tenant: a task recebe `empresa_id` como primeiro argumento,
seta contexto Python + `app.empresa_id` no Postgres para RLS.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import select, text

from app.core.tenant_context import reset_empresa_id, set_empresa_id
from app.infrastructure.db import models  # noqa: F401
from app.infrastructure.db.models.config import CredencialIntegracao
from app.workers import celery_app

log = structlog.get_logger()


def _credencial_tem_config_minima(cred: CredencialIntegracao) -> bool:
    """Verifica se a credencial tem os campos mínimos para tentar conectar.

    Hoje cobre WhatsApp (zapi/uazapi/evolution_api). Quando adicionar outros
    canais (email, sms), estender com `cred.categoria` no switch.
    """
    config = cred.config or {}
    if cred.categoria != "whatsapp":
        return False
    if cred.provedor == "zapi":
        return bool(config.get("instance_id")) and bool(config.get("token"))
    if cred.provedor in ("uazapi", "evolution_api"):
        return bool(config.get("base_url")) and bool(config.get("api_key"))
    return False


async def _run(empresa_id: UUID) -> dict[str, int]:
    from app.infrastructure.db.session import get_sessionmaker

    session_factory = get_sessionmaker()
    saudaveis = 0
    sem_config = 0

    async with session_factory() as session:
        await session.execute(
            text("SELECT set_config('app.empresa_id', :eid, true)"),
            {"eid": str(empresa_id)},
        )

        stmt = select(CredencialIntegracao).where(
            CredencialIntegracao.empresa_id == empresa_id,
            CredencialIntegracao.ativo.is_(True),
            CredencialIntegracao.categoria == "whatsapp",
        )
        credenciais = list((await session.execute(stmt)).scalars().all())

        agora = datetime.now(timezone.utc)
        for cred in credenciais:
            if _credencial_tem_config_minima(cred):
                cred.status = "configurada"
                saudaveis += 1
            else:
                cred.status = "config_incompleta"
                sem_config += 1
                log.warning(
                    "credencial_config_incompleta",
                    empresa_id=str(empresa_id),
                    provedor=cred.provedor,
                )
            cred.ultimo_health_check = agora

        await session.commit()

    sumario = {
        "configurada": saudaveis,
        "config_incompleta": sem_config,
        "total": len(credenciais),
    }
    log.info(
        "verificar_saude_canais_complete",
        empresa_id=str(empresa_id),
        **sumario,
    )
    return sumario


@celery_app.task(name="app.workers.tasks.verificar_saude_canais.executar")
def executar(empresa_id: str) -> dict[str, int]:
    eid = UUID(empresa_id)
    set_empresa_id(eid)
    try:
        return asyncio.run(_run(eid))
    finally:
        reset_empresa_id()
