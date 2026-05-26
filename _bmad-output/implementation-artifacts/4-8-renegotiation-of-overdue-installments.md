---
epic: 4
story: 8
title: "Renegotiation of Overdue Installments"
type: "Core"
status: done
---

# Story 4.8: Renegotiation of Overdue Installments

## User Story
As a Manager,
I want to renegotiate overdue receivables,
So that struggling customers can be brought back on track.

## Acceptance Criteria

1. **Given** multiple overdue installments of same customer selected, **When** "Renegotiate" triggered, **Then** modal shows sum with updated interest/fine.
2. Modal uses Epic 3 schedule builder for new schedule.
3. **Given** confirmed, **Then** original installments -> `renegociado` (immutable), new installments created.
4. `renegotiated` event with `{old_ids, new_ids, total_old, total_new}` in `audit_log`.

## Technical Context

### Architecture References
- **Architecture Section 5 (API Endpoints)**: `POST /api/v1/receivables/renegotiate` — renegotiates a set of overdue installments.
- **Architecture Section 10.1 (Frontend Structure)**: `frontend/src/app/features/system/finance/receivables/renegotiation-modal.component.ts`.
- **Architecture Section 4.1 (Domain Entities)**: `InstallmentAdjustment` with `kind='renegotiation'`; Installment status `renegociado` is immutable/terminal.
- **Architecture Section 6 (Backend Modules)**: `app/application/finance/renegotiate.py` use case.

### Files to Create/Modify
```
backend-api/
├── app/api/v1/receivable_routes.py            # POST /receivables/renegotiate
├── app/application/finance/renegotiate.py     # use case: validate overdue, sum totals, create new schedule
├── app/domain/finance/policies.py             # renegotiation rules (only overdue, same customer)
├── app/domain/finance/events.py               # InstallmentsRenegotiatedEvent

frontend/
├── src/app/features/system/finance/receivables/
│   ├── renegotiation-modal.component.ts       # modal with debt summary + schedule builder embed
│   ├── renegotiation-modal.component.html
│   └── renegotiation-modal.component.css
```

### Dependencies
- Story 4.1 (Receivables List — multi-select overdue installments triggers renegotiation).
- Story 4.2 (Updated value calculation — computes total with interest/fine for the selected installments).
- Epic 3 Schedule Builder component (reused for building the new payment schedule).
- `Contract` and `Installment` entities from Epic 3.

### Technical Notes
- Renegotiation request payload: `{ installment_ids: UUID[], new_schedule: ScheduleParams }` where `ScheduleParams` matches the Epic 3 schedule builder output (periodicity, start_date, number of installments, etc.).
- Validation: all selected installments must belong to the **same customer**, must have status `vencido` (overdue), and must not already be `renegociado` or `cancelado`.
- The total renegotiated amount = sum of `compute_updated_value()` for each selected installment (including accrued interest and fines).
- Original installments are set to `status='renegociado'` and become immutable — no further write-offs or modifications allowed.
- Each original installment gets an `InstallmentAdjustment(kind='renegotiation')` linking to the new installments.
- New installments are created under the same contract with incremented sequence numbers.
- Audit log entry contains `{old_ids, new_ids, total_old, total_new}` for full traceability.
- The frontend modal embeds the schedule builder from Epic 3 (same component used in contract creation), pre-filled with the renegotiated total as the base amount.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
