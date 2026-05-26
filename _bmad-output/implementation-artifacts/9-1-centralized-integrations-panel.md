---
epic: 9
story: 1
title: "Centralized Integrations Panel"
type: "Core"
status: done
---

# Story 9.1: Centralized Integrations Panel

## User Story
As an Admin,
I want a single screen to manage every integration,
So that plug-and-play is operationally real.

## Acceptance Criteria

1. Route `/system/config/integrations` with cards per category: WhatsApp Gateway, Open Finance / Banks, Payment Gateway, LLM Provider, OCR Provider, Storage, PDF Renderer. Module-specific integrations: e.g., Vehicle Module adds FIPE, Tracker.
2. Each card: active provider, status (healthy/degraded/error), actions: "Test connection", "Switch provider", "Configure".
3. "Switch provider": dialog lists available adapters with required credentials.
4. Credentials encrypted at rest (AES-256-GCM with master key).
5. Every change writes audit-log diff with secrets masked.
6. `GET /api/v1/integrations/health` returns status of every provider.

## Technical Context

### Architecture References
- **Architecture Section 5 (Admin / Configuration)**: `GET /api/v1/admin/integrations`, `PUT /api/v1/admin/integrations/{provider}`, `POST /api/v1/admin/integrations/{provider}/test`.
- **Architecture Section 15.1 (Security)**: AES-256-GCM encryption for sensitive fields; credentials encrypted at rest.
- **Architecture Section 10.1**: Frontend integrations UI at `frontend/src/app/features/system/config/integrations/`.
- **Architecture Section 6**: `backend-api/app/api/v1/admin_routes.py` for admin endpoints.
- **Architecture Section 6 (Infrastructure/Security)**: `backend-api/app/infrastructure/security/encryption.py` for AES-256-GCM.

### Files to Create/Modify
```
backend-api/
├── app/
│   ├── api/v1/admin_routes.py                          # Add integration management endpoints
│   ├── application/admin/
│   │   ├── __init__.py
│   │   ├── list_integrations.py                        # Use case: list all integration categories + status
│   │   ├── update_integration.py                       # Use case: update provider credentials (encrypted)
│   │   ├── test_integration.py                         # Use case: test connection to a provider
│   │   ├── switch_provider.py                          # Use case: switch active provider for a category
│   │   └── schemas.py                                  # IntegrationCardOut, IntegrationUpdateIn, HealthOut
│   ├── domain/integrations/
│   │   ├── __init__.py
│   │   ├── integration_registry.py                     # Registry of integration categories + available adapters
│   │   └── health_checker.py                           # Domain logic: check health of each provider
│   ├── infrastructure/repositories/
│   │   └── integration_repository.py                   # CRUD for integration_credentials table
│   └── infrastructure/security/
│       └── encryption.py                               # Modify: ensure encrypt/decrypt for credentials

frontend/
├── src/app/features/system/config/integrations/
│   ├── integrations.component.ts                       # Main integrations page with category cards
│   ├── integrations.component.html
│   ├── integrations.component.css
│   ├── components/
│   │   ├── integration-card/
│   │   │   ├── integration-card.component.ts           # Card: provider, status indicator, action buttons
│   │   │   ├── integration-card.component.html
│   │   │   └── integration-card.component.css
│   │   ├── credentials-modal/
│   │   │   ├── credentials-modal.component.ts          # Dialog: configure credentials (masked input)
│   │   │   ├── credentials-modal.component.html
│   │   │   └── credentials-modal.component.css
│   │   └── test-connection-button/
│   │       ├── test-connection-button.component.ts     # Button: test + show result (success/error)
│   │       ├── test-connection-button.component.html
│   │       └── test-connection-button.component.css
│   └── switch-provider-dialog/
│       ├── switch-provider-dialog.component.ts         # Dialog: list adapters, select, enter credentials
│       ├── switch-provider-dialog.component.html
│       └── switch-provider-dialog.component.css
└── src/app/core/services/integration.service.ts        # HTTP calls to /api/v1/admin/integrations/*
```

### Dependencies
- Epic 1 (Auth, RBAC — Admin role required)
- Hexagonal port/adapter pattern established across Epics 1-7 (each port already created by the epic that first needed it)
- `ModuleRegistry` for discovering module-specific integrations

### Technical Notes
- The `integration_registry.py` maintains a static map of integration categories (e.g., `whatsapp_gateway`, `payment_gateway`, `ocr_provider`) to their available adapter implementations. Module-specific categories are discovered via `ModuleRegistry`.
- Credentials are stored in an `integration_credentials` table with `config` JSONB encrypted via AES-256-GCM using the master key from environment. The encryption service in `backend-api/app/infrastructure/security/encryption.py` handles encrypt/decrypt.
- The "Test connection" action calls a `test()` method on the adapter interface for the given provider. Each adapter must implement this (e.g., WhatsApp adapter sends a health ping to Evolution API).
- The health endpoint `GET /api/v1/integrations/health` iterates all active integrations, calls their test method with a short timeout, and returns a map of `{category: {provider, status, latency_ms, error}}`.
- Audit log entries for credential changes must mask secret values: log the diff showing which fields changed but replace values with `"***"`.
- The switch provider flow: deactivate current adapter, activate new adapter, run test connection, persist if successful, rollback if failed.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
