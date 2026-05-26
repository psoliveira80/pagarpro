---
epic: 10
story: 6
title: "Worker Scheduler Consolidation and Monitoring"
type: "Core"
status: ready-for-dev
---

# Story 10.6: Worker Scheduler Consolidation and Monitoring

## User Story
As a System Administrator,
I want all scheduled tasks consolidated with proper crontab timing and a monitoring dashboard,
So that I can verify all automations are running correctly.

## Acceptance Criteria

1. All Celery Beat tasks use `crontab()` with exact times (not intervals):
   - 03:00 daily-backup
   - 04:00 generate-recurring-payables
   - 05:00 calculate-customer-scores
   - 06:00 generate-monthly-installments
   - 08:00 check-upcoming-due-dates
   - 09:00 check-overdue-installments
   - */30 check-paid-installments
   - */5 check-channel-health
   - */60 refresh-materialized-views
2. Admin endpoint GET `/api/v1/admin/scheduled-tasks` — lists all scheduled tasks with last run, next run, status.
3. Frontend: "Tarefas Agendadas" page at `/system/settings/scheduler` — table showing each task, schedule, last execution, status badge (ok/failed/never ran).
4. Failed task sends SSE alert to admin.
5. Tests: verify crontab configuration is valid.

## Technical Context

### Files to Create/Modify
```
backend-api/
├── app/workers/__init__.py                    # Consolidate all beat_schedule with crontab
├── app/api/v1/admin_routes.py                 # Add scheduled-tasks endpoint
frontend/
├── src/app/features/settings/scheduler.component.ts/html/css
├── src/app/features/system/system.routes.ts   # Add /settings/scheduler route
```

### Technical Notes
- Use `celery.schedules.crontab` instead of integer intervals
- Task results stored in Redis (Celery result backend) — read last execution info
- Add "Tarefas Agendadas" to settings sidebar menu

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] No regressions
