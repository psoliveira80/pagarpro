"""Port for monetary correction index providers (IGPM, IPCA, INPC, ...)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Protocol, runtime_checkable

CORRECTION_INDICES = ("igpm", "ipca", "inpc")


class CorrectionIndexUnavailableError(Exception):
    """Raised when neither the provider nor the cache can supply a rate."""


@runtime_checkable
class ICorrectionIndexProvider(Protocol):
    """Interface for monetary correction index providers.

    A rate of `0.53` means a 0.53% monthly inflation/correction; callers apply
    it as `base * (1 + rate / 100)`.
    """

    async def get_current_rate(self, index: str, reference_date: date) -> Decimal:
        """Return the most recent monthly correction rate for the given index.

        Args:
            index: one of ``CORRECTION_INDICES`` (case-insensitive).
            reference_date: date used to choose the cache bucket (year/month).

        Returns:
            Percentage rate as a ``Decimal`` (e.g. ``Decimal("0.53")`` = 0.53%).

        Raises:
            ValueError: if ``index`` is not recognized.
            CorrectionIndexUnavailableError: if the live provider is down and no
                cached value is available.
        """
        ...
