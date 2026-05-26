---
epic: 8
story: 1
title: "Main Dashboard"
type: "Core + Module Hooks"
status: done
---

# Story 8.1: Main Dashboard

## User Story
As a Manager,
I want to see business KPIs on a single screen,
So that I can read the operational pulse instantly.

## Acceptance Criteria

1. Route `/system/dashboard` with responsive card grid:
   - **Core KPIs**: Monthly Revenue (current vs previous, % delta), Monthly Expenses, Net Profit, Delinquency (R$ + %), Assets in Use, Assets Idle, Total Assets (R$), Next 7 Days Receivables, Pending Receipts, Portfolio Average Score.
   - **Module-injected widgets**: rendered via `IAssetModule.get_dashboard_widgets()`. E.g., Vehicle Module injects: Fleet Total (R$ FIPE consolidated), Active Vehicles, Parked, In Maintenance.
2. Cards reactive via Signals + `resource()`; refresh every 60 s or push via SSE.
3. Card click deep-links to filtered entity list.
4. Timeframe toggle: Today | This Week | This Month | This Quarter | This Year.
5. Charts: 12-month revenue line, expenses-by-category donut, delinquency-by-aging bars.

## Technical Context

### Architecture References
- **Architecture Section 5 (Reports & Dashboards)**: `GET /api/v1/dashboard/main` endpoint returns KPIs.
- **Architecture Section 5 (Real-time)**: `/sse/dashboard` for live KPI updates.
- **Architecture Section 7.1 (IAssetModule Protocol)**: `get_dashboard_widgets()` not explicitly on the protocol but implied; modules provide widget definitions via the registry.
- **Architecture Section 10.1**: Frontend dashboard component at `frontend/src/app/features/system/dashboard/`.
- **Architecture Section 10.2**: Signal-based component pattern with `resource()` for data fetching.
- **Architecture Section 6**: `backend-api/app/api/v1/dashboard_routes.py` for routes.

### Files to Create/Modify
```
backend-api/
├── app/
│   ├── api/v1/dashboard_routes.py              # GET /dashboard/main endpoint
│   ├── application/dashboard/
│   │   ├── __init__.py
│   │   ├── get_main_dashboard.py               # Use case: aggregate core KPIs
│   │   └── schemas.py                          # DashboardMainOut, KpiCardOut
│   ├── domain/dashboard/
│   │   ├── __init__.py
│   │   └── kpi_calculator.py                   # Pure domain logic for KPI calculations
│   └── infrastructure/repositories/
│       └── dashboard_repository.py             # Queries for revenue, expenses, delinquency, etc.

frontend/
├── src/app/features/system/dashboard/
│   ├── dashboard.component.ts                  # Main dashboard page component
│   ├── dashboard.component.html                # Card grid + charts layout
│   ├── dashboard.component.css
│   └── components/
│       ├── kpi-card/
│       │   ├── kpi-card.component.ts           # Reusable KPI card with delta indicator
│       │   ├── kpi-card.component.html
│       │   └── kpi-card.component.css
│       ├── revenue-chart/
│       │   ├── revenue-chart.component.ts      # 12-month revenue line chart
│       │   ├── revenue-chart.component.html
│       │   └── revenue-chart.component.css
│       ├── expenses-donut/
│       │   ├── expenses-donut.component.ts     # Expenses-by-category donut chart
│       │   ├── expenses-donut.component.html
│       │   └── expenses-donut.component.css
│       ├── delinquency-bars/
│       │   ├── delinquency-bars.component.ts   # Delinquency-by-aging bar chart
│       │   ├── delinquency-bars.component.html
│       │   └── delinquency-bars.component.css
│       └── timeframe-toggle/
│           ├── timeframe-toggle.component.ts   # Today/Week/Month/Quarter/Year selector
│           ├── timeframe-toggle.component.html
│           └── timeframe-toggle.component.css
├── src/app/core/services/dashboard.service.ts  # HTTP calls to /api/v1/dashboard/*
└── src/app/core/services/sse.service.ts        # Modify: subscribe to 'dashboard' channel
```

### Dependencies
- Epic 1 (Auth, base backend/frontend scaffold)
- Epic 2 (Customers, Assets — data must exist for KPIs)
- Epic 3 (Contracts — revenue/receivable data)
- Epic 4 (Finance — receivables, payables, delinquency data)
- `IAssetModule` protocol and `ModuleRegistry` (from Epic 2)

### Technical Notes
- The backend `get_main_dashboard` use case must query core KPIs from finance/contract tables, then call `ModuleRegistry.all()` to collect module-injected widgets via each module's widget method.
- SSE channel `/sse/dashboard` pushes partial KPI updates; the frontend subscribes and patches the local signal state.
- Use `resource()` for initial data fetch with 60-second polling as fallback if SSE disconnects.
- Charts should use a lightweight library (e.g., Chart.js or ngx-charts) already established in the project.
- Timeframe toggle changes the query parameter `?timeframe=today|week|month|quarter|year` and re-fetches via `resource()`.
- Card click emits a `routerLink` with query params to the relevant entity list (e.g., clicking "Delinquency" navigates to `/system/finance/receivables?status=vencido`).

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
