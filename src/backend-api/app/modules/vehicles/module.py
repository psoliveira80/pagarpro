"""VehicleModule — IAssetModule implementation for the vehicle vertical."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.assets.module_interface import (
    Action,
    AgentTool,
    FieldDefinition,
    IAssetModule,
    ScoreFactor,
    Widget,
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
from app.modules.vehicles.hooks import VehicleHooks


class VehicleModule:
    """Concrete module for the vehicle asset type."""

    def __init__(self) -> None:
        self._hooks = VehicleHooks()

    # ---- identity ----

    @property
    def asset_type(self) -> str:
        return "vehicle"

    @property
    def display_name(self) -> str:
        return "Veículos"

    @property
    def icon(self) -> str:
        return "heroTruck"

    # ---- event routing ----

    def handles_event(self, event_type: type[DomainEvent]) -> bool:
        return event_type in (
            InstallmentOverdueEvent,
            InstallmentPaidEvent,
            ContractCreatedEvent,
            ContractTerminatedEvent,
        )

    def on_contract_created(self, event: ContractCreatedEvent) -> list[Action]:
        return []

    def on_contract_terminated(self, event: ContractTerminatedEvent) -> list[Action]:
        return []

    def on_installment_overdue(
        self, event: InstallmentOverdueEvent, policy: dict
    ) -> list[Action]:
        return self._hooks.on_installment_overdue(event, policy)

    def on_installment_paid(self, event: InstallmentPaidEvent) -> list[Action]:
        return self._hooks.on_installment_paid(event)

    def on_partial_payment(
        self, event: PaymentPartiallyReceivedEvent
    ) -> list[Action]:
        return []

    def on_reconciliation_completed(
        self, event: ReconciliationCompletedEvent
    ) -> list[Action]:
        return []

    # ---- schema / details ----

    def get_asset_schema(self) -> list[FieldDefinition]:
        """Return extended fields for the vehicle asset type, including CNH."""
        return [
            FieldDefinition(name="plate", field_type="string", label="Placa", required=True),
            FieldDefinition(name="brand", field_type="string", label="Marca", required=True),
            FieldDefinition(name="model_name", field_type="string", label="Modelo", required=True),
            FieldDefinition(name="model_year", field_type="integer", label="Ano Modelo", required=True),
            FieldDefinition(name="fab_year", field_type="integer", label="Ano Fabricação", required=True),
            FieldDefinition(name="color", field_type="string", label="Cor"),
            FieldDefinition(name="chassi", field_type="string", label="Chassi"),
            FieldDefinition(name="renavam", field_type="string", label="Renavam"),
            FieldDefinition(name="fipe_code", field_type="string", label="Código FIPE"),
            # CNH fields — extends customer schema
            FieldDefinition(name="cnh_number", field_type="string", label="CNH"),
            FieldDefinition(name="cnh_category", field_type="string", label="Categoria CNH"),
            FieldDefinition(name="cnh_expiry", field_type="date", label="Validade CNH"),
        ]

    def get_asset_details(self, asset_id: str) -> dict:
        # Stub — actual implementation queries DB
        return {"asset_id": asset_id, "module": "vehicle"}

    def get_asset_financials(self, asset_id: str) -> dict:
        # Stub — actual implementation queries DB
        return {"asset_id": asset_id, "fipe_value": None}

    def get_dashboard_widgets(self) -> list[Widget]:
        return [
            Widget(
                widget_id="fleet_map",
                title="Mapa da Frota",
                widget_type="map",
            ),
            Widget(
                widget_id="vehicles_by_status",
                title="Veículos por Status",
                widget_type="pie_chart",
                config={"group_by": "status"},
            ),
        ]

    def get_report_dimensions(self) -> list[str]:
        return ["brand", "model_name", "model_year", "status", "color"]

    def get_agent_tools(self) -> list[AgentTool]:
        return [
            AgentTool(
                tool_id="check_vehicle_status",
                name="Consultar Status do Veículo",
                description="Retorna status atual e posição GPS de um veículo pela placa.",
                required_permissions=["vehicles.read"],
            ),
            AgentTool(
                tool_id="block_vehicle_gps",
                name="Bloquear Veículo via GPS",
                description="Envia comando de bloqueio ao rastreador do veículo.",
                required_permissions=["vehicles.block"],
            ),
            AgentTool(
                tool_id="unblock_vehicle_gps",
                name="Desbloquear Veículo via GPS",
                description="Envia comando de desbloqueio ao rastreador do veículo.",
                required_permissions=["vehicles.unblock"],
            ),
        ]

    def get_score_factors(self) -> list[ScoreFactor]:
        return [
            ScoreFactor(
                factor_id="vehicle_maintenance",
                name="Manutenção em Dia",
                weight=0.2,
                description="Veículo com revisões e documentação em dia.",
            ),
            ScoreFactor(
                factor_id="tracker_active",
                name="Rastreador Ativo",
                weight=0.3,
                description="Dispositivo GPS ativo e reportando posição.",
            ),
        ]

    def get_custom_routes(self) -> list[APIRouter]:
        from app.modules.vehicles.routes import router

        return [router]
