---
epic: 4
story: 10
title: "Installment Reversal — Full & Partial"
type: "Core"
status: done
---

# Story 4.10: Installment Reversal — Full & Partial

## User Story
As an Admin,
I want to reverse a paid installment fully or partially,
So that overpayments are corrected with full audit trail and the cash flow reflects reality.

## Acceptance Criteria

1. **Given** a `pago` or `pago_parcial` installment, **When** Admin clicks "Estornar", **Then** a modal asks: full or partial reversal, amount (if partial), reason, and Admin password re-auth.
2. Full reversal creates `InstallmentAdjustment` with `kind='full_reversal'` and generates a `Payable` with `linked_installment_id` pointing to the original title. The payable amount equals the original `paid_amount`.
3. Partial reversal creates `InstallmentAdjustment` with `kind='partial_reversal'` and generates a `Payable` for the delta amount with `linked_installment_id`.
4. The original installment status does NOT change — it stays `pago` or `pago_parcial` (immutable). The reversal lives entirely in the adjustment + payable.
5. `payables` table includes `linked_installment_id UUID REFERENCES installments(id)` for tracing reversals.
6. DRE and dashboards compute net revenue = gross received - sum of reversal payables.
7. Audit log records the reversal with module='core', category='financial', before/after payload, and Admin user ID.
8. The generated Payable is reconcilable against the bank statement's outgoing transaction in the reconciliation screen.

## Technical Context

### Architecture References
- InstallmentAdjustment with kind `full_reversal` / `partial_reversal`
- Payable with `linked_installment_id` FK
- Immutability: original installment status unchanged
- DRE net revenue = gross - reversals

### Files to Create/Modify
- `backend-api/app/application/finance/reverse_installment.py` — use case
- `backend-api/app/api/v1/receivable_routes.py` — add POST /receivables/{id}/reverse
- `backend-api/app/domain/finance/policies.py` — add reversal validation rules
- `frontend/src/app/features/system/finance/receivables/reversal-modal.component.ts|html|css`

### Dependencies
- Story 4.1 (receivables list)
- Story 4.3 (write-off modal pattern)
- Story 5.2 (payables domain — linked_installment_id column)

### Technical Notes
- Reversal requires Admin role + password re-auth (same pattern as vehicle block)
- The PG trigger `enforce_paid_immutability` is NOT bypassed — the original title stays untouched
- The reversal creates a NEW payable, not a negative receivable
- For conciliation: the bank statement will show an outgoing transaction matching the payable amount

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log with category='financial'
- [ ] No regressions
