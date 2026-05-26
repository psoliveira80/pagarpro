---
epic: 5
story: 1
title: "Categories & Suppliers Domain and CRUD API"
type: "Core"
status: done
---

# Story 5.1: Categories & Suppliers Domain and CRUD API

## User Story
As a Backend developer,
I want entities to categorize expenses and suppliers,
So that downstream reports are rich.

## Acceptance Criteria

1. `expense_categories` table: id, parent_id (self-referential hierarchy), name, color, icon, is_active, sort_order. Core defaults seeded; modules can register additional categories.
2. `suppliers` table: id, name, document (CPF/CNPJ), contact, bank_data (JSONB), is_active.
3. CRUD endpoints `/api/v1/expense-categories` and `/api/v1/suppliers` with permissions.
4. Default categories seeded: Maintenance, Fuel, Taxes, Insurance, Salaries, Rent, Utilities, Other.

## Technical Context

### Architecture References
- **Architecture Section 4.1 (Domain Entities)**: Finance domain — expense categories and suppliers support the Payable entity.
- **Architecture Section 5 (API Endpoints)**: CRUD under `/api/v1/expense-categories` and `/api/v1/suppliers`.
- **Architecture Section 6 (Backend Modules)**: `app/api/v1/payable_routes.py` (or dedicated routes), `app/infrastructure/db/models/`.
- **Architecture Section 2.4 (Hexagonal Pattern)**: Domain entities with repository interfaces; ORM in infrastructure layer.

### Files to Create/Modify
```
backend-api/
├── app/domain/finance/expense_category.py     # ExpenseCategory entity with self-referential hierarchy
├── app/domain/finance/supplier.py             # Supplier entity
├── app/infrastructure/db/models/expense_category.py  # SQLAlchemy ORM model
├── app/infrastructure/db/models/supplier.py          # SQLAlchemy ORM model
├── app/infrastructure/db/repositories/expense_category_repo.py  # CRUD + tree queries
├── app/infrastructure/db/repositories/supplier_repo.py          # CRUD + search
├── app/api/v1/expense_category_routes.py      # CRUD endpoints /api/v1/expense-categories
├── app/api/v1/supplier_routes.py              # CRUD endpoints /api/v1/suppliers
├── app/application/finance/manage_categories.py  # use cases: create, update, toggle, reorder
├── app/application/finance/manage_suppliers.py   # use cases: create, update, toggle
├── alembic/versions/xxxx_add_expense_categories_and_suppliers.py  # migration
├── app/infrastructure/db/seeds/expense_categories.py  # default category seeder
```

### Dependencies
- Alembic migration infrastructure from Epic 1.
- Auth/permission guards from Epic 1 (role-based access on CRUD endpoints).

### Technical Notes
- `expense_categories` uses a self-referential `parent_id` FK for hierarchical categorization (e.g., "Maintenance > Tires", "Maintenance > Oil Change"). The API should return a flat list with `parent_id` and also support a `?tree=true` query param that returns nested JSON.
- Default categories are seeded via a data migration or seed script: Maintenance, Fuel, Taxes, Insurance, Salaries, Rent, Utilities, Other. These have `is_active=True` and `parent_id=NULL` (top-level).
- Modules can register additional categories at startup (e.g., Vehicle Module might add "IPVA", "Licenciamento" under Taxes).
- `suppliers.bank_data` is JSONB storing bank details for payment: `{ bank_code, agency, account, pix_key, pix_key_type }`.
- `suppliers.document` stores CPF or CNPJ with validation (use the `Cpf`/`Cnpj` value objects or a unified document validator).
- Both entities support soft-deactivation via `is_active` toggle (not hard delete).
- Supplier autocomplete endpoint: `GET /api/v1/suppliers?search=term` for use in payable forms.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
