---
epic: 9
story: 3
title: "Module Management UI"
type: "Core"
status: done
---

# Story 9.3: Module Management UI

## User Story
As an Admin,
I want to enable/disable vertical modules and configure their hooks,
So that the platform adapts to my business needs.

## Acceptance Criteria

1. Route `/system/config/modules` lists registered modules with: name, status (active/inactive), toggle, "Configure" button.
2. **Given** toggle off, **Then** module stops receiving events, its hooks are deactivated, its UI sections/tabs/widgets disappear, menus hide module-specific items.
3. **Given** toggle on, **Then** module registers, receives events, UI sections appear.
4. "Configure" opens module-specific settings (e.g., Vehicle Module: block policy thresholds, FIPE refresh schedule).
5. Hooks configuration: list of events the module subscribes to, with policy editor per event.

## Technical Context

### Architecture References
- **Architecture Section 5 (Admin / Configuration)**: `GET /api/v1/admin/modules`, `PUT /api/v1/admin/modules/{asset_type}/config`, `GET /api/v1/admin/modules/{asset_type}/hooks`, `PUT /api/v1/admin/modules/{asset_type}/hooks/{event}`.
- **Architecture Section 7.1 (IAssetModule Protocol)**: Module interface with `get_hooks()` returning `IModuleHooks`.
- **Architecture Section 7.2 (Module Registration)**: `ModuleRegistry` for runtime registration/discovery.
- **Architecture Section 10.1**: Frontend modules config at `frontend/src/app/features/system/config/modules/`.

### Files to Create/Modify
```
backend-api/
├── app/
│   ├── api/v1/admin_routes.py                              # Add module management endpoints
│   ├── application/admin/
│   │   ├── list_modules.py                                 # Use case: list registered modules with status
│   │   ├── toggle_module.py                                # Use case: enable/disable a module
│   │   ├── configure_module.py                             # Use case: update module-specific settings
│   │   ├── list_module_hooks.py                            # Use case: list hooks for a module
│   │   ├── configure_hook.py                               # Use case: update hook policy for an event
│   │   └── schemas.py                                      # Add ModuleOut, ModuleConfigIn, HookPolicyIn
│   ├── core/module_registry.py                             # Modify: add enable/disable state, persist to DB
│   └── infrastructure/repositories/
│       └── module_config_repository.py                     # CRUD for module_configs table (status, settings)

frontend/
├── src/app/features/system/config/modules/
│   ├── modules-list.component.ts                           # Module list with toggle and configure button
│   ├── modules-list.component.html
│   ├── modules-list.component.css
│   ├── module-hooks-config.component.ts                    # Hook list with per-event policy editor
│   ├── module-hooks-config.component.html
│   ├── module-hooks-config.component.css
│   └── components/
│       ├── module-card/
│       │   ├── module-card.component.ts                    # Card: name, status toggle, configure CTA
│       │   ├── module-card.component.html
│       │   └── module-card.component.css
│       ├── module-settings-dialog/
│       │   ├── module-settings-dialog.component.ts         # Module-specific settings form (dynamic)
│       │   ├── module-settings-dialog.component.html
│       │   └── module-settings-dialog.component.css
│       └── hook-policy-editor/
│           ├── hook-policy-editor.component.ts             # Per-event policy: enabled, thresholds, conditions
│           ├── hook-policy-editor.component.html
│           └── hook-policy-editor.component.css
├── src/app/core/services/module.service.ts                 # HTTP calls to /api/v1/admin/modules/*
└── src/app/features/system/components/sidebar/
    └── sidebar.component.ts                                # Modify: conditionally show/hide module menu items
```

### Dependencies
- Epic 1 (Auth, RBAC — Admin role required)
- Epic 2B (Vehicle Module registered in `ModuleRegistry`)
- Architecture Section 7.2 (Module Registration bootstrap in `main.py`)

### Technical Notes
- Module enable/disable state must be persisted in a `module_configs` table: `asset_type` (PK), `is_active` (bool), `settings` (JSONB), `updated_at`. On application startup, `ModuleRegistry` checks this table and only activates modules marked as active.
- When a module is toggled off, the `EventDispatcher` must skip routing events to that module's hooks. The frontend must re-fetch the active modules list and reactively hide/show sidebar items, tabs, and dashboard widgets.
- The sidebar component should call `GET /api/v1/admin/modules` on init and use the response to conditionally render module-specific menu items (e.g., "Vehicles", "Fleet Map").
- Hook policy editor allows per-event configuration: enable/disable the hook, set thresholds (e.g., "only trigger remote block after 3 overdue installments"), and set conditions (e.g., "only for contracts > R$5000").
- Module-specific settings are rendered dynamically from a JSON schema provided by the module's configuration metadata. For Vehicle Module: block policy thresholds, FIPE refresh schedule, tracker polling interval.
- Every toggle and configuration change writes an audit log entry.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
