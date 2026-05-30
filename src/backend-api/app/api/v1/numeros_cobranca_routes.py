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
    """Payload pra cadastrar nova instância WhatsApp.

    O provedor NÃO vem no body — é inferido de `WhatsappProvedorConfig` da
    empresa (configurada via Integrações). Validação dos campos de
    instância segue o catálogo de `servico_whatsapp_provedor`.
    """
    apelido: str | None = Field(default=None, max_length=80)
    numero_e164: str = Field(min_length=8, max_length=20)
    eh_principal: bool = False
    config: dict = Field(default_factory=dict)


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


@router.post("", response_model=NumeroOut, status_code=201)
async def cadastrar_numero(
    body: NumeroCreateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> NumeroOut:
    """Cadastra uma instância WhatsApp no tenant.

    Provedor é INFERIDO de `WhatsappProvedorConfig` (configurada via
    `PUT /admin/whatsapp-provedor` — UI de Integrações). Sem provedor
    configurado → 412 com link pra Integrações.

    O config requerido vem do catálogo em
    `servico_whatsapp_provedor.descritor(provedor)['campos_instancia']`.
    """
    _check_admin(current_user)

    from app.application.services.servico_whatsapp_provedor import (
        CamposObrigatoriosFaltandoError,
        ServicoWhatsappProvedor,
        validar_config_instancia,
    )
    from app.infrastructure.db.models.integration_credential import IntegrationCredential

    provedor_servico = ServicoWhatsappProvedor(session, current_user.empresa_id)
    provedor_config = await provedor_servico.obter_config_ativa()
    if provedor_config is None:
        raise HTTPException(
            status_code=412,
            detail={
                "message": (
                    "Configure um provedor WhatsApp em Integrações antes de "
                    "adicionar instâncias."
                ),
                "link": "/sistema/configuracoes/integracoes",
            },
        )
    provedor = provedor_config.provedor

    try:
        validar_config_instancia(provedor, body.config)
    except CamposObrigatoriosFaltandoError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

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
        provedor=provedor,
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
        "provedor": provedor,
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
