---
epic: 8
story: 0
title: "Materialized Views and Dashboard Data Layer"
type: "Core"
status: done
---
# Story 8.0: Materialized Views and Dashboard Data Layer

## User Story
As a Developer,
I want materialized views for heavy dashboard queries,
So that dashboards load in under 1.5s.

## Acceptance Criteria

1. Alembic migration creates `mv_asset_roi` materialized view (as defined in Architecture Section 9.9).
2. Celery Beat job refreshes `mv_asset_roi` daily at 05:00 via `REFRESH MATERIALIZED VIEW CONCURRENTLY`.
3. Endpoint `POST /api/v1/admin/refresh-views` allows Admin to force-refresh manually.
4. Index on materialized view for fast lookups.

## Technical Context

### Architecture References
- **Architecture Section 9.9 (Materialized Views)**: Definition of `mv_asset_roi` with columns for asset ROI, depreciation, revenue, expenses.
- **Architecture Section 6 (Celery Beat Schedule)**: Daily refresh job scheduling.
- **NFR-1 (Performance)**: Dashboard render <= 1.5s on 4G.

### Files to Create/Modify
```
backend-api/
├── alembic/versions/xxx_create_mv_asset_roi.py        # Migration creating materialized view + index
├── app/infrastructure/db/views/mv_asset_roi.py        # View definition helper
├── app/workers/tasks/refresh_views.py                 # Celery task for refresh
├── app/api/v1/admin_routes.py                         # POST /admin/refresh-views endpoint (add/extend)
├── app/core/celery_beat_schedule.py                   # Add daily 05:00 schedule entry (extend)
├── app/tests/integration/
│   └── test_materialized_views.py                     # Integration tests
```

### Dependencies
- Story 3.1 (contracts/installments tables)
- Story 5.2 (payables table)

### Technical Notes
- Use `REFRESH MATERIALIZED VIEW CONCURRENTLY` to avoid locking reads during refresh.
- The `CONCURRENTLY` option requires a unique index on the materialized view — ensure the migration creates one.
- Vehicle Module will extend this view with vehicle-specific columns in its own migration.
- The Admin refresh endpoint should be rate-limited (max 1 refresh per 5 minutes) to prevent abuse.
- The Celery Beat job should log refresh duration for observability.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] No regressions
