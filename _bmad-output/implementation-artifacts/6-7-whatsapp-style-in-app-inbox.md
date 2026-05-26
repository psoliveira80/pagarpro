---
epic: 6
story: 7
title: "WhatsApp-style In-App Inbox"
type: "Core"
status: done
---

# Story 6.7: WhatsApp-style In-App Inbox

## User Story
As a Manager,
I want to see and reply to WhatsApp conversations in a familiar interface with status indicators and human takeover controls,
So that I can monitor agent performance and intervene when needed.

## Acceptance Criteria
1. Route `/system/inbox` with 3-pane layout:
   - **Left (320 px)**: conversation list with avatar, name, last message preview, timestamp, unread badge, agent status icon (active/paused/off), and **status badge**: green dot = flowing (agent responding normally), yellow dot = needs attention (agent hit max iterations or confidence < medium), red dot = no response (last inbound message > 15 min with no agent reply).
   - **Center (flex)**: message thread with bubbles (green for outbound, white for inbound), day separators, timestamps, delivery ticks, image lightbox, audio player, PDF preview.
   - **Right (340 px, collapsible)**: customer context pane (avatar, name, score, status, open titles with updated interest/fine values, quick actions: Generate Pix, Mark as Paid, Escalate).
2. **Status badges** on each conversation in the list:
   - **Green** (flowing): agent is active and last exchange was successful.
   - **Yellow** (needs attention): agent flagged low confidence, hit max iterations, or customer repeated a question.
   - **Red** (no response): inbound message received but no agent reply within configurable threshold (default 15 min).
3. **"Intervir" (human takeover) button** in conversation header: pauses the AI agent on that conversation, marks it as human-controlled, and focuses the input bar. The agent remains paused until explicitly resumed via a "Retomar Agente" button.
4. **Status-based filtering**: conversation list can be filtered by status (all, flowing, needs-attention, no-response) and sorted by last message time or status severity.
5. Chat input bar supports: text input, file attachments, emoji picker, audio recording.
6. Keyboard shortcuts: arrow keys walk conversations, `Ctrl+Enter` sends message, `/` focuses search.
7. In-conversation text search with highlighted results.
8. "Agent is typing..." indicator displayed while the agent turn is processing.
9. Real-time updates via Redis Pub/Sub -- new messages appear instantly without refresh.

## Technical Context

### Architecture References
- Frontend components: `frontend/src/app/features/inbox/` with sub-components for each pane.
- Real-time delivery: SSE or WebSocket connected to Redis Pub/Sub channel `conversations:{conversation_id}`.
- Backend endpoints: `GET /api/v1/conversations`, `GET /api/v1/conversations/{id}/messages`, `POST /api/v1/conversations/{id}/messages`, `POST /api/v1/conversations/{id}/agent/pause`, `POST /api/v1/conversations/{id}/agent/resume`, `POST /api/v1/conversations/{id}/mark-read`.
- Status badges are computed server-side based on conversation state and returned in the conversation list response.

### Files to Create/Modify
**Frontend:**
- `frontend/src/app/features/inbox/inbox.component.ts` -- 3-pane layout shell
- `frontend/src/app/features/inbox/inbox.component.html`
- `frontend/src/app/features/inbox/inbox.component.css`
- `frontend/src/app/features/inbox/components/conversation-list/conversation-list.component.ts` -- left pane with search, status filters, status badges, unread badge
- `frontend/src/app/features/inbox/components/conversation-list/conversation-status-badge.component.ts` -- green/yellow/red status dot component
- `frontend/src/app/features/inbox/components/chat-thread/chat-thread.component.ts` -- center pane message thread with infinite scroll
- `frontend/src/app/features/inbox/components/chat-message/chat-message.component.ts` -- individual message bubble (green/white, ticks, media)
- `frontend/src/app/features/inbox/components/chat-input/chat-input.component.ts` -- input bar with attachments, emoji, audio
- `frontend/src/app/features/inbox/components/customer-context-pane/customer-context-pane.component.ts` -- right pane with customer data and quick actions
- `frontend/src/app/features/inbox/components/human-takeover/human-takeover.component.ts` -- "Intervir" / "Retomar Agente" toggle button
- `frontend/src/app/features/inbox/inbox.routes.ts` -- lazy-loaded route definition
- `frontend/src/app/core/services/inbox-realtime.service.ts` -- SSE/WebSocket connection service for real-time updates

**Backend:**
- `backend-api/app/api/v1/conversation_routes.py` -- add `POST /conversations/{id}/agent/pause` (human takeover), `POST /conversations/{id}/agent/resume`, `POST /conversations/{id}/mark-read`, conversation list with computed status field
- `backend-api/app/application/agent/conversation_status.py` -- logic to compute conversation status (flowing/needs_attention/no_response) based on message timestamps, agent_runs, and configuration
- `backend-api/app/application/agent/pause_agent.py` -- use case: set `agent_paused_until=NULL` (indefinite pause) + `agent_active=false` for human takeover
- `backend-api/app/application/agent/send_human_message.py` -- use case: human sends message via WhatsApp gateway, persists in ConversationStore

**Tests:**
- `frontend/src/app/features/inbox/inbox.component.spec.ts`
- `frontend/src/app/features/inbox/components/conversation-list/conversation-list.component.spec.ts`
- `frontend/src/app/features/inbox/components/human-takeover/human-takeover.component.spec.ts`
- `backend-api/tests/unit/application/agent/test_conversation_status.py`
- `backend-api/tests/integration/test_pause_resume_agent.py`
- `backend-api/tests/integration/test_send_human_message.py`

### Dependencies
- Story 6.2 (Conversations & Messages domain -- data model, ConversationStore, REST endpoints).
- Story 6.1 (WhatsApp gateway -- for sending human messages).
- Story 6.4 (AI Agent -- for agent_runs data used in status computation, pause/resume logic).
- Epic 4 (Receivables -- for customer context pane showing open titles).

### Technical Notes
- The conversation list in the left pane uses virtual scrolling for performance with many conversations.
- Message thread uses reverse infinite scroll (scroll up to load older messages via cursor pagination).
- Status badge computation: server computes status on each conversation list query. Status is based on: (1) `agent_active` flag, (2) last `agent_runs` entry (did it error or hit max iterations?), (3) time since last inbound message vs last outbound response.
- "Intervir" sets `agent_active=false` and `agent_paused_until=NULL` (indefinite). "Retomar Agente" sets `agent_active=true`. While paused, inbound messages are persisted but no agent turn is triggered.
- Quick actions in the customer context pane call existing API endpoints (Pix QR from Epic 4, write-off from Epic 4).
- Audio recording uses MediaRecorder API; uploaded as attachment via the send message endpoint.
- The "Agent is typing..." indicator is shown when an SSE event `agent_typing` is received for the active conversation, hidden when the agent's response message arrives.
- Reconnection: auto-reconnect with exponential backoff (1s, 2s, 4s, max 30s) on connection loss.
- Mobile-first responsive: on mobile, left pane is full-width; tapping a conversation slides to the thread view; right pane is a bottom sheet.

### Session Context
- Docker-only development: backend on port 8100, PostgreSQL on 5433, Redis on 6380.
- Frontend: Angular 21, Standalone components, Signals, Tailwind v4.
- All UI must be mobile-first and responsive per project UX standards.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
