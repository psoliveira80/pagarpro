"""FIPE provider adapter using Parallelum API (fipe.parallelum.com.br)."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

log = structlog.get_logger()

_BASE_URL = "https://fipe.parallelum.com.br/api/v2"

_VEHICLE_TYPE_MAP = {
    "carros": "cars",
    "motos": "motorcycles",
    "caminhoes": "trucks",
}


class ParallelumFipeAdapter:
    """Adapter that fetches FIPE data from Parallelum API."""

    def __init__(self, base_url: str = _BASE_URL, timeout: float = 15.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def list_brands(self, vehicle_type: str = "carros") -> list[dict[str, Any]]:
        vt = _VEHICLE_TYPE_MAP.get(vehicle_type, vehicle_type)
        url = f"{self._base_url}/{vt}/brands"
        data = await self._get(url)
        # Normalize to same format as BrasilAPI: {valor/code, nome/name}
        return [{"code": str(b["code"]), "name": b["name"]} for b in data]

    async def list_models(self, vehicle_type: str, brand_code: str) -> list[dict[str, Any]]:
        vt = _VEHICLE_TYPE_MAP.get(vehicle_type, vehicle_type)
        url = f"{self._base_url}/{vt}/brands/{brand_code}/models"
        data = await self._get(url)
        return [{"code": str(m["code"]), "name": m["name"]} for m in data]

    async def list_years(self, vehicle_type: str, brand_code: str, model_code: str) -> list[dict[str, Any]]:
        vt = _VEHICLE_TYPE_MAP.get(vehicle_type, vehicle_type)
        url = f"{self._base_url}/{vt}/brands/{brand_code}/models/{model_code}/years"
        data = await self._get(url)
        return [{"code": y["code"], "name": y["name"]} for y in data]

    async def get_price(self, vehicle_type: str, brand_code: str, model_code: str, year_code: str) -> dict[str, Any]:
        vt = _VEHICLE_TYPE_MAP.get(vehicle_type, vehicle_type)
        url = f"{self._base_url}/{vt}/brands/{brand_code}/models/{model_code}/years/{year_code}"
        data = await self._get(url)
        return {
            "fipe_code": data.get("codeFipe", ""),
            "value": data.get("price", ""),
            "brand": data.get("brand", ""),
            "model": data.get("model", ""),
            "model_year": data.get("modelYear", ""),
            "fuel": data.get("fuel", ""),
            "reference_month": data.get("referenceMonth", ""),
            "vehicle_type": vehicle_type,
        }

    async def _get(self, url: str) -> Any:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                log.debug("parallelum_fipe_request", url=url)
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as exc:
            log.error("parallelum_fipe_error", url=url, status=exc.response.status_code)
            raise ValueError(f"Parallelum FIPE API retornou erro {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            log.error("parallelum_fipe_connection_error", url=url, error=str(exc))
            raise ValueError("Não foi possível conectar à API Parallelum FIPE") from exc
