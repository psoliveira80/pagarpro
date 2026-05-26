---
epic: 4
story: 3
title: "Manual Write-Off Modal"
type: "Core"
status: done
---

# Story 4.3: Manual Write-Off Modal

## User Story
As a Manager,
I want to write off an installment by entering payment data,
So that the title leaves "open" status.

## Acceptance Criteria

1. Modal: effective date (default today), paid amount (default `updated_value`), method (Pix/cash/transfer/card/other), notes, attachment drop-zone (required for Pix).
2. **Given** Pix and receipt uploaded, **Then** OCR runs in background, auto-populates value and date if confidence >= 70%.
3. **Given** Pix write-off confirmed, **Then** status -> `pago_aguardando_verificacao`.
4. **Given** cash or in-person card, **Then** status -> `pago_aguardando_verificacao`.
5. List refreshes; success toast shown.

## Technical Context

### Architecture References
- **Architecture Section 5 (API Endpoints)**: `POST /api/v1/receivables/{id}/write-off` — manual write-off with receipt upload.
- **Architecture Section 10.1 (Frontend Structure)**: `frontend/src/app/features/system/finance/receivables/write-off-modal.component.ts`.
- **Architecture Section 6 (Backend Modules)**: `app/application/finance/write_off_installment.py` use case.
- **Architecture Section 4.1 (Domain Entities)**: Installment status state machine — `em_aberto`/`vencido` -> `pago_aguardando_verificacao`.

### Files to Create/Modify
```
backend-api/
├── app/api/v1/receivable_routes.py            # POST /receivables/{id}/write-off
├── app/application/finance/write_off_installment.py  # orchestrate: validate, update status, store receipt, trigger OCR
├── app/domain/finance/policies.py             # write-off rules (status transitions, required fields)
├── app/domain/finance/events.py               # InstallmentWrittenOff event

frontend/
├── src/app/features/system/finance/receivables/
│   ├── write-off-modal.component.ts           # modal with form fields + file dropzone
│   ├── write-off-modal.component.html
│   └── write-off-modal.component.css
```

### Dependencies
- Story 4.1 (Receivables List — triggers the modal).
- Story 4.2 (Updated value calculation — pre-fills `paid_amount`).
- Story 4.5 (OCR Provider — for background receipt processing on Pix uploads).
- Shared `file-dropzone` component.
- Shared `modal` component.

### Technical Notes
- When method is `Pix`, attachment is **required**; for other methods it is optional.
- On Pix upload, dispatch a background Celery task to run OCR (Story 4.5). If OCR confidence >= 70%, auto-populate `paid_amount` and `effective_date` via SSE push to the frontend.
- Status transition logic belongs in `domain/finance/policies.py` — enforce that only `em_aberto` or `vencido` installments can be written off.
- Receipt file stored via `IStorageProvider` (MinIO/S3), URL saved to `installment.receipt_url`.
- Publish `InstallmentWrittenOff` domain event for downstream consumers.
- After successful write-off, emit SSE notification so the receivables list auto-refreshes.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
