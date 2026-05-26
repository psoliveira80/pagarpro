"""FIPE service with Redis caching (30-day TTL)."""

from __future__ import annotations

import json
from typing import Any

import structlog
from redis.asyncio import Redis

from app.modules.vehicles.ports.fipe_provider import IFipeProvider

log = structlog.get_logger()

_CACHE_TTL = 60 * 60 * 24 * 30  # 30 days in seconds
_CACHE_PREFIX = "fipe:"


class FipeService:
    """Service that wraps a FIPE provider with Redis caching."""

    def __init__(self, provider: IFipeProvider, redis: Redis) -> None:
        self._provider = provider
        self._redis = redis

    async def list_brands(self, vehicle_type: str = "carros") -> list[dict[str, Any]]:
        key = f"{_CACHE_PREFIX}brands:{vehicle_type}"
        return await self._cached(key, self._provider.list_brands, vehicle_type)

    async def list_models(self, vehicle_type: str, brand_code: str) -> list[dict[str, Any]]:
        key = f"{_CACHE_PREFIX}models:{vehicle_type}:{brand_code}"
        return await self._cached(key, self._provider.list_models, vehicle_type, brand_code)

    async def list_years(
        self, vehicle_type: str, brand_code: str, model_code: str
    ) -> list[dict[str, Any]]:
        key = f"{_CACHE_PREFIX}years:{vehicle_type}:{brand_code}:{model_code}"
        return await self._cached(
            key, self._provider.list_years, vehicle_type, brand_code, model_code
        )

    async def get_price(
        self, vehicle_type: str, brand_code: str, model_code: str, year_code: str
    ) -> dict[str, Any]:
        key = f"{_CACHE_PREFIX}price:{vehicle_type}:{brand_code}:{model_code}:{year_code}"
        return await self._cached(
            key, self._provider.get_price, vehicle_type, brand_code, model_code, year_code
        )

    async def _cached(self, key: str, func: Any, *args: Any) -> Any:
        try:
            raw = await self._redis.get(key)
            if raw is not None:
                log.debug("fipe_cache_hit", key=key)
                return json.loads(raw)
        except Exception:
            log.warning("fipe_cache_read_error", key=key, exc_info=True)

        result = await func(*args)

        try:
            await self._redis.setex(key, _CACHE_TTL, json.dumps(result, default=str))
        except Exception:
            log.warning("fipe_cache_write_error", key=key, exc_info=True)

        return result
