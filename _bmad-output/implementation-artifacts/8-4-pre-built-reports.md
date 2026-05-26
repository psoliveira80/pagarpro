---
epic: 8
story: 4
title: "Pre-built Reports"
type: "Core + Module Hooks"
status: done
---

# Story 8.4: Pre-built Reports

## User Story
As a Manager,
I want pre-built reports,
So that routine analyses are one click away.

## Acceptance Criteria

1. Route `/system/reports` with cards for:
   - **Core reports**: Top Customers by Revenue (12m), Aging of Delinquency, DRE Consolidated and per Asset, Customer ABC Curve.
   - **Module reports** (via `IAssetModule.get_report_dimensions()`): E.g., Vehicle Module adds: Top Vehicles by ROI (12m), Remote Block History, Fleet Position snapshot (date X).
2. Each report opens in viewer with filters, charts, table.
3. Export to Excel (formatted) and PDF (header/footer).
4. Heavy reports: Celery worker generation + SSE notification when ready.

## Technical Context

### Architecture References
- **Architecture Section 5 (Reports & Dashboards)**: `GET /api/v1/reports/built-in/{slug}`, `GET /api/v1/reports/{id}/export?format=xlsx|pdf`.
- **Architecture Section 6**: `backend-api/app/api/v1/report_routes.py` for routes; `backend-api/app/application/reports/run_built_in.py` and `export_xlsx.py` use cases.
- **Architecture Section 7.1 (IAssetModule)**: Modules register additional report definitions via `get_report_dimensions()`.
- **Architecture Section 10.1**: Frontend reports at `frontend/src/app/features/system/reports/`.
- **Architecture Section 6 (Workers)**: `backend-api/app/workers/tasks/generate_report.py` for heavy async report generation.

### Files to Create/Modify
```
backend-api/
├── app/
│   ├── api/v1/report_routes.py                     # GET /reports/built-in/{slug}, GET /reports/{id}/export
│   ├── application/reports/
│   │   ├── __init__.py
│   │   ├── run_built_in.py                         # Use case: execute a built-in report by slug
│   │   ├── export_xlsx.py                          # Use case: export report data to formatted Excel
│   │   ├── export_pdf.py                           # Use case: export report data to PDF with header/footer
│   │   └── schemas.py                              # ReportDefinitionOut, ReportDataOut, ReportFilterIn
│   ├── domain/reports/
│   │   ├── __init__.py
│   │   ├── built_in_registry.py                    # Registry of core built-in report definitions
│   │   └── report_definitions.py                   # Core report specs (slug, query logic, columns, chart type)
│   ├── infrastructure/repositories/
│   │   └── report_repository.py                    # SQL queries for each built-in report
│   └── workers/tasks/
│       └── generate_report.py                      # Celery task: heavy report generation + SSE notification

frontend/
├── src/app/features/system/reports/
│   ├── reports-list.component.ts                   # Report cards grid page
│   ├── reports-list.component.html
│   ├── reports-list.component.css
│   ├── report-viewer.component.ts                  # Report viewer: filters + chart + table
│   ├── report-viewer.component.html
│   ├── report-viewer.component.css
│   ├── components/
│   │   ├── report-card/
│   │   │   ├── report-card.component.ts            # Card with report name, description, icon
│   │   │   ├── report-card.component.html
│   │   │   └── report-card.component.css
│   │   ├── filter-pane/
│   │   │   ├── filter-pane.component.ts            # Date range, status, customer filters
│   │   │   ├── filter-pane.component.html
│   │   │   └── filter-pane.component.css
│   │   └── visualization/
│   │       ├── report-table.component.ts           # Tabular data display with sorting
│   │       ├── report-table.component.html
│   │       ├── report-table.component.css
│   │       ├── report-chart.component.ts           # Chart visualization (bar, line, pie)
│   │       ├── report-chart.component.html
│   │       └── report-chart.component.css
│   └── reports.routes.ts                           # Routes: /reports, /reports/:slug
└── src/app/core/services/report.service.ts         # HTTP calls to /api/v1/reports/*
```

### Dependencies
- Story 8.1 (SSE service for notifications when heavy reports finish)
- Epic 2 (Customer, Asset data)
- Epic 3 (Contract data)
- Epic 4 (Finance data — receivables, payables for DRE and delinquency)
- Epic 2B (Vehicle Module — provides module-specific report definitions)

### Technical Notes
- Built-in report slugs: `top-customers-revenue`, `aging-delinquency`, `dre-consolidated`, `dre-per-asset`, `customer-abc-curve`. Module reports are discovered via `ModuleRegistry.all()` calling each module's `get_report_dimensions()`.
- Each report definition includes: slug, display name, description, query function, default filters, chart type, and column definitions.
- For heavy reports (large date ranges, full DRE), the endpoint returns `202 Accepted` with a `report_job_id`. The Celery worker generates the report, stores the result, and pushes an SSE event `report.ready` with download URL.
- Excel export uses `openpyxl` with formatted headers, column widths, and number formats. PDF export uses WeasyPrint with company header/footer template.
- Module reports appear alongside core reports in the cards grid, distinguished by a module badge.
- The report viewer component dynamically renders filters, chart, and table based on the report definition metadata.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
