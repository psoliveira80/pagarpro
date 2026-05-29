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
    empresa_id,
) -> IWhatsAppGateway | None:
    """**LEGACY/DEPRECATED** — retorna o primeiro adapter WhatsApp ativo
    do tenant.

    Foi a função do modelo "1 provedor WhatsApp por empresa" anterior à
    Story 13.21 (multi-número Evolution Go). Hoje só serve para:

    - Providers legados (zapi/uazapi/evolution_api) que NÃO suportam
      multi-número e ainda existem em empresas migradas de schemas
      antigos.
    - Fallback emergencial quando o roteamento por cliente
      (`ServicoRoteamentoNumeros`) não consegue identificar destinatário.

    **NÃO USE em código novo.** Para envio outbound:
    - Conhece o cliente: `ServicoRoteamentoNumeros.credencial_para_outbound(cliente_id)`
      + `get_adapter_por_credencial_id(session, cred.id)`.
    - Conhece só o telefone: `get_evolution_go_por_credencial_telefone(session, empresa_id, telefone)`.

    Antes desta refatoração (2026-05-29) a função tinha cache GLOBAL
    cross-tenant — vazamento multi-tenant grave. Cache removido.
    """
    from app.infrastructure.db.models.integration_credential import IntegrationCredential

    stmt = select(IntegrationCredential).where(
        IntegrationCredential.empresa_id == empresa_id,
        IntegrationCredential.categoria == "whatsapp",
        IntegrationCredential.ativo.is_(True),
    ).order_by(IntegrationCredential.criado_em.asc()).limit(1)

    result = await session.execute(stmt)
    cred = result.scalar_one_or_none()

    if cred is None:
        log.warning("no_active_whatsapp_provider", empresa_id=str(empresa_id))
        return None

    return _build_adapter(cred.provedor, cred.config or {})


def clear_adapter_cache() -> None:
    """**No-op preservado pra compatibilidade com callers legados.**

    Antes existia cache global `_adapter_cache`; removido em 2026-05-29
    porque era cross-tenant. Adapters agora são construídos sob demanda
    a cada chamada — overhead aceitável dado o ganho de isolamento.
    """
    return None


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


async def get_evolution_go_por_credencial_telefone(
    session: AsyncSession,
    empresa_id,
    telefone: str,
) -> IWhatsAppGateway | None:
    """Encontra o adapter Evolution Go que o cliente identificado por
    `telefone` está usando.

    Lookup: cliente pelo telefone → cliente.numero_origem_id → credencial.
    Se não encontrar (cliente não cadastrado ou sem número atribuído), faz
    fallback: primeiro número ativo da empresa.

    Usado pelas tasks que precisam enviar mensagem **fora** de um webhook
    inbound (Stories 13.23 e 13.25).
    """
    from app.infrastructure.db.models.cadastro import Cliente
    from app.infrastructure.db.models.integration_credential import IntegrationCredential

    digits = "".join(c for c in telefone if c.isdigit())
    candidatos = {
        digits,
        f"+{digits}",
        digits[-11:],
        digits[-10:],
        digits[-9:],
    }
    cliente = (await session.execute(
        select(Cliente).where(
            Cliente.empresa_id == empresa_id,
            Cliente.telefone.in_(candidatos),
        )
        .limit(1)
    )).scalar_one_or_none()
    cred_id = cliente.numero_origem_id if cliente is not None else None

    cred: IntegrationCredential | None = None
    if cred_id is not None:
        # Defesa em profundidade: filtra por empresa_id mesmo no lookup por id
        # — regra inegociável multi-tenant. Se numero_origem_id estiver corrompido
        # apontando pra credencial de outra empresa (bug histórico/migração),
        # devolve None e cai pro fallback do tenant correto.
        cred = (await session.execute(
            select(IntegrationCredential).where(
                IntegrationCredential.id == cred_id,
                IntegrationCredential.empresa_id == empresa_id,
            )
        )).scalar_one_or_none()
    if cred is None:
        # Fallback: primeiro Evolution Go ativo da empresa
        cred = (await session.execute(
            select(IntegrationCredential).where(
                IntegrationCredential.empresa_id == empresa_id,
                IntegrationCredential.provedor == "evolution_go",
                IntegrationCredential.ativo.is_(True),
            )
            .limit(1)
        )).scalar_one_or_none()
    if cred is None:
        return None
    return _build_adapter(cred.provedor, cred.config or {})
