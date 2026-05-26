"""Port for payment gateway providers."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol, runtime_checkable


@runtime_checkable
class IPaymentGateway(Protocol):
    """Interface for payment gateway integrations."""

    async def create_charge(
        self,
        amount: Decimal,
        description: str,
        customer_id: str,
        metadata: dict | None = None,
    ) -> dict:
        """Create a payment charge.

        Returns a dict with at least: {id, status, provider_ref}.
        """
        ...

    async def get_charge_status(self, charge_id: str) -> dict:
        """Check the status of a charge.

        Returns a dict with at least: {id, status, paid_at}.
        """
        ...

    async def refund(self, charge_id: str, amount: Decimal | None = None) -> dict:
        """Refund a charge (full or partial).

        Returns a dict with at least: {id, status, refunded_amount}.
        """
        ...
