---
epic: 2B
story: 10
title: "Excel One-Shot Importer — Vehicles"
type: "Vehicle Module"
status: done
---

# Story 2B.10: Excel One-Shot Importer — Vehicles

## User Story

As a Manager going live,
I want to import existing vehicles from a spreadsheet,
So that I don't re-type fleet data.

## Acceptance Criteria

1. CLI `python -m app.cli import-excel --entity=vehicles --file=veiculos.xlsx` maps columns into vehicles table and syncs with core `assets`.
2. `--dry-run` validates and prints report without persisting.
3. Re-run with same input: existing records matched by plate are updated (idempotent).
4. End-of-run report: created, updated, skipped (with reasons).
5. Import writes a summary `audit_log` entry.

## Technical Context

### Architecture References

- **CLI Structure** (Section 6): `backend-api/app/cli/` — CLI commands
- **Additional Requirements**: CLI `python -m app.cli import-excel` with idempotent re-runs and `--dry-run`
- **Vehicle Model**: `vehicles` table with `plate` as unique key for matching
- **Core Assets Sync**: each imported vehicle must also create/update a record in `assets` table with `asset_type='vehicle'`
- **Audit**: `audit_log` with `action='vehicle.import'`, summary payload

### Files to Create/Modify

**Create:**
- `backend-api/app/cli/import_excel.py` — CLI command with `--entity`, `--file`, `--dry-run` flags
- `backend-api/app/modules/vehicles/services/vehicle_importer.py` — import logic: read Excel, validate rows, match by plate, create/update, sync assets
- `backend-api/tests/unit/modules/vehicles/test_vehicle_importer.py`
- `backend-api/tests/fixtures/veiculos_sample.xlsx` — test fixture with sample vehicle data

**Modify:**
- `backend-api/app/cli/__init__.py` — register `import-excel` command

### Dependencies

- Story 2B.3 (Vehicle model and CRUD service)
- Story 2B.1 (Vehicle Module structure)
- Epic 1 (CLI infrastructure, audit_log)

### Technical Notes

- **Excel parsing**: use `openpyxl` for `.xlsx` files. First row is headers. Column mapping should be configurable or convention-based: `placa` -> `plate`, `marca` -> `brand`, `modelo` -> `model`, `ano_modelo` -> `year_model`, `ano_fabricacao` -> `year_manufacture`, `cor` -> `color`, `combustivel` -> `fuel`, `km_inicial` -> `km_initial`, `valor_compra` -> `purchase_value`, `renavam` -> `renavam`, `chassi` -> `chassis`, `data_aquisicao` -> `acquisition_date`.
- **Validation per row**: validate plate format (Mercosul or legacy), required fields (plate, brand, model, year_model, year_manufacture), numeric fields. Collect validation errors per row.
- **Idempotency**: match by `plate` (UNIQUE). If vehicle with same plate exists, update fields. If not, create new. Track created/updated/skipped counts.
- **Asset sync**: for each created vehicle, also create `assets` row. For each updated vehicle, update corresponding `assets` row.
- **Dry-run mode**: validate all rows, print report with row-by-row status (OK, ERROR with reason, WILL_UPDATE, WILL_CREATE), but do NOT persist to database.
- **End-of-run report**: print to stdout: `Created: N, Updated: M, Skipped: K (with reasons)`. Also write a single `audit_log` entry with `action='vehicle.import'`, `payload_after={created: N, updated: M, skipped: K, filename: '...'}`.
- **Transaction**: wrap entire import in a single DB transaction. On any unrecoverable error, roll back everything.
- CLI entry point: `python -m app.cli import-excel --entity=vehicles --file=veiculos.xlsx [--dry-run]`.

## Dev Checklist

- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
