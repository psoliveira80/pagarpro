---
epic: 9
story: 6
title: "Load Tests and Performance Tuning"
type: "Core"
status: done
---

# Story 9.6: Load Tests and Performance Tuning

## User Story
As the Team,
I want to validate the system handles forecast load,
So that launch is safe.

## Acceptance Criteria

1. k6 suite in `tests/load/` covering: dashboard, receivables list, write-off, reconciliation.
2. Validated targets: 100 RPS sustained, P95 <= 300 ms (read), 500 ms (write).
3. Optimization changes documented: indexes, query rewrites, caching, cursor pagination.

## Technical Context

### Architecture References
- **Architecture Section 16 (Performance)**: API P50 <= 80ms, P95 <= 300ms (read), 500ms (write). Frontend FCP <= 1.2s, TTI <= 2.5s.
- **Architecture Section 16.2 (Backend optimizations)**: Indexes, cursor pagination, Redis caching, materialized views.
- **Architecture Section 17 (Testing Strategy)**: Testing pyramid with E2E at the top.
- **Architecture Section 14.5 (CI/CD)**: CI pipelines for automated testing.

### Files to Create/Modify
```
tests/
├── load/
│   ├── README.md                                       # How to run load tests, interpret results
│   ├── k6.config.js                                    # Shared k6 configuration (thresholds, stages)
│   ├── scenarios/
│   │   ├── dashboard.js                                # Scenario: GET /dashboard/main at sustained RPS
│   │   ├── receivables-list.js                         # Scenario: GET /receivables with filters + pagination
│   │   ├── write-off.js                                # Scenario: POST write-off flow (read + write)
│   │   └── reconciliation.js                           # Scenario: Import OFX + auto-match flow
│   ├── helpers/
│   │   ├── auth.js                                     # Helper: login and get JWT token
│   │   └── data-generators.js                          # Helper: generate test data payloads
│   └── results/
│       └── .gitkeep                                    # Directory for storing test result reports

backend-api/
├── app/
│   ├── infrastructure/repositories/                    # Modify: add missing indexes, optimize queries
│   └── api/v1/                                         # Modify: add cursor pagination where missing

docs/
└── PERFORMANCE.md                                      # Document: optimization changes, benchmark results
```

### Dependencies
- Story 8.1 (Dashboard endpoint must exist)
- Epic 4 (Finance endpoints: receivables list, write-off)
- Epic 5 (Reconciliation endpoints)
- Story 9.5 (Observability — Prometheus metrics to monitor during load tests)

### Technical Notes
- k6 is the load testing tool. Install via `npm install -g k6` or use the Docker image. Tests are written in JavaScript.
- Shared configuration in `k6.config.js` defines: stages (ramp-up 30s to 100 RPS, sustain 5 min, ramp-down 30s), thresholds (`http_req_duration{p(95)}<300` for reads, `<500` for writes), and failure rate `<1%`.
- Each scenario authenticates via `helpers/auth.js` which calls `POST /api/v1/auth/login` and caches the JWT token for subsequent requests.
- Dashboard scenario: `GET /api/v1/dashboard/main?timeframe=month` at 100 RPS sustained. Validates response status 200 and response time.
- Receivables list scenario: `GET /api/v1/receivables?status=pendente&page_size=25` with varying page cursors and filters.
- Write-off scenario: creates a write-off (POST), then verifies the installment status change (GET). Lower RPS target (20 RPS) for write operations.
- Reconciliation scenario: uploads an OFX file, triggers auto-match, confirms matches. Measures end-to-end latency.
- After running load tests, identify bottlenecks using Grafana dashboards (from Story 9.5). Common optimizations:
  - Add composite indexes on frequently filtered columns (e.g., `installments(status, due_date)`, `contracts(customer_id, status)`).
  - Rewrite N+1 queries to use JOINs or batch fetching.
  - Add Redis caching for dashboard KPIs (TTL 60s).
  - Implement cursor pagination (keyset pagination) on all list endpoints for consistent performance.
- Document all optimization changes in `docs/PERFORMANCE.md` with before/after metrics.
- Seed script required: load tests need a database with realistic data volume (10k customers, 50k contracts, 200k installments).

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
