---
epic: 6
story: 1
title: "WhatsApp Gateway Adapter"
type: "Core"
status: done
---

# Story 6.1: WhatsApp Gateway Adapter

## User Story
As the System,
I want an `IWhatsAppGateway` port with pluggable provider adapters (Z-API, Uazapi, Evolution API),
So that switching WhatsApp providers does not affect the domain logic.

## Acceptance Criteria
1. `IWhatsAppGateway` Protocol defined with methods: `send_text(phone, text)`, `send_template(phone, template_name, params)`, `send_media(phone, media_url, mime_type, caption)`, `parse_webhook(provider, headers, body) -> ReceivedMessage`.
2. Three adapters implemented: `ZapiAdapter`, `UazapiAdapter`, `EvolutionApiAdapter`. All conform to `IWhatsAppGateway` and are hot-swappable.
3. Factory pattern: `WhatsAppGatewayFactory` in `whatsapp_factory.py` reads the active provider and credentials from `integration_credentials` table (already exists from migration 0007) and returns the correct adapter instance.
4. Webhook endpoint `POST /api/v1/webhooks/whatsapp/{provider}` receives inbound messages, delegates to the correct adapter's `parse_webhook`, and emits a domain event.
5. Alembic migration pre-seeds `integration_credentials` with provider metadata rows for `zapi`, `uazapi`, and `evolution_api` (name, required_fields JSON, active flag) so the UI can render configuration forms.
6. Webhook signature validation logic lives inside each adapter's `parse_webhook` method; invalid signatures return 401.
7. Each adapter normalizes provider-specific payloads into a common `ReceivedMessage` domain object (sender_phone, text, media_url, media_mime, timestamp, external_id).
8. Unit tests for each adapter covering send_text, send_template, send_media, and parse_webhook flows with mocked HTTP responses.

## Technical Context

### Architecture References
- Hexagonal Architecture: all external providers behind a Protocol in `app/domain/ports/`. Domain never imports `infrastructure/`.
- Follows the same pattern as `IFipeProvider` (port) + `FipeApiAdapter` (adapter) and `ITrackerGateway` + tracker adapters.
- `integration_credentials` table already exists (migration 0007) with columns: id, tenant_id, provider_type, provider_name, credentials (JSONB encrypted), is_active, created_at, updated_at.
- Rate limiting: respect WhatsApp rate limits (1s default delay, 3s for new numbers) and quiet hours (no sends 22h-7h configurable).

### Files to Create/Modify
**Backend:**
- `backend-api/app/domain/ports/whatsapp_gateway.py` -- `IWhatsAppGateway` Protocol definition + `ReceivedMessage` dataclass
- `backend-api/app/infrastructure/adapters/whatsapp/__init__.py` -- package init
- `backend-api/app/infrastructure/adapters/whatsapp/zapi_adapter.py` -- Z-API adapter
- `backend-api/app/infrastructure/adapters/whatsapp/uazapi_adapter.py` -- Uazapi adapter
- `backend-api/app/infrastructure/adapters/whatsapp/evolution_api_adapter.py` -- Evolution API adapter
- `backend-api/app/infrastructure/adapters/whatsapp/whatsapp_factory.py` -- factory that reads `integration_credentials` and returns the active adapter
- `backend-api/app/api/v1/webhook_routes.py` -- `POST /api/v1/webhooks/whatsapp/{provider}` endpoint
- `backend-api/app/core/di.py` -- register WhatsApp gateway factory in DI container
- `backend-api/alembic/versions/xxxx_seed_whatsapp_providers.py` -- migration to pre-seed `integration_credentials` with provider metadata

**Tests:**
- `backend-api/tests/unit/adapters/whatsapp/test_zapi_adapter.py`
- `backend-api/tests/unit/adapters/whatsapp/test_uazapi_adapter.py`
- `backend-api/tests/unit/adapters/whatsapp/test_evolution_api_adapter.py`
- `backend-api/tests/unit/adapters/whatsapp/test_whatsapp_factory.py`
- `backend-api/tests/integration/test_webhook_whatsapp.py`

### Dependencies
- No prior story dependencies within Epic 6 (this is the foundation).
- Depends on Epic 1 foundation (DI container, settings infrastructure, `integration_credentials` table from migration 0007).

### Technical Notes
- Use `httpx.AsyncClient` for all outbound HTTP calls to provider APIs.
- Sensitive credentials (API keys, webhook secrets) are stored in `integration_credentials.credentials` JSONB column, encrypted at rest (AES-256-GCM) per architecture spec.
- Each adapter must handle provider-specific message status callbacks (sent, delivered, read) and normalize them into a common `MessageStatusUpdate` object.
- The factory caches adapter instances per tenant to avoid re-reading credentials on every call; cache invalidated when credentials are updated.
- `ReceivedMessage` includes an `external_id` field used for idempotency checks downstream.
- Evolution API is self-hosted (zero cost per message). Z-API and Uazapi are SaaS alternatives.
- The webhook endpoint does NOT require JWT auth (it is called by external providers), but MUST validate webhook signatures.

### Session Context
- Docker-only development: backend on port 8100, PostgreSQL on 5433, Redis on 6380.
- Adapters folder convention: `app/infrastructure/adapters/` (not `integrations/`).
- Existing port examples: `app/domain/ports/fipe_provider.py`, `app/domain/ports/tracker_gateway.py`, `app/domain/ports/email_sender.py`.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
