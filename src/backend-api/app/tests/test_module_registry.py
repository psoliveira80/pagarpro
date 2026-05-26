import pytest

from app.core.assets.module_interface import (
    Action,
    AgentTool,
    FieldDefinition,
    IAssetModule,
    ScoreFactor,
    Widget,
)
from app.core.assets.registry import (
    clear_registry,
    get_module,
    get_tools_for_context,
    list_modules,
    register_module,
)
from app.core.events.domain_events import (
    ContractCreatedEvent,
    ContractTerminatedEvent,
    DomainEvent,
    InstallmentOverdueEvent,
    InstallmentPaidEvent,
    PaymentPartiallyReceivedEvent,
    ReconciliationCompletedEvent,
)


class MockModule:
    asset_type = "test_vehicles"
    display_name = "Test Vehicles"
    icon = "heroTruck"

    def __init__(self) -> None:
        self.events_received: list[DomainEvent] = []

    def handles_event(self, event_type: type[DomainEvent]) -> bool:
        return event_type in (InstallmentOverdueEvent, InstallmentPaidEvent)

    def on_contract_created(self, event: ContractCreatedEvent) -> list[Action]:
        self.events_received.append(event)
        return []

    def on_contract_terminated(self, event: ContractTerminatedEvent) -> list[Action]:
        self.events_received.append(event)
        return []

    def on_installment_overdue(self, event: InstallmentOverdueEvent, policy: dict) -> list[Action]:
        self.events_received.append(event)
        return [Action(name="block_vehicle", payload={"reason": "overdue"})]

    def on_installment_paid(self, event: InstallmentPaidEvent) -> list[Action]:
        self.events_received.append(event)
        return [Action(name="unblock_vehicle", payload={})]

    def on_partial_payment(self, event: PaymentPartiallyReceivedEvent) -> list[Action]:
        return []

    def on_reconciliation_completed(self, event: ReconciliationCompletedEvent) -> list[Action]:
        return []

    def get_asset_schema(self) -> list[FieldDefinition]:
        return [FieldDefinition(name="plate", field_type="string", label="Placa", required=True)]

    def get_asset_details(self, asset_id: str) -> dict:
        return {"id": asset_id, "plate": "ABC-1234"}

    def get_asset_financials(self, asset_id: str) -> dict:
        return {"total_revenue": 1000.0}

    def get_dashboard_widgets(self) -> list[Widget]:
        return [Widget(widget_id="fleet_map", title="Mapa", widget_type="map")]

    def get_report_dimensions(self) -> list[str]:
        return ["vehicle_model", "vehicle_year"]

    def get_agent_tools(self) -> list[AgentTool]:
        return [
            AgentTool(
                tool_id="check_vehicle",
                name="Check Vehicle",
                description="Check vehicle status",
                required_permissions=["vehicles.read"],
            ),
        ]

    def get_score_factors(self) -> list[ScoreFactor]:
        return [ScoreFactor(factor_id="maintenance", name="Maintenance", weight=0.3)]

    def get_custom_routes(self) -> list:
        return []


@pytest.fixture(autouse=True)
def clean_registry():
    clear_registry()
    yield
    clear_registry()


def test_register_and_get_module():
    mod = MockModule()
    register_module(mod)
    assert get_module("test_vehicles") is mod
    assert get_module("nonexistent") is None


def test_list_modules():
    mod = MockModule()
    register_module(mod)
    modules = list_modules()
    assert len(modules) == 1
    assert modules[0].asset_type == "test_vehicles"


def test_handles_event():
    mod = MockModule()
    assert mod.handles_event(InstallmentOverdueEvent) is True
    assert mod.handles_event(ContractCreatedEvent) is False


def test_get_tools_with_permissions():
    mod = MockModule()
    register_module(mod)
    tools = get_tools_for_context(["vehicles.read"])
    assert len(tools) == 1
    assert tools[0].tool_id == "check_vehicle"


def test_get_tools_without_permissions():
    mod = MockModule()
    register_module(mod)
    tools = get_tools_for_context(["users.read"])
    assert len(tools) == 0


def test_protocol_check():
    mod = MockModule()
    assert isinstance(mod, IAssetModule)


def test_domain_event_serialization():
    event = InstallmentOverdueEvent(
        asset_type="test_vehicles",
        installment_id="inst-1",
        contract_id="contract-1",
        customer_id="cust-1",
        days_overdue=15,
        amount_due=500.0,
    )
    d = event.to_dict()
    assert d["_type"] == "InstallmentOverdueEvent"
    assert d["days_overdue"] == 15

    restored = DomainEvent.from_dict(d.copy())
    assert isinstance(restored, InstallmentOverdueEvent)
    assert restored.event_id == event.event_id
    assert restored.days_overdue == 15
