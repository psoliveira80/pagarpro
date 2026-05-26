"""Port: GPS tracker gateway protocol."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ITrackerGateway(Protocol):
    async def get_position(self, device_id: str, config: dict[str, Any]) -> dict[str, Any]:
        """Get latest position for a device."""
        ...

    async def block(self, device_id: str, config: dict[str, Any]) -> bool:
        """Send block command to tracker. Return True if successful."""
        ...

    async def unblock(self, device_id: str, config: dict[str, Any]) -> bool:
        """Send unblock command to tracker. Return True if successful."""
        ...

    async def health_check(self, config: dict[str, Any]) -> bool:
        """Check if the tracker provider API is reachable."""
        ...
