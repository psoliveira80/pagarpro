---
epic: 2B
story: 3
title: "Vehicle Domain Model, FIPE Integration, and Acquisition"
type: "Vehicle Module"
status: done
---

# Story 2B.3: Vehicle Domain Model, FIPE Integration, and Acquisition

## User Story

As a Backend developer,
I want a Vehicle entity with CRUD, FIPE refresh, and acquisition modeling,
So that the frontend can manage the fleet financially.

## Acceptance Criteria

1. `Vehicle` model with all fields from FR-VH-1, plus `asset_id` (FK to `assets`), `current_contract_id` (nullable), `current_customer_id` (nullable, derived).
2. CRUD endpoints under `/api/v1/modules/vehicles/` with permission checks.
3. On create/update, sync record in core `assets` table (create or update `asset_id`).
4. `POST /api/v1/modules/vehicles/{id}/refresh-fipe` updates `valor_fipe_atual` via active adapter.
5. Celery beat job (`0 3 5 * *`) refreshes FIPE for all active vehicles monthly.
6. `VehicleAcquisition` entity (1:1 with Vehicle) with acquisition form (FR-VH-3): type, down_payment, installments (JSONB), interest_rate, amortization_system.
7. `GET /api/v1/modules/vehicles/{id}/financials` returns: FIPE value, depreciation, total paid to acquisition, balance, total received, ROI %, payback.

## Technical Context

### Architecture References

- **DB Tables** (Section 9.5):
  - `vehicles` — all fields: `id`, `asset_id` (FK `assets`), `plate`, `renavam`, `chassis`, `brand`, `model`, `version`, `year_model`, `year_manufacture`, `color`, `fuel`, `km_initial`, `km_current`, `acquisition_date`, `purchase_value`, `fipe_code`, `fipe_value_current`, `fipe_value_updated_at`, `tracker_device_id`, `status`, `category`, `insurance_*`, `ipva_*`, `licensing_*`, timestamps, soft delete
  - `vehicle_acquisitions` — `id`, `vehicle_id` (FK unique), `type` (enum), `down_payment`, `installments_def` (JSONB), `interest_rate_pct_per_month`, `grace_days`, `amortization_system`, `notes`
  - `vehicle_photos` — `id`, `vehicle_id`, `url`, `is_primary`, `uploaded_at`
- **Core `assets` table** (Section 9.3): `id`, `asset_type='vehicle'`, `name`, `status`, `metadata`, `module_data`
- **API Endpoints** (Section 5.2):
  - `GET /api/v1/modules/vehicles` — list
  - `POST /api/v1/modules/vehicles` — create (creates asset + vehicle)
  - `GET /api/v1/modules/vehicles/{id}` — detail
  - `PATCH /api/v1/modules/vehicles/{id}` — update
  - `GET /api/v1/modules/vehicles/{id}/financials` — ROI, depreciation, payback
  - `POST /api/v1/modules/vehicles/{id}/refresh-fipe` — force FIPE update
  - `PUT /api/v1/modules/vehicles/{id}/acquisition` — define/update acquisition
  - `POST /api/v1/modules/vehicles/{id}/photos` — upload photo
- **Celery Beat** (Section 6): monthly FIPE refresh `0 3 5 * *`
- **Value Objects**: `Plate` (Mercosul format `AAA0A00` or old `AAA0000`), `Money`
- **Materialized View**: `mv_asset_roi` — finalized in Epic 8, but vehicle financials endpoint should use direct queries for now

### Files to Create/Modify

**Create:**
- `backend-api/app/modules/vehicles/models.py` — SQLAlchemy models: `Vehicle`, `VehicleAcquisition`, `VehiclePhoto`, `TrackerDevice`
- `backend-api/app/modules/vehicles/schemas.py` — Pydantic DTOs: `VehicleCreateDTO`, `VehicleUpdateDTO`, `VehicleResponseDTO`, `VehicleAcquisitionDTO`, `VehicleFinancialsDTO`
- `backend-api/app/modules/vehicles/services/vehicle_crud.py` — CRUD service with asset sync
- `backend-api/app/modules/vehicles/services/vehicle_roi.py` — pure function: compute FIPE depreciation, ROI %, payback
- `backend-api/app/modules/vehicles/services/fipe_service.py` — (extend from 2B.2) add `refresh_vehicle_fipe(vehicle_id)` and `refresh_all_active()`
- `backend-api/app/workers/tasks/fipe_monthly_refresh.py` — Celery task for monthly FIPE refresh
- `backend-api/tests/unit/modules/vehicles/test_vehicle_crud.py`
- `backend-api/tests/unit/modules/vehicles/test_vehicle_roi.py`
- `backend-api/tests/integration/modules/vehicles/test_vehicle_endpoints.py`

**Modify:**
- `backend-api/app/modules/vehicles/routes.py` — add CRUD + financials + refresh-fipe + acquisition + photos endpoints
- `backend-api/app/workers/beat_schedule.py` — add `fipe-monthly-refresh` entry: `crontab(minute=0, hour=3, day_of_month=5)`
- Alembic migration — create `vehicles`, `vehicle_acquisitions`, `vehicle_photos`, `tracker_devices` tables with all indexes

### Dependencies

- Story 2B.1 (Vehicle Module structure)
- Story 2B.2 (FIPE Provider Adapter)
- Story 2A.2 (Core assets CRUD — for asset sync)

### Technical Notes

- On vehicle create: first create a record in core `assets` table with `asset_type='vehicle'`, `name='{plate} - {brand} {model}'`, `status='disponivel'`; then create `vehicles` record with the `asset_id` FK.
- On vehicle update: sync relevant fields back to `assets.name`, `assets.status`, `assets.module_data`.
- `Plate` value object validates Mercosul format (`AAA0A00`) or legacy (`AAA0000`).
- Vehicle financials calculation is a pure function in `vehicle_roi.py`: `compute_vehicle_financials(purchase_value, fipe_current, total_received_from_contracts, total_paid_acquisition, months_owned)`.
- FIPE refresh Celery task: load all vehicles with `status != 'inativo'`, call `fipe_service.get_price()` for each, update `fipe_value_current` and `fipe_value_updated_at`.
- Permission checks: `vehicles.create`, `vehicles.read`, `vehicles.update`, `vehicles.delete`.

## Dev Checklist

- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
