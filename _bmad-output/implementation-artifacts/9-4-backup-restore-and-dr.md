---
epic: 9
story: 4
title: "Backup, Restore, and DR"
type: "Core"
status: done
---

# Story 9.4: Backup, Restore, and DR

## User Story
As an Operator,
I want verified automatic backups,
So that disasters are recoverable within SLA.

## Acceptance Criteria

1. Daily Celery beat at 03:00: `pg_dump`, compress, ship to off-site (S3/B2/Wasabi, configurable), 30-day retention.
2. Continuous WAL archiving via wal-g or pgBackRest.
3. Weekly restore test in isolated environment with smoke tests; failures alert admins.
4. `RUNBOOK_DR.md` committed with step-by-step restore playbook (RTO < 4h).

## Technical Context

### Architecture References
- **Architecture Section 6 (Workers)**: `backend-api/app/workers/tasks/backup.py` for Celery backup task.
- **Architecture Section 6 (Workers)**: `backend-api/app/workers/beat_schedule.py` for scheduling the daily backup.
- **Architecture Section 14 (Deployment)**: Docker Compose and infrastructure configuration.
- **Architecture Section 15.1 (Security)**: Backups must be encrypted; connection uses TLS.

### Files to Create/Modify
```
backend-api/
├── app/
│   ├── workers/tasks/
│   │   └── backup.py                                      # Celery task: pg_dump, compress, upload to off-site storage
│   ├── workers/beat_schedule.py                            # Modify: add daily backup at 03:00 UTC
│   ├── application/admin/
│   │   ├── trigger_backup.py                              # Use case: manual backup trigger (Admin only)
│   │   └── list_backups.py                                # Use case: list available backups with metadata
│   ├── infrastructure/adapters/
│   │   └── backup_storage_adapter.py                      # Adapter: upload/list/delete backups on S3/B2/Wasabi
│   └── domain/ports/
│       └── backup_storage_provider.py                     # Port: IBackupStorageProvider interface

infra/
├── backup/
│   ├── wal-g/
│   │   └── wal-g.env.example                              # WAL-G configuration template
│   ├── restore-test/
│   │   ├── docker-compose.restore-test.yml                # Isolated Postgres for weekly restore test
│   │   └── smoke-test.sh                                  # Script: restore backup + run basic queries
│   └── scripts/
│       ├── backup.sh                                      # Shell wrapper for pg_dump + compress + upload
│       └── restore.sh                                     # Shell script: download + decompress + pg_restore

docs/
└── RUNBOOK_DR.md                                          # Step-by-step disaster recovery playbook (RTO < 4h)
```

### Dependencies
- Epic 1 (PostgreSQL database, Celery + Redis infrastructure)
- Object storage adapter (S3-compatible) — may reuse MinIO adapter pattern from Epic 1

### Technical Notes
- The backup Celery task runs `pg_dump --format=custom --compress=9` against the production database, producing a compressed dump file. The file is then uploaded to the configured off-site storage (S3, Backblaze B2, or Wasabi) via `IBackupStorageProvider`.
- Backup naming convention: `backup-{YYYY-MM-DD-HHmmss}.dump.gz`. Metadata (size, checksum SHA256, duration) is logged.
- 30-day retention: after successful upload, the task lists existing backups and deletes any older than 30 days.
- WAL archiving: configure `wal-g` or `pgBackRest` in the PostgreSQL container for continuous WAL shipping to the same off-site storage. This enables point-in-time recovery (PITR).
- Weekly restore test: a separate Celery beat task (or CI cron job) spins up an isolated Postgres container via `docker-compose.restore-test.yml`, restores the latest backup, runs `smoke-test.sh` (basic SELECT queries against key tables), and reports success/failure. Failures trigger an alert to admins via the notification system.
- `RUNBOOK_DR.md` must include: prerequisites, step-by-step restore procedure, verification checklist, rollback plan, and contact escalation. Target RTO < 4 hours.
- The `IBackupStorageProvider` port follows the hexagonal pattern: the adapter is injected via DI, making it easy to swap storage providers.
- Backup encryption: the dump file is encrypted with AES-256 before upload using a dedicated backup encryption key (separate from the application encryption key).

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
