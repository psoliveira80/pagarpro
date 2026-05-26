---
epic: 6
story: 2
title: "Conversations & Messages Domain"
type: "Core"
status: done
---

# Story 6.2: Conversations & Messages Domain

## User Story
As a Backend developer,
I want a unified conversation and message persistence layer supporting multiple channels,
So that both WhatsApp and in-app chat share a single ConversationStore with full history retrieval.

## Acceptance Criteria
1. `conversations` table created with columns: `id` (UUID PK), `tenant_id` (FK), `customer_id` (FK, nullable -- null for in_app manager conversations), `user_id` (FK, nullable -- for in_app channel), `phone_e164` (nullable -- for whatsapp channel), `channel` (TEXT NOT NULL, enum: `whatsapp` | `in_app`), `last_message_at`, `unread_count`, `is_archived`, `agent_active` (bool default true), `agent_paused_until` (nullable timestamp), `created_at`, `updated_at`.
2. `conversation_messages` table created with columns: `id` (UUID PK), `conversation_id` (FK), `external_id` (UNIQUE, nullable -- only for whatsapp), `role` (TEXT NOT NULL, enum: `user` | `assistant` | `system` | `tool`), `tool_call_id` (TEXT, nullable -- links tool responses to tool calls), `content_text` (TEXT), `media_url` (TEXT, nullable), `media_mime` (TEXT, nullable), `sent_at` (TIMESTAMP NOT NULL), `delivered_at` (nullable), `read_at` (nullable), `sent_by` (TEXT -- `agent`, `system`, or `human:{user_id}`), `status` (TEXT), `metadata` (JSONB, nullable), `created_at`.
3. `ConversationStore` service class with methods: `get_or_create_conversation(tenant_id, channel, ...)`, `append_message(conversation_id, role, content, ...)`, `list_conversations(tenant_id, channel, filters, page)`, `get_messages(conversation_id, before_cursor, limit)`, `mark_read(conversation_id)`.
4. `GET /api/v1/conversations?channel=&search=&unread=&page=` returns paginated conversation list with customer name, last message preview, unread count, agent status. Filterable by channel.
5. `GET /api/v1/conversations/{id}/messages?before=&limit=` returns reverse-chronological cursor-paginated messages.
6. `POST /api/v1/conversations/{id}/messages` allows human operators to send messages (dispatches via WhatsApp gateway for whatsapp channel, or persists directly for in_app).
7. Messages are append-only (immutable once persisted). `external_id` UNIQUE constraint ensures idempotency for WhatsApp webhook deliveries.
8. Real-time message delivery via Redis Pub/Sub: new messages publish to channel `conversations:{conversation_id}` for SSE/WebSocket subscribers.

## Technical Context

### Architecture References
- Domain entities: `Conversation` and `ConversationMessage` (channel-agnostic, not WhatsApp-specific).
- `ConversationStore` is a shared service used by both the WhatsApp webhook pipeline (Story 6.3) and the in-app chat channel (Story 6.10).
- Real-time strategy: SSE for in-app chat streaming (Story 6.10), Redis Pub/Sub as the backbone for horizontal scaling.
- No pgvector/embedding columns -- RAG is deferred. Keep schema clean.

### Files to Create/Modify
**Backend:**
- `backend-api/app/domain/agent/conversation.py` -- `Conversation` and `ConversationMessage` domain entities
- `backend-api/app/domain/ports/conversation_store.py` -- `IConversationStore` Protocol
- `backend-api/app/infrastructure/db/models/conversation.py` -- SQLAlchemy ORM models for `conversations` and `conversation_messages`
- `backend-api/app/infrastructure/db/repositories/conversation_repo.py` -- implements `IConversationStore` with SQLAlchemy
- `backend-api/app/api/v1/conversation_routes.py` -- REST endpoints for conversations and messages (list, get messages, send message, mark read)
- `backend-api/app/application/agent/conversation_service.py` -- `ConversationStore` application service orchestrating persistence + pub/sub
- `backend-api/alembic/versions/xxxx_create_conversations_tables.py` -- migration for `conversations` + `conversation_messages` tables
- `backend-api/app/core/di.py` -- register ConversationStore in DI container

**Tests:**
- `backend-api/tests/unit/domain/test_conversation.py`
- `backend-api/tests/unit/domain/test_conversation_message.py`
- `backend-api/tests/integration/test_conversation_repo.py`
- `backend-api/tests/integration/test_conversation_routes.py`

### Dependencies
- Epic 1 foundation (database, auth, Redis Pub/Sub, SSE infrastructure from Story 1.9).
- Epic 2A Customer domain (customer_id FK for whatsapp conversations).
- Story 6.1 (WhatsApp gateway -- needed for sending human replies on whatsapp channel).

### Technical Notes
- `channel` column is indexed and used as a discriminator in queries. Conversations list endpoint filters by channel.
- Cursor pagination on messages uses `before` (message UUID) + `limit` for infinite scroll in chat UI.
- `role` enum (`user`, `assistant`, `system`, `tool`) aligns with LLM message formats for seamless agent integration.
- `tool_call_id` is populated when `role='tool'` to link a tool response back to the assistant's tool call request. This enables the ReAct loop to match tool results.
- `sent_by` field format: `"agent"` for AI agent, `"system"` for automated messages, `"human:{user_id}"` for manager-sent messages.
- `metadata` JSONB column stores channel-specific data (e.g., WhatsApp delivery ticks, template name, tool call details) without polluting the core schema.
- Redis Pub/Sub channel pattern: `conversations:{conversation_id}` for per-conversation subscriptions.
- Composite index on `(tenant_id, channel, last_message_at DESC)` for efficient conversation listing.
- Index on `(conversation_id, sent_at DESC)` for efficient message pagination.

### Session Context
- Docker-only development: backend on port 8100, PostgreSQL on 5433, Redis on 6380.
- Models folder: `app/infrastructure/db/models/`.
- Repositories folder: `app/infrastructure/db/repositories/`.
- Existing migration numbering: check latest migration number and increment.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
