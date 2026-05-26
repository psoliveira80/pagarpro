"""Generic REST-based GPS tracker adapter.

Configurable via JSONB stored in TrackerDevice.config. Expected keys:
  - base_url: str — the tracker API base URL
  - api_key: str — authentication key
  - headers: dict — optional extra headers
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

log = structlog.get_logger()


class GenericRestTrackerAdapter:
    """Adapter that talks to any REST-based tracker provider."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def _build_headers(self, config: dict[str, Any]) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key := config.get("api_key"):
            headers["Authorization"] = f"Bearer {api_key}"
        if extra := config.get("headers"):
            headers.update(extra)
        return headers

    def _base_url(self, config: dict[str, Any]) -> str:
        url = config.get("base_url", "")
        if not url:
            raise ValueError("Tracker config missing base_url")
        return url.rstrip("/")

    async def get_position(self, device_id: str, config: dict[str, Any]) -> dict[str, Any]:
        base = self._base_url(config)
        url = f"{base}/devices/{device_id}/position"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, headers=self._build_headers(config))
            resp.raise_for_status()
            return resp.json()

    async def block(self, device_id: str, config: dict[str, Any]) -> bool:
        base = self._base_url(config)
        url = f"{base}/devices/{device_id}/block"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, headers=self._build_headers(config))
            resp.raise_for_status()
            log.info("tracker_block_sent", device_id=device_id)
            return True

    async def unblock(self, device_id: str, config: dict[str, Any]) -> bool:
        base = self._base_url(config)
        url = f"{base}/devices/{device_id}/unblock"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, headers=self._build_headers(config))
            resp.raise_for_status()
            log.info("tracker_unblock_sent", device_id=device_id)
            return True

    async def health_check(self, config: dict[str, Any]) -> bool:
        base = self._base_url(config)
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(f"{base}/health", headers=self._build_headers(config))
                return resp.status_code < 500
        except Exception:
            return False
