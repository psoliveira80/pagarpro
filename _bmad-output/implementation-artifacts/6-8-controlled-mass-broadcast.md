---
epic: 6
story: 8
title: "Controlled Mass Broadcast"
type: "Core"
status: done
---

# Story 6.8: Controlled Mass Broadcast

## User Story
As a Manager,
I want to dispatch preventive collections to all customers due tomorrow,
So that I save time at scale.

## Acceptance Criteria
1. Route `/system/inbox/broadcast` with audience filters (due date range, overdue status, customer score range, contract status) and live recipient count/preview.
2. Message editor with placeholder insertion (same placeholders as agent templates).
3. Double-confirmation modal requiring password entry + display of 3 sample rendered messages before dispatch.
4. Time window configuration + staggered sends (1 message per X seconds, configurable) to avoid WhatsApp bans.
5. Post-broadcast report: sent/delivered/read/failed/replied counts, updated in real-time via webhook status updates.
6. Hard cap of 200 recipients per broadcast (anti-spam safety).

## Technical Context

### Architecture References
- Frontend: `frontend/src/app/features/inbox/components/broadcast-modal/broadcast-modal.component.ts`.
- Backend use case: `backend-api/app/application/collections/broadcast_send.py`.
- Celery task for staggered dispatch with configurable delay between sends.
- WhatsApp rate limiting: 1s default delay between sends, 3s for new numbers. No sends between 22h-7h.

### Files to Create/Modify
**Frontend:**
- `frontend/src/app/features/inbox/components/broadcast-modal/broadcast-modal.component.ts` — broadcast creation form with filters, preview, confirmation
- `frontend/src/app/features/inbox/components/broadcast-modal/broadcast-modal.component.html`
- `frontend/src/app/features/inbox/components/broadcast-modal/broadcast-modal.component.css`
- `frontend/src/app/features/inbox/inbox.component.ts` — add broadcast button to inbox toolbar

**Backend:**
- `backend-api/app/api/v1/conversation_routes.py` — add endpoints: `POST /api/v1/broadcasts` (create), `GET /api/v1/broadcasts/{id}` (status/report), `GET /api/v1/broadcasts/{id}/preview` (sample renderings)
- `backend-api/app/application/collections/broadcast_send.py` — use case: validate audience, render templates, create broadcast record, enqueue staggered tasks
- `backend-api/app/workers/tasks/broadcast_dispatch.py` — Celery task: sends individual messages with configurable delay, updates status per recipient
- `backend-api/app/infrastructure/db/models/broadcast.py` — ORM models: `Broadcast` (id, filters, template, status, created_by, created_at), `BroadcastRecipient` (id, broadcast_id, customer_id, conversation_id, status, sent_at, delivered_at, read_at, error)
- `backend-api/alembic/versions/xxxx_create_broadcast_tables.py` — migration

**Tests:**
- `backend-api/tests/unit/application/test_broadcast_send.py`
- `backend-api/tests/integration/test_broadcast_dispatch.py`
- `frontend/src/app/features/inbox/components/broadcast-modal/broadcast-modal.component.spec.ts`

### Dependencies
- Story 6.1 (WhatsApp gateway — for sending messages).
- Story 6.2 (Conversations domain — for finding/creating conversations per recipient).
- Story 6.7 (Inbox UI — broadcast is launched from the inbox).

### Technical Notes
- The 200-recipient hard cap is enforced both in the frontend (disable submit if > 200) and backend (validation error if > 200).
- Staggered sends: Celery task uses `countdown` parameter to schedule each message with incremental delay (e.g., recipient 1 at t=0, recipient 2 at t=1s, recipient 3 at t=2s).
- Time window enforcement: if current time is outside the configured service window (default 7h-22h), the broadcast is scheduled for the next valid window.
- Template rendering: replace placeholders with actual customer data. The preview endpoint renders 3 random recipients for admin review.
- Password confirmation: the broadcast creation endpoint requires the user's password as a second factor, verified via `password_hasher.verify`.
- Webhook status callbacks update `BroadcastRecipient.status` as messages are delivered/read.
- The post-broadcast report page uses SSE (`/sse/notifications`) to update delivery stats in real-time.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
