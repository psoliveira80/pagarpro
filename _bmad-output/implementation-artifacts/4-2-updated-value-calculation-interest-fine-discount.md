---
epic: 4
story: 2
title: "Updated Value Calculation — Interest, Fine, Discount"
type: "Core"
status: done
---

# Story 4.2: Updated Value Calculation — Interest, Fine, Discount

## User Story
As the System,
I want a pure function that computes the updated value of an overdue installment,
So that write-offs use the correct amount.

## Acceptance Criteria

1. `compute_updated_value(installment, on_date, contract_terms)` is a pure function in `domain/finance/calculations.py`.
2. Formula: `dias_atraso = max(0, on_date - due_date - grace_days)`; `multa = amount * fine_pct if dias_atraso > 0 else 0`; `juros = amount * interest_pct_per_day * dias_atraso`; `total = amount + multa + juros`.
3. `GET /api/v1/receivables/{id}/updated-value?on_date=` returns full breakdown (base, interest, fine, discount, total).
4. Manual discount requires mandatory `reason`, persisted to `installment_adjustments`.
5. Unit tests: on-time, short delay, long delay, within grace, with discount.

## Technical Context

### Architecture References
- **Architecture Section 4.3 (Partial Payments)**: Pure financial calculation functions in `domain/finance/calculations.py`.
- **Architecture Section 4.1 (Domain Entities)**: `InstallmentAdjustment` entity with `kind` enum including `discount`, `fine`, `interest`.
- **Architecture Section 5 (API Endpoints)**: `GET /receivables/{id}/updated-value?on_date=` — returns value with breakdown.
- **Architecture Section 2.4 (Hexagonal Pattern)**: Pure domain functions with no I/O; tested in isolation.

### Files to Create/Modify
```
backend-api/
├── app/domain/finance/calculations.py         # compute_updated_value() pure function
├── app/api/v1/receivable_routes.py            # GET /receivables/{id}/updated-value endpoint
├── app/application/finance/get_updated_value.py  # use case: load installment + contract, call pure fn
├── app/infrastructure/db/models/installment_adjustment.py  # ORM for installment_adjustments (if not yet)
├── app/tests/unit/domain/finance/
│   └── test_calculations.py                   # on-time, short delay, long delay, grace, discount
```

### Dependencies
- `Installment` and `Contract` entities from Epic 3.
- `InstallmentAdjustment` entity (append-only ledger).

### Technical Notes
- `compute_updated_value` must be a **pure function** — no database access, no side effects. Takes primitive/dataclass inputs, returns a frozen dataclass with `base`, `fine`, `interest`, `discount`, `total` fields.
- Use `Decimal` throughout for financial precision (2 decimal places for BRL).
- `grace_days` comes from `Contract.grace_days`; `fine_pct` from `Contract.late_fine_pct`; `interest_pct_per_day` from `Contract.late_interest_pct_per_day`.
- Discount application creates an `InstallmentAdjustment(kind='discount')` with mandatory `reason` field.
- The endpoint should accept an optional `discount` body/param for ad-hoc discount calculations.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
