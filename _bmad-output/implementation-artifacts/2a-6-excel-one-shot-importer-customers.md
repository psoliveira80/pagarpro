---
epic: 2A
story: 6
title: "Excel One-Shot Importer — Customers"
type: "Core"
status: done
---

# Story 2A.6: Excel One-Shot Importer — Customers

## User Story
As a Manager going live,
I want to import existing customers from a spreadsheet,
So that I don't re-type dozens of records.

## Acceptance Criteria

1. CLI `python -m app.cli import-excel --entity=customers --file=clientes.xlsx --sheet=Clientes` maps columns into `customers` table.
2. **Given** `--dry-run` flag, **Then** validates and prints diff report without persisting.
3. **Given** re-run with same input, **When** existing records found by CPF, **Then** updated (not duplicated).
4. End-of-run report: created, updated, skipped (with reasons).
5. Import writes a summary `audit_log` entry.

## Technical Context

### Architecture References
- **Architecture Section 6**: CLI scripts in `app/cli/`.
- **Architecture Section 4.2 — Catalog**: Customer entity fields — full_name, cpf, phone, email, address, birth_date, notes, tags, status.
- **Additional Requirements**: `python -m app.cli import-excel` with idempotent re-runs and `--dry-run`.

### Files to Create/Modify
```
backend-api/
├── app/
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── __main__.py                      # CLI entry point (if not already created)
│   │   └── import_excel.py                  # import-excel command
│   ├── application/
│   │   └── customers/
│   │       └── import_customers.py          # ImportCustomers use case (batch)
│   └── tests/
│       └── test_import_customers.py         # tests with sample Excel fixture
├── tests/
│   └── fixtures/
│       └── sample_customers.xlsx            # test fixture Excel file
```

### Dependencies
- **Story 1.1** (FastAPI skeleton, DB session, settings).
- **Story 1.3** (audit_log table, seed infrastructure).
- **Story 2A.1** (Customer model, repository, value objects — Cpf, PhoneE164).

### Technical Notes
- **Library**: Use `openpyxl` for reading `.xlsx` files. Add to `pyproject.toml` dependencies.
- **CLI framework**: Use `click` or Python's `argparse`. The command should be invocable as:
  ```bash
  python -m app.cli import-excel --entity=customers --file=clientes.xlsx --sheet=Clientes --dry-run
  ```
- **Column mapping**: Define a mapping dict from Excel column headers to Customer model fields. Support common Portuguese column names:
  ```python
  COLUMN_MAP = {
      "Nome Completo": "full_name",
      "CPF": "cpf",
      "Telefone": "phone",
      "Email": "email",
      "CEP": "address_cep",
      "Endereco": "address_street",
      "Numero": "address_number",
      "Bairro": "address_neighborhood",
      "Cidade": "address_city",
      "Estado": "address_state",
      "Data Nascimento": "birth_date",
      "Observacoes": "notes",
      "Tags": "tags",  # comma-separated
  }
  ```
- **Validation**: For each row:
  - Validate CPF/CNPJ using the `Cpf` value object.
  - Normalize phone to E.164 using `PhoneE164`.
  - Validate email format.
  - Report validation errors per row (row number + reason).
- **Idempotency**: Look up existing customer by CPF/CNPJ. If found, update fields (merge). If not found, create. This ensures re-running the same file does not create duplicates.
- **Dry-run mode**: When `--dry-run` is passed:
  - Process all rows.
  - Print a diff report: "Would create: X, Would update: Y, Would skip: Z".
  - List each row with its action and any validation issues.
  - Do NOT commit to the database (use a transaction that is rolled back, or simply skip persistence).
- **End-of-run report**: Print summary to stdout:
  ```
  Import complete:
    Created: 15
    Updated: 3
    Skipped: 2
      Row 7: Invalid CPF '123'
      Row 12: Missing required field 'full_name'
  ```
- **Audit log**: Write a single summary entry:
  ```python
  audit.record(
      user_id="system",
      action="customers.bulk_import",
      entity="customers",
      entity_id=None,
      payload_after={"created": 15, "updated": 3, "skipped": 2, "source": "clientes.xlsx"},
  )
  ```
- **Batch processing**: Process rows in batches of 50-100 for efficient DB writes. Use `session.add_all()` within a transaction.
- **Error handling**: Do not stop on individual row errors. Collect all errors and report at the end. Only rows that pass validation are persisted.
- **Sheet selection**: `--sheet` flag selects the worksheet name. Default to the first sheet if not specified.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
