"""BCB (Banco Central do Brasil) correction index adapter.

Public API, no auth. Series codes:
- IGPM = 189
- IPCA = 433
- INPC = 188

Endpoint: https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados/ultimos/1?formato=json
Response shape: [{"data": "DD/MM/YYYY", "valor": "0.53"}]
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
import structlog
from redis.asyncio import Redis

from app.domain.ports.correction_index_provider import (
    CORRECTION_INDICES,
    CorrectionIndexUnavailableError,
)

log = structlog.get_logger()

_BASE_URL = "https://api.bcb.gov.br/dados/serie"

SERIES_BY_INDEX: dict[str, int] = {
    "igpm": 189,
    "ipca": 433,
    "inpc": 188,
}

# Cache for 30 days — correction indexes are published monthly.
_CACHE_TTL_SECONDS = 30 * 24 * 60 * 60


def _cache_key(index: str, reference_date: date) -> str:
    return f"correction_index:{index}:{reference_date.strftime('%Y-%m')}"


class BcbCorrectionAdapter:
    """Fetches monthly correction rates from BCB SGS API with Redis caching."""

    def __init__(
        self,
        redis: Redis,
        base_url: str = _BASE_URL,
        timeout: float = 30.0,
    ) -> None:
        self._redis = redis
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def get_current_rate(self, index: str, reference_date: date) -> Decimal:
        normalized = index.lower()
        if normalized not in CORRECTION_INDICES:
            raise ValueError(
                f"Índice de correção desconhecido: {index!r}. "
                f"Valores aceitos: {', '.join(CORRECTION_INDICES)}."
            )

        cache_key = _cache_key(normalized, reference_date)
        try:
            rate = await self._fetch_from_bcb(normalized)
        except (httpx.HTTPError, ValueError) as exc:
            log.warning(
                "bcb_api_unavailable",
                index=normalized,
                error=str(exc),
            )
            cached = await self._read_cache(cache_key)
            if cached is None:
                # Try the previous month's bucket as a last resort.
                prev_key = _cache_key(
                    normalized, _previous_month(reference_date)
                )
                cached = await self._read_cache(prev_key)
            if cached is None:
                raise CorrectionIndexUnavailableError(
                    f"API BCB indisponível e nenhum valor em cache para {normalized}."
                ) from exc
            log.info(
                "bcb_cache_fallback", index=normalized, cached_rate=str(cached)
            )
            return cached

        await self._write_cache(cache_key, rate)
        return rate

    async def _fetch_from_bcb(self, index: str) -> Decimal:
        serie = SERIES_BY_INDEX[index]
        url = (
            f"{self._base_url}/bcdata.sgs.{serie}/dados/ultimos/1?formato=json"
        )
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            log.debug("bcb_api_request", url=url, index=index)
            resp = await client.get(url)
            resp.raise_for_status()
            payload = resp.json()

        return _parse_payload(payload, index)

    async def _read_cache(self, key: str) -> Decimal | None:
        raw = await self._redis.get(key)
        if raw is None:
            return None
        try:
            return Decimal(raw.decode() if isinstance(raw, bytes) else raw)
        except InvalidOperation:
            log.warning("correction_index_cache_corrupt", key=key, raw=raw)
            return None

    async def _write_cache(self, key: str, value: Decimal) -> None:
        await self._redis.set(key, str(value), ex=_CACHE_TTL_SECONDS)


def _parse_payload(payload: Any, index: str) -> Decimal:
    if not isinstance(payload, list) or not payload:
        raise ValueError(f"Resposta BCB vazia para {index}.")
    entry = payload[0]
    if not isinstance(entry, dict) or "valor" not in entry:
        raise ValueError(f"Resposta BCB inválida para {index}: {entry!r}.")
    try:
        return Decimal(str(entry["valor"]).replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError(
            f"Valor inválido na resposta BCB para {index}: {entry['valor']!r}."
        ) from exc


def _previous_month(reference: date) -> date:
    if reference.month == 1:
        return date(reference.year - 1, 12, 1)
    return date(reference.year, reference.month - 1, 1)
