"""Endpoints REST para gestão de números de cobrança WhatsApp (Story 13.21).

Topologia A (consolidada): provedor SaaS (Pablo) hospeda o Evolution Go
central e cria as instâncias quando provisiona um cliente novo. Essa tela
no FrotaUber é **read-only para conexão** — gestor não vê QR Code, não
conecta instâncias. Apenas monitora e administra status (marcar banido
manualmente, escolher principal).

Endpoints:
- `GET /numeros-cobranca` — lista números da empresa com contagem de clientes.
- `PUT /numeros-cobranca/{id}/marcar-banido` — ação manual do gestor.
- `PUT /numeros-cobranca/{id}/marcar-ativo` — reativa número (depois de
  reconexão manual no painel do Evolution Go).
- `PUT /numeros-cobranca/{id}/marcar-principal` — escolhe o número padrão
  para empate na atribuição (entre clientes novos).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import CurrentUserDep, SessionDep
from app.application.services.servico_roteamento_numeros import (
    ServicoRoteamentoNumeros,
)
from app.application.shared.audit_logger import AuditLogger


router = APIRouter(prefix="/numeros-cobranca", tags=["numeros-cobranca"])


# ───────── Schemas ─────────

class NumeroOut(BaseModel):
    credencial_id: str
    provedor: str
    instance_id: str | None
    numero_e164: str | None
    status_whatsapp: str
    eh_principal: bool
    clientes_atribuidos: int
    ultimo_health_check: str | None
    motivo_banimento: str | None


class MarcarBanidoRequest(BaseModel):
    motivo: str = Field(min_length=3, max_length=500)


class NumeroCreateRequest(BaseModel):
    """Payload pra cadastrar nova instância WhatsApp em QUALQUER provedor
    suportado (`evolution_go` padrão da Topologia A, `evolution_api`
    self-hosted, `zapi`, `uazapi`).

    Em Topologia A o provisionamento da instância acontece no provedor SaaS
    (Pablo) usando `evolution_go`. Empresas que rodam infra própria podem
    cadastrar outros providers — schemas validados em
    `validar_config_por_provedor`. Meta Cloud API (`meta_cloud`) está
    reservado mas sem adapter implementado.
    """
    provedor: str = Field(default="evolution_go", max_length=40)
    apelido: str | None = Field(default=None, max_length=80)
    numero_e164: str = Field(min_length=8, max_length=20)
    eh_principal: bool = False
    config: dict = Field(default_factory=dict)


# Schema por provedor: chave → (campos obrigatórios, suportado)
_PROVEDORES_SUPORTADOS: dict[str, tuple[tuple[str, ...], bool]] = {
    "evolution_go": (("instance_id", "instance_token"), True),
    "evolution_api": (("base_url", "api_key", "instance"), True),
    "zapi": (("instance_id", "token"), True),
    "uazapi": (("base_url", "api_key", "instance"), True),
    # Meta Cloud API oficial — sem adapter ainda. Cadastro bloqueado.
    "meta_cloud": (("phone_number_id", "access_token", "waba_id"), False),
}


def _validar_config_por_provedor(provedor: str, config: dict) -> None:
    if provedor not in _PROVEDORES_SUPORTADOS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Provedor '{provedor}' não reconhecido. "
                f"Suportados: {', '.join(_PROVEDORES_SUPORTADOS)}"
            ),
        )
    campos, ativo = _PROVEDORES_SUPORTADOS[provedor]
    if not ativo:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Provedor '{provedor}' reservado mas ainda sem adapter "
                "— em breve."
            ),
        )
    faltando = [c for c in campos if not str(config.get(c, "")).strip()]
    if faltando:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Campos obrigatórios faltando para {provedor}: "
                f"{', '.join(faltando)}"
            ),
        )


# ───────── Helpers ─────────

def _check_admin(current_user) -> None:
    roles = [(p.nome or "").lower() for p in (current_user.perfis or [])]
    if "admin" not in roles:
        raise HTTPException(
            status_code=403,
            detail="Apenas administradores podem gerenciar números de cobrança",
        )


# ───────── Endpoints ─────────

@router.get("", response_model=list[NumeroOut])
async def listar_numeros(
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Lista números da empresa com contagem de clientes atribuídos."""
    _check_admin(current_user)
    servico = ServicoRoteamentoNumeros(session, current_user.empresa_id)
    numeros = await servico.listar_numeros()
    return [NumeroOut(**n) for n in numeros]


