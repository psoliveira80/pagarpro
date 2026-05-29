"""Factory for WhatsApp gateway adapters.

Reads the active WhatsApp integration from `integration_credentials` table
and instantiates the correct adapter based on the `provider` field.

Each provider has its own adapter class implementing `IWhatsAppGateway`.
To add a new WhatsApp provider:
1. Create the adapter class implementing IWhatsAppGateway
2. Add it to _ADAPTER_REGISTRY below
3. Add the provider's fields in the frontend integrations page
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ports.whatsapp_gateway import IWhatsAppGateway

if TYPE_CHECKING:
    from app.infrastructure.db.models.integration_credential import IntegrationCredential
from app.infrastructure.adapters.whatsapp.evolution_api_adapter import EvolutionApiAdapter
from app.infrastructure.adapters.whatsapp.evolution_go_adapter import EvolutionGoAdapter
from app.infrastructure.adapters.whatsapp.uazapi_adapter import UazapiAdapter
from app.infrastructure.adapters.whatsapp.zapi_adapter import ZapiAdapter

log = structlog.get_logger()

# Registry: provider name → factory function
_ADAPTER_REGISTRY: dict[str, type] = {
    "zapi": ZapiAdapter,
    "uazapi": UazapiAdapter,
    "evolution_api": EvolutionApiAdapter,
    "evolution_go": EvolutionGoAdapter,
}

_adapter_cache: dict[str, IWhatsAppGateway] = {}


def _build_adapter(provider: str, config: dict) -> IWhatsAppGateway | None:
    """Instantiate adapter from provider name + config dict."""
    if provider == "zapi":
        return ZapiAdapter(
            instance_id=config.get("instance_id", ""),
            token=config.get("token", ""),
            client_token=config.get("client_token"),
            base_url=config.get("base_url", "https://api.z-api.io"),
        )
    elif provider == "uazapi":
        return UazapiAdapter(
            base_url=config.get("base_url", ""),
            api_key=config.get("api_key", ""),
        )
    elif provider == "evolution_api":
        return EvolutionApiAdapter(
            base_url=config.get("base_url", ""),
            api_key=config.get("api_key", ""),
            instance_name=config.get("instance", "default"),
        )
    elif provider == "evolution_go":
        # Story 13.21 — api_url e admin_token são globais do SaaS
        # (variáveis de ambiente). Credencial da empresa só guarda
        # instance_id, instance_token e numero_e164.
        from app.infrastructure.settings import get_settings
        settings = get_settings()
        return EvolutionGoAdapter(
            api_url=settings.EVOLUTION_GO_API_URL,
            instance_token=config.get("instance_token", ""),
            instance_id=config.get("instance_id"),
        )
    else:
        log.error("unknown_whatsapp_provider", provider=provider)
        return None


async def get_whatsapp_gateway(
    session: AsyncSession,
) -> IWhatsAppGateway | None:
    """Get the active WhatsApp gateway adapter from integration_credentials."""
    from app.infrastructure.db.models.integration_credential import IntegrationCredential

    # Check cache first
    if _adapter_cache:
        return next(iter(_adapter_cache.values()))

    stmt = select(IntegrationCredential).where(
        IntegrationCredential.categoria == "whatsapp",
        IntegrationCredential.ativo.is_(True),
    ).limit(1)

    result = await session.execute(stmt)
    cred = result.scalar_one_or_none()

    if cred is None:
        log.warning("no_active_whatsapp_provider")
        return None

    adapter = _build_adapter(cred.provedor, cred.config or {})
    if adapter:
        _adapter_cache[cred.provedor] = adapter

    return adapter


def clear_adapter_cache() -> None:
    """Clear cached adapters (e.g., after credential update)."""
    _adapter_cache.clear()


# ─────────────────── Story 13.21 — Evolution Go multi-número ─────────────────

async def get_adapter_por_credencial_id(
    session: AsyncSession,
    credencial_id,
) -> IWhatsAppGateway | None:
    """Carrega adapter de uma credencial específica.

    Diferente de `get_whatsapp_gateway` (que pega o primeiro ativo do tenant),
    esta função aceita o `credencial_id` específico e retorna o adapter
    correspondente. Usado pelo `ServicoRoteamentoNumeros` quando o cliente
    tem um número específico atribuído (`cliente.numero_origem_id`).
    """
    from app.infrastructure.db.models.integration_credential import IntegrationCredential

    stmt = select(IntegrationCredential).where(IntegrationCredential.id == credencial_id)
    cred = (await session.execute(stmt)).scalar_one_or_none()
    if cred is None:
        log.warning("credencial_nao_encontrada", credencial_id=str(credencial_id))
        return None
    return _build_adapter(cred.provedor, cred.config or {})


async def get_evolution_go_por_instance_id(
    session: AsyncSession,
    instance_id: str,
) -> tuple[IWhatsAppGateway, IntegrationCredential] | tuple[None, None]:
    """Identifica a credencial Evolution Go pelo `instance_id` do webhook.

    O webhook do Evolution Go traz `instanceId` no payload root. Esta função
    busca a `IntegrationCredential` com esse instance_id no JSONB `config`
    e retorna o adapter + a credencial. Usado pelo `process_inbound_whatsapp`.
    """
    from app.infrastructure.db.models.integration_credential import IntegrationCredential

    # Busca por (provedor='evolution_go', config->>'instance_id' = instance_id)
    stmt = select(IntegrationCredential).where(
        IntegrationCredential.provedor == "evolution_go",
        IntegrationCredential.config["instance_id"].astext == instance_id,
    ).limit(1)
    cred = (await session.execute(stmt)).scalar_one_or_none()
    if cred is None:
        log.warning("evolution_go_credencial_nao_encontrada", instance_id=instance_id)
        return None, None

    adapter = _build_adapter(cred.provedor, cred.config or {})
    if adapter is None:
        return None, None
    return adapter, cred
