from __future__ import annotations

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


# =============================================================================
# Domain Events — Story 13.1
# =============================================================================
# NOMES EN MANTIDOS COMO CANONICAL para preservar compatibilidade de
# serialização (eventos persistidos em Redis Streams / audit_log usam
# `type(self).__name__` no campo `_type`). Trocar canonical agora invalidaria
# eventos antigos no replay.
#
# NOMES PT-BR ficam como aliases para uso preferencial em código novo.
# Registry aceita ambos os nomes em `from_dict`, garantindo que eventos
# emitidos com qualquer convenção possam ser deserializados.
#
# Migração completa para PT-BR canonical (com replay de eventos antigos)
# fica documentada como débito técnico — ver `docs/glossario-ptbr.md` seção
# "Domínio Financeiro — Tabela de Renames EN→PT-BR".

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


# Aliases PT-BR (Story 13.1) — preferenciais para código novo. Mesma classe,
# mesma serialização — apenas alternam o ponto de import.
EventoContratoAtivado = ContractCreatedEvent
EventoContratoEncerrado = ContractTerminatedEvent
EventoTituloVencido = InstallmentOverdueEvent
EventoTituloPago = InstallmentPaidEvent
EventoPagamentoParcialRecebido = PaymentPartiallyReceivedEvent
EventoConciliacaoCompletada = ReconciliationCompletedEvent
EventoScoreClienteAlterado = CustomerScoreChangedEvent


# Registry aceita ambos os nomes para `from_dict` funcionar com eventos
# legados (`_type='ContractCreatedEvent'`) e eventos novos emitidos com
# nome PT-BR explícito.
_EVENT_REGISTRY: dict[str, type[DomainEvent]] = {
    # EN canonical (forma persistida em Redis Streams / audit log)
    "ContractCreatedEvent": ContractCreatedEvent,
    "ContractTerminatedEvent": ContractTerminatedEvent,
    "InstallmentOverdueEvent": InstallmentOverdueEvent,
    "InstallmentPaidEvent": InstallmentPaidEvent,
    "PaymentPartiallyReceivedEvent": PaymentPartiallyReceivedEvent,
    "ReconciliationCompletedEvent": ReconciliationCompletedEvent,
    "CustomerScoreChangedEvent": CustomerScoreChangedEvent,
    # PT-BR aliases (aceitos para retro-compat se algum código novo emitir com nome PT-BR)
    "EventoContratoAtivado": ContractCreatedEvent,
    "EventoContratoEncerrado": ContractTerminatedEvent,
    "EventoTituloVencido": InstallmentOverdueEvent,
    "EventoTituloPago": InstallmentPaidEvent,
    "EventoPagamentoParcialRecebido": PaymentPartiallyReceivedEvent,
    "EventoConciliacaoCompletada": ReconciliationCompletedEvent,
    "EventoScoreClienteAlterado": CustomerScoreChangedEvent,
}
