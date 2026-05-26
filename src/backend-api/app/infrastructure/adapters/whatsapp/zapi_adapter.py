"""Z-API WhatsApp adapter."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import httpx
import structlog

from app.domain.ports.whatsapp_gateway import (
    IWhatsAppGateway,
    MessageStatusUpdate,
    ReceivedMessage,
)

log = structlog.get_logger()


class ZapiAdapter:
    """WhatsApp adapter for Z-API (api.z-api.io)."""

    def __init__(
        self,
        instance_id: str,
        token: str,
        client_token: str | None = None,
        base_url: str = "https://api.z-api.io",
    ):
        self.instance_id = instance_id
        self.token = token
        self.client_token = client_token
        self.base_url = f"{base_url}/instances/{instance_id}/token/{token}"

    async def send_text(self, phone: str, text: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/send-text",
                json={"phone": phone, "message": text},
            )
            resp.raise_for_status()
            return resp.json()

    async def send_template(
        self, phone: str, template_name: str, params: dict[str, str]
    ) -> dict[str, Any]:
        body = {
            "phone": phone,
            "template": template_name,
            "params": list(params.values()),
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{self.base_url}/send-template", json=body)
            resp.raise_for_status()
            return resp.json()

    async def send_media(
        self, phone: str, media_url: str, mime_type: str, caption: str | None = None
    ) -> dict[str, Any]:
        endpoint = "send-image" if mime_type.startswith("image/") else "send-document"
        body: dict[str, Any] = {"phone": phone, "image": media_url}
        if caption:
            body["caption"] = caption
        if not mime_type.startswith("image/"):
            body = {"phone": phone, "document": media_url, "fileName": "file"}
            if caption:
                body["caption"] = caption

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{self.base_url}/{endpoint}", json=body)
            resp.raise_for_status()
            return resp.json()

    async def parse_webhook(
        self, headers: dict[str, str], body: dict[str, Any]
    ) -> ReceivedMessage | MessageStatusUpdate | None:
        # Validate client token if configured
        if self.client_token:
            token = headers.get("client-token", "")
            if token != self.client_token:
                raise ValueError("Invalid webhook client token")

        # Status update
        if "status" in body and "messageId" in body:
            return MessageStatusUpdate(
                external_id=body["messageId"],
                status=body["status"],
                timestamp=body.get("datetime"),
            )

        # Inbound message
        if body.get("isStatusReply") is False or "text" in body or "image" in body:
            text_content = None
            media_url = None
            media_mime = None
            is_audio = False

            if "text" in body and isinstance(body["text"], dict):
                text_content = body["text"].get("message")
            elif "text" in body and isinstance(body["text"], str):
                text_content = body["text"]

            if "image" in body:
                media_url = body["image"].get("imageUrl")
                media_mime = body["image"].get("mimetype", "image/jpeg")
            elif "audio" in body:
                media_url = body["audio"].get("audioUrl")
                media_mime = body["audio"].get("mimetype", "audio/ogg")
                is_audio = True
            elif "document" in body:
                media_url = body["document"].get("documentUrl")
                media_mime = body["document"].get("mimetype", "application/pdf")

            return ReceivedMessage(
                sender_phone=body.get("phone", ""),
                text=text_content,
                media_url=media_url,
                media_mime=media_mime,
                timestamp=body.get("momment") or body.get("datetime"),
                external_id=body.get("messageId"),
                is_audio=is_audio,
                raw_payload=body,
            )

        return None
