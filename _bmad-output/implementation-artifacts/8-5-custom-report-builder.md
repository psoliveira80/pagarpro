---
epic: 8
story: 5
title: "Custom Report Builder"
type: "Core"
status: done
---

# Story 8.5: Custom Report Builder

## User Story
As an advanced Manager,
I want to compose my own reports,
So that I don't depend on engineering for new analyses.

## Acceptance Criteria

1. Route `/system/reports/builder` with three drag-and-drop zones:
   - **Available Dimensions**: customer, asset, contract, category, month, status, etc. + module-registered dimensions.
   - **Rows** and **Columns** targets.
   - **Measures** (count, sum, avg, min, max of numeric fields).
2. Filters: date range, status, customer.
3. Preview table updates live.
4. "Save as" persists to `saved_reports`.

## Technical Context

### Architecture References
- **Architecture Section 5 (Reports & Dashboards)**: `POST /api/v1/reports/run` executes custom report; `POST /api/v1/reports/saved` persists; `GET /api/v1/reports/saved` lists saved reports.
- **Architecture Section 9.10 (Data Model)**: `saved_reports` table with `definition` JSONB column storing dimensions/measures/filters.
- **Architecture Section 10.1**: Frontend report builder at `frontend/src/app/features/system/reports/report-builder.component.ts` with `dimension-palette/`, `filter-pane/`, and `visualization/` sub-components.
- **Architecture Section 7.1 (IAssetModule)**: Modules register additional dimensions via `get_report_dimensions()`.

### Files to Create/Modify
```
backend-api/
├── app/
│   ├── api/v1/report_routes.py                     # Add POST /reports/run, POST /reports/saved, GET /reports/saved
│   ├── application/reports/
│   │   ├── run_custom.py                           # Use case: execute custom report from definition JSONB
│   │   ├── save_report.py                          # Use case: persist report definition
│   │   ├── list_saved_reports.py                   # Use case: list user's saved reports
│   │   └── schemas.py                              # Add ReportDefinitionIn, SavedReportOut, RunReportIn
│   ├── domain/reports/
│   │   ├── dimension_registry.py                   # Registry of available dimensions (core + module)
│   │   └── query_builder.py                        # Build dynamic SQL from dimension/measure/filter definition
│   └── infrastructure/repositories/
│       └── saved_report_repository.py              # CRUD for saved_reports table

frontend/
├── src/app/features/system/reports/
│   ├── report-builder.component.ts                 # Main builder page with drag-and-drop zones
│   ├── report-builder.component.html
│   ├── report-builder.component.css
│   ├── components/
│   │   └── dimension-palette/
│   │       ├── dimension-palette.component.ts      # Available dimensions list (draggable)
│   │       ├── dimension-palette.component.html
│   │       └── dimension-palette.component.css
│   └── reports.routes.ts                           # Modify: add /reports/builder route
└── src/app/core/services/report.service.ts         # Add runCustomReport(), saveReport(), listSavedReports()
```

### Dependencies
- Story 8.4 (report viewer, filter pane, visualization components are reused)
- Epic 2B (Vehicle Module provides module-registered dimensions)
- Alembic migration for `saved_reports` table (Architecture Section 9.10)

### Technical Notes
- The `query_builder.py` dynamically constructs a SQL query from the JSONB report definition. It maps dimension names to actual table columns/joins, applies aggregate functions for measures, and appends filter conditions. Use parameterized queries only — never string interpolation.
- Available dimensions are registered at startup: core dimensions from a static list (customer_name, asset_name, contract_status, category, month, year, etc.) plus module dimensions discovered via `ModuleRegistry.all()` calling `get_report_dimensions()`.
- Drag-and-drop uses Angular CDK `DragDrop` module. Three drop zones: Available Dimensions (source), Rows (target), Columns (target). Measures are selected via checkboxes with aggregate function dropdowns.
- Live preview debounces 500ms after any change, sends `POST /api/v1/reports/run` with the current definition, and renders the result in the shared `report-table` and `report-chart` components from Story 8.4.
- "Save as" opens a dialog for name and sharing toggle, then persists via `POST /api/v1/reports/saved`. Saved reports appear in the reports list alongside built-in reports.
- The `saved_reports` table uses `owner_user_id` for ownership and `is_shared` boolean for visibility to other users.
- Maximum of 3 row dimensions and 2 column dimensions to keep queries performant. Enforce this in both frontend and backend validation.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
