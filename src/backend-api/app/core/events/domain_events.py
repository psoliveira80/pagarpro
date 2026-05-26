from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass(frozen=True)
class DomainEvent:
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    asset_type: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["event_id"] = str(d["event_id"])
        d["occurred_at"] = d["occurred_at"].isoformat()
        d["_type"] = type(self).__name__
        return d

    @classmethod
    def from_dict(cls, data: dict) -> DomainEvent:
        event_type = data.pop("_type", None)
        klass = _EVENT_REGISTRY.get(event_type, cls)
        data["event_id"] = UUID(data["event_id"])
        data["occurred_at"] = datetime.fromisoformat(data["occurred_at"])
        return klass(**data)


@dataclass(frozen=True)
class ContractCreatedEvent(DomainEvent):
    contract_id: str = ""
    customer_id: str = ""


@dataclass(frozen=True)
class ContractTerminatedEvent(DomainEvent):
    contract_id: str = ""
    customer_id: str = ""
    reason: str = ""


@dataclass(frozen=True)
class InstallmentOverdueEvent(DomainEvent):
    installment_id: str = ""
    contract_id: str = ""
    customer_id: str = ""
    days_overdue: int = 0
    amount_due: float = 0.0


@dataclass(frozen=True)
class InstallmentPaidEvent(DomainEvent):
    installment_id: str = ""
    contract_id: str = ""
    customer_id: str = ""
    amount_paid: float = 0.0


@dataclass(frozen=True)
class PaymentPartiallyReceivedEvent(DomainEvent):
    installment_id: str = ""
    contract_id: str = ""
    amount_received: float = 0.0
    amount_remaining: float = 0.0


@dataclass(frozen=True)
class ReconciliationCompletedEvent(DomainEvent):
    bank_account_id: str = ""
    matched_count: int = 0
    unmatched_count: int = 0


@dataclass(frozen=True)
class CustomerScoreChangedEvent(DomainEvent):
    customer_id: str = ""
    old_score: float = 0.0
    new_score: float = 0.0


_EVENT_REGISTRY: dict[str, type[DomainEvent]] = {
    cls.__name__: cls
    for cls in [
        ContractCreatedEvent,
        ContractTerminatedEvent,
        InstallmentOverdueEvent,
        InstallmentPaidEvent,
        PaymentPartiallyReceivedEvent,
        ReconciliationCompletedEvent,
        CustomerScoreChangedEvent,
    ]
}
