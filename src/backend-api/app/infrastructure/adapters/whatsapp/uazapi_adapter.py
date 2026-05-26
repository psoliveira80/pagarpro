"""Uazapi WhatsApp adapter.

API Docs: https://docs.uazapi.com
Endpoint pattern: POST {base_url}/send/text
Auth: Header 'apikey: {api_key}'
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from app.domain.ports.whatsapp_gateway import (
    IWhatsAppGateway,
    MessageStatusUpdate,
    ReceivedMessage,
)

log = structlog.get_logger()


class UazapiAdapter(IWhatsAppGateway):
    """WhatsApp adapter for Uazapi (docs.uazapi.com)."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._headers = {
            "Content-Type": "application/json",
            "token": api_key,
        }

    async def send_text(self, phone: str, text: str) -> dict[str, Any]:
        """POST /send/text — sends a text message."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/send/text",
                headers=self._headers,
                json={"number": phone, "text": text},
            )
            log.info("uazapi_send_text", phone=phone, status=resp.status_code)
            resp.raise_for_status()
            return resp.json()

    async def send_template(
        self, phone: str, template_name: str, params: dict[str, str]
    ) -> dict[str, Any]:
        # Uazapi doesn't have a native template endpoint — send as text
        text = template_name
        for key, value in params.items():
            text = text.replace(f"{{{key}}}", value)
        return await self.send_text(phone, text)

    async def send_media(
        self, phone: str, media_url: str, mime_type: str, caption: str | None = None
    ) -> dict[str, Any]:
        """POST /send/image or /send/document depending on mime type."""
        if mime_type.startswith("image/"):
            endpoint = "/send/image"
            body: dict[str, Any] = {
                "number": phone,
                "image": media_url,
                "caption": caption or "",
            }
        else:
            endpoint = "/send/document"
            body = {
                "number": phone,
                "document": media_url,
                "fileName": caption or "document",
            }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}{endpoint}",
                headers=self._headers,
                json=body,
            )
            log.info("uazapi_send_media", phone=phone, endpoint=endpoint, status=resp.status_code)
            resp.raise_for_status()
            return resp.json()

    async def parse_webhook(
        self, headers: dict[str, str], body: dict[str, Any]
    ) -> ReceivedMessage | MessageStatusUpdate | None:
        event = body.get("event", "")

        if event == "message.status":
            return MessageStatusUpdate(
                external_id=body.get("messageId", ""),
                status=body.get("status", ""),
                timestamp=body.get("timestamp"),
            )

        if event in ("message", "message.new"):
            data = body.get("data", body)
            text_content = data.get("body") or data.get("text") or data.get("message")
            media_url = data.get("mediaUrl")
            media_mime = data.get("mimetype")
            is_audio = (media_mime or "").startswith("audio/")

            return ReceivedMessage(
                sender_phone=data.get("from", data.get("remoteJid", "")),
                text=text_content,
                media_url=media_url,
                media_mime=media_mime,
                timestamp=data.get("timestamp"),
                external_id=data.get("messageId") or data.get("key", {}).get("id"),
                is_audio=is_audio,
                raw_payload=body,
            )

        return None
