"""Channel Registry — discovers and manages messaging channel adapters.

Usage:
    from app.core.channels.registry import channel_registry

    # At startup (main.py lifespan):
    channel_registry.register(ZApiWhatsAppChannel(config))
    channel_registry.register(EvolutionWhatsAppChannel(config))

    # At runtime:
    channel = channel_registry.get_active_channel("whatsapp")
    await channel.send_text("+5511999998888", "Hello")

    # Health check all channels:
    statuses = await channel_registry.health_check_all()
"""

from __future__ import annotations

import structlog

from app.domain.ports.message_channel import ChannelHealth, IMessageChannel

log = structlog.get_logger()


class ChannelRegistry:
    """Singleton registry for all messaging channel adapters."""

    def __init__(self) -> None:
        # key = "{channel_type}:{provider_name}" e.g. "whatsapp:zapi"
        self._channels: dict[str, IMessageChannel] = {}

    def register(self, channel: IMessageChannel) -> None:
        key = f"{channel.channel_type}:{channel.provider_name}"
        self._channels[key] = channel
        log.info(
            "channel_registered",
            channel_type=channel.channel_type,
            provider=channel.provider_name,
            display_name=channel.display_name,
        )

    def unregister(self, channel_type: str, provider_name: str) -> None:
        key = f"{channel_type}:{provider_name}"
        self._channels.pop(key, None)

    def get_channel(self, channel_type: str, provider_name: str) -> IMessageChannel | None:
        return self._channels.get(f"{channel_type}:{provider_name}")

    def get_channels_by_type(self, channel_type: str) -> list[IMessageChannel]:
        return [ch for key, ch in self._channels.items() if key.startswith(f"{channel_type}:")]

    def get_all_channels(self) -> list[IMessageChannel]:
        return list(self._channels.values())

    def list_available_types(self) -> list[str]:
        """Return unique channel types that have at least one adapter registered."""
        return list({ch.channel_type for ch in self._channels.values()})

    async def health_check_all(self) -> list[ChannelHealth]:
        results: list[ChannelHealth] = []
        for ch in self._channels.values():
            try:
                result = await ch.health_check()
                results.append(result)
            except Exception as exc:
                from datetime import datetime, timezone

                results.append(ChannelHealth(
                    channel_type=ch.channel_type,
                    provider=ch.provider_name,
                    is_healthy=False,
                    latency_ms=None,
                    message=str(exc),
                    checked_at=datetime.now(timezone.utc),
                ))
        return results

    async def health_check_type(self, channel_type: str) -> list[ChannelHealth]:
        channels = self.get_channels_by_type(channel_type)
        results: list[ChannelHealth] = []
        for ch in channels:
            try:
                results.append(await ch.health_check())
            except Exception as exc:
                from datetime import datetime, timezone

                results.append(ChannelHealth(
                    channel_type=ch.channel_type,
                    provider=ch.provider_name,
                    is_healthy=False,
                    latency_ms=None,
                    message=str(exc),
                    checked_at=datetime.now(timezone.utc),
                ))
        return results

    def clear(self) -> None:
        """Clear all channels — for testing."""
        self._channels.clear()


# Singleton instance
channel_registry = ChannelRegistry()
