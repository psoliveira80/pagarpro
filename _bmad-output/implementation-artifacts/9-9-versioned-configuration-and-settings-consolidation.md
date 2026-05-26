---
epic: 9
story: 9
title: "Versioned Configuration and Settings Consolidation"
type: "Core"
status: done
---

# Story 9.9: Versioned Configuration and Settings Consolidation

## User Story
As an Admin,
I want all configurations versioned with change history,
So that I can audit who changed what and when.

## Acceptance Criteria

1. Every configuration section (Company, Billing, Agent, Integrations, Modules, Permissions, Templates) maintains a versioned history with who, when, and prior value.
2. Route `/system/config/history` shows configuration change log with diff viewer.
3. Consolidated Settings screen at `/system/config` with all sections.

## Technical Context

### Architecture References
- **Architecture Section 5 (Admin / Configuration)**: `GET /api/v1/admin/settings`, `PUT /api/v1/admin/settings` endpoints.
- **Architecture Section 10.1**: Frontend config at `frontend/src/app/features/system/config/` with sub-sections: `general/`, `company/`, `billing-rules/`, `agent/`, `integrations/`, `modules/`, `users/`, `permissions/`, `templates/`.
- **Architecture Section 9 (Data Model)**: `feature_flags` table for versioned configuration flags.
- **Architecture Section 15.1 (Security)**: Sensitive configuration values encrypted at rest.

### Files to Create/Modify
```
backend-api/
├── app/
│   ├── api/v1/admin_routes.py                              # Add versioned settings endpoints
│   ├── application/admin/
│   │   ├── get_settings.py                                 # Use case: get consolidated settings by section
│   │   ├── update_settings.py                              # Use case: update a config section (with versioning)
│   │   ├── get_config_history.py                           # Use case: list configuration change history
│   │   └── schemas.py                                      # Add SettingsSectionOut, SettingsUpdateIn, ConfigHistoryOut
│   ├── domain/config/
│   │   ├── __init__.py
│   │   └── config_versioning.py                            # Domain logic: create version snapshot before update
│   └── infrastructure/repositories/
│       ├── settings_repository.py                          # CRUD for settings table
│       └── config_history_repository.py                    # CRUD for config_versions table
├── alembic/versions/
│   └── xxxx_add_config_versions_table.py                   # Migration: config_versions table

frontend/
├── src/app/features/system/config/
│   ├── config.component.ts                                 # Consolidated settings page with section tabs
│   ├── config.component.html
│   ├── config.component.css
│   ├── general/
│   │   ├── general-settings.component.ts                   # General settings section
│   │   ├── general-settings.component.html
│   │   └── general-settings.component.css
│   ├── company/
│   │   ├── company-settings.component.ts                   # Company info settings
│   │   ├── company-settings.component.html
│   │   └── company-settings.component.css
│   ├── config-history/
│   │   ├── config-history.component.ts                     # Configuration change log with diff viewer
│   │   ├── config-history.component.html
│   │   └── config-history.component.css
│   ├── config-history/components/
│   │   └── config-diff-viewer/
│   │       ├── config-diff-viewer.component.ts             # JSON diff viewer for config changes
│   │       ├── config-diff-viewer.component.html
│   │       └── config-diff-viewer.component.css
│   └── config.routes.ts                                    # Modify: add /config/history route, consolidate all section routes
└── src/app/core/services/settings.service.ts               # HTTP calls to /api/v1/admin/settings, /config/history
```

### Dependencies
- Epic 1 (Auth, RBAC — Admin role required)
- Stories 9.1 (Integrations panel) and 9.3 (Module management) — these config sections must already exist
- Epic 7 (Agent configuration section)

### Technical Notes
- Create a `config_versions` table: `id` (UUID), `section` (text: 'company', 'billing', 'agent', 'integrations', 'modules', 'permissions', 'templates'), `version` (integer, auto-increment per section), `value_before` (JSONB), `value_after` (JSONB), `changed_by_user_id` (UUID FK), `changed_at` (timestamptz), `change_summary` (text).
- Every `PUT /api/v1/admin/settings/{section}` must: (1) read current value, (2) insert a `config_versions` row with before/after, (3) update the settings value, (4) write audit log. All in a single transaction.
- The consolidated settings page at `/system/config` uses a tab layout: Company, Billing Rules, Agent, Integrations, Modules, Users & Permissions, Templates, History. Each tab lazy-loads its component.
- The config history page shows a filterable table: section, version, changed_by, changed_at, change_summary. Expanding a row shows the diff viewer with before/after JSON comparison.
- Settings storage: use a `settings` table with `section` (PK) and `value` (JSONB). This is simpler than multiple tables per section and allows the consolidated approach.
- Sensitive values in settings (API keys, secrets) must be encrypted before storage and decrypted on read, using the same AES-256-GCM encryption service from Story 9.1.
- The diff viewer can reuse the `json-diff-viewer` component created in Story 9.2 (Audit Log).

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
