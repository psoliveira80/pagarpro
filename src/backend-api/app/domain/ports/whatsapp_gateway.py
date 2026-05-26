"""Port for WhatsApp gateway providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class ReceivedMessage:
    """Normalized inbound WhatsApp message."""

    sender_phone: str
    text: str | None = None
    media_url: str | None = None
    media_mime: str | None = None
    timestamp: str | None = None
    external_id: str | None = None
    is_audio: bool = False
    raw_payload: dict = field(default_factory=dict)


@dataclass
class MessageStatusUpdate:
    """Normalized message status callback."""

    external_id: str
    status: str  # sent | delivered | read | failed
    timestamp: str | None = None


@runtime_checkable
class IWhatsAppGateway(Protocol):
    """Interface for WhatsApp provider adapters."""

    async def send_text(self, phone: str, text: str) -> dict[str, Any]:
        """Send a plain text message."""
        ...

    async def send_template(
        self, phone: str, template_name: str, params: dict[str, str]
    ) -> dict[str, Any]:
        """Send a template message."""
        ...

    async def send_media(
        self, phone: str, media_url: str, mime_type: str, caption: str | None = None
    ) -> dict[str, Any]:
        """Send a media message (image, PDF, audio)."""
        ...

    async def parse_webhook(
        self, headers: dict[str, str], body: dict[str, Any]
    ) -> ReceivedMessage | MessageStatusUpdate | None:
        """Parse and validate an inbound webhook payload.

        Returns ReceivedMessage for inbound messages, MessageStatusUpdate for
        delivery status callbacks, or None if the payload is not relevant.

        Raises ValueError if signature validation fails.
        """
        ...
