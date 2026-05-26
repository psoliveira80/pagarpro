"""Webhook endpoint for payment gateway providers (Story 4-9)."""

import structlog
from fastapi import APIRouter, Request

from app.api.deps import SessionDep
from app.infrastructure.db.models.payable import WebhookEventRaw

log = structlog.get_logger()

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/payment-gateway/{provider}")
async def receive_webhook(
    provider: str,
    request: Request,
    session: SessionDep,
) -> dict:
    """Receive and store raw webhook events from payment gateway providers.

    This is a stub endpoint. The event is stored raw for later processing.
    """
    try:
        payload = await request.json()
    except Exception:
        payload = {"raw_body": (await request.body()).decode("utf-8", errors="replace")}

    event = WebhookEventRaw(
        provider=provider,
        event_type=payload.get("type") or payload.get("event_type"),
        payload=payload,
        processed=False,
    )
    session.add(event)
    await session.commit()

    log.info("webhook_received", provider=provider, event_id=str(event.id))

    return {"status": "received", "event_id": str(event.id)}
