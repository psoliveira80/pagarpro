---
epic: 4
story: 6
title: "Receipt Validation Queue"
type: "Core"
status: done
---

# Story 4.6: Receipt Validation Queue

## User Story
As a Validator,
I want a queue of pending receipts,
So that I can validate quickly in batch.

## Acceptance Criteria

1. Route `/system/finance/validation-queue` lists installments in `pago_aguardando_verificacao` ordered by date ascending.
2. Split layout: list left, file viewer center (image/PDF with zoom), right pane with title data and Approve/Reject/Request Resubmission.
3. Keyboard: `A` approve, `R` reject, arrow next/previous.
4. **Given** approve, **Then** status -> `pago_aguardando_verificacao`, `audit_log` event with `validated_by_user_id`.
5. **Given** reject, **Then** reason required (predefined + free text).
6. **Given** "Request Resubmission", **Then** WhatsApp message dispatched (uses Epic 6), status unchanged.
7. Top KPIs: pending, validated today, rejected today.

## Technical Context

### Architecture References
- **Architecture Section 5 (API Endpoints)**: `GET /api/v1/receivables/validation-queue`, `POST /api/v1/receivables/{id}/validate`, `POST /api/v1/receivables/{id}/request-resubmission`.
- **Architecture Section 10.1 (Frontend Structure)**: `frontend/src/app/features/system/finance/receivables/validation-queue.component.ts`.
- **Architecture Section 6 (Backend Modules)**: `app/application/finance/validate_receipt.py` use case.
- **Architecture Section 4.1 (Domain Entities)**: Installment status transition `pago_aguardando_verificacao` on approval.

### Files to Create/Modify
```
backend-api/
├── app/api/v1/receivable_routes.py            # GET /receivables/validation-queue, POST /receivables/{id}/validate, POST /receivables/{id}/request-resubmission
├── app/application/finance/validate_receipt.py # use case: approve/reject with audit log
├── app/application/finance/request_resubmission.py  # use case: trigger WhatsApp message

frontend/
├── src/app/features/system/finance/receivables/
│   ├── validation-queue.component.ts          # 3-pane split layout
│   ├── validation-queue.component.html
│   └── validation-queue.component.css
├── src/app/features/system/finance/receivables/components/
│   ├── receipt-viewer/
│   │   ├── receipt-viewer.component.ts        # image/PDF viewer with zoom
│   │   ├── receipt-viewer.component.html
│   │   └── receipt-viewer.component.css
│   └── validation-actions/
│       ├── validation-actions.component.ts    # approve/reject/resubmit buttons + reason form
│       ├── validation-actions.component.html
│       └── validation-actions.component.css
```

### Dependencies
- Story 4.3 (Write-Off Modal — creates installments in `pago_aguardando_verificacao` status).
- Shared `pdf-viewer` component.
- Shared `kpi-card` component for top KPIs.
- Shared `shortcut.directive.ts` for keyboard navigation.
- Epic 6 (WhatsApp Gateway) for "Request Resubmission" — can be stubbed initially.

### Technical Notes
- The validation queue endpoint returns installments filtered by `status='pago_aguardando_verificacao'`, ordered by `due_date ASC`.
- Split layout uses CSS Grid with 3 columns: list (25%), file viewer (45%), action pane (30%).
- Approve action: transition status to `pago_aguardando_verificacao`, create `audit_log` entry with `validated_by_user_id` and timestamp.
- Reject action: requires a reason (select from predefined list + optional free text). Status reverts to a rejection state or stays for re-upload.
- "Request Resubmission" dispatches a WhatsApp message to the customer requesting a clearer receipt. If Epic 6 is not yet implemented, log the intent and show a toast indicating the message will be sent when WhatsApp integration is active.
- KPIs (`pending`, `validated_today`, `rejected_today`) fetched via a separate lightweight endpoint or included in the queue response metadata.
- Arrow keys navigate the list; `A`/`R` trigger approve/reject with confirmation.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
