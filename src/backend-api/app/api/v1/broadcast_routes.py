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
    """List all available messaging channels — reads from integration_credentials DB."""
    from app.infrastructure.db.models.integration_credential import IntegrationCredential

    stmt = select(IntegrationCredential).where(IntegrationCredential.ativo.is_(True))
    result = await session.execute(stmt)
    db_integrations = result.scalars().all()

    configured = {i.categoria: i for i in db_integrations}

    all_types = [
        {"type": "whatsapp", "label": "WhatsApp"},
        {"type": "email", "label": "E-mail", "coming_soon": True},
        {"type": "sms", "label": "SMS", "coming_soon": True},
        {"type": "telegram", "label": "Telegram", "coming_soon": True},
    ]

    channels = []
    for t in all_types:
        intg = configured.get(t["type"])
        channels.append({
            "channel_type": t["type"],
            "provider": intg.provedor if intg else None,
            "display_name": f"{t['label']} ({intg.provedor})" if intg else t["label"],
            "label": t["label"],
            "configured": intg is not None,
            "healthy": intg.status == "healthy" if intg else False,
            "coming_soon": bool(t.get("coming_soon", False)),
        })

    return channels


@router.get("/channel-status")
async def get_channel_status(
    session: SessionDep,
    user: CurrentUserDep,
) -> dict:
    """Check WhatsApp channel health — reads from DB."""
    from app.infrastructure.db.models.integration_credential import IntegrationCredential

    stmt = select(IntegrationCredential).where(
        IntegrationCredential.categoria == "whatsapp",
        IntegrationCredential.ativo.is_(True),
    )
    result = await session.execute(stmt)
    cred = result.scalar_one_or_none()

    if cred is None:
        return {"configured": False, "healthy": False, "provider": None, "message": "Nenhum canal WhatsApp configurado"}

    return {
        "configured": True,
        "healthy": cred.status == "healthy",
        "provider": cred.provedor,
        "message": f"Canal {cred.provedor} configurado",
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

    # Check WhatsApp channel is configured
    channel_stmt = select(IntegrationCredential).where(
        IntegrationCredential.categoria == "whatsapp",
        IntegrationCredential.ativo.is_(True),
    )
    channel_result = await session.execute(channel_stmt)
    if channel_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=422,
            detail="Nenhum canal WhatsApp configurado. Configure um canal em Configurações > Integrações antes de enviar.",
        )

    # Get campaign
    stmt = select(BroadcastCampaign).where(BroadcastCampaign.id == broadcast_id)
    result = await session.execute(stmt)
    campaign = result.scalar_one_or_none()

    if campaign is None:
        raise HTTPException(status_code=404, detail="Aviso não encontrado")

    if campaign.status not in ("rascunho", "agendado"):
        raise HTTPException(status_code=400, detail="Este aviso já foi enviado ou está em andamento")

    # Count recipients (active customers with phone)
    recipients_count_stmt = select(func.count()).select_from(Customer).where(
        Customer.excluido_em.is_(None),
        Customer.status == "ativo",
        Customer.phone.isnot(None),
        Customer.phone != "",
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
