---
epic: 2B
story: 5
title: "Vehicles List and Card Grid"
type: "Vehicle Module"
status: done
---

# Story 2B.5: Vehicles List and Card Grid

## User Story

As a Manager,
I want to see the fleet as a table or cards,
So that I can scan its state quickly.

## Acceptance Criteria

1. Toggle Table <-> Cards; preference persisted to localStorage.
2. Cards: photo, model, plate, status badge, current driver, ROI %, next due date, mini-map with position.
3. Filters: status, brand, year, current driver, tag.
4. KPI strip: Fleet Total (R$ FIPE sum), Active Vehicles, Parked Vehicles.

## Technical Context

### Architecture References

- **Frontend Structure** (Section 10.1):
  - `frontend/src/app/features/system/vehicles/vehicles-list.component.ts`
  - `frontend/src/app/features/system/vehicles/vehicle-detail.component.ts`
- **Shared Components**: `shared/components/data-table/`, `shared/components/data-list/`, `shared/components/kpi-card/`, `shared/components/badge/`, `shared/components/leaflet-map/`
- **API Endpoints**:
  - `GET /api/v1/modules/vehicles` — paginated list with filters
  - `GET /api/v1/modules/vehicles/{id}/position` — current position for mini-map
  - `GET /api/v1/modules/vehicles/{id}/financials` — ROI data
- **Angular Patterns**: Signals for view mode toggle, `resource()` for data fetching, `localStorage` persistence

### Files to Create/Modify

**Create:**
- `frontend/src/app/features/system/vehicles/vehicles-list.component.ts`
- `frontend/src/app/features/system/vehicles/vehicles-list.component.html`
- `frontend/src/app/features/system/vehicles/vehicles-list.component.css`
- `frontend/src/app/features/system/vehicles/components/vehicle-card/vehicle-card.component.ts`
- `frontend/src/app/features/system/vehicles/components/vehicle-card/vehicle-card.component.html`
- `frontend/src/app/features/system/vehicles/components/vehicle-card/vehicle-card.component.css`
- `frontend/src/app/features/system/vehicles/components/vehicle-kpi-strip/vehicle-kpi-strip.component.ts`
- `frontend/src/app/features/system/vehicles/components/vehicle-kpi-strip/vehicle-kpi-strip.component.html`
- `frontend/src/app/features/system/vehicles/components/vehicle-kpi-strip/vehicle-kpi-strip.component.css`

**Modify:**
- `frontend/src/app/features/system/vehicles/vehicles.routes.ts` — add list route (`/vehicles`)
- `frontend/src/app/features/system/vehicles/services/vehicle.service.ts` — add list, filters, KPI methods

### Dependencies

- Story 2B.3 (Vehicle CRUD backend endpoints)
- Story 2B.4 (Vehicle wizard — for "New Vehicle" button navigation)

### Technical Notes

- **View mode toggle**: signal `viewMode = signal<'table' | 'cards'>('cards')`, synced to `localStorage.getItem('vehicles-view-mode')` on init, `localStorage.setItem(...)` on change.
- **Table mode**: reuse `shared/components/data-table/` with columns: plate, brand/model, status, current driver, FIPE value, ROI %, next due date. Sortable and paginated.
- **Card mode**: reuse `shared/components/data-list/` or custom grid. Each card shows photo (or placeholder), model, plate badge, status badge (color-coded), current driver name, ROI %, next due date, mini Leaflet map with single marker.
- **KPI strip**: 3 `kpi-card` components above the list — Fleet Total (sum of `fipe_value_current` for active vehicles, formatted as R$), Active Vehicles count, Parked Vehicles count. Data comes from a summary endpoint or computed from the list response.
- **Filters**: status multi-select, brand typeahead, year range, current driver search, tag chips. Applied as query params to `GET /api/v1/modules/vehicles`.
- **Mini-map on card**: small Leaflet instance (150x100px) with a single marker using the vehicle's last known position. If no position data, show placeholder.

## Dev Checklist

- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
