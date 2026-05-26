"""FIPE provider adapter using BrasilAPI."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

log = structlog.get_logger()

_BASE_URL = "https://brasilapi.com.br/api/fipe"


class ApiFipeAdapter:
    """Adapter that fetches FIPE data from BrasilAPI."""

    def __init__(self, base_url: str = _BASE_URL, timeout: float = 15.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def list_brands(self, vehicle_type: str = "carros") -> list[dict[str, Any]]:
        url = f"{self._base_url}/marcas/v1/{vehicle_type}"
        return await self._get(url)

    async def list_models(self, vehicle_type: str, brand_code: str) -> list[dict[str, Any]]:
        # BrasilAPI does not have a direct models endpoint; use FIPE tabela endpoint
        # We use the /tabelas/v1 and /preco/v1 pattern
        # For simplicity, query by brand and return grouped models
        url = f"{self._base_url}/marcas/v1/{vehicle_type}/{brand_code}/modelos"
        return await self._get(url)

    async def list_years(
        self, vehicle_type: str, brand_code: str, model_code: str
    ) -> list[dict[str, Any]]:
        url = f"{self._base_url}/marcas/v1/{vehicle_type}/{brand_code}/modelos/{model_code}/anos"
        return await self._get(url)

    async def get_price(
        self,
        vehicle_type: str,
        brand_code: str,
        model_code: str,
        year_code: str,
    ) -> dict[str, Any]:
        url = f"{self._base_url}/preco/v1/{year_code}"
        return await self._get(url)

    async def _get(self, url: str) -> Any:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                log.debug("fipe_api_request", url=url)
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as exc:
            log.error("fipe_api_error", url=url, status=exc.response.status_code)
            raise ValueError(f"FIPE API retornou erro {exc.response.status_code}. Tente novamente mais tarde.") from exc
        except httpx.RequestError as exc:
            log.error("fipe_api_connection_error", url=url, error=str(exc))
            raise ValueError("Não foi possível conectar à API FIPE. Verifique sua conexão.") from exc
