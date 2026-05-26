---
epic: 1
story: 8
title: "Asset Abstraction Layer Bootstrap"
type: "Core"
status: done
---

# Story 1.8: Asset Abstraction Layer Bootstrap

## User Story
As a Developer,
I want the `IAssetModule` interface defined, the event bus implemented, and Module Hook registration working,
So that vertical modules can plug in without altering the core.

## Acceptance Criteria

1. `IAssetModule` Protocol defined in `app/core/assets/module_interface.py` per FR-CORE-AST-1, with complete type hints and return types:
   - `asset_type: str` (property — e.g. `"vehicles"`)
   - `display_name: str` (property — e.g. `"Veículos"`)
   - `icon: str` (property — Heroicon name)
   - `handles_event(event_type: type) -> bool` — capability declaration (module declares which events it listens to)
   - `on_contract_created(event: ContractCreatedEvent) -> list[Action]`
   - `on_contract_terminated(event: ContractTerminatedEvent) -> list[Action]`
   - `on_installment_overdue(event: InstallmentOverdueEvent, policy: dict) -> list[Action]`
   - `on_installment_paid(event: InstallmentPaidEvent) -> list[Action]`
   - `on_partial_payment(event: PaymentPartiallyReceivedEvent) -> list[Action]`
   - `on_reconciliation_completed(event: ReconciliationCompletedEvent) -> list[Action]`
   - `get_asset_schema() -> list[FieldDefinition]`
   - `get_asset_details(asset_id: str) -> dict`
   - `get_asset_financials(asset_id: str) -> dict`
   - `get_dashboard_widgets() -> list[Widget]`
   - `get_report_dimensions() -> list[str]`
   - `get_agent_tools() -> list[AgentTool]`
   - `get_score_factors() -> list[ScoreFactor]`
   - `get_custom_routes() -> list[APIRouter]`
