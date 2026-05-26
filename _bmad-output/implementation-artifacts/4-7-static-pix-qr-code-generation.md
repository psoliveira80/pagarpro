---
epic: 4
story: 7
title: "Static Pix QR Code Generation"
type: "Core"
status: done
---

# Story 4.7: Static Pix QR Code Generation

## User Story
As the System,
I want to generate a Pix BR Code per installment,
So that collections are immediately payable at zero cost.

## Acceptance Criteria

1. Company Pix key configured in Settings > Company (key + beneficiary name).
2. `GET /api/v1/receivables/{id}/pix-qr` returns SVG/PNG QR + "Copy and Paste" BR Code text.
3. Uses `pix-utils` following BCB MN-002 spec.
4. TXID embeds installment ID for reconciliation.
5. Receivable detail: "Generate Pix QR" button opens modal with QR + "Send via WhatsApp" CTA.

## Technical Context

### Architecture References
- **Architecture Section 3.1 (Tech Stack)**: `pix-utils` (or custom implementation) for BR Code generation, latest version.
- **Architecture Section 5 (API Endpoints)**: `GET /api/v1/receivables/{id}/pix-qr` — QR Code Pix BR Code.
- **Architecture Section 10.1 (Frontend Structure)**: `frontend/src/app/features/system/finance/receivables/pix-qr-modal.component.ts`.
- **Architecture Section 2.1 (Design Decisions)**: Default payment = Pix via WhatsApp (zero cost); gateways are optional plugins.

### Files to Create/Modify
```
backend-api/
├── app/api/v1/receivable_routes.py            # GET /receivables/{id}/pix-qr
├── app/application/finance/generate_pix_qr.py # use case: build BR Code, render QR image
├── app/domain/finance/pix_brcode.py           # pure function: build BR Code string per BCB MN-002
├── app/infrastructure/db/models/company_settings.py  # pix_key, beneficiary_name fields (if not existing)
├── app/tests/unit/domain/finance/
│   └── test_pix_brcode.py                     # BR Code format validation tests

frontend/
├── src/app/features/system/finance/receivables/
│   ├── pix-qr-modal.component.ts              # modal: QR image + copy-paste BR Code + WhatsApp CTA
│   ├── pix-qr-modal.component.html
│   └── pix-qr-modal.component.css
```

### Dependencies
- `pix-utils` Python package (or equivalent) in `pyproject.toml`.
- `qrcode` Python package for SVG/PNG rendering.
- Company settings with Pix key configuration (Admin/Settings feature).
- Story 4.1 (Receivables List — "Generate Pix QR" button in row actions or detail view).

### Technical Notes
- BR Code generation follows BCB MN-002 (Manual Normativo de Arranjos de Pagamentos):
  - Payload format: EMV QR Code static with merchant info, amount, and TXID.
  - TXID should embed the installment ID (e.g., `INST{installment_id}`) for future reconciliation.
- `pix_brcode.py` is a **pure function** that takes `pix_key`, `beneficiary_name`, `amount`, `city`, `txid` and returns the BR Code string.
- QR image rendered server-side using `qrcode` library; response includes both `image_base64` (SVG or PNG) and `brcode_text` (copy-paste payload).
- Frontend modal displays the QR image, a text field with the BR Code (with copy button), and a "Send via WhatsApp" CTA (dispatches to Epic 6 when available).
- Company Pix key is stored in a settings table; if not configured, the endpoint returns 422 with a clear error message guiding the admin to configure it.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
