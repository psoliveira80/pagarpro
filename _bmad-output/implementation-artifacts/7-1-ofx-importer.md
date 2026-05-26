---
epic: 7
story: 1
title: "OFX Importer"
type: "Core"
status: done
---

# Story 7.1: OFX Importer

## User Story
As a Manager,
I want to upload an OFX file from my bank,
So that transactions enter the system automatically.

## Acceptance Criteria
1. Route `/system/finance/reconciliation` exposes an "Import OFX" button opening a drop-zone.
2. Drop-zone accepts `.ofx` files; backend parses via `ofxparse` library.
3. **Given** overlapping FITIDs in the uploaded file, **Then** existing transactions are skipped (deduplication via UNIQUE constraint).
4. `bank_transactions` table created with columns: `id` (UUID PK), `account_id`, `fitid`, `posted_at`, `amount` (signed decimal), `description_raw`, `description_clean`, `type`, `status` (`pendente`/`conciliada`/`ignorada`), `reconciled_to_kind` (`installment`/`payable`/`revenue`/`expense`/null), `reconciled_to_id` (UUID nullable), `imported_from` (`ofx`/`pdf`/`open_finance`/`manual`), `imported_at`; with `UNIQUE(account_id, fitid)`.
5. Pre-classification: regex/heuristics extract sender name from Pix descriptions in `description_clean`.
6. Import summary displayed after upload: total parsed, new inserted, duplicates skipped.

## Technical Context

### Architecture References
- OFX parser: `backend-api/app/infrastructure/parsing/ofx_parser.py` using `ofxparse >= 0.21`.
- Domain entity: `BankTransaction` in `backend-api/app/domain/finance/` or dedicated reconciliation context.
- API endpoints: `POST /api/v1/reconciliation/import-ofx`, `GET /api/v1/reconciliation/transactions`.
- Indexes: `idx_btx_status` on `status` WHERE `status='pendente'`, `idx_btx_posted` on `posted_at DESC`.

### Files to Create/Modify
**Backend:**
- `backend-api/app/infrastructure/parsing/ofx_parser.py` — OFX file parsing with `ofxparse`, returns list of normalized transaction dicts
- `backend-api/app/application/reconciliation/import_ofx.py` — use case: parse OFX, deduplicate by FITID, bulk insert, return summary
- `backend-api/app/api/v1/reconciliation_routes.py` — `POST /api/v1/reconciliation/import-ofx` (file upload), `GET /api/v1/reconciliation/transactions?status=&date_from=&date_to=&page=`
- `backend-api/app/infrastructure/db/models/bank_transaction.py` — `BankTransaction` ORM model
- `backend-api/app/infrastructure/db/repositories/bank_transaction_repo.py` — repository with bulk upsert (skip on conflict)
- `backend-api/app/domain/ports/repositories.py` — add `IBankTransactionRepo` protocol
- `backend-api/alembic/versions/xxxx_create_bank_transactions.py` — migration with UNIQUE constraint and indexes

**Frontend:**
- `frontend/src/app/features/finance/reconciliation/reconciliation.component.ts` — reconciliation page shell (if not yet created)
- `frontend/src/app/features/finance/reconciliation/components/ofx-uploader/ofx-uploader.component.ts` — drop-zone for .ofx files with upload progress and summary display
- `frontend/src/app/features/finance/reconciliation/components/ofx-uploader/ofx-uploader.component.html`
- `frontend/src/app/features/finance/reconciliation/components/ofx-uploader/ofx-uploader.component.css`
- `frontend/src/app/features/finance/reconciliation/reconciliation.routes.ts` — lazy-loaded route

**Tests:**
- `backend-api/tests/unit/infrastructure/test_ofx_parser.py` — test with sample OFX files
- `backend-api/tests/unit/application/test_import_ofx.py` — test deduplication, bulk insert, summary
- `backend-api/tests/integration/test_reconciliation_import_ofx.py`

### Dependencies
- Epic 1 (Database infrastructure, migrations framework).
- No dependencies on other Epic 7 stories (this is the foundation).

### Technical Notes
- `ofxparse` returns `OfxParser.parse(file).account.statement.transactions` — each has `id` (FITID), `date`, `amount`, `memo`, `type`.
- `description_clean`: strip bank-specific prefixes, normalize whitespace, extract Pix sender name via regex patterns like `PIX - (.+?) -` or `PAGAMENTO PIX (.+)`.
- The UNIQUE constraint on `(account_id, fitid)` means bulk insert should use `INSERT ... ON CONFLICT DO NOTHING` to silently skip duplicates.
- `account_id` references a bank account record; for MVP, a single default account can be assumed, with multi-account support added later.
- Signed amount: positive = credit (inbound), negative = debit (outbound). This follows OFX standard.
- The `type` column stores OFX transaction type (e.g., `debit`, `credit`, `directdebit`, `payment`, `other`).

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
