"""No-op payment gateway adapter.

Default adapter that always returns success. Used as a placeholder
until a real payment gateway integration is configured.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import structlog

log = structlog.get_logger()


class NoOpPaymentGateway:
    """No-op payment gateway that always succeeds."""

    async def create_charge(
        self,
        amount: Decimal,
        description: str,
        customer_id: str,
        metadata: dict | None = None,
    ) -> dict:
        charge_id = str(uuid4())
        log.info(
            "noop_gateway_create_charge",
            charge_id=charge_id,
            amount=str(amount),
            customer_id=customer_id,
        )
        return {
            "id": charge_id,
            "status": "approved",
            "provider_ref": f"noop-{charge_id[:8]}",
        }

    async def get_charge_status(self, charge_id: str) -> dict:
        log.info("noop_gateway_get_charge_status", charge_id=charge_id)
        return {
            "id": charge_id,
            "status": "approved",
            "paid_at": datetime.now(timezone.utc).isoformat(),
        }

    async def refund(self, charge_id: str, amount: Decimal | None = None) -> dict:
        refund_id = str(uuid4())
        log.info(
            "noop_gateway_refund",
            charge_id=charge_id,
            refund_id=refund_id,
            amount=str(amount) if amount else "full",
        )
        return {
            "id": refund_id,
            "status": "refunded",
            "refunded_amount": str(amount) if amount else "full",
        }
