---
epic: 3
story: 3
title: "Visual Installment Builder Frontend"
type: "Core"
status: done
---

# Story 3.3: Visual Installment Builder Frontend

## User Story

As a Manager,
I want a visual UI to compose installments,
So that I see the schedule before committing.

## Acceptance Criteria

1. `ScheduleBuilderComponent` in `features/system/contracts/components/schedule-builder/`.
2. Left pane: configurator (down payment toggle, regular installments, extras, grace days).
3. Right pane: preview table updated reactively via `resource()` calling preview endpoint with debounce.
4. **Given** "Custom Schedule" toggle, **Then** configurator hidden, manual editing only.
5. Preview table supports drag-and-drop (CDK) reorder, inline editing for value and date.
6. "Add installment" and "Remove" buttons.
7. Footer: total parceled, total overall, count, last date, total period.

## Technical Context

### Architecture References

- **Frontend Structure** (Section 10.1):
  - `frontend/src/app/features/system/contracts/components/schedule-builder/` — central drag-and-drop component
  - `frontend/src/app/features/system/contracts/components/schedule-preview/`
- **Shared Components**: `shared/components/data-table/`, `shared/components/drag-list/` (CDK wrapper), `shared/components/input-money/`, `shared/components/input-date/`, `shared/components/toggle/`
- **API Endpoint**: `POST /api/v1/contracts/preview-schedule` — returns computed schedule from definition
- **Angular Patterns**: `resource()` API for data fetching with debounce, Signals, CDK Drag-Drop for reorder, Reactive Forms

### Files to Create/Modify

**Create:**
- `frontend/src/app/features/system/contracts/components/schedule-builder/schedule-builder.component.ts`
- `frontend/src/app/features/system/contracts/components/schedule-builder/schedule-builder.component.html`
- `frontend/src/app/features/system/contracts/components/schedule-builder/schedule-builder.component.css`
- `frontend/src/app/features/system/contracts/components/schedule-preview/schedule-preview.component.ts`
- `frontend/src/app/features/system/contracts/components/schedule-preview/schedule-preview.component.html`
- `frontend/src/app/features/system/contracts/components/schedule-preview/schedule-preview.component.css`
- `frontend/src/app/features/system/contracts/services/contract.service.ts` — API client for preview-schedule endpoint

### Dependencies

- Story 3.2 (Installment Builder Backend — preview endpoint)
- Shared components: `drag-list`, `input-money`, `input-date`, `toggle`

### Technical Notes

- **Two-pane layout**: left pane is the configurator form (signal-driven), right pane is the preview table. Both update reactively.
- **Configurator fields**:
  - Toggle "Entrada" (down payment) -> shows amount input
  - "Parcelas regulares" -> count input + periodicity select (mensal/quinzenal/semanal)
  - "Extras semestrais" -> toggle + amount
  - "Extras anuais" -> toggle + amount
  - "Carencia (dias)" -> number input
  - Toggle "Personalizado" -> hides all above, enables manual table editing
- **Preview table reactive update**: use `resource()` calling `POST /api/v1/contracts/preview-schedule` with the current form values. Add 500ms debounce so it doesn't fire on every keystroke. The resource re-fetches whenever the definition signal changes.
- **Drag-and-drop reorder**: CDK `cdkDropList` on the preview table rows. On drop, resequence items (update `sequence` numbers) and call preview again or update locally.
- **Inline editing**: clicking a cell in the preview table (amount or date) turns it into an editable input. On blur/enter, the value is committed to the local schedule array. This enables the "Custom Schedule" mode.
- **"Add installment" button**: appends a new row to the custom schedule with default values. "Remove" button on each row removes it.
- **Footer calculations**: computed signals: `totalParceled` (sum of all amounts), `totalOverall` (same unless down payment separate), `installmentCount`, `lastDate`, `totalPeriod` (months between first and last date).
- **Output**: the component emits a `scheduleChanged` event with the final `ScheduleDefinition` for the parent wizard to consume.

## Dev Checklist

- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
