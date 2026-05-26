---
epic: 3
story: 4
title: "Contract Creation Wizard"
type: "Core"
status: done
---

# Story 3.4: Contract Creation Wizard

## User Story

As a Manager,
I want a guided wizard to create a contract,
So that data comes in cleanly and consistently.

## Acceptance Criteria

1. 4 steps: **Customer & Asset** (search-typeahead selectors for customer and asset from `assets` table), **Terms** (dates, interest/fine, purchase option), **Schedule** (Story 3.3 component), **Clauses & Review** (Tiptap rich text + PDF preview).
2. Cross-validations: customer is `ativo`, asset is `disponivel`, end_date >= start_date.
3. **Given** any step, **When** "Salvar Rascunho", **Then** persisted as `rascunho`, resumable.
4. **Given** confirm, **Then** contract -> `vigente`, PDF rendering enqueued, installments generated atomically. `ContractCreatedEvent` published.
5. Success toast with "View Contract" deep link.

## Technical Context

### Architecture References

- **Frontend Structure** (Section 10.1):
  - `frontend/src/app/features/system/contracts/contract-wizard.component.ts` — 4-step wizard
  - `frontend/src/app/features/system/contracts/components/schedule-builder/` — Story 3.3
  - `frontend/src/app/features/system/contracts/components/contract-pdf-viewer/`
- **Shared Components**: `shared/components/stepper/`, `shared/components/select-async/` (typeahead), `shared/components/input-date/`, `shared/components/input-money/`, `shared/components/toggle/`, `shared/components/toast/`
- **API Endpoints**:
  - `POST /api/v1/contracts` — create (rascunho)
  - `PATCH /api/v1/contracts/{id}` — update rascunho
  - `POST /api/v1/contracts/{id}/activate` — vigente (generates installments + PDF)
  - `GET /api/v1/customers` — search customers
  - `GET /api/v1/assets` — search assets
- **Use Cases**:
  - `backend-api/app/application/contracts/activate_contract.py` — activate: generate installments, enqueue PDF, publish ContractCreatedEvent

### Files to Create/Modify

**Create (Frontend):**
- `frontend/src/app/features/system/contracts/contract-wizard.component.ts`
- `frontend/src/app/features/system/contracts/contract-wizard.component.html`
- `frontend/src/app/features/system/contracts/contract-wizard.component.css`
- `frontend/src/app/features/system/contracts/contracts.routes.ts` — routes for wizard (`/contracts/new`), list, detail

**Create (Backend):**
- `backend-api/app/application/contracts/activate_contract.py` — use case: validate, change status to `vigente`, generate installments (using `schedule_calculator`), create `contract_events.installments_generated`, enqueue PDF render task, publish `ContractCreatedEvent`
- `backend-api/app/api/v1/contract_routes.py` — add `POST /{id}/activate` endpoint (if not already present)
- `backend-api/tests/integration/test_contract_activation.py`

**Modify:**
- `frontend/src/app/features/system/system.routes.ts` — add contracts routes
- `frontend/src/app/features/system/contracts/services/contract.service.ts` — add create, update, activate methods

### Dependencies

- Story 3.1 (Contract domain model)
- Story 3.2 (Installment Builder Backend — preview + persist)
- Story 3.3 (Visual Installment Builder Frontend — schedule-builder component)
- Story 3.5 (Contract PDF Generation — PDF task is enqueued on activation)

### Technical Notes

- **Step 1 — Customer & Asset**: two `select-async` components. Customer search queries `GET /api/v1/customers?search=...` filtered to `status='ativo'`. Asset search queries `GET /api/v1/assets?status=disponivel&search=...`. Both display name + identifier.
- **Step 2 — Terms**: form fields for `start_date`, `end_date`, `periodicity` (select), `due_day` (1-28), `late_interest_pct_per_day`, `late_fine_pct`, `grace_days`, `has_purchase_option` (toggle), `residual_value` (shown if purchase option on). Cross-validation: `end_date >= start_date`.
- **Step 3 — Schedule**: embed `ScheduleBuilderComponent` (Story 3.3). Pass `total_amount` computed from terms. The builder calls the preview endpoint and shows the installment table.
- **Step 4 — Clauses & Review**: Tiptap rich-text editor for `terms_md` (contract clauses). Below, a read-only summary of all previous steps. "Preview PDF" button calls the preview endpoint or renders a local approximation.
- **"Salvar Rascunho" button**: available at every step. Calls `POST /api/v1/contracts` (first save) or `PATCH /api/v1/contracts/{id}` (subsequent). Shows toast "Rascunho salvo".
- **"Finalizar" button**: only on step 4. Calls `POST /api/v1/contracts/{id}/activate`. On success, shows toast with "Ver Contrato" link navigating to `/contracts/{id}`.
- **Backend activate_contract use case**: (1) validate contract is `rascunho`, (2) validate customer active + asset disponivel, (3) set status to `vigente`, (4) call `compute_schedule` to generate installments, (5) bulk insert installments, (6) create `contract_events` entry type `installments_generated`, (7) enqueue Celery task `render_contract_pdf`, (8) publish `ContractCreatedEvent` to EventBus, (9) update asset status to `em_contrato`.

## Dev Checklist

- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
