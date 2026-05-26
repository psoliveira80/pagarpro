---
epic: 5
story: 2
title: "Payables Domain and API"
type: "Core"
status: done
---

# Story 5.2: Payables Domain and API

## User Story
As a Backend developer,
I want a Payable entity with REST endpoints,
So that the frontend can manage expenses.

## Acceptance Criteria

1. `payables` table: id, description, supplier_id (nullable), category_id, asset_id (nullable, FK to `assets` for per-asset costing), amount, due_date, status (`em_aberto`/`pago`/`cancelado`), paid_at, paid_amount, payment_method, attachment_url, notes, created_by, recurring_template_id (nullable).
2. CRUD endpoints under `/api/v1/payables`.
3. **Given** payable `em_aberto`, **When** `POST /api/v1/payables/{id}/pay`, **Then** status -> `pago`, audit entry.
4. **Given** "Quick Pay" intent, **When** `POST /api/v1/payables/quick-pay`, **Then** create + pay atomically.

## Technical Context

### Architecture References
- **Architecture Section 4.1 (Domain Entities)**: `Payable` entity with full field list, statuses `em_aberto`/`pago`/`cancelado`.
- **Architecture Section 5 (API Endpoints)**: `GET/POST /payables`, `GET/PATCH /payables/{id}`, `POST /payables/{id}/pay`, `POST /payables/quick-pay`.
- **Architecture Section 6 (Backend Modules)**: `app/api/v1/payable_routes.py`, `app/application/finance/pay_payable.py`, `app/application/finance/quick_pay.py`.
- **Architecture Section 10.1 (Frontend Structure)**: `frontend/src/app/features/system/finance/payables/` components.

### Files to Create/Modify
```
backend-api/
├── app/domain/finance/payable.py              # Payable entity
├── app/domain/finance/events.py               # PayablePaid, PayableCreated events (add to existing)
├── app/infrastructure/db/models/payable.py    # SQLAlchemy ORM model
├── app/infrastructure/db/repositories/payable_repo.py  # CRUD + filtered queries
├── app/api/v1/payable_routes.py               # full CRUD + pay + quick-pay endpoints
├── app/application/finance/create_payable.py  # use case: create payable
├── app/application/finance/pay_payable.py     # use case: mark as paid with audit
├── app/application/finance/quick_pay.py       # use case: atomic create + pay
├── alembic/versions/xxxx_add_payables.py      # migration

frontend/
├── src/app/features/system/finance/payables/
│   ├── payables-list.component.ts             # list with filters, status badges, actions
│   ├── payables-list.component.html
│   ├── payables-list.component.css
│   ├── payable-form.component.ts              # create/edit drawer or modal
│   ├── payable-form.component.html
│   ├── payable-form.component.css
│   ├── payables.routes.ts                     # lazy route /system/finance/payables
│   └── services/
│       └── payables.service.ts                # HttpClient calls to /api/v1/payables
```

### Dependencies
- Story 5.1 (Categories & Suppliers — FK references `category_id` and `supplier_id`).
- `Asset` entity from Epic 2 (optional FK `asset_id` for per-asset cost tracking).
- Auth/permission guards from Epic 1.
- Shared `data-table`, `modal`, `badge` components.

### Technical Notes
- `Payable.status` transitions: `em_aberto` -> `pago` (via pay), `em_aberto` -> `cancelado` (via cancel). No reverse transitions.
- `POST /payables/{id}/pay` payload: `{ paid_amount, payment_method, paid_at (default now), attachment_url (optional), notes (optional) }`.
- `POST /payables/quick-pay` payload combines creation and payment fields in one request. The use case creates the payable with `status='pago'` in a single atomic transaction.
- `asset_id` is nullable — when set, the expense is attributed to a specific asset for ROI/cost tracking.
- `recurring_template_id` links to `RecurringPayableTemplate` (Story 5.3) when the payable was auto-generated.
- `created_by` stores the `user_id` of the creator for audit purposes.
- All mutations (create, pay, cancel) generate `audit_log` entries.
- Frontend payables list should support filters: status, category, supplier, date range, asset.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
