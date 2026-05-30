"""ServicoWhatsappProvedor — gerencia a config de provedor WhatsApp por empresa.

Separa o que é provider-level (qual API + chaves globais) do que é
instance-level (cada número/instância individual). Cada empresa tem 1
provedor configurado; instâncias vivem em `credenciais_integracao`
(categoria=whatsapp) e herdam dessa config no merge do `_build_adapter`.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.shared.audit_logger import AuditLogger
from app.infrastructure.db.models.config import (
    CredencialIntegracao,
    WhatsappProvedorConfig,
)


log = structlog.get_logger()


# Catálogo de provedores. Para cada um, separa explicitamente o que vai em
# Integrações (campos_provedor: URL + chaves globais) do que vai em Canais
# (campos_instancia: dados específicos da instância). Multi_numero indica
# se o provedor aceita mais de uma linha em `credenciais_integracao`.
_CAMPO = dict[str, Any]


_CATALOGO: list[dict[str, Any]] = [
    {
        "id": "evolution_go",
        "label": "Evolution Go (SaaS provedor)",
        "help": (
            "Instância hospedada no Evolution Go central — Topologia A. "
            "URL e admin token vêm do ambiente do SaaS. Aqui não há campos "
            "de provedor; cadastre as instâncias em Canais ›  WhatsApp."
        ),
        "campos_provedor": [],
        "campos_instancia": [
            {"key": "instance_id", "label": "Instance ID", "type": "text", "required": True},
            {"key": "instance_token", "label": "Instance Token", "type": "password", "required": True},
        ],
        "disponivel": True,
        "multi_numero": True,
    },
    {
        "id": "evolution_api",
        "label": "Evolution API (self-hosted)",
        "help": (
            "Sua própria instância Evolution API rodando em servidor próprio. "
            "Informe a URL e a API key master aqui — cada instância depois "
            "usa apenas o nome (`instance`)."
        ),
        "campos_provedor": [
            {"key": "base_url", "label": "URL do Servidor", "type": "url", "required": True},
            {"key": "api_key", "label": "API Key (master)", "type": "password", "required": True},
        ],
        "campos_instancia": [
            {"key": "instance", "label": "Nome da Instância", "type": "text", "required": True},
        ],
        "disponivel": True,
        "multi_numero": False,
    },
    {
        "id": "zapi",
        "label": "Z-API",
        "help": "Acesse z-api.io. Cada instância tem seu Instance ID + Token; não há config global.",
        "campos_provedor": [],
        "campos_instancia": [
            {"key": "instance_id", "label": "Instance ID", "type": "text", "required": True},
            {"key": "token", "label": "Token", "type": "password", "required": True},
            {"key": "client_token", "label": "Client Token (webhook)", "type": "password", "required": False},
        ],
        "disponivel": True,
        "multi_numero": False,
    },
    {
        "id": "uazapi",
        "label": "Uazapi",
        "help": "Acesse uazapi.com. URL e chave master vão aqui; cada instância tem seu nome.",
        "campos_provedor": [
            {"key": "base_url", "label": "URL da API", "type": "url", "required": True},
            {"key": "api_key", "label": "API Key (master)", "type": "password", "required": True},
        ],
        "campos_instancia": [
            {"key": "instance", "label": "Instância", "type": "text", "required": True},
        ],
        "disponivel": True,
        "multi_numero": False,
    },
    {
        "id": "meta_cloud",
        "label": "Meta Cloud API (oficial)",
        "help": "Em breve — adapter para WhatsApp Business Platform oficial.",
        "campos_provedor": [
            {"key": "waba_id", "label": "WABA ID", "type": "text", "required": True},
            {"key": "access_token", "label": "Access Token", "type": "password", "required": True},
        ],
        "campos_instancia": [
            {"key": "phone_number_id", "label": "Phone Number ID", "type": "text", "required": True},
        ],
        "disponivel": False,
        "multi_numero": True,
    },
]


_POR_ID = {p["id"]: p for p in _CATALOGO}


def catalogo() -> list[dict[str, Any]]:
    """Catálogo completo pra alimentar a UI."""
    return _CATALOGO


def descritor(provedor_id: str) -> dict[str, Any] | None:
    return _POR_ID.get(provedor_id)


class ProvedorDesconhecidoError(Exception):
    """Provider id não está no catálogo."""


class ProvedorIndisponivelError(Exception):
    """Provider está no catálogo mas `disponivel=False` (em breve)."""


class CamposObrigatoriosFaltandoError(Exception):
    """Body não trouxe todos os required do nível pedido."""

    def __init__(self, faltando: list[str]):
        self.faltando = faltando
        super().__init__(f"Campos obrigatórios faltando: {', '.join(faltando)}")


class ProvedorTemInstanciasError(Exception):
    """Trocar de provider quebraria instâncias existentes — exige `forcar=True`."""

    def __init__(self, credencial_ids: list[UUID]):
        self.credencial_ids = credencial_ids
        super().__init__(
            f"Provider atual tem {len(credencial_ids)} instância(s) cadastrada(s). "
            "Trocar de provider desativa todas elas."
        )


def _validar_campos(provedor_id: str, config: dict, nivel: str) -> None:
    """nivel = 'provedor' ou 'instancia'."""
    desc = _POR_ID.get(provedor_id)
    if desc is None:
        raise ProvedorDesconhecidoError(provedor_id)
    chave = "campos_provedor" if nivel == "provedor" else "campos_instancia"
    requeridos = [c["key"] for c in desc[chave] if c.get("required")]
    faltando = [k for k in requeridos if not str(config.get(k, "")).strip()]
    if faltando:
        raise CamposObrigatoriosFaltandoError(faltando)


def validar_config_instancia(provedor_id: str, config: dict) -> None:
    """Wrapper público para o handler de POST /numeros-cobranca."""
    _validar_campos(provedor_id, config, "instancia")


class ServicoWhatsappProvedor:
    def __init__(self, session: AsyncSession, empresa_id: UUID) -> None:
        self.session = session
        self.empresa_id = empresa_id

    async def obter_config_ativa(self) -> WhatsappProvedorConfig | None:
        stmt = select(WhatsappProvedorConfig).where(
            WhatsappProvedorConfig.empresa_id == self.empresa_id,
            WhatsappProvedorConfig.ativo.is_(True),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def contar_instancias_ativas(self) -> int:
        from sqlalchemy import func
        stmt = select(func.count(CredencialIntegracao.id)).where(
            CredencialIntegracao.empresa_id == self.empresa_id,
            CredencialIntegracao.categoria == "whatsapp",
            CredencialIntegracao.ativo.is_(True),
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def listar_instancias_ativas_ids(self) -> list[UUID]:
        stmt = select(CredencialIntegracao.id).where(
            CredencialIntegracao.empresa_id == self.empresa_id,
            CredencialIntegracao.categoria == "whatsapp",
            CredencialIntegracao.ativo.is_(True),
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def definir_provedor(
        self,
        provedor: str,
        config: dict,
        ator_id: UUID | None = None,
        forcar: bool = False,
    ) -> WhatsappProvedorConfig:
        desc = _POR_ID.get(provedor)
        if desc is None:
            raise ProvedorDesconhecidoError(provedor)
        if not desc.get("disponivel", True):
            raise ProvedorIndisponivelError(provedor)
        _validar_campos(provedor, config, "provedor")

        atual = await self.obter_config_ativa()
        trocando = atual is not None and atual.provedor != provedor

        if trocando and not forcar:
            ids = await self.listar_instancias_ativas_ids()
            if ids:
                raise ProvedorTemInstanciasError(ids)

        # Limpa só campos do nível provedor — não toca em chaves que não
        # pertencem ao catálogo (deixa o caller decidir).
        campos_validos = {c["key"] for c in desc["campos_provedor"]}
        config_persistir = {k: v for k, v in config.items() if k in campos_validos}

        if atual is None:
            atual = WhatsappProvedorConfig(
                empresa_id=self.empresa_id,
                provedor=provedor,
                config=config_persistir,
                ativo=True,
                atualizado_por_id=ator_id,
            )
            self.session.add(atual)
            await self.session.flush()
            action = "provider.whatsapp.criado"
        else:
            payload_before = {"provedor": atual.provedor, "config": atual.config}
            atual.provedor = provedor
            atual.config = config_persistir
            atual.atualizado_por_id = ator_id
            await self.session.flush()
            action = "provider.whatsapp.atualizado"

            if trocando:
                # Desativa todas as credenciais antigas em batch
                await self.session.execute(
                    update(CredencialIntegracao)
                    .where(
                        CredencialIntegracao.empresa_id == self.empresa_id,
                        CredencialIntegracao.categoria == "whatsapp",
                        CredencialIntegracao.ativo.is_(True),
                    )
                    .values(ativo=False, status="desativado_por_troca_de_provedor")
                )
                action = "provider.whatsapp.trocado_com_forca"
                payload_before["instancias_desativadas"] = len(
                    await self.listar_instancias_ativas_ids()
                )

        audit = AuditLogger(self.session)
        await audit.record(
            action=action,
            user_id=str(ator_id) if ator_id else None,
            entity="whatsapp_provedor_config",
            entity_id=str(atual.id),
            category="security",
            payload_before=payload_before if action.startswith("provider.whatsapp.atualizado") or action.startswith("provider.whatsapp.trocado") else None,
            payload_after={"provedor": provedor, "config_keys": list(config_persistir.keys())},
        )
        return atual
