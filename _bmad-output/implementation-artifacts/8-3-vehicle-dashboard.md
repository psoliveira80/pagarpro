---
epic: 8
story: 3
title: "Vehicle Dashboard"
type: "Vehicle Module"
status: done
---

# Story 8.3: Vehicle Dashboard

## User Story
As a Manager,
I want to analyze each vehicle's viability,
So that I can decide on sale/replacement.

## Acceptance Criteria

1. "Analysis" tab on vehicle detail page (injected by Vehicle Module).
2. Cards: Investment, Current FIPE, Depreciation, Total Received, ROI %, Accumulated Profit, Payback months.
3. Reads from materialized view `mv_asset_roi`; Celery job refreshes on schedule.
4. Line chart: accumulated investment vs accumulated revenue.
5. **Given** tracker provides KM, **Then** R$/day and R$/km productivity shown.
6. Timeline of drivers who used the vehicle.

## Technical Context

### Architecture References
- **Architecture Section 7.1 (IAssetModule Protocol)**: Vehicle Module implements `IAssetModule`; the "Analysis" tab is a module-injected UI section.
- **Architecture Section 9.11 (Materialized Views)**: `mv_asset_roi` view provides pre-aggregated ROI, depreciation, total_received, total_spent per asset.
- **Architecture Section 5 (Reports & Dashboards)**: `GET /api/v1/dashboard/asset/{id}` endpoint.
- **Architecture Section 10.1**: Vehicle tabs at `frontend/src/app/features/system/vehicles/vehicle-tabs/`.
- **Architecture Section 6**: Module-specific code in `backend-api/app/modules/vehicles/`.

### Files to Create/Modify
```
backend-api/
├── app/
│   ├── api/v1/dashboard_routes.py                      # Add GET /dashboard/asset/{id}
│   ├── application/dashboard/
│   │   ├── get_asset_dashboard.py                      # Use case: read mv_asset_roi + tracker data
│   │   └── schemas.py                                  # Add AssetDashboardOut, DriverTimelineEntry
│   ├── infrastructure/repositories/
│   │   └── dashboard_repository.py                     # Add asset ROI query from mv_asset_roi
│   ├── modules/vehicles/
│   │   ├── repositories/vehicle_dashboard_repo.py      # Vehicle-specific queries (KM, drivers)
│   │   └── use_cases/get_vehicle_analysis.py           # Compose ROI + productivity + driver timeline
│   └── workers/tasks/
│       └── refresh_mv_asset_roi.py                     # Celery task: REFRESH MATERIALIZED VIEW CONCURRENTLY

frontend/
├── src/app/features/system/vehicles/vehicle-tabs/
│   ├── vehicle-roi-tab.component.ts                    # Analysis tab component
│   ├── vehicle-roi-tab.component.html
│   └── vehicle-roi-tab.component.css
├── src/app/features/system/vehicles/vehicle-tabs/components/
│   ├── roi-cards/
│   │   ├── roi-cards.component.ts                      # Investment, FIPE, ROI%, Payback cards
│   │   ├── roi-cards.component.html
│   │   └── roi-cards.component.css
│   ├── investment-revenue-chart/
│   │   ├── investment-revenue-chart.component.ts       # Accumulated investment vs revenue line chart
│   │   ├── investment-revenue-chart.component.html
│   │   └── investment-revenue-chart.component.css
│   ├── productivity-cards/
│   │   ├── productivity-cards.component.ts             # R$/day, R$/km cards (conditional on tracker)
│   │   ├── productivity-cards.component.html
│   │   └── productivity-cards.component.css
│   └── driver-timeline/
│       ├── driver-timeline.component.ts                # Timeline of drivers who used the vehicle
│       ├── driver-timeline.component.html
│       └── driver-timeline.component.css
└── src/app/core/services/dashboard.service.ts          # Add getAssetDashboard(id)
```

### Dependencies
- Epic 2B (Vehicle Module, FIPE integration, `mv_asset_roi` materialized view DDL)
- Story 8.1 (shared KPI card component, dashboard service)
- Epic 3 (Contracts — revenue data linked to assets)
- Epic 4 (Finance — payables/receivables for ROI calculation)

### Technical Notes
- `mv_asset_roi` is defined in the schema (Architecture Section 9.11). A Celery beat task must refresh it daily (or on-demand after significant financial events). Use `REFRESH MATERIALIZED VIEW CONCURRENTLY mv_asset_roi` to avoid locking reads.
- The Celery task `refresh_mv_asset_roi` should be registered in `backend-api/app/workers/beat_schedule.py` to run daily at a configurable time.
- Payback months = `purchase_value / (total_received / months_since_purchase)`. Handle division by zero when no revenue yet.
- R$/day = `total_received / days_in_service`. R$/km = `total_received / total_km`. These are only shown if the tracker integration provides KM data (`module_data->>'total_km'`).
- Driver timeline is built from `contracts` joined with `customers` where `asset_id` matches the vehicle, ordered chronologically.
- The "Analysis" tab is injected into the vehicle detail page by the Vehicle Module's UI registration, following the module injection pattern.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
