---
epic: 6
story: 6
title: "Customer Score Calculation"
type: "Core + Module Hooks"
status: done
---

# Story 6.6: Customer Score Calculation

## User Story
As a Backend developer,
I want a periodically recomputed score per customer,
So that agent decisions are data-driven.

## Acceptance Criteria
1. Daily Celery beat job (`0 2 * * *`) recomputes a 0-100 score per customer using: punctuality over last 12 months (60% weight), average overdue days (20% inverted), relationship tenure (10% bonus), historical paid amount (10%).
2. **Module contribution**: active modules can add score factors via `IAssetModule`. E.g., Vehicle Module adds "prior blocks count" as a penalty factor.
3. Formula weights are configurable in Settings > Score (Admin-editable).
4. `customer_score_history` table records daily snapshot with factor breakdown (JSONB).
5. Customer detail page "Score" tab plots evolution chart over time.

## Technical Context

### Architecture References
- Score computation use case: `backend-api/app/application/collections/compute_score.py`.
- Domain: `backend-api/app/domain/collections/score.py` — pure score calculation logic.
- Celery task: `backend-api/app/workers/tasks/score_recompute.py` — daily cron job.
- `customer_score_history` table: id, customer_id, score, factors (JSONB), taken_at. Index on `(customer_id, taken_at DESC)`.
- Domain event: `CustomerScoreChanged` emitted when score crosses configurable thresholds.

### Files to Create/Modify
**Backend:**
- `backend-api/app/domain/collections/score.py` — pure score calculation functions (no I/O)
- `backend-api/app/domain/finance/calculations.py` — add punctuality and overdue days calculation helpers
- `backend-api/app/application/collections/compute_score.py` — use case: fetch data, compute score, persist history, emit events
- `backend-api/app/workers/tasks/score_recompute.py` — Celery beat task
- `backend-api/app/workers/beat_schedule.py` — register `score_recompute` at `0 2 * * *`
- `backend-api/app/infrastructure/db/models/customer_score.py` — `CustomerScoreHistory` ORM model
- `backend-api/alembic/versions/xxxx_create_customer_score_history.py` — migration
- `backend-api/app/domain/collections/events.py` — add `CustomerScoreChanged` event
- `backend-api/app/api/v1/customer_routes.py` — add `GET /api/v1/customers/{id}/score-history` endpoint
- `backend-api/app/api/v1/admin_routes.py` — add score formula config endpoints

**Frontend:**
- `frontend/src/app/features/customers/components/score-tab/score-tab.component.ts` — score evolution chart (line chart with ngx-charts or Chart.js)
- `frontend/src/app/features/customers/components/score-tab/score-tab.component.html`
- `frontend/src/app/features/customers/components/score-tab/score-tab.component.css`
- `frontend/src/app/features/config/billing-rules/` — add score weight configuration fields

**Tests:**
- `backend-api/tests/unit/domain/test_score_calculation.py` — pure unit tests for score formula
- `backend-api/tests/unit/application/test_compute_score.py`
- `backend-api/tests/integration/test_score_recompute_task.py`

### Dependencies
- Epic 2A (Customer domain — customer records and relationship tenure).
- Epic 4 (Receivables — installment payment history for punctuality/overdue calculations).
- Epic 1 (IAssetModule — for module score factor injection, Celery beat infrastructure).

### Technical Notes
- Score formula (default weights): `score = punctuality_12m * 0.60 + (1 - avg_overdue_ratio) * 0.20 + tenure_bonus * 0.10 + paid_amount_bonus * 0.10`. All factors normalized to 0-1 range before weighting.
- Punctuality: ratio of installments paid on or before due date in the last 12 months.
- Average overdue days: average days past due across all overdue installments, inverted (fewer days = higher score).
- Tenure bonus: capped at 1.0 after 24 months of active contract.
- Paid amount bonus: ratio of total paid vs total billed, capped at 1.0.
- Module factors are additive adjustments (can be negative penalties) applied after core calculation, with configurable max impact (e.g., -10 points max from vehicle blocks).
- The `CustomerScoreChanged` event enables downstream reactions (e.g., agent policy adjustments, collection cadence changes).
- Chart on frontend should show score over last 12 months with factor breakdown tooltip on hover.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
