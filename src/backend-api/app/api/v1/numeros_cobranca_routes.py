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
    NenhumNumeroAtivoError,
    ServicoRoteamentoNumeros,
)


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
