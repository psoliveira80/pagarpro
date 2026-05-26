---
epic: 3
story: 8
title: "Contract Termination"
type: "Core"
status: done
---

# Story 3.8: Contract Termination

## User Story

As a Manager,
I want to terminate a contract with settlement calculation,
So that asset return is documented.

## Acceptance Criteria

1. "Terminate" modal: reason, effective date, rescission fine policy (toggle "Apply X% fine", default from Settings).
2. Backend computes: `sum(open_installments) * pct_fine + manual_adjustment`.
3. **Given** confirm, **Then** final receivable (or credit) created, open installments -> `cancelado`, contract -> `rescindido`, `ContractTerminated` event published (vertical module reacts — e.g., Vehicle Module sets vehicle to `disponivel`).
4. `contract_events.terminated` entry written.

## Technical Context

### Architecture References

- **FR-CORE-CTR-8**: Contract termination with rescission calculation, final receivable or credit, `ContractTerminated` event for vertical module actions
- **API Endpoint** (Section 5.2): `POST /api/v1/contracts/{id}/terminate`
- **Use Case** (Section 6): `backend-api/app/application/contracts/terminate_contract.py`
- **Domain Event** (Section 7.3): `ContractTerminated` with `contract_id`, `asset_id`, `asset_type`, `reason`
- **Module Hook** (Section 7.4): `VehicleHooks.on_contract_terminated` sets vehicle status to `disponivel`
- **DB**: `contracts.status` -> `rescindido`, `contracts.terminated_at`, `contracts.termination_reason`

### Files to Create/Modify

**Create (Backend):**
- `backend-api/app/application/contracts/terminate_contract.py` — use case: validate, compute settlement, cancel open installments, create final receivable/credit, update contract status, publish ContractTerminated event, record contract_event
- `backend-api/app/domain/contracts/termination_calculator.py` — pure function: `compute_rescission(open_installments, fine_pct, manual_adjustment) -> RescissionResult`
- `backend-api/tests/unit/domain/contracts/test_termination_calculator.py`
- `backend-api/tests/integration/test_contract_termination.py`

**Create (Frontend):**
- `frontend/src/app/features/system/contracts/components/terminate-modal/terminate-modal.component.ts`
- `frontend/src/app/features/system/contracts/components/terminate-modal/terminate-modal.component.html`
- `frontend/src/app/features/system/contracts/components/terminate-modal/terminate-modal.component.css`

**Modify:**
- `backend-api/app/api/v1/contract_routes.py` — add `POST /{id}/terminate` endpoint
- `frontend/src/app/features/system/contracts/contract-detail.component.ts` — add "Rescindir" button opening terminate modal
- `frontend/src/app/features/system/contracts/services/contract.service.ts` — add `terminate(contractId, payload)` method

### Dependencies

- Story 3.1 (Contract model, installments, contract_events, domain events)
- Story 2B.1 (Vehicle Module hooks — reacts to ContractTerminated)
- Epic 1 (EventBus, audit_log)

### Technical Notes

- **Termination flow**:
  1. Validate contract status is `vigente` (can't terminate a draft or already terminated contract).
  2. Load all open installments (status in `em_aberto`, `vencido`).
  3. Compute rescission: `sum(open_amounts) * fine_pct + manual_adjustment`. Result can be positive (customer owes) or negative (credit to customer).
  4. If positive: create a final receivable installment (kind `custom`, due_date = effective_date).
  5. If negative: record as credit (could be a payable to customer or credit note — depends on business rules; for MVP, create a note in contract_events payload).
  6. Cancel all open installments: set status to `cancelado`. Each gets an `installment_adjustments` entry with `kind='bulk_edit'`, reason `'contract_terminated'`.
  7. Update contract: `status='rescindido'`, `terminated_at=effective_date`, `termination_reason=reason`.
  8. Insert `contract_events` with `event_type='terminated'`, payload includes fine calculation, cancelled installment IDs.
  9. Publish `ContractTerminated` event to EventBus.
  10. Update asset status to `disponivel` (done by Core or by module hook).
- **Fine policy default**: loaded from Settings (e.g., `rescission_fine_pct = 0.10` meaning 10% of remaining). The modal pre-fills this but allows override.
- **Frontend modal**: fields for reason (text), effective_date (date picker, default today), apply_fine toggle (default on), fine_pct (pre-filled from settings), manual_adjustment (optional R$ input). Shows computed total before confirmation.
- **Audit**: `audit_log` entry with `action='contract.terminated'`, full payload.

## Dev Checklist

- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
