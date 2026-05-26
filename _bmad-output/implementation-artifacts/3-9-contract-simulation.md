---
epic: 3
story: 9
title: "Contract Simulation"
type: "Core"
status: done
---

# Story 3.9: Contract Simulation

## User Story

As a Manager,
I want to simulate a contract without persisting,
So that I can explore scenarios before committing.

## Acceptance Criteria

1. `POST /api/v1/contracts/simulate` accepts full contract + schedule definition, returns computed installments and totals.
2. No database writes; uses the same `schedule_calculator.py` pure function.
3. Frontend preview modal shows all installments with totals.

## Technical Context

### Architecture References

- **FR-CORE-CTR-10**: Contract simulation without persistence
- **Domain Pure Function**: `backend-api/app/domain/contracts/schedule_calculator.py` — same function used by preview-schedule and contract creation
- **API Endpoint**: `POST /api/v1/contracts/simulate` (new, similar to preview-schedule but includes full contract context)

### Files to Create/Modify

**Create (Backend):**
- `backend-api/app/application/contracts/simulate_contract.py` — use case: validate input, call schedule_calculator, compute totals (total amount, total interest if applicable, payment period, monthly average), return full simulation result without DB write
- `backend-api/app/api/v1/schemas/contracts.py` — add `ContractSimulationRequestDTO`, `ContractSimulationResponseDTO` (includes installments list + summary totals)
- `backend-api/tests/unit/application/contracts/test_simulate_contract.py`

**Create (Frontend):**
- `frontend/src/app/features/system/contracts/components/simulation-modal/simulation-modal.component.ts`
- `frontend/src/app/features/system/contracts/components/simulation-modal/simulation-modal.component.html`
- `frontend/src/app/features/system/contracts/components/simulation-modal/simulation-modal.component.css`

**Modify:**
- `backend-api/app/api/v1/contract_routes.py` — add `POST /simulate` endpoint
- `frontend/src/app/features/system/contracts/contracts-list.component.ts` — add "Simular Contrato" button opening the simulation modal
- `frontend/src/app/features/system/contracts/services/contract.service.ts` — add `simulate(payload)` method

### Dependencies

- Story 3.2 (Schedule calculator — reused pure function)
- Story 3.3 (Schedule Builder — reused component for input)

### Technical Notes

- **Difference from preview-schedule**: the simulate endpoint accepts the full contract context (customer info for display, asset info, terms, schedule definition) and returns a richer response including: all installments, summary totals (total_amount, count, first_due_date, last_due_date, monthly_average, total_with_extras), and optionally a cost breakdown (interest cost if applicable).
- **No DB writes**: this endpoint does not touch the database at all. It's a pure computation endpoint. No audit log needed.
- **Use case**: receives `ContractSimulationRequestDTO`, validates the schedule definition (same validations as preview-schedule), calls `compute_schedule()`, then computes summary statistics, returns `ContractSimulationResponseDTO`.
- **Frontend modal**: opens from the contracts list page (or a dedicated "Simulador" nav item). Contains a simplified version of the contract wizard (terms + schedule builder), plus a "Simular" button that calls the endpoint and displays results in a table below. No persistence, no stepper — just a form + result.
- **Response DTO**:
  ```
  {
    installments: [{sequence, due_date, amount, kind}],
    summary: {
      total_amount, installment_count, first_due_date, last_due_date,
      monthly_average, has_down_payment, down_payment_amount,
      extras_total, regular_total
    }
  }
  ```
- Permission: any authenticated user with `contracts.read` permission can simulate (since no data is created).

## Dev Checklist

- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
