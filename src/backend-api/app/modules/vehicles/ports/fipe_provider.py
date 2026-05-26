"""Port: FIPE data provider protocol."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class IFipeProvider(Protocol):
    async def list_brands(self, vehicle_type: str = "carros") -> list[dict[str, Any]]:
        """Return list of brands from FIPE table."""
        ...

    async def list_models(self, vehicle_type: str, brand_code: str) -> list[dict[str, Any]]:
        """Return list of models for a given brand."""
        ...

    async def list_years(self, vehicle_type: str, brand_code: str, model_code: str) -> list[dict[str, Any]]:
        """Return list of years for a given brand/model."""
        ...

    async def get_price(
        self, vehicle_type: str, brand_code: str, model_code: str, year_code: str
    ) -> dict[str, Any]:
        """Return FIPE price details for a specific vehicle."""
        ...
