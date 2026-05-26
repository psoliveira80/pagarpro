---
epic: 9
story: 2
title: "Audit Log Search and Viewer"
type: "Core"
status: done
---

# Story 9.2: Audit Log Search and Viewer

## User Story
As an Auditor,
I want to query the entire action history,
So that I can trace any event.

## Acceptance Criteria

1. Route `/system/audit` with searchable table: user, action, entity, date, IP, payload.
2. Filters: user, entity, action (multi-select), date range.
3. Row expand: payload diff before/after in collapsible JSON pretty-print.
4. Integrity indicator: "OK" if HMAC verifies, "ALERT: tampered" if not.
5. CSV export respects active filter.

## Technical Context

### Architecture References
- **Architecture Section 5 (Admin / Configuration)**: `GET /api/v1/admin/audit-log?...` endpoint with query parameters.
- **Architecture Section 10.1**: Frontend audit UI at `frontend/src/app/features/system/audit/`.
- **Architecture Section 15.1 (Security)**: HMAC-signed audit entries for tamper detection.
- **Architecture Section 6**: `backend-api/app/application/shared/audit_logger.py` for the existing audit logging service.

### Files to Create/Modify
```
backend-api/
├── app/
│   ├── api/v1/admin_routes.py                          # Add GET /admin/audit-log with filters + pagination
│   ├── application/admin/
│   │   ├── search_audit_log.py                         # Use case: search/filter audit entries
│   │   ├── verify_audit_integrity.py                   # Use case: verify HMAC of a single entry
│   │   ├── export_audit_csv.py                         # Use case: export filtered results to CSV
│   │   └── schemas.py                                  # Add AuditLogSearchIn, AuditLogEntryOut
│   ├── infrastructure/repositories/
│   │   └── audit_repository.py                         # Query audit_logs with filters, pagination, full-text
│   └── application/shared/
│       └── audit_logger.py                             # Modify: add HMAC verification method

frontend/
├── src/app/features/system/audit/
│   ├── audit-list.component.ts                         # Main audit log page with searchable table
│   ├── audit-list.component.html
│   ├── audit-list.component.css
│   ├── audit-detail-modal.component.ts                 # Expandable row: JSON diff before/after
│   ├── audit-detail-modal.component.html
│   ├── audit-detail-modal.component.css
│   └── audit.routes.ts                                 # Route: /system/audit
├── src/app/features/system/audit/components/
│   ├── audit-filters/
│   │   ├── audit-filters.component.ts                  # Filter bar: user, entity, action, date range
│   │   ├── audit-filters.component.html
│   │   └── audit-filters.component.css
│   ├── integrity-badge/
│   │   ├── integrity-badge.component.ts                # "OK" or "ALERT: tampered" indicator
│   │   ├── integrity-badge.component.html
│   │   └── integrity-badge.component.css
│   └── json-diff-viewer/
│       ├── json-diff-viewer.component.ts               # Collapsible JSON pretty-print with before/after diff
│       ├── json-diff-viewer.component.html
│       └── json-diff-viewer.component.css
└── src/app/core/services/audit.service.ts              # HTTP calls to /api/v1/admin/audit-log
```

### Dependencies
- Epic 1 (Auth, RBAC — Auditor/Admin role required; HMAC signing established in audit_logger)
- Audit log entries written by all prior epics (mutations across the system)

### Technical Notes
- The audit_logs table stores: `id`, `user_id`, `action`, `entity_type`, `entity_id`, `ip_address`, `payload_before` (JSONB), `payload_after` (JSONB), `hmac_signature`, `created_at`.
- HMAC verification: recompute HMAC over the stored fields using the server's HMAC secret key and compare with `hmac_signature`. Display "OK" (green badge) if match, "ALERT: tampered" (red badge) if mismatch.
- Filters map to query parameters: `?user_id=...&entity_type=...&action=...&date_from=...&date_to=...&page=...&page_size=...`. Action filter supports multi-select (comma-separated).
- CSV export streams the filtered result set with columns: timestamp, user_email, action, entity_type, entity_id, ip_address, payload_summary. Uses `StreamingResponse` for large exports.
- JSON diff viewer renders `payload_before` and `payload_after` side-by-side with highlighted differences. Use a simple recursive diff algorithm to mark added/removed/changed keys.
- Pagination uses cursor-based pagination (by `created_at` + `id`) for consistent ordering on large datasets.
- The table supports sorting by date (default: newest first), user, action, and entity.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
