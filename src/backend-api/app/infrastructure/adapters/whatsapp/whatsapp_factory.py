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

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ports.whatsapp_gateway import IWhatsAppGateway
from app.infrastructure.adapters.whatsapp.evolution_api_adapter import EvolutionApiAdapter
from app.infrastructure.adapters.whatsapp.uazapi_adapter import UazapiAdapter
from app.infrastructure.adapters.whatsapp.zapi_adapter import ZapiAdapter

log = structlog.get_logger()

# Registry: provider name → factory function
_ADAPTER_REGISTRY: dict[str, type] = {
    "zapi": ZapiAdapter,
    "uazapi": UazapiAdapter,
    "evolution_api": EvolutionApiAdapter,
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
