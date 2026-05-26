---
epic: 3
story: 1
title: "Contract, Installment, ContractEvent Domain Model"
type: "Core"
status: done
---

# Story 3.1: Contract, Installment, ContractEvent Domain Model

## User Story

As a Backend developer,
I want the contracts domain modeled in the database,
So that financial rules have a correct foundation.

## Acceptance Criteria

1. `contracts` table: id, customer_id, asset_id (FK to `assets`), status (`rascunho`/`vigente`/`encerrado`/`rescindido`), start_date, end_date, total_amount, periodicity, due_day, late_interest_pct_per_day, late_fine_pct, grace_days, has_purchase_option, residual_value, terms_md, pdf_url, version, created_by, signed_at, terminated_at, termination_reason, soft delete.
2. `installments` table: id, contract_id, sequence, due_date, amount, status (`em_aberto`/`vencido`/`pago_aguardando_verificacao`/`pago`/`pago_parcial`/`renegociado`/`cancelado`), kind (`regular`/`down_payment`/`extra_semestral`/`extra_anual`/`custom`), paid_at, paid_amount, payment_method, receipt_url, notes, parent_installment_id (nullable — reference to original title in partial payment), `UNIQUE(contract_id, sequence)`.
3. `contract_events` table (append-only): id, contract_id, event_type, payload (JSONB), pdf_hash, created_by, created_at. Types: `created`, `signed`, `installments_generated`, `installments_reissued`, `bulk_edit`, `cancellation_requested`, `terminated`, `pdf_generated`.
4. `installment_adjustments` table (append-only): id, installment_id, kind (`discount`/`fine`/`interest`/`renegotiation`/`bulk_edit`/`partial_payment`/`reverse_write_off`), amount_delta, snapshot_before, snapshot_after, reason, applied_by, applied_at.
5. PG trigger `enforce_paid_immutability`: **Given** installment status is `pago`, **When** UPDATE attempts to change `amount`, `due_date`, `paid_at`, `paid_amount`, or revert status, **Then** exception raised. Exception: status -> `cancelado` only when session var `app.reverse_write_off=true`.
6. Indexes: `installments(contract_id)`, `installments(due_date, status)`, `installments(status)`.
7. On contract finalization (status -> `vigente`), publish `ContractCreatedEvent` on event bus.

## Technical Context

### Architecture References

- **DB Schema** (Section 9.6): Full DDL for `contracts`, `installments`, `installment_adjustments`, `contract_events` tables with all constraints, indexes, and triggers
- **ENUMs** (Section 9.1): `contract_status`, `periodicity`, `installment_kind`, `installment_status`, `payment_method`
- **Domain Entities** (Section 4.2 — Contracts):
  - `Contract` (Aggregate Root): all fields listed
  - `Installment` (Entity child of Contract)
  - `InstallmentAdjustment` (append-only child)
  - `ContractEvent` (append-only child)
- **Domain Events** (Section 7.3): `ContractCreatedEvent` with `contract_id`, `asset_id`, `asset_type`
- **Trigger**: `enforce_paid_immutability` — blocks UPDATE on paid installments except `cancelado` via `app.reverse_write_off=true` session var

### Files to Create/Modify

**Create:**
- `backend-api/app/domain/contracts/contract.py` — `Contract` domain entity
- `backend-api/app/domain/contracts/installment.py` — `Installment` domain entity with state machine methods
- `backend-api/app/domain/contracts/events.py` — `ContractCreated`, `ContractTerminated`, `InstallmentsGenerated`, `InstallmentsReissued`
- `backend-api/app/infrastructure/db/models/contract.py` — SQLAlchemy ORM model for `contracts`
- `backend-api/app/infrastructure/db/models/installment.py` — SQLAlchemy ORM model for `installments`
- `backend-api/app/infrastructure/db/models/contract_event.py` — SQLAlchemy ORM model for `contract_events`
- `backend-api/app/infrastructure/db/models/installment_adjustment.py` — SQLAlchemy ORM model for `installment_adjustments`
- `backend-api/app/infrastructure/db/repositories/contract_repo.py` — `ContractRepository(IContractRepo)`
- `backend-api/app/infrastructure/db/repositories/installment_repo.py` — `InstallmentRepository(IInstallmentRepo)`
- `backend-api/app/domain/ports/repositories.py` — add `IContractRepo`, `IInstallmentRepo` protocols (if not already present)
- Alembic migration — create all 4 tables, ENUMs, indexes, trigger `enforce_paid_immutability`, trigger for `contract_events` append-only
- `backend-api/tests/unit/domain/contracts/test_contract_entity.py`
- `backend-api/tests/unit/domain/contracts/test_installment_entity.py`
- `backend-api/tests/integration/test_paid_immutability_trigger.py`

### Dependencies

- Epic 1 (Foundation: DB infrastructure, Alembic, EventBus, audit_log)
- Story 2A.2 (Core assets table — `asset_id` FK target)
- Story 2A.1 (Customers table — `customer_id` FK target)

### Technical Notes

- **Immutability trigger**: The PG trigger `enforce_paid_immutability` is critical. It must block changes to `amount`, `due_date`, `paid_at`, `paid_amount`, or status reversion on rows where `status='pago'`. The only exception is setting status to `cancelado` when the session variable `app.reverse_write_off` is set to `'true'` (used by Admin reverse-write-off operation).
- **Contract domain entity** should have methods: `activate()` (rascunho -> vigente), `terminate(reason)`, `increment_version()`.
- **Installment domain entity** should have methods: `mark_overdue()`, `write_off(paid_amount, paid_at, method, receipt_url, new_status)`, `cancel()`, `create_remainder(amount, due_date)`.
- **ContractEvent** is append-only: no UPDATE/DELETE trigger similar to `audit_log`.
- **Event publishing**: when `contract.activate()` is called, the use case publishes `ContractCreated` event to the EventBus so vertical modules can react (e.g., Vehicle Module sets vehicle status to `em_contrato`).
- **Indexes**: ensure `installments(contract_id)` for efficient contract->installments loading, `installments(due_date, status)` for overdue detection jobs, `installments(status)` for filtering, `installments(parent_installment_id)` for partial payment chain.

## Dev Checklist

- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
