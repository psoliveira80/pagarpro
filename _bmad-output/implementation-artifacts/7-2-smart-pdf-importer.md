---
epic: 7
story: 2
title: "Smart PDF Importer"
type: "Core"
status: done
---

# Story 7.2: Smart PDF Importer

## User Story
As a Manager,
I want to upload a PDF statement,
So that even banks without OFX support work.

## Acceptance Criteria
1. Drop-zone on reconciliation page accepts `.pdf` files. Backend parses using `pdfplumber` with per-bank heuristics for BB, Itau, Bradesco, Santander, Caixa, Nubank, Inter, and C6.
2. **Given** heuristics produce < 80% confidence, **When** LLM fallback is enabled (feature flag), **Then** LLM is called with a structured-JSON prompt to extract transactions; otherwise, a manual review screen is displayed.
3. LLM call is gated by a feature flag with cost-tracking metric (Prometheus counter `llm_pdf_parse_cost_usd`).
4. Review screen: parsed rows displayed in a table where the user can mark/unmark suspicious rows before persisting.
5. Rows persisted to `bank_transactions` with `imported_from='pdf'`.
6. Deduplication by content hash (since PDFs lack FITIDs): hash of `(posted_at, amount, description_raw)` used as synthetic FITID.

## Technical Context

### Architecture References
- PDF parser: `backend-api/app/infrastructure/parsing/pdf_extract_parser.py` — per-bank heuristics using `pdfplumber >= 0.11`.
- LLM fallback: uses `ILLMProvider` port (from Story 6.4) with structured JSON output prompt.
- Celery task: `backend-api/app/workers/tasks/parse_pdf_extract.py` — async processing for large PDFs.
- Reuses `bank_transactions` table from Story 7.1.

### Files to Create/Modify
**Backend:**
- `backend-api/app/infrastructure/parsing/pdf_extract_parser.py` — pdfplumber-based parser with per-bank heuristic modules (column positions, date formats, amount formats per bank)
- `backend-api/app/application/reconciliation/import_pdf.py` — use case: parse PDF, compute confidence, optionally call LLM fallback, return parsed rows for review
- `backend-api/app/api/v1/reconciliation_routes.py` — add `POST /api/v1/reconciliation/import-pdf` (file upload), `POST /api/v1/reconciliation/import-pdf/confirm` (persist reviewed rows)
- `backend-api/app/workers/tasks/parse_pdf_extract.py` — Celery task for async PDF parsing
- `backend-api/app/infrastructure/settings.py` — add `PDF_LLM_FALLBACK_ENABLED` feature flag

**Frontend:**
- `frontend/src/app/features/finance/reconciliation/components/pdf-uploader/pdf-uploader.component.ts` — drop-zone for .pdf files
- `frontend/src/app/features/finance/reconciliation/components/pdf-uploader/pdf-uploader.component.html`
- `frontend/src/app/features/finance/reconciliation/components/pdf-uploader/pdf-uploader.component.css`
- `frontend/src/app/features/finance/reconciliation/components/pdf-review-table/pdf-review-table.component.ts` — table with checkbox per row, suspicious rows highlighted, edit capability

**Tests:**
- `backend-api/tests/unit/infrastructure/test_pdf_extract_parser.py` — test with sample statements from each bank
- `backend-api/tests/unit/application/test_import_pdf.py` — test confidence calculation, LLM fallback trigger, review flow
- `backend-api/tests/integration/test_reconciliation_import_pdf.py`

### Dependencies
- Story 7.1 (OFX Importer — `bank_transactions` table and repository).
- Story 6.4 (AI Agent Engine — `ILLMProvider` port for LLM fallback, only if LLM fallback is enabled).

### Technical Notes
- Per-bank heuristics: each bank's PDF statement has a different layout. The parser identifies the bank from header text, then applies bank-specific column extraction logic (date column position, amount sign convention, description column).
- Confidence calculation: percentage of rows where all required fields (date, amount, description) were successfully extracted. Below 80% triggers LLM fallback.
- LLM fallback prompt: send the raw text of the PDF page with instructions to extract transactions as JSON array `[{date, amount, description, type}]`. Use structured output / JSON mode.
- Synthetic FITID for PDFs: `sha256(f"{posted_at.isoformat()}|{amount}|{description_raw}")` — used for deduplication on re-import.
- The review screen is a two-step flow: 1) Upload PDF -> parse -> show review table. 2) User reviews, marks suspicious rows, confirms -> persist to `bank_transactions`.
- Large PDFs: parsing runs as a Celery task with progress reported via SSE. Frontend polls for completion.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
