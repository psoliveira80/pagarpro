"""Port: Messaging channel interface.

Every messaging channel (WhatsApp, Email, SMS, Telegram, etc.) MUST implement
this Protocol. The system discovers available channels at runtime via
the ChannelRegistry.

To add a new channel:
1. Create an adapter class implementing IMessageChannel
2. Register it in ChannelRegistry at app startup (main.py lifespan)
3. Add integration_credentials row for the provider

The health_check() method is called periodically and on-demand to verify
the channel is operational. A simple ping/pong or API status check suffices.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class MessageReceipt:
    """Returned after sending a message."""
    provider_message_id: str
    channel_type: str
    sent_at: datetime


@dataclass(frozen=True)
class InboundMessage:
    """Normalized inbound message from any channel."""
    channel_type: str
    provider: str
    from_address: str      # phone number, email, etc.
    to_address: str
    body: str
    media_url: str | None
    message_id: str
    timestamp: datetime
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class ChannelHealth:
    """Health check result."""
    channel_type: str
    provider: str
    is_healthy: bool
    latency_ms: float | None
    message: str
    checked_at: datetime


@runtime_checkable
class IMessageChannel(Protocol):
    """Interface that every messaging channel adapter MUST implement."""

    @property
    def channel_type(self) -> str:
        """Channel identifier: 'whatsapp', 'email', 'sms', 'telegram'."""
        ...

    @property
    def provider_name(self) -> str:
        """Provider name: 'zapi', 'evolution_api', 'smtp', etc."""
        ...

    @property
    def display_name(self) -> str:
        """Human-readable name: 'WhatsApp (Z-API)', 'E-mail (SMTP)', etc."""
        ...

    async def send_text(self, to: str, text: str) -> MessageReceipt:
        """Send a text message to the given address."""
        ...

    async def send_media(self, to: str, media_url: str, caption: str) -> MessageReceipt:
        """Send a media message (image, PDF, etc.)."""
        ...

    async def parse_webhook(self, payload: dict[str, Any]) -> InboundMessage:
        """Parse raw webhook payload into a normalized InboundMessage."""
        ...

    async def health_check(self) -> ChannelHealth:
        """Check if the channel is operational. Must be lightweight (< 5s)."""
        ...


# Alias PT-BR (Story 13.18) — preferencial pra código novo.
ICanalMensagem = IMessageChannel
