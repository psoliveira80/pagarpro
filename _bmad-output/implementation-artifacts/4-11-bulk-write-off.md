---
epic: 4
story: 11
title: "Bulk Write-Off"
type: "Core"
status: done
---

# Story 4.11: Bulk Write-Off

## User Story
As a Manager,
I want to write off multiple installments of the same customer with a single payment,
So that batch payments are fast.

## Acceptance Criteria

1. User selects multiple open/overdue installments of the same customer in the receivables list.
2. "Baixa em Lote" action opens a modal showing selected titles, sum total (with interest/fines), and a single payment form.
3. Payment distributes across titles in due-date order (oldest first).
4. Each title gets its own `InstallmentAdjustment` and status change.
5. If paid amount < total selected, the last title gets a partial write-off with remainder title generated.
6. Audit log records the bulk operation with all affected installment IDs.

## Technical Context

### Architecture References
- **PRD FR-CORE-CR-4**: Bulk write-off across multiple installments of same customer.
- **Architecture Section 2.4**: Domain logic in pure functions, infrastructure handles persistence.
- **Epic 4 patterns**: Reuses write-off modal pattern (Story 4.3) and partial payment logic (Story 4.4).

### Files to Create/Modify
```
backend-api/
├── app/
│   ├── domain/
│   │   └── finance/
│   │       └── bulk_write_off.py               # Pure function: distribute payment across titles
│   ├── api/
│   │   └── v1/
│   │       └── receivables.py                  # Add POST /api/v1/receivables/bulk-write-off
│   └── tests/
│       ├── test_bulk_write_off_domain.py       # Unit tests for distribution logic
│       └── test_bulk_write_off_api.py          # Integration tests
frontend/
├── src/app/features/system/finance/receivables/
│   └── components/
│       └── bulk-write-off-modal/
│           ├── bulk-write-off-modal.component.ts
│           ├── bulk-write-off-modal.component.html
│           └── bulk-write-off-modal.component.css
```

### Dependencies
- Story 4.2 (updated value calculation — interest/fine computation)
- Story 4.3 (manual write-off modal — UI pattern reuse)
- Story 4.4 (partial payment support — remainder title generation logic)

### Technical Notes
- Distribution algorithm: sort selected installments by `due_date ASC`, apply payment to each in order until exhausted.
- For each fully covered title: create `InstallmentAdjustment(kind='write_off')`, set status to `pago_aguardando_verificacao`.
- For partially covered last title: reuse Story 4.4 partial payment logic (partial write-off + new remainder title).
- Endpoint: `POST /api/v1/receivables/bulk-write-off` with body `{installment_ids: UUID[], payment: {date, amount, method, notes, attachment_url}}`.
- Validate all installments belong to the same customer; reject mixed-customer requests.
- Validate all installments are in status `em_aberto` or `vencido`.
- Entire operation in a single DB transaction; rollback on any failure.
- Audit log entry includes: `{operation: 'bulk_write_off', customer_id, installment_ids, total_paid, distribution: [{id, amount_applied, new_status}]}`.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] No regressions
