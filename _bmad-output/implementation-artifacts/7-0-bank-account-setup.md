---
epic: 7
story: 0
title: "Bank Account Setup"
type: "Core"
status: done
---
# Story 7.0: Bank Account Setup

## User Story
As a Manager,
I want to register my bank accounts in the system,
So that imported transactions can be linked to the correct account.

## Acceptance Criteria

1. `bank_accounts` table: id UUID PK, name TEXT, bank_code VARCHAR(5), agency VARCHAR(10), account_number VARCHAR(20), type TEXT, is_active BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ.
2. CRUD API under `/api/v1/bank-accounts` with Admin permission.
3. Settings > Company > "Contas Bancárias" UI with list + create/edit form.
4. At least one bank account must exist before OFX/PDF import is allowed.

## Technical Context

### Architecture References
- **Architecture Section 7 (Bank Reconciliation)**: Bank account as the anchor entity for imported transactions.
- **Architecture Section 5 (API Endpoints)**: REST CRUD pattern under `/api/v1/bank-accounts`.

### Files to Create/Modify
```
backend-api/
├── app/domain/finance/models/bank_account.py      # BankAccount entity
├── app/infrastructure/db/models/bank_account.py   # SQLAlchemy model
├── app/api/v1/bank_account_routes.py              # CRUD endpoints
├── app/application/finance/bank_account_service.py # Service layer
├── alembic/versions/xxx_create_bank_accounts.py   # Migration
├── app/tests/unit/domain/finance/
│   └── test_bank_account.py                       # Unit tests
├── app/tests/integration/api/
│   └── test_bank_account_routes.py                # Integration tests

frontend/
├── src/app/features/system/config/company/
│   ├── bank-accounts-list.component.ts
│   ├── bank-accounts-list.component.html
│   ├── bank-account-form.component.ts
│   └── bank-account-form.component.html
```

### Dependencies
- Story 1.3 (DB migrations)

### Technical Notes
- The `bank_accounts` table is referenced by `bank_transactions.account_id` (Story 7.1).
- The guard preventing OFX/PDF import without a bank account should be a pre-condition check in the import endpoints (Stories 7.1, 7.2).
- Admin-only permission ensures only authorized users manage bank accounts.
- The `type` field supports values like "corrente", "poupanca", "pagamento".

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] No regressions
