"""Celery task: verificar saúde dos canais de mensageria da empresa.

Executa a cada 5 minutos via Celery Beat, **uma vez por empresa ativa**.
Para cada `CredencialIntegracao` ativa da empresa na categoria `whatsapp`:

1. Valida que a credencial tem os campos mínimos pra conectar
   (config_incompleta indica cadastro inacabado).
2. Se config OK, instancia o adapter via factory tenant-aware
   (`get_adapter_por_credencial_id`) e chama `adapter.health_check()`
   se exposto pelo provider. Atualiza `status` conforme retorno.
3. Atualiza `ultimo_health_check` sempre.

Concorrência: cada credencial é checada com `asyncio.wait_for(timeout=5s)`
e dentro de um `gather` — uma instância lenta não bloqueia as demais.

Notas:
- Story 13.21 introduziu **multi-número Evolution Go** — cada credencial
  é uma INSTÂNCIA distinta. Esta task verifica TODAS, não só "a primeira".
- Para o caso específico de Evolution Go, há também
  `monitorar_saude_numeros` (system-wide) que atualiza saúde + dispara
  re-atribuição em caso de banimento. Esta task aqui é por empresa e
  cobre todos os providers (zapi/uazapi/evolution_api/evolution_go).
- Isolamento tenant garantido por `set_empresa_id` + `app.empresa_id` RLS.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select, text

from app.core.tenant_context import reset_empresa_id, set_empresa_id
from app.infrastructure.db import models  # noqa: F401
from app.infrastructure.db.models.config import CredencialIntegracao
from app.workers import celery_app

log = structlog.get_logger()


HEALTH_CHECK_TIMEOUT_S = 5.0


def _credencial_tem_config_minima(cred: CredencialIntegracao) -> bool:
    """Verifica se a credencial tem os campos mínimos para tentar conectar."""
    config = cred.config or {}
    if cred.categoria != "whatsapp":
        return False
    if cred.provedor == "zapi":
        return bool(config.get("instance_id")) and bool(config.get("token"))
    if cred.provedor in ("uazapi", "evolution_api"):
        return bool(config.get("base_url")) and bool(config.get("api_key"))
    if cred.provedor == "evolution_go":
        return bool(config.get("instance_id")) and bool(config.get("instance_token"))
    return False


async def _checar_uma(session, cred: CredencialIntegracao) -> tuple[str, str | None]:
    """Roda health check real numa credencial. Retorna `(status, detalhe)`."""
    from app.infrastructure.adapters.whatsapp.whatsapp_factory import (
        get_adapter_por_credencial_id,
    )

    if not _credencial_tem_config_minima(cred):
        return "config_incompleta", None

    adapter = await get_adapter_por_credencial_id(session, cred.id)
    if adapter is None:
        return "error", "adapter_nao_instanciavel"

    health_check = getattr(adapter, "health_check", None)
    if health_check is None:
        # Provider sem capability — assume configurada (sem evidência contrária).
        return "configurada", None
    try:
        info: dict[str, Any] = await asyncio.wait_for(
            health_check(), timeout=HEALTH_CHECK_TIMEOUT_S
        )
    except asyncio.TimeoutError:
        return "error", "timeout"
    except Exception as exc:
        return "error", str(exc)[:200]

    if info.get("connected") is True:
        return "healthy", None
    if info.get("banido"):
        return "error", "banido"
    erro = info.get("erro") or "desconectado"
    if str(erro).lower() in ("connecting", "qr"):
        return "degraded", f"instancia em {erro}"
    return "error", str(erro)


async def _run(empresa_id: UUID) -> dict[str, int]:
    from app.infrastructure.db.session import get_sessionmaker

    session_factory = get_sessionmaker()
    contagem: dict[str, int] = {
        "healthy": 0, "degraded": 0, "error": 0,
        "configurada": 0, "config_incompleta": 0, "total": 0,
    }

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
        contagem["total"] = len(credenciais)

        resultados = await asyncio.gather(
            *(_checar_uma(session, cred) for cred in credenciais),
            return_exceptions=False,
        )

        agora = datetime.now(timezone.utc)
        for cred, (status, detalhe) in zip(credenciais, resultados):
            cred.status = status
            cred.ultimo_health_check = agora
            contagem[status] = contagem.get(status, 0) + 1
            if status in ("error", "degraded", "config_incompleta") and detalhe:
                log.info(
                    "credencial_health_alerta",
                    empresa_id=str(empresa_id),
                    credencial_id=str(cred.id),
                    provedor=cred.provedor,
                    status=status,
                    detalhe=detalhe,
                )

        await session.commit()

    log.info("verificar_saude_canais_complete", empresa_id=str(empresa_id), **contagem)
    return contagem


@celery_app.task(name="app.workers.tasks.verificar_saude_canais.executar")
def executar(empresa_id: str) -> dict[str, int]:
    eid = UUID(empresa_id)
    set_empresa_id(eid)
    try:
        return asyncio.run(_run(eid))
    finally:
        reset_empresa_id()
