---
epic: 2B
story: 1
title: "Vehicle Module Structure and IAssetModule Registration"
type: "Vehicle Module"
status: done
---

# Story 2B.1: Vehicle Module Structure and IAssetModule Registration

## User Story

As a Developer,
I want the Vehicle Module structured and registered in the core,
So that it receives domain events and injects domain-specific functionality.

## Acceptance Criteria

1. Directory `backend-api/app/modules/vehicles/` with: `__init__.py`, `module.py` (IAssetModule implementation), `models.py`, `routes.py`, `services.py`, `hooks.py`, `ports/`, `adapters/`.
2. Class `VehicleModule(IAssetModule)` implements all interface methods: `on_contract_created`, `on_contract_terminated`, `on_installment_overdue`, `on_installment_paid`, `on_reconciliation_completed`, `get_asset_details`, `get_asset_financials`, `get_dashboard_widgets`, `get_report_dimensions`, `get_collection_tools`.
3. Module registered at startup via `register_module(VehicleModule())`.
4. Entry in `active_modules`: `module_id='vehicles'`, `is_active=True`.
5. Tests: publish `InstallmentOverdueEvent` -> Vehicle Module hook is called.

## Technical Context

### Architecture References

- **IAssetModule Protocol**: `backend-api/app/domain/ports/asset_module.py` (Section 7.1 of ARCHITECTURE.md)
- **IModuleHooks Protocol**: same file, defines `on_installment_overdue`, `on_installment_paid`, `on_contract_terminated`, `on_partial_payment`
- **ModuleRegistry**: `backend-api/app/core/module_registry.py` (Section 7.2) — singleton registry, `register()` / `get()` / `all()` / `get_all_agent_tools()`
- **EventBus**: `backend-api/app/infrastructure/messaging/event_bus.py` (Section 7.3) — dispatches domain events to module hooks by `asset_type`
- **Domain Events**: `backend-api/app/domain/shared/events.py` — `InstallmentOverdue`, `InstallmentPaid`, `ContractTerminated`, `PartialPaymentApplied`
- **DB Tables**: `asset_modules` (registry of installed modules), `module_hooks_config` (per-module event hook policies)
- **Bootstrap**: `backend-api/app/main.py` — `register_modules()` function mounts module routes dynamically under `/api/v1/modules/{asset_type}`

### Files to Create/Modify

**Create:**
- `backend-api/app/modules/vehicles/__init__.py`
- `backend-api/app/modules/vehicles/module.py` — `VehicleModule(IAssetModule)` implementation
- `backend-api/app/modules/vehicles/models.py` — placeholder (populated in Story 2B.3)
- `backend-api/app/modules/vehicles/routes.py` — `APIRouter` placeholder
- `backend-api/app/modules/vehicles/services.py` — placeholder
- `backend-api/app/modules/vehicles/hooks.py` — `VehicleHooks(IModuleHooks)` stub implementations
- `backend-api/app/modules/vehicles/schemas.py` — DTOs placeholder
- `backend-api/app/modules/vehicles/agent_tools.py` — placeholder (populated in Story 2B.8)
- `backend-api/app/modules/vehicles/ports/__init__.py`
- `backend-api/app/modules/vehicles/ports/fipe_provider.py` — placeholder
- `backend-api/app/modules/vehicles/ports/tracker_gateway.py` — placeholder
- `backend-api/app/modules/vehicles/adapters/__init__.py`
- `backend-api/app/modules/vehicles/adapters/fipe/` — placeholder
- `backend-api/app/modules/vehicles/adapters/tracker/` — placeholder
- `backend-api/tests/unit/modules/vehicles/test_vehicle_module_registration.py`
- `backend-api/tests/unit/modules/vehicles/test_vehicle_hooks_dispatch.py`

**Modify:**
- `backend-api/app/main.py` — add `register_modules()` call importing `VehicleModule`
- Alembic migration — seed `asset_modules` row: `asset_type='vehicle'`, `display_name='Veiculos'`, `is_active=True`, `hooks_class_path='app.modules.vehicles.hooks.VehicleHooks'`, `routes_module_path='app.modules.vehicles.routes'`

### Dependencies

- Story 1.8 (Foundation: IAssetModule interface, ModuleRegistry, EventBus, asset_modules table)

### Technical Notes

- `VehicleModule.asset_type` returns `"vehicle"` and `display_name` returns `"Veiculos"`.
- All interface methods should have working stubs (return empty lists/dicts or log and pass) so the module is functional from day one.
- `get_hooks()` returns a `VehicleHooks` instance. The hooks class receives `TrackerService` and `db_session_factory` via DI (stub for now).
- `get_router()` returns an `APIRouter` — initially empty, populated in subsequent stories.
- `get_agent_tools()` returns empty list initially; populated in Story 2B.8.
- Module registration in `main.py` follows the pattern in Architecture Section 7.2.
- Test must verify: create `EventBus`, register `VehicleModule`, publish `InstallmentOverdue` event with `asset_type="vehicle"`, assert `VehicleHooks.on_installment_overdue` was called.
- Seed migration inserts into `asset_modules` and default `module_hooks_config` rows for `InstallmentOverdue` and `InstallmentPaid` events.

## Dev Checklist

- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
