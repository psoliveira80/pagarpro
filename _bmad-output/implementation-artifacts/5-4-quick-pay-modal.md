---
epic: 5
story: 4
title: "Quick Pay Modal"
type: "Core"
status: done
---

# Story 5.4: Quick Pay Modal

## User Story
As a Manager,
I want a fast shortcut to record an expense already paid,
So that instant logging is trivial.

## Acceptance Criteria

1. Floating "Lancar e Pagar" button (FAB) available on every screen + command palette.
2. Compact modal: description, supplier (autocomplete + create-inline), category, amount, date (default today), method, attachment, asset (optional).
3. **Given** confirm, **Then** payable created with `status='pago'` in single atomic transaction.

## Technical Context

### Architecture References
- **Architecture Section 5 (API Endpoints)**: `POST /api/v1/payables/quick-pay` — atomic create + pay.
- **Architecture Section 10.1 (Frontend Structure)**: `frontend/src/app/features/system/finance/payables/quick-pay-modal.component.ts`.
- **Architecture Section 10.1 (Frontend Structure)**: Command palette at `frontend/src/app/shared/components/command-palette/`.

### Files to Create/Modify
```
backend-api/
├── app/api/v1/payable_routes.py               # POST /payables/quick-pay (from Story 5.2)
├── app/application/finance/quick_pay.py       # use case: atomic create + pay (from Story 5.2)

frontend/
├── src/app/features/system/finance/payables/
│   ├── quick-pay-modal.component.ts           # compact modal with all fields
│   ├── quick-pay-modal.component.html
│   └── quick-pay-modal.component.css
├── src/app/features/system/components/
│   └── quick-pay-fab/
│       ├── quick-pay-fab.component.ts         # floating action button visible on all system pages
│       ├── quick-pay-fab.component.html
│       └── quick-pay-fab.component.css
├── src/app/shared/components/command-palette/
│   └── command-palette.component.ts           # register "Lancar e Pagar" command (modify existing)
```

### Dependencies
- Story 5.1 (Categories & Suppliers — category select, supplier autocomplete with inline create).
- Story 5.2 (Payables Domain — the `quick-pay` endpoint and use case).
- Shared `modal`, `select-async`, `input-money`, `file-dropzone` components.
- Command palette infrastructure.

### Technical Notes
- The FAB ("Lancar e Pagar") is placed in the system shell layout (`system.component.ts`) so it appears on every authenticated page. It is a fixed-position button (bottom-right corner).
- The command palette (Ctrl+K) should include a "Lancar e Pagar" / "Quick Pay" action that opens the same modal.
- Supplier field uses `select-async` with server-side search (`GET /api/v1/suppliers?search=`). An inline "Create new supplier" link opens a minimal inline form (name + document) without navigating away — the new supplier is created via `POST /api/v1/suppliers` and immediately selected.
- Category field is a hierarchical select showing the category tree from Story 5.1.
- Amount uses `input-money` component with BRL formatting.
- Date defaults to today but can be changed (for retroactive logging).
- Asset field is optional — uses `select-async` searching assets.
- On confirm, a single `POST /api/v1/payables/quick-pay` call creates the payable with `status='pago'` atomically. Success shows a toast; the modal closes.
- Attachment is optional — uploaded via the file dropzone and stored via `IStorageProvider`.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
