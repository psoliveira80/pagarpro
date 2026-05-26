---
epic: 7
story: 4
title: "Drag-and-Drop Reconciliation Screen"
type: "Core"
status: done
---

# Story 7.4: Drag-and-Drop Reconciliation Screen

## User Story
As a Manager,
I want to reconcile transactions with titles by dragging them,
So that the work is fast and visual.

## Acceptance Criteria
1. Route `/system/finance/reconciliation` with 50/50 split pane layout:
   - **Left pane**: bank transactions with `status=pendente`, filterable by date range, value range, and type.
   - **Right pane**: system titles (installments + payables in `pago_aguardando_verificacao` status).
2. Drag a row from one pane onto a row in the other pane to trigger a confirmation modal showing the diff (amounts, dates, descriptions).
3. Auto-match algorithm: `score = exact_value(60%) + date_window(30%) + description_match(10%)`; matches with score >= 0.85 highlighted with a "match suggested" badge.
4. "Accept all suggestions" button for bulk-matching all high-confidence suggestions in one action.
5. N:1 and 1:N reconciliation supported via multi-select (select multiple rows on one side, drop onto a single row on the other).
6. Unmatched transaction can be converted to a payable or free-form revenue entry.
7. On match confirmation: title status transitions to `pago` (immutable), transaction status transitions to `conciliada` (locked). Both changes are atomic.
8. Top indicators bar: pending transactions count, pending titles count, conciliated today count.

## Technical Context

### Architecture References
- Frontend: `frontend/src/app/features/finance/reconciliation/reconciliation.component.ts` — main drag-and-drop split component.
- Sub-components: `transactions-pane/`, `pending-titles-pane/`, `match-suggestion-card/`.
- Backend endpoints: `GET /api/v1/reconciliation/transactions`, `GET /api/v1/reconciliation/match-suggestions`, `POST /api/v1/reconciliation/match`, `POST /api/v1/reconciliation/transactions/{id}/ignore`, `POST /api/v1/reconciliation/unmatched-as-payable`, `POST /api/v1/reconciliation/unmatched-as-revenue`.
- Auto-match Celery task: `backend-api/app/workers/tasks/auto_match_reconciliation.py` — runs hourly.
- State machine: `pago_aguardando_verificacao` -> `pago` (final, immutable).

### Files to Create/Modify
**Backend:**
- `backend-api/app/application/reconciliation/auto_match.py` — auto-match algorithm: compute score per (transaction, title) pair, return ranked suggestions
- `backend-api/app/application/reconciliation/confirm_match.py` — use case: atomically update title to `pago` + transaction to `conciliada`, link via `reconciled_to_kind/id`, emit `ReconciliationCompleted` domain event
- `backend-api/app/api/v1/reconciliation_routes.py` — add `GET /match-suggestions`, `POST /match`, `POST /transactions/{id}/ignore`, `POST /unmatched-as-payable`, `POST /unmatched-as-revenue`
- `backend-api/app/workers/tasks/auto_match_reconciliation.py` — hourly Celery beat task running auto-match
- `backend-api/app/workers/beat_schedule.py` — register `auto_match_reconciliation` at minute 15 of every hour
- `backend-api/app/domain/finance/events.py` — add `ReconciliationCompleted` domain event

**Frontend:**
- `frontend/src/app/features/finance/reconciliation/reconciliation.component.ts` — 50/50 split layout with drag-and-drop zones, top indicators
- `frontend/src/app/features/finance/reconciliation/reconciliation.component.html`
- `frontend/src/app/features/finance/reconciliation/reconciliation.component.css`
- `frontend/src/app/features/finance/reconciliation/components/transactions-pane/transactions-pane.component.ts` — left pane: bank transactions list with filters, drag source
- `frontend/src/app/features/finance/reconciliation/components/pending-titles-pane/pending-titles-pane.component.ts` — right pane: system titles list, drop target
- `frontend/src/app/features/finance/reconciliation/components/match-suggestion-card/match-suggestion-card.component.ts` — suggested match badge with confidence score, accept/dismiss buttons
- `frontend/src/app/features/finance/reconciliation/components/match-confirm-modal/match-confirm-modal.component.ts` — confirmation modal showing transaction vs title diff

**Tests:**
- `backend-api/tests/unit/application/test_auto_match.py` — test scoring algorithm with various scenarios
- `backend-api/tests/unit/application/test_confirm_match.py` — test atomic state transitions, N:1 and 1:N cases
- `backend-api/tests/integration/test_reconciliation_match.py`
- `frontend/src/app/features/finance/reconciliation/reconciliation.component.spec.ts`

### Dependencies
- Story 7.1 (OFX Importer — `bank_transactions` table with data to reconcile).
- Epic 4 (Receivables — installment state machine, `pago_aguardando_verificacao` states).
- Epic 5 (Payables — for "unmatched as payable" conversion).

### Technical Notes
- Auto-match scoring breakdown: `exact_value` (60%) = 1.0 if amounts match exactly, scaled down by `1 - abs(diff)/max(abs(txn), abs(title))`; `date_window` (30%) = 1.0 if same day, 0.8 if within 3 days, 0.5 if within 7 days, 0.0 if > 7 days; `description_match` (10%) = trigram similarity between `description_clean` and customer name using `pg_trgm`.
- Drag-and-drop: use Angular CDK `DragDrop` module for cross-pane drag operations.
- N:1 reconciliation: multiple transactions summing to one title amount. 1:N: one transaction matching multiple titles summing to the transaction amount. Both require sum validation in the confirmation modal.
- "Accept all suggestions" creates a batch of match confirmations in a single transaction.
- After match confirmation, the `ReconciliationCompleted` domain event is emitted, which modules can react to (e.g., update asset ROI calculations).
- The title's transition to `pago` triggers the `enforce_paid_immutability` database trigger, making it permanently immutable.
- "Unmatched as payable": creates a new payable record from the transaction data (amount, date, description as expense name). "Unmatched as revenue": creates a free-form revenue entry.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
