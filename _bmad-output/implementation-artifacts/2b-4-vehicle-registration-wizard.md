---
epic: 2B
story: 4
title: "Vehicle Registration Wizard"
type: "Vehicle Module"
status: done
---

# Story 2B.4: Vehicle Registration Wizard

## User Story

As a Manager,
I want a guided wizard to register a vehicle,
So that the many fields don't overwhelm me.

## Acceptance Criteria

1. 4 steps: **Identification** (plate, renavam, chassis, color), **FIPE Data** (cascading brand/model/year selectors with auto-filled value), **Acquisition** (date, purchase value, payment form with dynamic sub-form), **Documents & Photos** (insurance, IPVA, photos).
2. FIPE selectors with typeahead and inline loading.
3. **Given** "Financiamento" selected, **Then** sub-form: down payment, installment count, rate, amortization (Price/SAC), preview table.
4. Stepper + Back/Next; form state preserved across steps.
5. Final step: preview before commit; on confirm, create vehicle + acquisition atomically.

## Technical Context

### Architecture References

- **Frontend Structure** (Section 10.1):
  - `frontend/src/app/features/system/vehicles/vehicle-wizard.component.ts` — 4-step wizard
  - `frontend/src/app/features/system/vehicles/components/fipe-selector/` — cascading FIPE selectors
  - `frontend/src/app/features/system/vehicles/components/acquisition-form/` — acquisition sub-form
  - `frontend/src/app/features/system/vehicles/components/photo-gallery/` — photo upload
- **Shared Components**: `shared/components/stepper/`, `shared/components/input-plate/`, `shared/components/input-money/`, `shared/components/file-dropzone/`
- **API Endpoints**:
  - `POST /api/v1/modules/vehicles` — create vehicle + acquisition atomically
  - `GET /api/v1/modules/vehicles/fipe/brands|models|years|price` — FIPE cascading data
- **Angular Patterns**: Standalone components, Signals, `resource()` for data fetching, Reactive Forms

### Files to Create/Modify

**Create:**
- `frontend/src/app/features/system/vehicles/vehicle-wizard.component.ts`
- `frontend/src/app/features/system/vehicles/vehicle-wizard.component.html`
- `frontend/src/app/features/system/vehicles/vehicle-wizard.component.css`
- `frontend/src/app/features/system/vehicles/components/fipe-selector/fipe-selector.component.ts`
- `frontend/src/app/features/system/vehicles/components/fipe-selector/fipe-selector.component.html`
- `frontend/src/app/features/system/vehicles/components/fipe-selector/fipe-selector.component.css`
- `frontend/src/app/features/system/vehicles/components/acquisition-form/acquisition-form.component.ts`
- `frontend/src/app/features/system/vehicles/components/acquisition-form/acquisition-form.component.html`
- `frontend/src/app/features/system/vehicles/components/acquisition-form/acquisition-form.component.css`
- `frontend/src/app/features/system/vehicles/components/photo-gallery/photo-gallery.component.ts`
- `frontend/src/app/features/system/vehicles/components/photo-gallery/photo-gallery.component.html`
- `frontend/src/app/features/system/vehicles/components/photo-gallery/photo-gallery.component.css`
- `frontend/src/app/features/system/vehicles/services/vehicle.service.ts` — API client for vehicle CRUD + FIPE
- `frontend/src/app/features/system/vehicles/services/fipe.service.ts` — API client for FIPE cascading endpoints

**Modify:**
- `frontend/src/app/features/system/vehicles/vehicles.routes.ts` — add route for wizard (`/vehicles/new`)

### Dependencies

- Story 2B.2 (FIPE Provider Adapter — backend endpoints)
- Story 2B.3 (Vehicle domain model — backend CRUD endpoints)
- Story 2A.4 or shared stepper component (from Epic 1 or 2A)

### Technical Notes

- **Stepper component**: reuse `shared/components/stepper/` if available from Epic 1; otherwise create a lightweight stepper with step index signal.
- **FIPE cascading selectors**: `fipe-selector` component uses `resource()` to fetch brands on init, then models on brand change, then years on model change, then price on year change. Each level resets downstream selections.
- **Acquisition form dynamic sub-form**: when `type` signal changes to `financiamento`, render financing fields (down_payment, installment_count, rate, amortization_system). Use `computed()` to calculate preview table of acquisition installments.
- **Form state preserved**: use a single Reactive Form group spanning all steps; each step shows/hides relevant controls.
- **Final preview step**: read-only summary of all entered data, "Confirmar" button calls `POST /api/v1/modules/vehicles` with combined payload.
- **Plate input**: use `shared/components/input-plate/` with Mercosul mask.
- **Photo upload**: `file-dropzone` with image preview, uploads to vehicle photos endpoint after creation.

## Dev Checklist

- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
