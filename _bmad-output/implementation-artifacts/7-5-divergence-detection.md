---
epic: 7
story: 5
title: "Divergence Detection"
type: "Core"
status: done
---

# Story 7.5: Divergence Detection

## User Story
As the System,
I want to flag inconsistencies,
So that the manager can investigate.

## Acceptance Criteria
1. Top-of-screen "Alerts" panel on the reconciliation page with three categories:
   - **Orphan transactions**: bank transactions with no compatible title match (potential unknown revenue or bank error).
   - **Suspect paid titles**: titles flagged as `pago` without a matching `conciliada` bank transaction (potential erroneous write-off).
   - **Value mismatches**: bank transactions matched to candidate titles where amounts differ beyond a configurable tolerance (default R$ 0.50).
2. Click on any alert opens a contextual investigation pane showing the transaction and/or title details with action buttons (ignore, create payable, flag for review).
3. Alert counts refresh automatically when new transactions are imported or matches are confirmed.

## Technical Context

### Architecture References
- Frontend: part of `frontend/src/app/features/finance/reconciliation/reconciliation.component.ts` — alerts panel rendered at the top of the reconciliation page.
- Backend: divergence detection queries run against `bank_transactions` and `installments` tables.
- The reconciliation page already exists from Story 7.4; this story adds the alerts layer.

### Files to Create/Modify
**Backend:**
- `backend-api/app/application/reconciliation/detect_divergences.py` — use case: query for orphan transactions, suspect paid titles, and value mismatches; return categorized alert list
- `backend-api/app/api/v1/reconciliation_routes.py` — add `GET /api/v1/reconciliation/divergences` endpoint returning categorized alerts with counts and details
- `backend-api/app/infrastructure/db/repositories/bank_transaction_repo.py` — add queries: orphan transactions (pendente status older than X days), paid titles without matching conciliada transaction, value mismatch candidates

**Frontend:**
- `frontend/src/app/features/finance/reconciliation/components/divergence-panel/divergence-panel.component.ts` — alerts panel with three category tabs, counts, and alert list
- `frontend/src/app/features/finance/reconciliation/components/divergence-panel/divergence-panel.component.html`
- `frontend/src/app/features/finance/reconciliation/components/divergence-panel/divergence-panel.component.css`
- `frontend/src/app/features/finance/reconciliation/components/investigation-pane/investigation-pane.component.ts` — contextual detail pane for a selected alert with action buttons (ignore, create payable, flag)
- `frontend/src/app/features/finance/reconciliation/reconciliation.component.ts` — integrate divergence panel at the top of the page
- `frontend/src/app/features/finance/reconciliation/reconciliation.component.html` — add divergence panel slot

**Tests:**
- `backend-api/tests/unit/application/test_detect_divergences.py` — test each divergence category detection
- `backend-api/tests/integration/test_divergences_endpoint.py`
- `frontend/src/app/features/finance/reconciliation/components/divergence-panel/divergence-panel.component.spec.ts`

### Dependencies
- Story 7.1 (OFX Importer — `bank_transactions` table with imported data).
- Story 7.4 (Reconciliation Screen — parent page where divergence panel is integrated).
- Epic 4 (Receivables — installment data for suspect paid title detection).

### Technical Notes
- **Orphan transactions**: `SELECT * FROM bank_transactions WHERE status = 'pendente' AND imported_at < NOW() - INTERVAL '3 days'` — transactions pending for more than 3 days with no match suggestion above threshold.
- **Suspect paid titles**: `SELECT i.* FROM installments i WHERE i.status = 'pago' AND NOT EXISTS (SELECT 1 FROM bank_transactions bt WHERE bt.reconciled_to_id = i.id AND bt.status = 'conciliada')` — titles marked as paid but never confirmed by a bank transaction.
- **Value mismatches**: detected during auto-match when the best candidate has a score >= 0.85 but `exact_value` component < 1.0 (amounts differ). Store these as "partial match" suggestions with the mismatch amount highlighted.
- Alert counts displayed as badges on each category tab. Total alert count shown in the sidebar navigation for the reconciliation page.
- Actions from the investigation pane:
  - "Ignore": sets transaction status to `ignorada` with reason.
  - "Create payable": calls `/reconciliation/unmatched-as-payable` (from Story 7.4).
  - "Flag for review": creates an internal note/task for the Admin.
- Divergence detection can also run as a daily Celery task that sends summary notifications via SSE to logged-in managers.
- Configurable tolerance for value mismatches stored in Settings; default R$ 0.50.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
