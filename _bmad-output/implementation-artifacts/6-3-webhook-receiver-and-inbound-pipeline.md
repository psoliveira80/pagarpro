---
epic: 6
story: 3
title: "Webhook Receiver and Inbound Pipeline"
type: "Core"
status: done
---

# Story 6.3: Webhook Receiver and Inbound Pipeline

## User Story
As the System,
I want to receive and process inbound WhatsApp messages with idempotency,
So that no message is ever lost.

## Acceptance Criteria
1. `POST /api/v1/webhooks/whatsapp/{provider}` validates webhook signature per provider; raw payload persisted to `webhook_events_raw` table with idempotency on `(provider, external_id)`.
2. Handler enqueues a Celery task on the `whatsapp_inbound` queue after raw persistence.
3. Worker normalizes the raw payload to a `ReceivedMessage` domain object, finds or creates conversation by phone number, persists `WhatsAppMessage`, and enqueues an agent-turn task.
4. Inbound media (images, PDFs, audio) downloaded to MinIO before OCR/classification processing.
5. Duplicate `external_id` returns `{"status": "duplicate"}` with HTTP 200, no side effects.
6. Failed processing does not lose the raw event — retry from `webhook_events_raw`.

## Technical Context

### Architecture References
- Webhook ingestion framework: `webhook_events_raw` table with `UNIQUE(provider, external_id)` established in Epic 1.
- Inbound webhook route: `POST /webhooks/whatsapp/{provider}` per architecture API table.
- Celery task: `backend-api/app/workers/tasks/handle_inbound_whatsapp.py`.
- Media storage: MinIO via `IStorageProvider` port.
- After message persistence, enqueue `run_agent_turn` task (Story 6.4).

### Files to Create/Modify
**Backend:**
- `backend-api/app/api/v1/webhook_routes.py` — add WhatsApp webhook endpoint `POST /webhooks/whatsapp/{provider}`
- `backend-api/app/application/collections/handle_inbound_message.py` — use case: normalize, find/create conversation, persist message, enqueue agent turn
- `backend-api/app/workers/tasks/handle_inbound_whatsapp.py` — Celery task wrapping the use case
- `backend-api/app/infrastructure/parsing/pix_receipt_classifier.py` — heuristic classifier for inbound media (image/PDF with Pix patterns)
- `backend-api/app/domain/collections/message.py` — add `ReceivedMessage` value object for normalized inbound data
- `backend-api/app/workers/celery_app.py` — register `whatsapp_inbound` queue

**Tests:**
- `backend-api/tests/unit/application/test_handle_inbound_message.py`
- `backend-api/tests/integration/test_webhook_whatsapp.py`
- `backend-api/tests/unit/infrastructure/test_pix_receipt_classifier.py`

### Dependencies
- Story 6.1 (WhatsApp gateway adapter — `webhook_parse` method for signature validation and payload normalization).
- Story 6.2 (Conversations & Messages domain — tables and repository for persistence).
- Epic 1 (`webhook_events_raw` table).

### Technical Notes
- The webhook endpoint must return HTTP 200 as fast as possible (< 200ms) to avoid provider retries; all heavy processing is async via Celery.
- `webhook_parse` on the selected adapter handles signature validation and returns a normalized `ReceivedMessage` or raises `InvalidSignature`.
- Media download to MinIO should use a separate Celery task or be part of the inbound handler with timeout protection.
- The `whatsapp_inbound` Celery queue should have retry policy: max 3 retries with exponential backoff (10s, 60s, 300s).
- Conversation lookup is by `phone_e164` — if no conversation exists for the phone, create one and link to customer by phone match.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
