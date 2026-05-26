---
epic: 2B
story: 8
title: "Overdue Hook — GPS Block Policy"
type: "Vehicle Module"
status: done
---

# Story 2B.8: Overdue Hook — GPS Block Policy

## User Story

As the Vehicle Module,
I want to react to `InstallmentOverdueEvent` by checking the block policy,
So that vehicles are blocked automatically when configured.

## Acceptance Criteria

1. Hook `on_installment_overdue` in `VehicleModule` checks parametrized policy: `dias_atraso >= X` AND `score < Y`.
2. If conditions met AND policy requires human approval -> create notification for Admin with "Approve Block" / "Reject".
3. If conditions met AND auto-approval enabled -> dispatch `block_vehicle` via `ITrackerGateway`.
4. `vehicle_blocked` event written to `audit_log` with reason, associated title, customer score.
5. On `InstallmentPaidEvent`, hook checks if vehicle is blocked and all overdue titles are cleared -> auto-dispatch `unblock_vehicle`.

## Technical Context

### Architecture References

- **FR-VH-7**: Hook `on_installment_overdue` checks parametrized block policy (days overdue >= X AND score < Y), dispatch GPS block via `ITrackerGateway` with mandatory human approval
- **FR-VH-8**: Additional collection agent tools: `bloquear_veiculo`, `desbloquear_veiculo`, `verificar_localizacao_veiculo` injected via `IAssetModule.get_collection_tools()`
- **VehicleHooks** (Section 7.4): `on_installment_overdue`, `on_installment_paid`, `on_contract_terminated`
- **Domain Events**: `InstallmentOverdue` (with `days_overdue`, `customer_id`, `asset_id`, `asset_type`), `InstallmentPaid` (with `is_partial`)
- **DB Table**: `module_hooks_config` — policy JSONB: `{auto_block: bool, min_days_overdue: int, min_score_threshold: int, requires_approval: bool}`
- **Agent Tools** (Section 7.5): `VEHICLE_AGENT_TOOLS` in `backend-api/app/modules/vehicles/agent_tools.py`
- **Audit**: `audit_log` with `action='vehicle.block'` / `vehicle.unblock`

### Files to Create/Modify

**Create:**
- `backend-api/app/modules/vehicles/agent_tools.py` — `VEHICLE_AGENT_TOOLS` list with `bloquear_veiculo`, `desbloquear_veiculo`, `verificar_localizacao` tool definitions

**Modify:**
- `backend-api/app/modules/vehicles/hooks.py` — implement full `on_installment_overdue` logic (policy check, notification or auto-block) and `on_installment_paid` logic (auto-unblock if applicable)
- `backend-api/app/modules/vehicles/module.py` — `get_agent_tools()` returns `VEHICLE_AGENT_TOOLS`; `execute_agent_tool()` dispatches to tracker service; `get_collection_tools()` returns tool definitions
- `backend-api/app/modules/vehicles/services/tracker_service.py` — add `check_and_block_if_policy_met()` and `check_and_unblock_if_cleared()` methods

**Create (tests):**
- `backend-api/tests/unit/modules/vehicles/test_overdue_hook.py`
- `backend-api/tests/unit/modules/vehicles/test_paid_hook_unblock.py`
- `backend-api/tests/unit/modules/vehicles/test_agent_tools.py`

### Dependencies

- Story 2B.1 (Vehicle Module hooks structure)
- Story 2B.6 (GPS Tracker Adapter — block/unblock via ITrackerGateway)
- Epic 1 (EventBus, audit_log, notification system)

### Technical Notes

- **Policy loading**: `VehicleHooks.on_installment_overdue` loads `module_hooks_config` row for `event_type='InstallmentOverdue'` and `asset_module_id` matching the vehicle module. Policy JSONB contains: `{auto_block: true, min_days_overdue: 15, min_score_threshold: 40, requires_approval: true}`.
- **Flow with human approval**: if `requires_approval=true`, create a notification/pending action (could be a record in a `pending_actions` table or SSE notification to Admin). Admin sees "Vehicle X - Approve Block?" in the UI. On approval, the block command executes.
- **Flow with auto-approval**: if `requires_approval=false` (rare), directly call `tracker_service.block(vehicle_id, reason)`. This should be very explicitly configured.
- **Unblock on payment**: `on_installment_paid` checks: (1) is the vehicle currently blocked? (2) are there any remaining overdue titles for this contract/asset? If all clear, auto-dispatch `unblock_vehicle`. Partial payments (`event.is_partial=True`) do NOT trigger unblock.
- **Agent tools**: `bloquear_veiculo(asset_id, reason)`, `desbloquear_veiculo(asset_id)`, `verificar_localizacao(asset_id)`. These are registered via `get_agent_tools()` and executed via `execute_agent_tool()` which delegates to `TrackerService`.
- All block/unblock actions write signed `audit_log` entries with reason, title ID, customer score snapshot.

## Dev Checklist

- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
