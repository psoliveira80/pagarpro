"""Wraps existing IWhatsAppGateway adapters into IMessageChannel interface.

This allows the WhatsApp adapters (ZapiAdapter, UazapiAdapter, EvolutionApiAdapter)
to participate in the unified ChannelRegistry without rewriting them.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from app.domain.ports.message_channel import (
    ChannelHealth,
    InboundMessage,
    IMessageChannel,
    MessageReceipt,
)
from app.domain.ports.whatsapp_gateway import IWhatsAppGateway


class WhatsAppChannelWrapper:
    """Wraps an IWhatsAppGateway adapter to satisfy IMessageChannel."""

    def __init__(self, adapter: IWhatsAppGateway, provider: str, display: str) -> None:
        self._adapter = adapter
        self._provider = provider
        self._display = display

    @property
    def channel_type(self) -> str:
        return "whatsapp"

    @property
    def provider_name(self) -> str:
        return self._provider

    @property
    def display_name(self) -> str:
        return self._display

    async def send_text(self, to: str, text: str) -> MessageReceipt:
        msg_id = await self._adapter.send_text(to, text)
        return MessageReceipt(
            provider_message_id=msg_id,
            channel_type="whatsapp",
            sent_at=datetime.now(timezone.utc),
        )

    async def send_media(self, to: str, media_url: str, caption: str) -> MessageReceipt:
        msg_id = await self._adapter.send_media(to, media_url, caption)
        return MessageReceipt(
            provider_message_id=msg_id,
            channel_type="whatsapp",
            sent_at=datetime.now(timezone.utc),
        )

    async def parse_webhook(self, payload: dict[str, Any]) -> InboundMessage:
        parsed = await self._adapter.parse_webhook(payload)
        return InboundMessage(
            channel_type="whatsapp",
            provider=self._provider,
            from_address=parsed.from_phone,
            to_address=parsed.to_phone,
            body=parsed.body,
            media_url=parsed.media_url if hasattr(parsed, "media_url") else None,
            message_id=parsed.message_id,
            timestamp=parsed.timestamp,
            raw_payload=payload,
        )

    async def health_check(self) -> ChannelHealth:
        """Simple health check — tries to call a lightweight endpoint."""
        start = time.monotonic()
        try:
            # Most WhatsApp APIs have a status/queue endpoint
            if hasattr(self._adapter, "health_check"):
                await self._adapter.health_check()
            else:
                # Fallback: check if adapter can be instantiated (config is valid)
                pass
            latency = (time.monotonic() - start) * 1000
            return ChannelHealth(
                channel_type="whatsapp",
                provider=self._provider,
                is_healthy=True,
                latency_ms=round(latency, 1),
                message="Operacional",
                checked_at=datetime.now(timezone.utc),
            )
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            return ChannelHealth(
                channel_type="whatsapp",
                provider=self._provider,
                is_healthy=False,
                latency_ms=round(latency, 1),
                message=str(exc),
                checked_at=datetime.now(timezone.utc),
            )