@router.get("/provedores")
async def listar_provedores_suportados(
    current_user: CurrentUserDep,
) -> list[dict]:
    """Lista provedores WhatsApp suportados pra alimentar o seletor da UI.

    Cada entrada traz `id`, `label`, `campos` (lista de campos requeridos
    com tipo) e `disponivel` (false = reservado/em breve). Restrito a
    admin — gestor comum não escolhe provider.
    """
    _check_admin(current_user)
    catalogo: list[dict] = [
        {
            "id": "evolution_go",
            "label": "Evolution Go (SaaS provedor)",
            "help": (
                "Instância hospedada no Evolution Go central — Topologia A. "
                "Use as credenciais geradas no painel SaaS."
            ),
            "campos": [
                {"key": "instance_id", "label": "Instance ID", "type": "text", "required": True},
                {"key": "instance_token", "label": "Instance Token", "type": "password", "required": True},
            ],
            "disponivel": True,
            "multi_numero": True,
        },
        {
            "id": "evolution_api",
            "label": "Evolution API (self-hosted)",
            "help": "Sua própria instância Evolution API rodando em servidor próprio.",
            "campos": [
                {"key": "base_url", "label": "URL do Servidor", "type": "url", "required": True},
                {"key": "api_key", "label": "API Key", "type": "password", "required": True},
                {"key": "instance", "label": "Nome da Instância", "type": "text", "required": True},
            ],
            "disponivel": True,
            "multi_numero": False,
        },
        {
            "id": "zapi",
            "label": "Z-API",
            "help": "Acesse z-api.io para obter Instance ID + Token.",
            "campos": [
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
            "help": "Acesse uazapi.com para obter base_url + chave.",
            "campos": [
                {"key": "base_url", "label": "URL da API", "type": "url", "required": True},
                {"key": "api_key", "label": "API Key", "type": "password", "required": True},
                {"key": "instance", "label": "Instância", "type": "text", "required": True},
            ],
            "disponivel": True,
            "multi_numero": False,
        },
        {
            "id": "meta_cloud",
            "label": "Meta Cloud API (oficial)",
            "help": "Em breve — adapter para WhatsApp Business Platform oficial.",
            "campos": [
                {"key": "phone_number_id", "label": "Phone Number ID", "type": "text", "required": True},
                {"key": "access_token", "label": "Access Token", "type": "password", "required": True},
                {"key": "waba_id", "label": "WABA ID", "type": "text", "required": True},
            ],
            "disponivel": False,
            "multi_numero": True,
        },
    ]
    return catalogo


@router.post("", response_model=NumeroOut, status_code=201)
async def cadastrar_numero(
    body: NumeroCreateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> NumeroOut:
    """Cadastra uma instância WhatsApp no tenant — provedor à escolha.

    Substitui `POST /admin/integrations` para `category='whatsapp'` (que
    fica bloqueado por validator no schema). Multi-tenant garantido pelo
    `current_user.empresa_id`. Se for marcada como principal, qualquer
    outra principal da mesma empresa é rebaixada.

    O config requerido depende do provedor — ver
    `GET /numeros-cobranca/provedores` para o catálogo.
    """
    _check_admin(current_user)
    _validar_config_por_provedor(body.provedor, body.config)

    from app.infrastructure.db.models.integration_credential import IntegrationCredential

    config_persistir = dict(body.config)
    config_persistir.update({
        "numero_e164": body.numero_e164,
        "apelido": body.apelido,
        "status_whatsapp": "ativo",
        "eh_principal": False,  # ServicoRoteamentoNumeros marca abaixo
    })

    cred = IntegrationCredential(
        empresa_id=current_user.empresa_id,
        categoria="whatsapp",
        provedor=body.provedor,
        ativo=True,
        status="configurada",
        config=config_persistir,
    )
    session.add(cred)
    await session.flush()

    servico = ServicoRoteamentoNumeros(session, current_user.empresa_id)
    if body.eh_principal:
        await servico.definir_numero_principal(cred.id, ator_id=current_user.id)

    audit = AuditLogger(session)
    audit_after = {
        "provedor": body.provedor,
        "numero_e164": body.numero_e164,
        "eh_principal": body.eh_principal,
        # Não loga tokens/keys — só identificadores não-sensíveis
        "instance_id": body.config.get("instance_id"),
        "instance": body.config.get("instance"),
        "phone_number_id": body.config.get("phone_number_id"),
    }
    await audit.record(
        action="numero_whatsapp.cadastrado",
        user_id=str(current_user.id),
        entity="credenciais_integracao",
        entity_id=str(cred.id),
        category="security",
        payload_after={k: v for k, v in audit_after.items() if v is not None},
    )
    await session.commit()

    numeros = await servico.listar_numeros()
    novo = next((n for n in numeros if n["credencial_id"] == str(cred.id)), None)
    if novo is None:
        raise HTTPException(status_code=500, detail="Credencial sumiu após cadastro")
    return NumeroOut(**novo)


@router.put("/{credencial_id}/marcar-banido", response_model=dict)
async def marcar_numero_banido(
    credencial_id: UUID,
    body: MarcarBanidoRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Marca número como banido manualmente. Dispara migração automática
    de todos os clientes atribuídos pra outros números ativos."""
    _check_admin(current_user)
    servico = ServicoRoteamentoNumeros(session, current_user.empresa_id)
    try:
        migrados = await servico.marcar_numero_banido(
            credencial_id=credencial_id,
            motivo=body.motivo,
            ator_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()
    return {
        "credencial_id": str(credencial_id),
        "clientes_migrados": migrados,
        "motivo": body.motivo,
    }


@router.put("/{credencial_id}/marcar-ativo", response_model=dict)
async def marcar_numero_ativo(
    credencial_id: UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Reativa número (depois de gestor reconectar no painel do Evolution Go).

    NÃO reatribui clientes — distribuição balanceia em novos atendimentos.
    """
    _check_admin(current_user)
    servico = ServicoRoteamentoNumeros(session, current_user.empresa_id)
    try:
        await servico.marcar_numero_ativo(credencial_id, ator_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()
    return {"credencial_id": str(credencial_id), "status": "ativo"}


@router.put("/{credencial_id}/marcar-principal", response_model=dict)
async def marcar_numero_principal(
    credencial_id: UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Define este número como principal (preferido em caso de empate de
    contagem entre números ativos da empresa). Só 1 principal por empresa."""
    _check_admin(current_user)
    servico = ServicoRoteamentoNumeros(session, current_user.empresa_id)
    try:
        await servico.definir_numero_principal(credencial_id, ator_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await session.commit()
    return {"credencial_id": str(credencial_id), "eh_principal": True}
