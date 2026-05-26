"""Pure functions for computing installment schedules.

Supports:
  - Frequencies: monthly, biweekly, weekly, custom_dates
  - Amortization methods: price (French / PMT), sac (constant amortization), fixed (equal values)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class InstallmentPreview:
    number: int
    due_date: date
    principal: Decimal
    interest: Decimal
    value: Decimal  # principal + interest


def _add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                       31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


def _generate_due_dates(
    start_date: date,
    num_installments: int,
    frequency: str,
    custom_dates: list[date] | None = None,
) -> list[date]:
    if frequency == "custom_dates":
        if not custom_dates or len(custom_dates) < num_installments:
            raise ValueError("custom_dates must contain at least num_installments dates")
        return sorted(custom_dates[:num_installments])

    dates: list[date] = []
    for i in range(num_installments):
        if frequency == "monthly":
            dates.append(_add_months(start_date, i + 1))
        elif frequency == "biweekly":
            dates.append(start_date + timedelta(weeks=2 * (i + 1)))
        elif frequency == "weekly":
            dates.append(start_date + timedelta(weeks=i + 1))
        else:
            raise ValueError(f"Unknown frequency: {frequency}")
    return dates


def calculate_schedule(
    total_value: Decimal,
    num_installments: int,
    start_date: date,
    frequency: str = "monthly",
    interest_rate: Decimal = Decimal("0"),
    method: str = "fixed",
    custom_dates: list[date] | None = None,
) -> list[InstallmentPreview]:
    """Return a list of InstallmentPreview for the given parameters.

    Args:
        total_value: The principal (total loan / contract value).
        num_installments: Number of installments to generate.
        start_date: The contract start date — first installment is one period after.
        frequency: monthly | biweekly | weekly | custom_dates.
        interest_rate: Monthly interest rate as a decimal (e.g. 0.02 = 2%).
        method: price | sac | fixed.
        custom_dates: Required when frequency == "custom_dates".
    """
    if num_installments <= 0:
        raise ValueError("num_installments must be > 0")
    if total_value <= 0:
        raise ValueError("total_value must be > 0")

    due_dates = _generate_due_dates(start_date, num_installments, frequency, custom_dates)
    n = num_installments
    rate = interest_rate
    pv = total_value

    if method == "fixed":
        # Simple equal division — no interest
        base = (pv / n).quantize(TWO_PLACES, ROUND_HALF_UP)
        remainder = pv - base * n
        installments: list[InstallmentPreview] = []
        for i, dd in enumerate(due_dates):
            val = base + (remainder if i == n - 1 else Decimal("0"))
            installments.append(InstallmentPreview(
                number=i + 1, due_date=dd, principal=val,
                interest=Decimal("0"), value=val,
            ))
        return installments

    if method == "price":
        # French amortization (PMT)
        if rate == 0:
            pmt = (pv / n).quantize(TWO_PLACES, ROUND_HALF_UP)
        else:
            r = rate
            pmt = (pv * r * (1 + r) ** n / ((1 + r) ** n - 1)).quantize(TWO_PLACES, ROUND_HALF_UP)

        balance = pv
        installments = []
        for i, dd in enumerate(due_dates):
            interest_amount = (balance * rate).quantize(TWO_PLACES, ROUND_HALF_UP)
            principal_amount = pmt - interest_amount
            if i == n - 1:
                # Last installment: settle remaining balance
                principal_amount = balance
                interest_amount = (balance * rate).quantize(TWO_PLACES, ROUND_HALF_UP)
                pmt = principal_amount + interest_amount

            balance -= principal_amount
            installments.append(InstallmentPreview(
                number=i + 1, due_date=dd,
                principal=principal_amount,
                interest=interest_amount,
                value=pmt,
            ))
        return installments

    if method == "sac":
        # Constant amortization
        amort = (pv / n).quantize(TWO_PLACES, ROUND_HALF_UP)
        balance = pv
        installments = []
        for i, dd in enumerate(due_dates):
            interest_amount = (balance * rate).quantize(TWO_PLACES, ROUND_HALF_UP)
            if i == n - 1:
                amort = balance  # settle remainder
            val = amort + interest_amount
            balance -= amort
            installments.append(InstallmentPreview(
                number=i + 1, due_date=dd,
                principal=amort,
                interest=interest_amount,
                value=val,
            ))
        return installments

    raise ValueError(f"Unknown method: {method}")
