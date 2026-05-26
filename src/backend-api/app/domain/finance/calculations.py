"""Updated-value calculation for receivables.

Computes interest, fines, and early-payment discounts.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

TWO_PLACES = Decimal("0.01")


def compute_updated_value(
    original_value: Decimal,
    due_date: date,
    payment_date: date | None = None,
    interest_rate_monthly: Decimal = Decimal("0.02"),
    fine_rate: Decimal = Decimal("0.02"),
    discount_early_days: int = 0,
    discount_rate: Decimal = Decimal("0"),
) -> dict:
    """Compute the updated value of a receivable on a given date.

    Returns a dict with: original, interest, fine, discount, total.
    """
    on_date = payment_date or date.today()

    interest = Decimal("0")
    fine = Decimal("0")
    discount = Decimal("0")

    if on_date > due_date:
        # Overdue: apply fine + daily pro-rata interest
        days_overdue = (on_date - due_date).days
        fine = (original_value * fine_rate).quantize(TWO_PLACES, ROUND_HALF_UP)
        # Daily interest = monthly rate / 30
        daily_rate = interest_rate_monthly / 30
        interest = (original_value * daily_rate * days_overdue).quantize(TWO_PLACES, ROUND_HALF_UP)
    elif on_date < due_date and discount_early_days > 0 and discount_rate > 0:
        days_early = (due_date - on_date).days
        if days_early <= discount_early_days:
            discount = (original_value * discount_rate).quantize(TWO_PLACES, ROUND_HALF_UP)

    total = original_value + interest + fine - discount

    return {
        "original": original_value,
        "interest": interest,
        "fine": fine,
        "discount": discount,
        "total": total,
    }
