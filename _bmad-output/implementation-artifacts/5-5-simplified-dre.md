---
epic: 5
story: 5
title: "Simplified DRE"
type: "Core"
status: done
---

# Story 5.5: Simplified DRE

## User Story
As a Manager,
I want to see Income - Expenses by period,
So that I can read the operation's result.

## Acceptance Criteria

1. Route `/system/finance/dre` with filters: period (month/quarter/custom), asset, category.
2. Structure: Revenues (by source), Expenses (by category), Gross Margin, Margin %.
3. Bar chart comparing months with drilldown on click.
4. Export to Excel and PDF with formatting preserved.

## Technical Context

### Architecture References
- **Architecture Section 10.1 (Frontend Structure)**: `frontend/src/app/features/system/finance/dre/dre.component.ts` and `dre-table/` component.
- **Architecture Section 5 (API Endpoints)**: Report-style endpoint aggregating receivables (revenues) and payables (expenses) by period.
- **Architecture Section 6 (Backend Modules)**: `app/application/reports/` for report generation; `app/application/reports/export_xlsx.py` for Excel export.
- **Architecture Section 3.1 (Tech Stack)**: `ngx-echarts` for charts (frontend), `openpyxl` for Excel export (backend).

### Files to Create/Modify
```
backend-api/
├── app/api/v1/report_routes.py                # GET /api/v1/reports/dre — aggregated DRE data
├── app/application/reports/generate_dre.py    # use case: aggregate revenues and expenses by period
├── app/application/reports/export_dre_xlsx.py # use case: generate Excel with DRE formatting
├── app/application/reports/export_dre_pdf.py  # use case: generate PDF with DRE formatting

frontend/
├── src/app/features/system/finance/dre/
│   ├── dre.component.ts                       # main DRE page with filters and chart
│   ├── dre.component.html
│   ├── dre.component.css
│   ├── dre.routes.ts                          # lazy route /system/finance/dre
│   ├── components/
│   │   └── dre-table/
│   │       ├── dre-table.component.ts         # structured income/expense table with totals
│   │       ├── dre-table.component.html
│   │       └── dre-table.component.css
│   └── services/
│       └── dre.service.ts                     # HttpClient calls to /api/v1/reports/dre
```

### Dependencies
- Story 5.1 (Categories — expenses grouped by category in the DRE).
- Story 5.2 (Payables — expense data source).
- Epic 3/4 (Contracts/Installments — revenue data source from paid installments).
- Shared `chart-card` component (wrapper for ngx-echarts).
- `openpyxl` and `WeasyPrint` packages for backend exports.

### Technical Notes
- DRE (Demonstrativo de Resultado do Exercicio) structure:
  - **Revenues**: Sum of paid installments (`status='pago'`) grouped by source (contract type, customer, etc.) for the selected period.
  - **Expenses**: Sum of paid payables (`status='pago'`) grouped by `expense_category` for the selected period.
  - **Gross Margin**: Revenues - Expenses.
  - **Margin %**: (Gross Margin / Revenues) * 100.
- API endpoint `GET /api/v1/reports/dre?period=2026-01&period_type=month&asset_id=&category_id=` returns structured JSON with revenues array, expenses array, and computed totals.
- Period filters: `month` (single month), `quarter` (3 months), `custom` (arbitrary date range).
- Asset filter narrows revenues/expenses to a specific asset (useful for per-vehicle P&L).
- Bar chart uses `ngx-echarts` showing monthly comparison (revenues vs expenses bars) for the last N months. Clicking a bar drills down to show the detailed breakdown for that month.
- Excel export preserves the DRE table structure with formatted headers, currency formatting, and subtotals. Uses `openpyxl` on the backend.
- PDF export uses `WeasyPrint` with an HTML/Jinja2 template matching the on-screen layout.
- Export endpoints: `GET /api/v1/reports/dre/export?format=xlsx` and `GET /api/v1/reports/dre/export?format=pdf` with the same filter parameters.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
