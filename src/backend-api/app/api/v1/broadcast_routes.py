"""Broadcast campaign endpoints (Epic 6)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update

from app.api.deps import CurrentUserDep, SessionDep
from app.application.shared.audit_logger import AuditLogger
from app.infrastructure.db.models.agent import BroadcastCampaign

log = structlog.get_logger()

router = APIRouter(prefix="/broadcasts", tags=["broadcasts"])


# --- Schemas ---

class BroadcastCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    template: str = Field(..., min_length=1)
    audience_filter: dict | None = None
    scheduled_at: str | None = None


class BroadcastResponse(BaseModel):
    id: str
    name: str
    template: str
    audience_filter: dict | None = None
    status: str
    total_recipients: int
    sent_count: int
    created_by: str | None = None
    created_at: str
    scheduled_at: str | None = None

    model_config = {"from_attributes": True}


def _campaign_to_response(c: BroadcastCampaign) -> BroadcastResponse:
    return BroadcastResponse(
        id=str(c.id),
        name=c.nome,
        template=c.mensagem,
        audience_filter=c.filtros,
        status=c.status,
        total_recipients=c.total_destinatarios,
        sent_count=c.enviadas,
        created_by=str(c.criado_por_id) if c.criado_por_id else None,
        created_at=c.criado_em.isoformat(),
        scheduled_at=c.agendado_para.isoformat() if c.agendado_para else None,
    )


# --- Endpoints ---

@router.get("", response_model=list[BroadcastResponse])
async def list_broadcasts(
    session: SessionDep,
    user: CurrentUserDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> list[BroadcastResponse]:
    """List broadcast campaigns."""
    stmt = (
        select(BroadcastCampaign)
        .order_by(BroadcastCampaign.criado_em.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    campaigns = result.scalars().all()
    return [_campaign_to_response(c) for c in campaigns]


@router.post("", response_model=BroadcastResponse, status_code=201)
async def create_broadcast(
    body: BroadcastCreateRequest,
    session: SessionDep,
    user: CurrentUserDep,
) -> BroadcastResponse:
    """Create a new broadcast campaign."""
    campaign = BroadcastCampaign(
        nome=body.name,
        mensagem=body.template,
        filtros=body.audience_filter or {},
        status="rascunho",
        criado_por_id=user.id,
    )
    if body.scheduled_at:
        campaign.agendado_para = datetime.fromisoformat(body.scheduled_at)

    session.add(campaign)

    audit = AuditLogger(session)
    await audit.record(
        action="broadcast.create",
        user_id=str(user.id),
        entity="broadcast_campaign",
        payload_after={"name": body.name},
    )

    await session.commit()
    await session.refresh(campaign)

    return _campaign_to_response(campaign)


@router.get("/channels")
async def list_channels(
    session: SessionDep,
    user: CurrentUserDep,
) -> list[dict]:
    """Lista canais de mensageria + status agregado.

    WhatsApp: agora pode ter N instâncias por empresa (Story 13.21).
    `configured` = ao menos 1 instância ativa; `healthy` = todas ativas
    estão em estado conectado/configurada.
    """
    from app.infrastructure.db.models.integration_credential import IntegrationCredential

    stmt = select(IntegrationCredential).where(
        IntegrationCredential.empresa_id == user.empresa_id,
        IntegrationCredential.ativo.is_(True),
    )
    result = await session.execute(stmt)
    db_integrations = result.scalars().all()

    # Agrupa por categoria (uma categoria pode ter N credenciais — caso WhatsApp)
    por_categoria: dict[str, list[IntegrationCredential]] = {}
    for cred in db_integrations:
        por_categoria.setdefault(cred.categoria, []).append(cred)

    all_types: list[tuple[str, str, bool]] = [
        ("whatsapp", "WhatsApp", False),
        ("email", "E-mail", True),
        ("sms", "SMS", True),
        ("telegram", "Telegram", True),
    ]

    channels = []
    for type_id, label, coming_soon in all_types:
        creds = por_categoria.get(type_id, [])
        configured = len(creds) > 0
        healthy_states = {"healthy", "configurada"}
        healthy = configured and all(c.status in healthy_states for c in creds)
        provider = creds[0].provedor if configured else None
        if type_id == "whatsapp" and len(creds) > 1:
            display_name = f"{label} ({len(creds)} números)"
        elif configured:
            display_name = f"{label} ({provider})"
        else:
            display_name = label
        channels.append({
            "channel_type": type_id,
            "provider": provider,
            "instances_count": len(creds),
            "display_name": display_name,
            "label": label,
            "configured": configured,
            "healthy": healthy,
            "coming_soon": coming_soon,
        })

    return channels


@router.get("/channel-status")
async def get_channel_status(
    session: SessionDep,
    user: CurrentUserDep,
) -> dict:
    """Resumo do canal WhatsApp do tenant: # instâncias, # saudáveis.

    Antes retornava só "a primeira credencial". Agora retorna agregação
    consistente com multi-número (Story 13.21).
    """
    from app.infrastructure.db.models.integration_credential import IntegrationCredential

    stmt = select(IntegrationCredential).where(
        IntegrationCredential.empresa_id == user.empresa_id,
        IntegrationCredential.categoria == "whatsapp",
        IntegrationCredential.ativo.is_(True),
    )
    result = await session.execute(stmt)
    creds = list(result.scalars().all())

    if not creds:
        return {
            "configured": False,
            "healthy": False,
            "instances_count": 0,
            "healthy_count": 0,
            "provider": None,
            "message": (
                "Nenhum número WhatsApp configurado. Cadastre em "
                "Configurações › Canais › WhatsApp."
            ),
        }

    healthy_states = {"healthy", "configurada"}
    saudaveis = sum(1 for c in creds if c.status in healthy_states)
    return {
        "configured": True,
        "healthy": saudaveis == len(creds),
        "instances_count": len(creds),
        "healthy_count": saudaveis,
        "provider": creds[0].provedor,
        "message": (
            f"{saudaveis} de {len(creds)} número(s) "
            f"em estado saudável"
        ),
    }


@router.get("/{broadcast_id}", response_model=BroadcastResponse)
async def get_broadcast(
    broadcast_id: UUID,
    session: SessionDep,
    user: CurrentUserDep,
) -> BroadcastResponse:
    """Get a broadcast campaign by ID."""
    stmt = select(BroadcastCampaign).where(BroadcastCampaign.id == broadcast_id)
    result = await session.execute(stmt)
    campaign = result.scalar_one_or_none()

    if campaign is None:
        raise HTTPException(status_code=404, detail="Broadcast not found")

    return _campaign_to_response(campaign)


@router.post("/{broadcast_id}/send", status_code=202)
async def send_broadcast(
    broadcast_id: UUID,
    session: SessionDep,
    user: CurrentUserDep,
) -> dict:
    """Trigger sending a broadcast campaign."""
    from app.infrastructure.db.models.integration_credential import IntegrationCredential
    from app.infrastructure.db.models.customer import Customer

    # Confere que o tenant tem AO MENOS 1 número WhatsApp ativo (Story 13.21
    # multi-número — qualquer instância ativa basta porque o roteamento por
    # cliente escolhe a credencial certa em tempo de envio).
    channel_stmt = select(IntegrationCredential).where(
        IntegrationCredential.empresa_id == user.empresa_id,
        IntegrationCredential.categoria == "whatsapp",
        IntegrationCredential.ativo.is_(True),
    ).limit(1)
    channel_result = await session.execute(channel_stmt)
    if channel_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "Nenhum número WhatsApp configurado. Cadastre em "
                "Configurações › Canais › WhatsApp antes de enviar."
            ),
        )

    # Get campaign — multi-tenant guard.
    stmt = select(BroadcastCampaign).where(
        BroadcastCampaign.id == broadcast_id,
        BroadcastCampaign.empresa_id == user.empresa_id,
    )
    result = await session.execute(stmt)
    campaign = result.scalar_one_or_none()

    if campaign is None:
        raise HTTPException(status_code=404, detail="Aviso não encontrado")

    if campaign.status not in ("rascunho", "agendado"):
        raise HTTPException(status_code=400, detail="Este aviso já foi enviado ou está em andamento")

    # Conta destinatários (clientes ativos COM telefone, DA EMPRESA do user).
    recipients_count_stmt = select(func.count()).select_from(Customer).where(
        Customer.empresa_id == user.empresa_id,
        Customer.excluido_em.is_(None),
        Customer.status == "ativo",
        Customer.telefone.isnot(None),
        Customer.telefone != "",
    )
    recipients_result = await session.execute(recipients_count_stmt)
    total_recipients = recipients_result.scalar_one()

    if total_recipients == 0:
        raise HTTPException(
            status_code=422,
            detail="Nenhum destinatário elegível. Não há clientes ativos com telefone cadastrado.",
        )

    campaign.status = "enviando"
    campaign.total_destinatarios = total_recipients

    audit = AuditLogger(session)
    await audit.record(
        action="broadcast.send",
        user_id=str(user.id),
        entity="broadcast_campaign",
        entity_id=str(broadcast_id),
        payload_after={"status": "enviando", "total_destinatarios": total_recipients},
    )

    await session.commit()

    # Enqueue Celery task
    try:
        from app.workers import celery_app

        celery_app.send_task(
            "app.workers.tasks.send_broadcast.send_broadcast",
            args=[str(broadcast_id)],
            queue="default",
        )
    except Exception:
        log.warning("celery_broadcast_enqueue_failed", exc_info=True)

    return {"status": "enviando", "campaign_id": str(broadcast_id), "total_recipients": total_recipients}
