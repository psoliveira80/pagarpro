---
epic: 4
story: 4
title: "Partial Payment Support"
type: "Core"
status: done
---

# Story 4.4: Partial Payment Support

## User Story
As the System,
I want to handle partial payments correctly,
So that the difference is tracked as a new receivable.

## Acceptance Criteria

1. `compute_partial_payment(title_amount, paid_amount, original_due_date, grace_days)` pure function in `domain/finance/calculations.py` returns: `original_new_status='pago_parcial'`, `remainder_amount`, `remainder_due_date`, `adjustment_delta`.
2. **Given** paid_amount < title amount, **When** `POST /api/v1/receivables/{id}/partial-write-off` is called with payment data, **Then**:
   - Original title receives `paid_amount` and status `pago_parcial`.
   - `InstallmentAdjustment` with `kind='partial_payment'` created, recording `amount_delta` and reference to new title in `reason` (JSON).
   - A NEW title is generated for the difference (`title.amount - paid_amount`) with `kind='regular'`, `due_date` = next vencimento or same day + `grace_days`, linked to same contract, with `parent_installment_id` pointing to original.
   - Contract sequence incremented.
3. `PaymentPartiallyReceivedEvent` published on event bus (modules can react).
4. Unit tests: various partial amounts, edge cases (paid = 0, paid = full).

## Technical Context

### Architecture References
- **Architecture Section 4.3 (Partial Payments)**: Full domain logic description with `compute_partial_payment` pure function and `PartialPaymentResult` dataclass.
- **Architecture Section 5 (API Endpoints)**: `POST /api/v1/receivables/{id}/partial-write-off` — partial payment creating remainder title.
- **Architecture Section 4.1 (Domain Entities)**: `InstallmentAdjustment` with `kind='partial_payment'`, `Installment` with `parent_installment_id`.
- **Architecture Section 6 (Backend Modules)**: `app/application/finance/partial_write_off.py` use case.

### Files to Create/Modify
```
backend-api/
├── app/domain/finance/calculations.py         # compute_partial_payment() — add/extend
├── app/api/v1/receivable_routes.py            # POST /receivables/{id}/partial-write-off
├── app/application/finance/partial_write_off.py  # orchestrate: validate, split, create new title
├── app/domain/finance/events.py               # PaymentPartiallyReceivedEvent
├── app/infrastructure/db/models/installment.py  # ensure parent_installment_id FK exists
├── app/tests/unit/domain/finance/
│   └── test_partial_payment.py                # various amounts, edge cases

frontend/
├── src/app/features/system/finance/receivables/
│   ├── partial-write-off-modal.component.ts   # modal showing remainder preview
│   ├── partial-write-off-modal.component.html
│   └── partial-write-off-modal.component.css
```

### Dependencies
- Story 4.1 (Receivables List — triggers the modal via row action).
- Story 4.2 (Updated value calculation — determines the full amount before partial).
- `Contract` and `Installment` entities from Epic 3.

### Technical Notes
- The `compute_partial_payment` pure function is already sketched in Architecture Section 4.3. Implement exactly as specified: returns `PartialPaymentResult` frozen dataclass.
- The use case must run in a single DB transaction: update original installment, create `InstallmentAdjustment`, create new `Installment`, increment contract sequence.
- Edge case: `paid_amount == 0` should be rejected (validation error). `paid_amount >= title_amount` should redirect to full write-off (Story 4.3).
- The new remainder title inherits the same `contract_id` and gets `parent_installment_id` pointing to the original.
- Frontend modal should show a live preview: "Paying R$ X of R$ Y — remainder R$ Z due on DD/MM/YYYY".
- Publish `PaymentPartiallyReceivedEvent` so modules (e.g., Vehicle Module) can react.
- Use `SELECT ... FOR UPDATE` on the installment row before processing partial payment to prevent race conditions from concurrent payments on the same title.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
