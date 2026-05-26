from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str = "BRL"

    def __post_init__(self) -> None:
        if self.amount.as_tuple().exponent < -2:
            raise ValueError("Money supports max 2 decimal places")

    def __add__(self, other: "Money") -> "Money":
        if other.currency != self.currency:
            raise ValueError("currency mismatch")
        return Money(self.amount + other.amount, self.currency)


@dataclass(frozen=True, slots=True)
class Cpf:
    value: str

    @classmethod
    def parse(cls, raw: str) -> "Cpf":
        digits = "".join(c for c in raw if c.isdigit())
        if len(digits) != 11:
            raise ValueError("CPF must have 11 digits")
        return cls(digits)


@dataclass(frozen=True, slots=True)
class PhoneE164:
    value: str

    def __post_init__(self) -> None:
        if not self.value.startswith("+") or len(self.value) < 10:
            raise ValueError("Phone must be E.164 format")


_VALID_CNH_CATEGORIES = {"A", "B", "C", "D", "E", "AB", "AC", "AD", "AE"}


@dataclass(frozen=True, slots=True)
class Cnh:
    """Brazilian driver's license (CNH) value object.

    Validates:
      - number: exactly 11 digits
      - category: one of A, B, C, D, E, AB, AC, AD, AE
    """

    number: str
    category: str

    @classmethod
    def parse(cls, number: str, category: str) -> "Cnh":
        digits = "".join(c for c in number if c.isdigit())
        if len(digits) != 11:
            raise ValueError("CNH number must have 11 digits")
        cat = category.upper().strip()
        if cat not in _VALID_CNH_CATEGORIES:
            raise ValueError(
                f"CNH category must be one of {sorted(_VALID_CNH_CATEGORIES)}"
            )
        return cls(number=digits, category=cat)
