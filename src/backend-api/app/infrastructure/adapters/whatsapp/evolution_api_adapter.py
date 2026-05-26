"""Evolution API WhatsApp adapter (self-hosted)."""

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


class EvolutionApiAdapter:
    """WhatsApp adapter for Evolution API (self-hosted, zero cost)."""

    def __init__(self, base_url: str, api_key: str, instance_name: str = "default"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.instance_name = instance_name
        self._headers = {"apikey": api_key, "Content-Type": "application/json"}

    async def send_text(self, phone: str, text: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/message/sendText/{self.instance_name}",
                headers=self._headers,
                json={"number": phone, "text": text},
            )
            resp.raise_for_status()
            return resp.json()

    async def send_template(
        self, phone: str, template_name: str, params: dict[str, str]
    ) -> dict[str, Any]:
        # Evolution API does not natively support template messages
        # We send as text with filled-in params
        text = template_name
        for key, value in params.items():
            text = text.replace(f"{{{{{key}}}}}", value)
        return await self.send_text(phone, text)

    async def send_media(
        self, phone: str, media_url: str, mime_type: str, caption: str | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "number": phone,
            "media": media_url,
            "mimetype": mime_type,
        }
        if caption:
            body["caption"] = caption

        endpoint = "sendImage" if mime_type.startswith("image/") else "sendDocument"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/message/{endpoint}/{self.instance_name}",
                headers=self._headers,
                json=body,
            )
            resp.raise_for_status()
            return resp.json()

    async def parse_webhook(
        self, headers: dict[str, str], body: dict[str, Any]
    ) -> ReceivedMessage | MessageStatusUpdate | None:
        # Validate apikey header
        incoming_key = headers.get("apikey", "")
        if incoming_key and incoming_key != self.api_key:
            raise ValueError("Invalid webhook apikey")

        event = body.get("event", "")

        if event == "messages.update":
            data = body.get("data", {})
            return MessageStatusUpdate(
                external_id=data.get("key", {}).get("id", ""),
                status=data.get("status", ""),
                timestamp=data.get("dateTime"),
            )

        if event == "messages.upsert":
            data = body.get("data", {})
            msg = data if isinstance(data, dict) else {}
            key = msg.get("key", {})

            # Skip outgoing messages
            if key.get("fromMe", False):
                return None

            text_content = msg.get("message", {}).get("conversation") or msg.get(
                "message", {}
            ).get("extendedTextMessage", {}).get("text")
            media_url = None
            media_mime = None
            is_audio = False

            message_content = msg.get("message", {})
            if "imageMessage" in message_content:
                media_mime = message_content["imageMessage"].get("mimetype", "image/jpeg")
                media_url = message_content["imageMessage"].get("url")
            elif "audioMessage" in message_content:
                media_mime = message_content["audioMessage"].get("mimetype", "audio/ogg")
                media_url = message_content["audioMessage"].get("url")
                is_audio = True
            elif "documentMessage" in message_content:
                media_mime = message_content["documentMessage"].get(
                    "mimetype", "application/pdf"
                )
                media_url = message_content["documentMessage"].get("url")

            return ReceivedMessage(
                sender_phone=key.get("remoteJid", "").replace("@s.whatsapp.net", ""),
                text=text_content,
                media_url=media_url,
                media_mime=media_mime,
                timestamp=str(msg.get("messageTimestamp", "")),
                external_id=key.get("id"),
                is_audio=is_audio,
                raw_payload=body,
            )

        return None
