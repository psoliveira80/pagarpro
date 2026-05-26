---
epic: 3
story: 6
title: "Bulk Edit on Open Installments"
type: "Core"
status: done
---

# Story 3.6: Bulk Edit on Open Installments

## User Story

As a Manager,
I want to update many open installments at once,
So that ad-hoc adjustments are quick.

## Acceptance Criteria

1. Contract installment table supports multi-row selection (checkbox + Shift-click range).
2. Floating "Bulk Actions" bar: Postpone X days, Apply discount X% or X R$, Set value, Cancel, Recreate.
3. **Given** bulk action, **Then** applied **only** to installments with status in (`em_aberto`, `vencido`). Paid titles are immutable — skipped with notification.
4. Before/after diff preview in confirmation modal.
5. Backend applies in single transaction with `contract_events.bulk_edit` event.
6. After bulk edit, if installments were changed, old open titles are cancelled and new ones generated (reissue). `contract_events.installments_reissued` event recorded.

## Technical Context

### Architecture References

- **FR-CORE-CTR-6**: Bulk-edit open installments (postpone, discount, cancel) in atomic transaction with audit event. Paid titles immutable.
- **FR-CORE-CTR-3**: Contract changes that affect installments cancel open titles and reissue new ones.
- **API Endpoint** (Section 5.2): `POST /api/v1/contracts/{id}/installments/bulk-edit`
- **Use Case** (Section 6): `backend-api/app/application/contracts/bulk_edit_installments.py`
- **Domain**: `installment_adjustments` table records each change; `contract_events` records `bulk_edit` and `installments_reissued` events
- **Frontend** (Section 10.1): `frontend/src/app/features/system/contracts/components/installment-bulk-edit-modal/`

### Files to Create/Modify

**Create (Backend):**
- `backend-api/app/application/contracts/bulk_edit_installments.py` — use case: validate, apply changes, record adjustments, optionally reissue, record events
- `backend-api/app/api/v1/schemas/contracts.py` — add `BulkEditRequestDTO` (action type, params, installment_ids), `BulkEditPreviewDTO` (before/after per installment)
- `backend-api/tests/unit/application/contracts/test_bulk_edit.py`
- `backend-api/tests/integration/test_bulk_edit_endpoint.py`

**Create (Frontend):**
- `frontend/src/app/features/system/contracts/components/installment-bulk-edit-modal/installment-bulk-edit-modal.component.ts`
- `frontend/src/app/features/system/contracts/components/installment-bulk-edit-modal/installment-bulk-edit-modal.component.html`
- `frontend/src/app/features/system/contracts/components/installment-bulk-edit-modal/installment-bulk-edit-modal.component.css`

**Modify:**
- `backend-api/app/api/v1/contract_routes.py` — add `POST /{id}/installments/bulk-edit`
- `frontend/src/app/features/system/contracts/contract-detail.component.ts` — add installment table with multi-select and bulk actions bar

### Dependencies

- Story 3.1 (Contract/Installment model, installment_adjustments, contract_events)
- Story 3.2 (Schedule calculator — for reissue/recreate)

### Technical Notes

- **Bulk action types**:
  - `postpone`: shift `due_date` by N days for selected installments
  - `discount_pct`: reduce `amount` by X% for selected
  - `discount_abs`: reduce `amount` by X R$ for selected
  - `set_value`: set `amount` to X for selected
  - `cancel`: set status to `cancelado` for selected
  - `recreate`: cancel selected, then generate new installments using schedule_calculator
- **Immutability enforcement**: backend filters `installment_ids` to only those with status in `['em_aberto', 'vencido']`. If any paid titles are in the selection, they are skipped and their IDs returned in the response as `skipped_ids` with reason.
- **Diff preview**: before executing, the endpoint can accept a `preview=true` query param that returns the before/after state without persisting. The frontend modal shows this diff (old value -> new value per row).
- **Single transaction**: all changes wrapped in one DB transaction. For each modified installment, an `installment_adjustments` record is created with `kind='bulk_edit'`, `snapshot_before`, `snapshot_after`, `reason` (action description).
- **Reissue logic** (AC 6): if the action is `recreate`, the old open titles are marked `cancelado` and new ones are generated via `schedule_calculator` from the contract's current definition. A `contract_events.installments_reissued` event is recorded with `payload={cancelled_ids: [...], new_ids: [...]}`.
- **Frontend multi-select**: checkboxes on each row. Shift+click selects range. Floating bar appears when selection > 0 with action buttons.
- **Audit**: the bulk_edit action creates a `contract_events.bulk_edit` entry with `payload={action, params, affected_ids, skipped_ids}`.

## Dev Checklist

- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
