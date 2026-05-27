from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from fastapi import APIRouter

from app.core.events.domain_events import (
    ContractCreatedEvent,
    ContractTerminatedEvent,
    DomainEvent,
    InstallmentOverdueEvent,
    InstallmentPaidEvent,
    PaymentPartiallyReceivedEvent,
    ReconciliationCompletedEvent,
)


@dataclass
class Action:
    name: str
    payload: dict[str, Any]

    def execute(self) -> None:
        pass


@dataclass
class FieldDefinition:
    name: str
    field_type: str
    label: str
    required: bool = False


@dataclass
class Widget:
    widget_id: str
    title: str
    widget_type: str
    config: dict[str, Any] | None = None


@dataclass
class AgentTool:
    tool_id: str
    name: str
    description: str
    required_permissions: list[str]
    handler: Any = None


@dataclass
class ScoreFactor:
    factor_id: str
    name: str
    weight: float
    description: str = ""


@runtime_checkable
class IAssetModule(Protocol):
    @property
    def asset_type(self) -> str: ...

    @property
    def display_name(self) -> str: ...

    @property
    def icon(self) -> str: ...

    def handles_event(self, event_type: type[DomainEvent]) -> bool: ...

    def on_contract_created(self, event: ContractCreatedEvent) -> list[Action]: ...

    def on_contract_terminated(self, event: ContractTerminatedEvent) -> list[Action]: ...

    def on_installment_overdue(self, event: InstallmentOverdueEvent, policy: dict) -> list[Action]: ...

    def on_installment_paid(self, event: InstallmentPaidEvent) -> list[Action]: ...

    def on_partial_payment(self, event: PaymentPartiallyReceivedEvent) -> list[Action]: ...

    def on_reconciliation_completed(self, event: ReconciliationCompletedEvent) -> list[Action]: ...

    def get_asset_schema(self) -> list[FieldDefinition]: ...

    def get_asset_details(self, asset_id: str) -> dict: ...

    def get_asset_financials(self, asset_id: str) -> dict: ...

    def get_dashboard_widgets(self) -> list[Widget]: ...

    def get_report_dimensions(self) -> list[str]: ...

    def get_agent_tools(self) -> list[AgentTool]: ...

    def get_score_factors(self) -> list[ScoreFactor]: ...

    def get_custom_routes(self) -> list[APIRouter]: ...


# Alias PT-BR (Story 13.18) — preferencial pra código novo do Epic 13 em diante.
# Mesma classe Protocol; consumidores podem importar qualquer um dos dois nomes.
# Métodos individuais (on_*, get_*) mantêm nomes em inglês — rename é refactor
# cross-cutting documentado como débito na Story 13.1.
IModuloVertical = IAssetModule
