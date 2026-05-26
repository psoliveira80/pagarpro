---
epic: 3
story: 5
title: "Contract PDF Generation"
type: "Core"
status: done
---

# Story 3.5: Contract PDF Generation

## User Story

As the System,
I want to render a professional PDF from each contract,
So that the manager can print or send it.

## Acceptance Criteria

1. Celery task `render_contract_pdf(contract_id)` loads contract + customer + asset details (via `IAssetModule.get_asset_details()`) + installments, renders Jinja2 -> HTML -> WeasyPrint -> PDF.
2. Template in `app/infrastructure/pdf/templates/contract.html.j2` with configurable clauses, data, installment table, signature space.
3. PDFs stored in MinIO at `contracts/{contract_id}/v{version}.pdf`; URL saved in `contract.pdf_url`.
4. SHA-256 hash recorded in `contract_events.pdf_generated`.
5. On contract edit, version increments; prior versions remain accessible.
6. `GET /api/v1/contracts/{id}/pdf?version=` returns presigned MinIO URL (5-min TTL).

## Technical Context

### Architecture References

- **FR-CORE-CTR-4**: PDF rendering (Jinja2 + WeasyPrint), stored in S3-compatible storage with SHA-256 hash
- **Infrastructure** (Section 6):
  - `backend-api/app/infrastructure/pdf/weasyprint_renderer.py`
  - `backend-api/app/infrastructure/pdf/templates/contract.html.j2`
- **Celery Tasks** (Section 6): `backend-api/app/workers/tasks/render_contract_pdf.py`
- **Storage**: MinIO via `IStorageProvider` — `backend-api/app/infrastructure/integrations/storage/s3_compatible_adapter.py`
- **API Endpoint**: `GET /api/v1/contracts/{id}/pdf?version=` — presigned URL
- **Domain Ports**: `IPdfRenderer` in `backend-api/app/domain/ports/pdf_renderer.py`, `IStorageProvider` in `backend-api/app/domain/ports/storage_provider.py`
- **IAssetModule**: `get_asset_details(asset_id)` provides module-specific data for the PDF template

### Files to Create/Modify

**Create:**
- `backend-api/app/infrastructure/pdf/weasyprint_renderer.py` — `WeasyPrintRenderer(IPdfRenderer)` implementation
- `backend-api/app/infrastructure/pdf/templates/contract.html.j2` — Jinja2 HTML template with: header (company info), parties (customer + asset details), terms table, installment schedule table, clauses (from `terms_md`), signature space, footer
- `backend-api/app/workers/tasks/render_contract_pdf.py` — Celery task: load data, render PDF, upload to MinIO, record hash in contract_events
- `backend-api/app/application/contracts/render_pdf.py` — use case orchestrating the render flow
- `backend-api/app/domain/ports/pdf_renderer.py` — `IPdfRenderer` Protocol with `render_html_to_pdf(html: str) -> bytes`
- `backend-api/tests/unit/test_pdf_render_task.py`
- `backend-api/tests/integration/test_contract_pdf_endpoint.py`

**Modify:**
- `backend-api/app/api/v1/contract_routes.py` — add `GET /{id}/pdf` endpoint returning presigned MinIO URL
- `backend-api/app/infrastructure/db/models/contract.py` — ensure `pdf_url` and `version` fields are present
- `backend-api/app/core/di.py` — wire `IPdfRenderer` -> `WeasyPrintRenderer`

### Dependencies

- Story 3.1 (Contract model with `pdf_url`, `version`, `contract_events` table)
- Story 3.4 (Contract activation enqueues PDF render task)
- Epic 1 (MinIO/IStorageProvider, Celery infrastructure)

### Technical Notes

- **Render flow**: (1) Load contract with relationships (customer, asset). (2) If asset has a module, call `ModuleRegistry.get(asset_type).get_asset_details(asset_id)` for extra data (e.g., vehicle plate, model). (3) Render `contract.html.j2` with Jinja2 context. (4) Pass HTML to WeasyPrint to get PDF bytes. (5) Compute SHA-256 hash. (6) Upload to MinIO at path `contracts/{contract_id}/v{version}.pdf`. (7) Update `contract.pdf_url`. (8) Insert `contract_events` row with `event_type='pdf_generated'`, `payload={version, hash, size}`, `pdf_hash=hash`.
- **Template design**: clean, professional layout. Use CSS for print. Include: company logo/name (from Settings), contract number, date, customer info, asset info (generic + module-specific), terms table (periodicity, interest, fine, grace), full installment schedule table (sequence, due_date, amount, kind), clauses section (rendered markdown from `terms_md`), signature lines.
- **Versioning**: `contract.version` starts at 1 and increments on each edit. Prior PDFs remain in MinIO. `GET /pdf?version=2` fetches the specific version; no version param returns latest.
- **Presigned URL**: MinIO/S3 presigned GET URL with 5-minute expiry. The endpoint returns `{url: "https://...", expires_in: 300}`.
- **WeasyPrint** must be installed as a system dependency (requires cairo, pango, etc.). Dockerfile must include these.

## Dev Checklist

- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
