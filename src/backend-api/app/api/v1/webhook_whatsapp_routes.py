"""WhatsApp webhook receiver endpoint (Epic 6)."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request

from app.api.deps import SessionDep
from app.infrastructure.db.models.conversation import ConversationMessage
from app.infrastructure.db.models.payable import WebhookEventRaw

log = structlog.get_logger()

router = APIRouter(prefix="/webhooks", tags=["webhooks-whatsapp"])

# Map of provider -> expected header name for webhook signature
_SIGNATURE_HEADERS: dict[str, str] = {
    "zapi": "x-zapi-signature",
    "uazapi": "x-webhook-secret",
    "evolution_api": "x-evolution-signature",
}


async def _validate_webhook_signature(
    provider: str, request: Request, body: bytes
) -> None:
    """Validate webhook signature if a secret is configured for the provider.

    Raises HTTPException(403) when signature is invalid.
    Logs a warning (but allows) when no secret is configured (dev mode).
    """
    from app.core.config import settings

    webhook_secret: str | None = getattr(
        settings, f"WHATSAPP_{provider.upper()}_WEBHOOK_SECRET", None
    )

    if not webhook_secret:
        log.warning(
            "webhook_no_secret_configured",
            provider=provider,
            hint="Configure a webhook secret for production use",
        )
        return

    sig_header = _SIGNATURE_HEADERS.get(provider, "x-webhook-signature")
    received_sig = request.headers.get(sig_header, "")

    if not received_sig:
        raise HTTPException(status_code=403, detail="Missing webhook signature")

    expected_sig = hmac.new(
        webhook_secret.encode(), body, hashlib.sha256
    ).hexdigest()

    # Support "sha256=<hex>" prefix format
    clean_sig = received_sig.removeprefix("sha256=")

    if not hmac.compare_digest(clean_sig, expected_sig):
        log.warning("webhook_signature_mismatch", provider=provider)
        raise HTTPException(status_code=403, detail="Invalid webhook signature")


@router.post("/whatsapp/{provider}")
async def receive_whatsapp_webhook(
    provider: str,
    request: Request,
    session: SessionDep,
) -> dict:
    """Receive inbound WhatsApp webhook.

    This endpoint:
    1. Validates webhook signature (if secret configured)
    2. Persists raw payload to webhook_events_raw (idempotency on provider+external_id)
    3. Enqueues Celery task for async processing
    4. Returns 200 immediately
    """
    raw_body = await request.body()

    # B-H1: Validate webhook signature before processing
    await _validate_webhook_signature(provider, request, raw_body)

    try:
        payload = await request.json()
    except Exception:
        payload = {"raw_body": raw_body.decode("utf-8", errors="replace")}

    headers = dict(request.headers)

    # Extract external_id for idempotency
    external_id = _extract_external_id(provider, payload)

    # Check for duplicate
    if external_id:
        from sqlalchemy import select, and_

        dup_stmt = select(WebhookEventRaw.id).where(
            WebhookEventRaw.provider == f"whatsapp_{provider}",
            WebhookEventRaw.payload["external_id"].as_string() == external_id,
        ).limit(1)
        try:
            dup_result = await session.execute(dup_stmt)
            if dup_result.scalar_one_or_none() is not None:
                return {"status": "duplicate"}
        except Exception:
            pass

    # Persist raw event
    event = WebhookEventRaw(
        provider=f"whatsapp_{provider}",
        event_type="inbound",
        payload={**payload, "external_id": external_id, "headers": headers},
        processed=False,
    )
    session.add(event)
    await session.commit()

    # Enqueue Celery task for async processing
    try:
        from app.workers import celery_app

        celery_app.send_task(
            "app.workers.tasks.process_inbound_whatsapp.process_inbound_whatsapp",
            args=[str(event.id), provider],
            queue="whatsapp_inbound",
        )
    except Exception:
        log.warning("celery_enqueue_failed", exc_info=True)

    log.info("whatsapp_webhook_received", provider=provider, event_id=str(event.id))
    return {"status": "received", "event_id": str(event.id)}


def _extract_external_id(provider: str, payload: dict) -> str | None:
    """Extract the external message ID from provider-specific payload."""
    if provider == "zapi":
        return payload.get("messageId")
    elif provider == "uazapi":
        data = payload.get("data", payload)
        return data.get("messageId") or data.get("key", {}).get("id")
    elif provider == "evolution_api":
        data = payload.get("data", {})
        return data.get("key", {}).get("id")
    return payload.get("messageId") or payload.get("id")
