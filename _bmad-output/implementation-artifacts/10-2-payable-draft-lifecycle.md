---
epic: 10
story: 2
title: "Payable Draft Lifecycle (Rascunho → Pendente → Pago/Cancelado)"
type: "Core"
status: ready-for-dev
---

# Story 10.2: Payable Draft Lifecycle

## User Story
As a Manager,
I want recurring payables generated as drafts that I can fill in and save,
So that the system reminds me of fixed expenses without requiring exact values upfront.

## Acceptance Criteria

1. Payable status lifecycle enforced: `rascunho` → `pendente` → `pago` | `cancelado`.
2. `rascunho`: can edit all fields, can DELETE (hard delete).
3. `pendente`: can edit, can pay, can cancel (soft — sets `status=cancelado`, never hard delete).
4. `pago` and `cancelado`: immutable.
5. Recurring template generates payables with `status=rascunho` (update existing task).
6. SSE notification to manager: "Título de {description} gerado como rascunho — preencha o valor".
7. Frontend: visual distinction for rascunho (dashed border, pencil icon), "Preencher" button.
8. Tests: verify lifecycle transitions, verify hard delete allowed only for rascunho.

## Technical Context

### Architecture References
- `docs/architecture-recurrence-and-collection.md` Section 2

### Files to Create/Modify
```
backend-api/
├── app/api/v1/payable_routes.py            # Enforce lifecycle rules
├── app/workers/tasks/generate_recurring_payables.py  # Status=rascunho + SSE notify
frontend/
├── src/app/features/finance/payables-list.component.html  # Visual distinction
```

### Session Context
- Existing payable table already has `status` column
- SSE infrastructure exists (app/api/sse.py)

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] No regressions
