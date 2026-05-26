"""Compute final balance for contract termination."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class TerminationSummary:
    open_installments_count: int
    open_installments_total: Decimal
    paid_total: Decimal
    fine_amount: Decimal
    final_balance: Decimal  # open_total - fine  (amount to refund/forgive)


def compute_termination(
    installments: list[dict],
    fine_amount: Decimal = Decimal("0"),
) -> TerminationSummary:
    """Compute termination summary from a list of installment dicts.

    Each dict must have keys: status, current_value, paid_value.
    """
    open_total = Decimal("0")
    paid_total = Decimal("0")
    open_count = 0

    for inst in installments:
        status = inst["status"]
        if status in ("em_aberto", "vencido"):
            open_total += Decimal(str(inst["current_value"]))
            open_count += 1
        if status in ("pago", "pago_parcial", "pago_aguardando_verificacao"):
            paid_total += Decimal(str(inst["paid_value"]))

    final_balance = open_total - fine_amount

    return TerminationSummary(
        open_installments_count=open_count,
        open_installments_total=open_total,
        paid_total=paid_total,
        fine_amount=fine_amount,
        final_balance=final_balance,
    )
