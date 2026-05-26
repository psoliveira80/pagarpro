---
epic: 5
story: 3
title: "Recurring Expenses"
type: "Core"
status: done
---

# Story 5.3: Recurring Expenses

## User Story
As the System,
I want auto-generated recurring payables,
So that the manager doesn't forget fixed obligations.

## Acceptance Criteria

1. `recurring_payable_templates` table: id, description, supplier_id, category_id, asset_id, amount, periodicity (`mensal`/`bimestral`/`anual`), day_of_month, start_date, end_date (nullable), is_active.
2. CRUD endpoints under `/api/v1/recurring-payables`.
3. **Given** daily Celery beat job (`0 4 * * *`), **When** template active and today matches day_of_month and no payable exists for current period, **Then** new payable created.
4. "Recurring Expenses" screen: templates with active toggle, next dates, "Generate now" button.

## Technical Context

### Architecture References
- **Architecture Section 4.1 (Domain Entities)**: `RecurringPayableTemplate` entity with periodicity enum and scheduling fields.
- **Architecture Section 5 (API Endpoints)**: `GET/POST /recurring-payables`, `PATCH /recurring-payables/{id}`, `POST /recurring-payables/{id}/run-now`.
- **Architecture Section 6 (Backend Modules)**: Celery beat job for auto-generation; `app/application/finance/` use cases.
- **Architecture Section 3.1 (Tech Stack)**: Celery for async task processing and scheduled jobs.

### Files to Create/Modify
```
backend-api/
├── app/domain/finance/recurring_payable.py    # RecurringPayableTemplate entity
├── app/infrastructure/db/models/recurring_payable.py  # SQLAlchemy ORM model
├── app/infrastructure/db/repositories/recurring_payable_repo.py  # CRUD + active templates query
├── app/api/v1/recurring_payable_routes.py     # CRUD + run-now endpoints
├── app/application/finance/create_recurring_template.py  # use case: create template
├── app/application/finance/generate_recurring_payables.py  # use case: generate payables from active templates
├── app/workers/tasks/generate_recurring_payables.py  # Celery task scheduled at 0 4 * * *
├── alembic/versions/xxxx_add_recurring_payable_templates.py  # migration

frontend/
├── src/app/features/system/finance/payables/
│   ├── recurring-list.component.ts            # list of templates with active toggle
│   ├── recurring-list.component.html
│   ├── recurring-list.component.css
│   ├── recurring-form.component.ts            # create/edit form for recurring template
│   ├── recurring-form.component.html
│   └── recurring-form.component.css
```

### Dependencies
- Story 5.1 (Categories & Suppliers — FK references in templates).
- Story 5.2 (Payables Domain — templates generate Payable entities).
- Celery + Celery Beat infrastructure from Epic 1.

### Technical Notes
- Periodicity options: `mensal` (monthly), `bimestral` (every 2 months), `anual` (yearly).
- The Celery beat job runs daily at 04:00 (`0 4 * * *`). For each active template:
  1. Determine the current period based on `periodicity` and `day_of_month`.
  2. Check if a payable with `recurring_template_id = template.id` already exists for the current period (idempotent — prevents duplicates on retries).
  3. If no payable exists and `start_date <= today` and (`end_date is NULL` or `end_date >= today`), create a new payable with `status='em_aberto'`.
- `POST /recurring-payables/{id}/run-now` triggers immediate generation for the current period (manual override). Same idempotency check applies.
- Frontend recurring list shows: description, supplier, category, amount, periodicity, next generation date, active toggle, "Generate now" button.
- Next generation date is computed client-side from `day_of_month` and `periodicity` for display purposes.
- Templates support `end_date = NULL` for indefinite recurrence.
- `asset_id` on template allows recurring costs to be attributed to specific assets (e.g., monthly insurance for a specific vehicle).

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
