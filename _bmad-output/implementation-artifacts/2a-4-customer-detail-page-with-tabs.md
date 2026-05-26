---
epic: 2A
story: 4
title: "Customer Detail Page with Tabs"
type: "Core"
status: done
---

# Story 2A.4: Customer Detail Page with Tabs

## User Story
As a Manager,
I want to see the full life of a customer on one page,
So that I have complete context before any decision.

## Acceptance Criteria

1. Route `/system/customers/:id` renders `CustomerDetailComponent`.
2. Header: avatar, name, CPF/CNPJ, large score visual, status, primary actions (Edit, WhatsApp Message).
3. Core tabs: **Overview**, **Contracts**, **Receivables**, **Score**, **Documents**, **Conversations**, **Audit**. Vertical modules can inject additional tabs. Each tab lazy-loaded.
4. Overview: metric cards (total contracted, received, open balance, upcoming), event timeline.
5. URL preserves active tab via `?tab=...`.

## Technical Context

### Architecture References
- **Architecture Section 2.5**: Feature components in `features/system/...`; lazy loading per feature.
- **Architecture Section 5.2 — Customers endpoints**: `GET /customers/{id}`, `GET /customers/{id}/financials` (KPIs), `GET /customers/{id}/score-history`, `GET /customers/{id}/attachments`.
- **Architecture Section 3.2**: Signals + resource() for data fetching, Tailwind v4 for styling.

### Files to Create/Modify
```
frontend/
├── src/app/
│   ├── features/
│   │   └── system/
│   │       └── customers/
│   │           ├── customers.routes.ts                       # add /:id route
│   │           ├── customer-detail/
│   │           │   ├── customer-detail.component.ts          # main detail page
│   │           │   ├── customer-detail.component.html
│   │           │   └── customer-detail.component.css
│   │           ├── customer-overview/
│   │           │   ├── customer-overview.component.ts        # Overview tab content
│   │           │   └── customer-overview.component.html
│   │           ├── customer-contracts-tab/
│   │           │   └── customer-contracts-tab.component.ts   # Contracts tab (placeholder until Epic 3)
│   │           ├── customer-receivables-tab/
│   │           │   └── customer-receivables-tab.component.ts # Receivables tab (placeholder until Epic 4)
│   │           ├── customer-score-tab/
│   │           │   └── customer-score-tab.component.ts       # Score history tab
│   │           ├── customer-documents-tab/
│   │           │   └── customer-documents-tab.component.ts   # Attachments/documents tab
│   │           ├── customer-conversations-tab/
│   │           │   └── customer-conversations-tab.component.ts # placeholder until Epic 6
│   │           └── customer-audit-tab/
│   │               └── customer-audit-tab.component.ts       # Audit log tab for this customer
│   ├── shared/
│   │   └── components/
│   │       ├── tabs/
│   │       │   └── tabs.component.ts                         # reusable tab container
│   │       ├── metric-card/
│   │       │   └── metric-card.component.ts                  # KPI card with label + value + trend
│   │       └── timeline/
│   │           └── timeline.component.ts                     # vertical event timeline
│   ├── core/
│   │   └── services/
│   │       └── customers.service.ts                          # add getById, getFinancials, getScoreHistory
```

### Dependencies
- **Story 1.2** (Angular skeleton, shared components).
- **Story 1.6** (AuthGuard, JWT interceptor).
- **Story 2A.1** (Customer API — GET by ID, financials endpoint).
- **Story 2A.2** (Customers list — for navigation).
- **Story 2A.3** (Customer form — Edit button opens drawer).

### Technical Notes
- **Tab component**: Reusable `TabsComponent` in `shared/components/tabs/`. Accepts a list of tab definitions `{id, label, icon?, component?}`. Active tab stored as a signal, synced with URL `?tab=` query param.
- **Lazy tab loading**: Each tab content is a standalone component loaded only when the tab is activated. Use `@defer` or `@if(activeTab() === 'overview')` pattern.
- **Module-injected tabs**: Design the tabs array to be extensible. Active modules can register additional tabs (e.g., Vehicle Module might add a "Vehicles" tab). For now, define the extension point — a service or injection token that modules can contribute to.
- **Overview tab**:
  - 4 metric cards at top: "Total Contratado", "Total Recebido", "Saldo em Aberto", "Proximos Vencimentos". Data from `GET /customers/{id}/financials`.
  - Event timeline below: recent events (contract created, payment received, overdue, etc.). Use `TimelineComponent`.
  - Use `resource()` to fetch financials data.
- **Score tab**: Show score value prominently (large number with color), plus a chart of score history over time (use ngx-echarts or simple bar chart). Data from `GET /customers/{id}/score-history`.
- **Documents tab**: List attachments from `GET /customers/{id}/attachments`. Show thumbnail (images) or file icon, name, kind badge, upload date, download/delete actions. Allow uploading new attachments inline.
- **Audit tab**: Query `audit_log` filtered by `entity='customer'` and `entity_id=customer.id`. Display in a table with timestamp, action, user, and expandable payload diff.
- **Header**: 
  - Avatar: circular image or initials fallback.
  - Score: large circular gauge or badge with color coding (same as list: 0-30 red, 31-60 yellow, 61-85 blue, 86-100 green).
  - Status badge: colored pill.
  - Edit button: opens customer form drawer in edit mode (Story 2A.3).
  - WhatsApp button: opens `https://wa.me/{phone}` in new tab.
- **Contracts/Receivables/Conversations tabs**: Show "Coming soon" placeholder with icon. These will be populated in Epics 3, 4, and 6 respectively.
- **URL state**: On tab change, update `?tab=overview` (or contracts, receivables, etc.). On page load, read `?tab` to set initial active tab (default: overview).

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
