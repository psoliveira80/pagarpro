---
epic: 8
story: 2
title: "Customer Dashboard"
type: "Core"
status: done
---

# Story 8.2: Customer Dashboard

## User Story
As a Manager,
I want a financial dashboard per customer,
So that I can negotiate with data.

## Acceptance Criteria

1. "Dashboard" tab on customer detail page.
2. Cards: Total Contracted, Total Paid, Total Open, Total Overdue, Current Score (gauge), Punctuality % (12m).
3. Timeline chart: each payment colored by status.
4. Table: active contracts with balances and per-contract ROI.
5. "Export customer history" -> PDF.

## Technical Context

### Architecture References
- **Architecture Section 5 (Reports & Dashboards)**: `GET /api/v1/dashboard/customer/{id}` endpoint.
- **Architecture Section 10.1**: Customer detail tabs at `frontend/src/app/features/system/customers/customer-tabs/`.
- **Architecture Section 9.3 (Data Model)**: `customers`, `contracts`, `installments` tables drive the KPIs.
- **Architecture Section 6**: `backend-api/app/api/v1/dashboard_routes.py` for routes.

### Files to Create/Modify
```
backend-api/
├── app/
│   ├── api/v1/dashboard_routes.py              # Add GET /dashboard/customer/{id}
│   ├── application/dashboard/
│   │   ├── get_customer_dashboard.py           # Use case: aggregate per-customer KPIs
│   │   └── schemas.py                          # Add CustomerDashboardOut, ContractBalanceRow
│   ├── application/reports/
│   │   └── export_customer_history.py          # Use case: generate customer history PDF
│   └── infrastructure/repositories/
│       └── dashboard_repository.py             # Add customer-specific aggregation queries

frontend/
├── src/app/features/system/customers/customer-tabs/
│   ├── customer-dashboard-tab.component.ts     # New dashboard tab component
│   ├── customer-dashboard-tab.component.html
│   └── customer-dashboard-tab.component.css
├── src/app/features/system/customers/customer-tabs/components/
│   ├── score-gauge/
│   │   ├── score-gauge.component.ts            # Gauge chart for customer score
│   │   ├── score-gauge.component.html
│   │   └── score-gauge.component.css
│   └── payment-timeline/
│       ├── payment-timeline.component.ts       # Timeline chart with color-coded payments
│       ├── payment-timeline.component.html
│       └── payment-timeline.component.css
├── src/app/features/system/customers/
│   └── customers.routes.ts                     # Modify: add dashboard tab route
└── src/app/core/services/dashboard.service.ts  # Add getCustomerDashboard(id)
```

### Dependencies
- Story 8.1 (shared dashboard service and KPI card component)
- Epic 2 (Customer detail page and tab structure)
- Epic 3 (Contracts data)
- Epic 4 (Finance — receivables, payments, score)

### Technical Notes
- The customer dashboard tab is added to the existing `customer-detail.component.ts` tab set.
- KPI queries aggregate across all contracts belonging to the customer: `SUM(installments.amount)` grouped by status.
- Punctuality % = count of installments paid on or before due_date / total paid installments over 12 months.
- Score gauge uses the customer's `current_score` field computed by the scoring Celery task.
- Payment timeline chart shows each installment as a point on a time axis, colored: green (paid on time), yellow (paid late), red (overdue), gray (pending).
- "Export customer history" triggers a Celery task that generates a PDF via WeasyPrint, then notifies via SSE when ready. Endpoint: `GET /api/v1/reports/customer/{id}/export?format=pdf`.
- Per-contract ROI is `(total_paid - total_payables) / total_contracted * 100` for each active contract row.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