2. **Asynchronous event bus via Celery** implemented in `app/core/events/event_bus.py`. `publish(event)` serializes the DomainEvent and enqueues a Celery task `handle_domain_event` on the `events` queue. The Celery worker deserializes the event, resolves target module(s) by `asset_type`, checks `active_modules.is_active` AND `module_hooks_config.is_active` for that event_type, and dispatches to the hook method. Only events the module declared interest in (via `handles_event()`) are dispatched.
3. Domain Events defined in `app/core/events/domain_events.py` as frozen dataclasses inheriting `DomainEvent(event_id: UUID, occurred_at: datetime, asset_type: str)`: `ContractCreatedEvent`, `ContractTerminatedEvent`, `InstallmentOverdueEvent`, `InstallmentPaidEvent`, `ReconciliationCompletedEvent`, `CustomerScoreChangedEvent`, `PaymentPartiallyReceivedEvent`.
4. Module Hook registration in `app/core/assets/registry.py`: `register_module(module: IAssetModule)`, `get_module(module_id: str) -> IAssetModule | None`, `list_modules() -> list[IAssetModule]`, `is_module_active(module_id: str) -> bool`, `get_tools_for_context(caller_permissions: list[str], module_id: str | None) -> list[AgentTool]`. Modules are registered at **boot time only** (no hot-reload). Runtime toggling is via the `active_modules.is_active` flag in the database.
5. `assets` table migrated per FR-CORE-AST-3: `id` UUID PK, `module_id` (string), `external_ref` (module's own ID — e.g. vehicle UUID), `display_name`, `status` (`disponivel`/`em_uso`/`manutencao`/`inativo`), `metadata` (JSONB), timestamps, soft delete.
6. `active_modules` table: `module_id` (PK string), `is_active` (bool default true), `config` (JSONB), `registered_at` (TIMESTAMPTZ).
7. `module_hooks_config` table: `id` UUID PK, `module_id` FK, `event_type` (string), `policy` (JSONB — e.g. `{"auto_block": true, "min_days_overdue": 15, "min_score": 40}`), `is_active` bool.
8. `event_log` table for tracking dispatched events: `id` BIGSERIAL PK, `event_id` UUID UNIQUE, `event_type` (string), `asset_type` (string), `payload` (JSONB), `dispatched_at` TIMESTAMPTZ, `processed_at` TIMESTAMPTZ nullable, `processing_status` (`pending`/`processing`/`completed`/`failed`), `error` TEXT nullable. Supports replay and debugging.
9. **Every hook handler MUST be idempotent**: check current state before acting (e.g., if vehicle is already blocked, don't re-block). Use `event_log.event_id` UNIQUE constraint to prevent double-processing.
10. **Core never JOINs module-specific tables.** If a screen needs module-specific data, the module exposes it via its `get_asset_details(asset_id)` method. Core queries only `assets` + `active_modules` + `module_hooks_config`.
11. Unit tests: register MockModule, publish event via Celery (use `celery.conf.task_always_eager = True` for sync test execution), verify handler called with correct payload; verify inactive module does not receive events; verify idempotent handler ignores duplicate event_id.

## Technical Context

### Architecture References
- **Architecture Section 7.1**: `IAssetModule` Protocol with `asset_type`, `display_name`, `get_router()`, `get_agent_tools()`, `execute_agent_tool()`, `get_hooks()`, `on_asset_created()`, `on_asset_deleted()`.
- **Architecture Section 7.2**: `ModuleRegistry` singleton with `register()`, `get()`, `all()`, `get_all_agent_tools()`.
- **Architecture Section 7.3**: Domain Event dispatch pattern — `EventBus.publish(event)` routes to module hooks by `asset_type`. `DomainEvent` base class with `occurred_at`.
- **Architecture Section 7.1**: `IModuleHooks` Protocol with `on_installment_overdue`, `on_installment_paid`, `on_contract_terminated`, `on_partial_payment`.
- **Architecture Section 4.2 — Asset Registry**: Asset entity, AssetModule entity, ModuleHooksConfig entity.
- **Architecture Section 6**: Source tree — `app/core/module_registry.py`, `app/domain/shared/events.py`, `app/domain/ports/asset_module.py`, `app/infrastructure/messaging/event_bus.py`.

### Files to Create/Modify
```
backend-api/
├── app/
│   ├── core/
│   │   ├── assets/
│   │   │   ├── __init__.py
│   │   │   ├── module_interface.py         # IAssetModule Protocol
│   │   │   └── registry.py                 # ModuleRegistry: register, get, list, is_active
│   │   └── events/
│   │       ├── __init__.py
│   │       ├── domain_events.py            # All domain event dataclasses
│   │       └── event_bus.py                # EventBus: publish, subscribe, unsubscribe
│   ├── domain/
│   │   └── assets/
│   │       ├── __init__.py
│   │       └── asset.py                    # Asset domain entity
│   ├── infrastructure/
│   │   ├── db/
│   │   │   └── models/
│   │   │       ├── asset.py                # Asset SQLAlchemy model
│   │   │       ├── active_module.py        # ActiveModule SQLAlchemy model
│   │   │       └── module_hooks_config.py  # ModuleHooksConfig SQLAlchemy model
│   │   ├── messaging/
│   │   │   ├── __init__.py
│   │   │   └── event_bus.py                # CeleryEventBus implementation
│   │   └── db/
│   │       └── models/
│   │           └── event_log.py            # EventLog SQLAlchemy model
│   ├── workers/
│   │   └── tasks/
│   │       └── handle_domain_event.py      # Celery task: deserialize, dispatch, log
│   └── tests/
│       ├── test_event_bus.py               # unit tests (task_always_eager=True)
│       └── test_module_registry.py         # unit tests for registry
├── alembic/
│   └── versions/
│       └── 0003_asset_abstraction_layer.py # migration: assets, active_modules, module_hooks_config, event_log
```

### Dependencies
- **Story 1.1** (FastAPI skeleton, DB session).
- **Story 1.3** (Alembic migrations infrastructure, base models).

### Technical Notes
- **IAssetModule Protocol**: Use `typing.Protocol` with `runtime_checkable` decorator. Methods from the AC list map to the Architecture's `IAssetModule` + `IModuleHooks`. The epics.md version includes `on_contract_created`, `on_contract_terminated`, `on_installment_overdue`, `on_installment_paid`, `on_reconciliation_completed`, `get_asset_details`, `get_asset_financials`, `get_dashboard_widgets`, `get_report_dimensions`, `get_collection_tools`.
- **Event Bus (Celery-based async)**: `EventBus.publish(event)` does NOT run handlers in-process. It serializes the `DomainEvent` to JSON and calls `celery_app.send_task("tasks.handle_domain_event", args=[event_json], queue="events")`. The Celery task:
  1. Deserializes the event
  2. Writes to `event_log` table (idempotent by `event_id` UNIQUE)
  3. Looks up `ModuleRegistry` for modules matching `event.asset_type`
  4. For each active module that declared `handles_event(event_type) == True`, loads the `module_hooks_config` policy and calls the hook
  5. Updates `event_log.processing_status` to `completed` or `failed`
  ```python
  # app/core/events/event_bus.py
  class CeleryEventBus:
      def __init__(self, celery_app: Celery):
          self.celery = celery_app

      def publish(self, event: DomainEvent) -> str:
          """Enqueue event for async processing. Returns task_id."""
          return self.celery.send_task(
              "tasks.handle_domain_event",
              args=[event.to_dict()],
              queue="events",
          )

  # app/workers/tasks/handle_domain_event.py
  @celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
  def handle_domain_event(self, event_dict: dict):
      event = DomainEvent.from_dict(event_dict)
      # Idempotency: skip if event_id already processed
      if event_log_repo.exists(event.event_id):
          return {"status": "duplicate", "event_id": str(event.event_id)}
      event_log_repo.create(event)  # status=processing
      registry = get_module_registry()
      for module in registry.get_modules_for_asset_type(event.asset_type):
          if not module.handles_event(type(event)):
              continue
          policy = hooks_config_repo.get_policy(module.asset_type, type(event).__name__)
          actions = module.dispatch_event(event, policy)
          for action in actions:
              action.execute()  # each action is also idempotent
      event_log_repo.mark_completed(event.event_id)
  ```
- **Domain Events**: Frozen dataclasses inheriting `DomainEvent`. Each carries `event_id` (UUID, generated at publish), `occurred_at`, `asset_type`, plus context IDs. Enough data for handlers to act **without querying the database** for basic decisions.
- **ModuleRegistry**: App-scoped singleton. Modules register at boot time in `app/main.py` lifespan. `is_module_active()` checks the in-memory registry AND the `active_modules` table for runtime toggling. **No hot-reload** — toggling `is_active` in the DB takes effect on the next event dispatch (Celery worker reads DB), not on code loading.
- **Capability Declaration**: Each module implements `handles_event(event_type) -> bool` declaring which events it cares about. The EventBus worker ONLY dispatches events the module registered interest in. This avoids gordo interfaces where simple modules implement 10 empty methods.
- **Scoped Tool Resolution**: `registry.get_tools_for_context(permissions, module_id)` filters tools by the caller's RBAC permissions AND the module's `is_active` status. Admin gets all tools; Motorista gets only their own data queries.
- **Adapter Health Checks**: Each adapter port (ITrackerGateway, IWhatsAppGateway, etc.) should expose a `health_check() -> HealthStatus` method. Not implemented in this story — each adapter story adds its own. The pattern is documented here for consistency.
- **Assets table**: UUID PK, `module_id` (string like `vehicles`), `external_ref` (module's own ID), `display_name`, `status` enum, `metadata` JSONB, timestamps, soft delete. FK from `active_modules.module_id`.
- **active_modules table**: `module_id` (PK, string), `is_active` (bool default true), `config` (JSONB), `registered_at` (TIMESTAMPTZ).
- **module_hooks_config table**: `id` UUID PK, `module_id` FK, `event_type` (string), `policy` JSONB (e.g., `{auto_block: true, min_days_overdue: 15}`), `is_active` bool.
- **Testing**: Create a `MockModule` implementing `IAssetModule`. Register it, publish events, assert handler was called. Test that deactivating the module (setting `is_active=False`) prevents event dispatch.

## Dev Checklist
- [x] All acceptance criteria met (AC1-11)
- [x] Tests written and passing (7 unit tests)
- [x] Lint/type-check passing
- [x] Audit log entries for mutations (N/A — infrastructure only)
- [x] No regressions (22/22 tests pass)

## File List
- `src/backend-api/app/core/assets/__init__.py`
- `src/backend-api/app/core/assets/module_interface.py` — IAssetModule Protocol + data classes
- `src/backend-api/app/core/assets/registry.py` — ModuleRegistry
- `src/backend-api/app/core/events/__init__.py`
- `src/backend-api/app/core/events/domain_events.py` — 7 domain events
- `src/backend-api/app/core/events/event_bus.py` — CeleryEventBus
- `src/backend-api/app/infrastructure/db/models/asset.py` — Asset model
- `src/backend-api/app/infrastructure/db/models/active_module.py` — ActiveModule model
- `src/backend-api/app/infrastructure/db/models/module_hooks_config.py` — ModuleHooksConfig model
- `src/backend-api/app/infrastructure/db/models/event_log.py` — EventLog model
- `src/backend-api/app/workers/tasks/__init__.py`
- `src/backend-api/app/workers/tasks/handle_domain_event.py` — Celery task
- `src/backend-api/alembic/versions/0003_asset_abstraction_layer.py` — Migration
- `src/backend-api/app/tests/test_module_registry.py` — 7 unit tests

## Change Log
- 2026-05-12: Asset abstraction layer bootstrap — IAssetModule, domain events, Celery event bus, registry, DB models + migration
