---
epic: 4
story: 1
title: "Master Receivables List"
type: "Core"
status: done
---

# Story 4.1: Master Receivables List

## User Story
As a Manager,
I want to see every receivable in one powerful table,
So that I can operate financials at scale.

## Acceptance Criteria

1. Route `/system/finance/receivables` renders `ReceivablesListComponent`.
2. Filters: status (multi-select), customer, asset, contract, due-date range, value range.
3. Columns: due date, customer (avatar), asset, contract (link), original value, updated value (interest/fine), status (badge), method, row actions.
4. Row actions: Write-off, Partial Write-off, View, Edit (if open), Cancel (if open).
5. Footer totals: "Selected: R$ X | Filter total: R$ Y | Delinquency: R$ Z".
6. Keyboard shortcuts: `b` writes off selected, `Space` selects, `f` focuses filters.

## Technical Context

### Architecture References
- **Architecture Section 5 (API Endpoints)**: `GET /api/v1/receivables` — filtered list with pagination, sorting, status multi-select.
- **Architecture Section 10.1 (Frontend Structure)**: `frontend/src/app/features/system/finance/receivables/receivables-list.component.ts`.
- **Architecture Section 4.1 (Domain Entities)**: `Installment` entity with statuses `em_aberto`, `vencido`, `pago_aguardando_verificacao`, `pago`, `pago_parcial`, `renegociado`, `cancelado`.
- **Architecture Section 2.5 (Frontend Pattern)**: Signals + `resource()` API for data fetching; zero NgRx.

### Files to Create/Modify
```
backend-api/
├── app/api/v1/receivable_routes.py            # GET /receivables with filter/sort/pagination
├── app/application/finance/list_receivables.py # use case: query with filters
├── app/infrastructure/db/repositories/installment_repo.py  # add filtered query methods

frontend/
├── src/app/features/system/finance/receivables/
│   ├── receivables-list.component.ts          # main list with data-table, filters, footer totals
│   ├── receivables-list.component.html
│   ├── receivables-list.component.css
│   └── receivables.routes.ts                  # lazy route /system/finance/receivables
├── src/app/features/system/finance/receivables/services/
│   └── receivables.service.ts                 # HttpClient calls to /api/v1/receivables
```

### Dependencies
- Shared `data-table` component (Epic 1 shared UI).
- Shared `badge` component for status rendering.
- Shared `shortcut.directive.ts` for keyboard shortcuts.
- `Installment` domain model and ORM mapping from Epic 3.

### Technical Notes
- Use `resource()` signal API for server-side filtered data fetching.
- Footer totals should be computed server-side via aggregate query and returned alongside paginated results (separate `totals` field in the API response envelope).
- Status badges should use `installment-status.pipe.ts` for enum-to-label mapping.
- Keyboard shortcuts (`b`, `Space`, `f`) bound via `shortcut.directive.ts` on the host element.
- Row actions open modals defined in Stories 4.3 (Write-off), 4.4 (Partial Write-off), 4.7 (Pix QR).

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
