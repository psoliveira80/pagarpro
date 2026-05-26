---
epic: 3
story: 2
title: "Installment Builder Backend — Preview + Persist"
type: "Core"
status: done
---

# Story 3.2: Installment Builder Backend — Preview + Persist

## User Story

As a Backend developer,
I want an endpoint that computes a schedule from an installment definition,
So that the frontend can preview before persisting.

## Acceptance Criteria

1. **Given** payload with `start_date`, optional `down_payment`, optional `regular`, optional `extras[]`, optional `grace_days`, optional `custom_overrides[]`, **When** `POST /api/v1/contracts/preview-schedule` is called, **Then** response returns ordered list with `sequence`, `due_date`, `amount`, `kind`.
2. Total of computed installments matches expected total (coherence check).
3. Supports `custom_only` mode for fully hand-edited schedules.
4. `POST /api/v1/contracts/` persists contract + all installments + `contract_events.created` atomically.
5. Schedule calculation in `app/domain/contracts/schedule_calculator.py` with 100% unit test coverage (no I/O).

## Technical Context

### Architecture References

- **Domain Pure Function** (Section 6): `backend-api/app/domain/contracts/schedule_calculator.py` — PURO, calcula parcelas
- **API Endpoints** (Section 5.2 — Contracts):
  - `POST /api/v1/contracts/preview-schedule` — preview de parcelamento
  - `POST /api/v1/contracts` — cria (rascunho)
- **Use Cases** (Section 6):
  - `backend-api/app/application/contracts/preview_schedule.py`
  - `backend-api/app/application/contracts/create_contract.py`
- **FR-CORE-CTR-2**: Visual installment builder: down payment, N regular installments, semestral/annual extras, grace period, custom schedule
- **FR-CORE-CTR-3**: On finalization, auto-generate titles

### Files to Create/Modify

**Create:**
- `backend-api/app/domain/contracts/schedule_calculator.py` — pure function `compute_schedule(definition: ScheduleDefinition) -> list[ScheduleItem]`. Handles: down_payment, regular installments with periodicity, semestral extras, annual extras, grace_days offset, custom_overrides, custom_only mode.
- `backend-api/app/application/contracts/preview_schedule.py` — use case that calls `compute_schedule` and returns preview DTO
- `backend-api/app/application/contracts/create_contract.py` — use case: validate, persist contract + installments + contract_event atomically
- `backend-api/app/api/v1/contract_routes.py` — FastAPI router with `POST /preview-schedule` and `POST /` endpoints
- `backend-api/app/api/v1/schemas/contracts.py` — Pydantic DTOs: `ScheduleDefinitionDTO`, `SchedulePreviewItemDTO`, `ContractCreateDTO`, `ContractResponseDTO`
- `backend-api/tests/unit/domain/contracts/test_schedule_calculator.py` — 100% coverage: all modes and edge cases
- `backend-api/tests/integration/test_contract_creation.py`

**Modify:**
- `backend-api/app/api/v1/__init__.py` or `main.py` — register contract routes

### Dependencies

- Story 3.1 (Contract domain model, tables, repositories)

### Technical Notes

- **`schedule_calculator.py`** is a pure function with ZERO I/O. It receives a dataclass `ScheduleDefinition` and returns a list of `ScheduleItem(sequence, due_date, amount, kind)`.
- **Definition structure**:
  ```python
  @dataclass
  class ScheduleDefinition:
      start_date: date
      periodicity: str  # 'mensal', 'quinzenal', 'semanal', 'diaria'
      due_day: int | None  # for monthly
      total_amount: Decimal
      down_payment: Decimal | None
      regular_count: int | None
      extras: list[ExtraInstallment]  # semestral/annual with month offsets
      grace_days: int
      custom_overrides: list[CustomItem] | None  # overrides for specific sequences
      custom_only: bool  # if True, use only custom_overrides
  ```
- **Coherence check**: sum of all generated installments must equal `total_amount`. If not (rounding), adjust last installment by the difference (< 0.01 typically).
- **Grace days**: shift the first regular installment's due_date by `grace_days` from `start_date`.
- **`custom_only` mode**: ignores `regular_count`, `down_payment`, `extras`; uses only `custom_overrides` as the full schedule.
- **Contract creation atomicity**: single DB transaction wrapping: (1) insert `contracts` row with `status='rascunho'`, (2) call `compute_schedule`, (3) bulk-insert `installments`, (4) insert `contract_events` with `event_type='created'`.
- On create, status is `rascunho`. Activation (vigente) happens in Story 3.4 when the user confirms.

## Dev Checklist

- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
