"""Vehicle module event hooks — handles domain events for the vehicle vertical."""

from __future__ import annotations

import structlog

from app.core.assets.module_interface import Action
from app.core.events.domain_events import (
    InstallmentOverdueEvent,
    InstallmentPaidEvent,
)

log = structlog.get_logger()

# Default policy thresholds
DEFAULT_MIN_DAYS_OVERDUE = 5
DEFAULT_MIN_SCORE = 0  # block regardless of score by default


class VehicleHooks:
    """Event handler implementations for the vehicle module."""

    def on_installment_overdue(
        self, event: InstallmentOverdueEvent, policy: dict
    ) -> list[Action]:
        """Check overdue policy and dispatch GPS block if criteria met.

        Policy keys:
          - min_days_overdue (int): minimum days before auto-block (default 5)
          - min_score (int): customer score floor; block only if score <= this (default 0 = always)
        """
        min_days = policy.get("min_days_overdue", DEFAULT_MIN_DAYS_OVERDUE)
        min_score = policy.get("min_score", DEFAULT_MIN_SCORE)

        if event.days_overdue < min_days:
            log.info(
                "vehicle_hook_skip_block",
                reason="days_below_threshold",
                days=event.days_overdue,
                threshold=min_days,
            )
            return []

        # If min_score > 0 the caller should provide customer score in policy
        customer_score = policy.get("customer_score", 0)
        if min_score > 0 and customer_score > min_score:
            log.info(
                "vehicle_hook_skip_block",
                reason="score_above_threshold",
                score=customer_score,
                threshold=min_score,
            )
            return []

        log.info(
            "vehicle_hook_dispatch_block",
            installment_id=event.installment_id,
            customer_id=event.customer_id,
            days_overdue=event.days_overdue,
        )

        return [
            Action(
                name="block_vehicle",
                payload={
                    "customer_id": event.customer_id,
                    "contract_id": event.contract_id,
                    "installment_id": event.installment_id,
                    "reason": f"overdue_{event.days_overdue}_days",
                },
            )
        ]

    def on_installment_paid(self, event: InstallmentPaidEvent) -> list[Action]:
        """Auto-unblock vehicle when overdue installment is paid.

        In a full implementation, this would check if ALL overdue installments
        are cleared before unblocking. For now, it issues an unblock action
        that the orchestrator should validate.
        """
        log.info(
            "vehicle_hook_dispatch_unblock",
            installment_id=event.installment_id,
            customer_id=event.customer_id,
        )

        return [
            Action(
                name="unblock_vehicle",
                payload={
                    "customer_id": event.customer_id,
                    "contract_id": event.contract_id,
                    "installment_id": event.installment_id,
                    "reason": "installment_paid",
                },
            )
        ]
