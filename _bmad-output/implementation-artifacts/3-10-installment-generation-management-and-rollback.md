---
epic: 3
story: 10
title: "Installment Generation Management & Rollback"
type: "Core"
status: done
---

# Story 3.10: Installment Generation Management & Rollback

## User Story
As a Manager,
I want to view all installment generations of a contract and rollback mistake generations instantly,
So that I don't pollute the system with hundreds of canceled titles from a typo.

## Acceptance Criteria

1. Contract detail page gains a "Gerações" tab listing all `installment_generations` with batch_label, installment count, total amount, status (active/rolled_back), `has_financial_activity` badge.
2. **Given** a generation with `has_financial_activity = FALSE`, **When** the user clicks "Rollback", **Then** all installments of that generation are **hard deleted** (not canceled), the generation is marked `rolled_back_at = now()`, and an audit_log entry records all deleted installment IDs.
3. **Given** a generation with `has_financial_activity = TRUE`, **When** the user views it, **Then** the "Rollback" button is hidden and a "Cancelar em massa" button is shown instead. Clicking it sets all open installments of that generation to `cancelado`.
4. `has_financial_activity` flips to TRUE when ANY installment in the generation: receives a write-off (full/partial), is sent for collection (Pix card sent via WhatsApp), receives a payment-gateway charge, or has any `installment_adjustment`.
5. The rollback action requires Admin role confirmation.
6. After rollback, the contract's installment list updates immediately.

## Technical Context

### Architecture References
- `installment_generations` table with `has_financial_activity` flag
- `generation_id` FK on installments table
- Rollback = hard DELETE when no financial activity; bulk cancel when activity exists

### Files to Create/Modify
- `backend-api/app/infrastructure/db/models/installment_generation.py` — SQLAlchemy model
- `backend-api/app/application/contracts/rollback_generation.py` — use case
- `backend-api/app/api/v1/contract_routes.py` — add GET /contracts/{id}/generations and POST /contracts/{id}/generations/{gen_id}/rollback
- `frontend/src/app/features/system/contracts/contract-tabs/contract-generations-tab.component.ts|html|css`

### Dependencies
- Story 3.1 (installment_generations table must exist)
- Story 3.4 (contract detail page with tabs)

### Technical Notes
- Hard delete uses `DELETE FROM installments WHERE generation_id = :gen_id` — only allowed when `has_financial_activity = FALSE`
- The `has_financial_activity` flag is flipped by a DB trigger or application-level check on any financial mutation touching an installment in that generation
- Rollback is irreversible — once hard-deleted, the data is gone (but audit_log keeps the record of what was deleted)

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for rollback with deleted IDs
- [ ] No regressions
