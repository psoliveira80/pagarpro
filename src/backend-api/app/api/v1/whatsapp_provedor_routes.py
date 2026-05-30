"""Endpoints REST para a config de provedor WhatsApp da empresa (1:1).

Separa o que é provider-level (URL + chaves master) do que é instance-level
(números, instance_id, etc — esses vivem em /numeros-cobranca).

Endpoints:
- `GET  /admin/whatsapp-provedor` — config atual + catálogo de providers.
- `PUT  /admin/whatsapp-provedor` — upsert. Troca com instâncias existentes
  exige `forcar=true` no body (UI confirma com SweetAlert).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import CurrentUserDep, SessionDep
from app.application.services.servico_whatsapp_provedor import (
    CamposObrigatoriosFaltandoError,
    ProvedorDesconhecidoError,
    ProvedorIndisponivelError,
    ProvedorTemInstanciasError,
    ServicoWhatsappProvedor,
    catalogo,
)


router = APIRouter(prefix="/admin/whatsapp-provedor", tags=["whatsapp-provedor"])


# ───────── Schemas ─────────

class ProvedorConfigOut(BaseModel):
    id: str
    empresa_id: str
    provedor: str
    config: dict[str, Any]
    ativo: bool
    atualizado_em: str | None


class CatalogoOut(BaseModel):
    config: ProvedorConfigOut | None
    opcoes: list[dict[str, Any]]


class DefinirProvedorRequest(BaseModel):
    provedor: str = Field(min_length=1, max_length=40)
    config: dict[str, Any] = Field(default_factory=dict)
    forcar: bool = False


# ───────── Helpers ─────────

def _check_admin(current_user) -> None:
    roles = [(p.nome or "").lower() for p in (current_user.perfis or [])]
    if "admin" not in roles:
        raise HTTPException(
            status_code=403,
            detail="Apenas administradores podem mudar o provedor WhatsApp",
        )


# ───────── Endpoints ─────────

@router.get("", response_model=CatalogoOut)
async def obter_provedor_e_opcoes(
    session: SessionDep,
    current_user: CurrentUserDep,
) -> CatalogoOut:
    """Retorna a config ativa de provedor da empresa + catálogo de opções."""
    _check_admin(current_user)
    servico = ServicoWhatsappProvedor(session, current_user.empresa_id)
    config = await servico.obter_config_ativa()
    out: ProvedorConfigOut | None = None
    if config is not None:
        out = ProvedorConfigOut(
            id=str(config.id),
            empresa_id=str(config.empresa_id),
            provedor=config.provedor,
            config=dict(config.config or {}),
            ativo=config.ativo,
            atualizado_em=config.atualizado_em.isoformat() if config.atualizado_em else None,
        )
    return CatalogoOut(config=out, opcoes=catalogo())


@router.put("", response_model=ProvedorConfigOut)
async def definir_provedor(
    body: DefinirProvedorRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ProvedorConfigOut:
    """Upsert do provedor + sua config global. Quando trocar de provedor com
    instâncias existentes, exige `forcar=true` (UI mostra confirmação)."""
    _check_admin(current_user)
    servico = ServicoWhatsappProvedor(session, current_user.empresa_id)
    try:
        config = await servico.definir_provedor(
            provedor=body.provedor,
            config=body.config,
            ator_id=current_user.id,
            forcar=body.forcar,
        )
    except ProvedorDesconhecidoError as exc:
        raise HTTPException(status_code=422, detail=f"Provedor '{exc}' não reconhecido")
    except ProvedorIndisponivelError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Provedor '{exc}' reservado mas ainda sem adapter — em breve.",
        )
    except CamposObrigatoriosFaltandoError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ProvedorTemInstanciasError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(exc),
                "instancias_afetadas": len(exc.credencial_ids),
                "instancia_ids": [str(i) for i in exc.credencial_ids],
                "como_resolver": "Reenvie com forcar=true para desativar todas as instâncias antigas.",
            },
        )

    await session.commit()
    return ProvedorConfigOut(
        id=str(config.id),
        empresa_id=str(config.empresa_id),
        provedor=config.provedor,
        config=dict(config.config or {}),
        ativo=config.ativo,
        atualizado_em=config.atualizado_em.isoformat() if config.atualizado_em else None,
    )
