---
epic: 6
story: 10
title: "In-App Chat Channel"
type: "Core"
status: done
---

# Story 6.10: In-App Chat Channel

## User Story
As a Manager,
I want a floating chat panel in the web UI with streaming responses, suggestion chips, and structured response cards,
So that I can query the agent for business intelligence and perform actions without leaving the app.

## Acceptance Criteria
1. **Floating button** positioned bottom-right of the screen (not in the header). Icon: chat bubble. Badge shows unread count. Click toggles a **slide-in panel** from the right edge.
2. **Slide-in panel** design:
   - Glassmorphism styling: semi-transparent background with backdrop blur, rounded corners, subtle shadow.
   - Header with "Assistente IA" title, minimize button, close button.
   - Messages area with chat bubbles (user on right in primary color, assistant on left in surface color).
   - Input bar at bottom with text input and send button.
   - Panel width: 400px on desktop, full-width on mobile.
3. **Suggestion chips**: on empty/new conversation, display clickable chips for common questions: "Resumo de inadimplencia", "Titulos vencidos hoje", "Historico de pagamentos", "Posicao do veiculo". Chips disappear after first message.
4. **Structured response cards**: when the agent returns structured data (tables, lists, summaries), render as cards with:
   - Title and subtitle
   - Data table or key-value pairs
   - Action buttons (e.g., "Ver detalhes" navigates to entity, "Exportar" triggers CSV download, "Gerar Pix" calls action endpoint)
   - Confidence indicator: colored dot (green = high, yellow = medium, red = low) with tooltip showing confidence level
5. **SSE streaming**: agent responses stream token-by-token via Server-Sent Events. Typing indicator shows while streaming. Text appears incrementally in the assistant bubble.
6. The chat uses the same `AgentOrchestrator` pipeline as WhatsApp -- same tools, same RBAC, same LLM. Channel is identified as `channel='in_app'` in `ConversationStore`.
7. The Manager's JWT provides RBAC context (no phone number lookup needed). Each user gets one persistent `in_app` conversation per tenant.
8. Messages persisted in `conversations` + `conversation_messages` tables with `channel='in_app'` and `role` values (user/assistant/tool).
9. Supports text input and file upload (receipts, screenshots) via MinIO path `chat/{user_id}/{uuid}-{filename}`.

## Technical Context

### Architecture References
- **Architecture Section 2.4**: Hexagonal -- in-app chat is just another channel adapter into the same agent pipeline.
- **Story 6.4**: Agent Engine with Tool-Use -- same `AgentOrchestrator` and `AgentToolRegistry` reused here.
- **Story 6.2**: ConversationStore -- shared persistence for both channels.
- **Story 1.9**: SSE infrastructure (Redis Pub/Sub) -- reused for streaming responses.
- The floating button and panel are global components rendered in the app shell, available on all routes.

### Files to Create/Modify
**Backend:**
- `backend-api/app/api/v1/in_app_chat.py` -- endpoints:
  - `POST /api/v1/chat/messages` -- send message, triggers agent turn, returns SSE stream
  - `GET /api/v1/chat/history?before=&limit=` -- get current user's in_app conversation messages
  - `GET /api/v1/chat/stream/{run_id}` -- SSE endpoint for streaming agent response
- `backend-api/app/infrastructure/adapters/chat/in_app_channel.py` -- `InAppChannelAdapter` that calls `AgentOrchestrator` directly (not via Celery) for streaming support
- `backend-api/app/application/agent/stream_agent_turn.py` -- use case: run agent turn with streaming, yield SSE events for each token chunk and tool result

**Frontend:**
- `frontend/src/app/shared/components/chat-fab/chat-fab.component.ts` -- floating action button bottom-right with unread badge
- `frontend/src/app/shared/components/chat-panel/chat-panel.component.ts` -- slide-in panel with glassmorphism styling
- `frontend/src/app/shared/components/chat-panel/chat-panel.component.html` -- template: header, messages, input, chips
- `frontend/src/app/shared/components/chat-panel/chat-panel.component.css` -- glassmorphism styles, slide-in animation
- `frontend/src/app/shared/components/chat-panel/components/suggestion-chips/suggestion-chips.component.ts` -- clickable suggestion chips
- `frontend/src/app/shared/components/chat-panel/components/response-card/response-card.component.ts` -- structured data card with actions and confidence indicator
- `frontend/src/app/shared/components/chat-panel/components/confidence-indicator/confidence-indicator.component.ts` -- green/yellow/red dot with tooltip
- `frontend/src/app/core/services/in-app-chat.service.ts` -- HTTP + SSE service: send message, receive streaming response, manage conversation state

**App Shell:**
- `frontend/src/app/app.component.html` -- add `<app-chat-fab>` and `<app-chat-panel>` to the root template (rendered globally)

**Tests:**
- `backend-api/tests/unit/application/agent/test_stream_agent_turn.py`
- `backend-api/tests/integration/test_in_app_chat.py`
- `frontend/src/app/shared/components/chat-panel/chat-panel.component.spec.ts`
- `frontend/src/app/shared/components/chat-fab/chat-fab.component.spec.ts`

### Dependencies
- Story 6.4 (Agent Engine -- AgentOrchestrator pipeline with streaming support).
- Story 6.2 (ConversationStore -- shared persistence with `channel='in_app'`).
- Story 6.12 (Internal AI Chat BI Tools -- the tools available in the in-app channel).
- Story 1.9 (SSE infrastructure -- Redis Pub/Sub for streaming).
- Story 6.7 (Inbox UI patterns -- chat bubble styling, message rendering patterns to reuse).

### Technical Notes
- The floating button uses `position: fixed; bottom: 1.5rem; right: 1.5rem; z-index: 50;` to stay above all content.
- Slide-in panel animation: `transform: translateX(100%)` to `translateX(0)` with 200ms ease-out transition.
- Glassmorphism CSS: `background: rgba(255, 255, 255, 0.8); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.2);` (with dark mode variant).
- SSE streaming implementation: `POST /api/v1/chat/messages` returns 202 with a `run_id`. Client then connects to `GET /api/v1/chat/stream/{run_id}` SSE endpoint. Events: `token` (partial text), `tool_start` (tool name), `tool_result` (structured data for response card), `done` (final message with confidence), `error`.
- Structured response detection: when a tool returns tabular data, the agent formats it as a JSON block with `type: "card"` in the response metadata. The frontend renders this as a `ResponseCardComponent` instead of plain text.
- Confidence indicator logic: derived from `agent_runs.iterations` count and whether fallback responses were used. High (1-3 iterations, direct answer), Medium (4-7 iterations or partial data), Low (8-10 iterations or error recovery).
- Each user gets one `in_app` conversation. On first message, `ConversationStore.get_or_create_conversation(tenant_id, channel='in_app', user_id=current_user.id)` is called.
- File uploads go through MinIO: `chat/{user_id}/{uuid}-{filename}`. The message's `media_url` stores the MinIO object path.
- The panel should not interfere with the inbox route (`/system/inbox`); when on that route, the floating button can be hidden or dimmed.
- `Ctrl+K` keyboard shortcut opens the chat panel (command palette style).

### Session Context
- Docker-only development: backend on port 8100, PostgreSQL on 5433, Redis on 6380.
- Frontend: Angular 21, Standalone components, Signals, Tailwind v4, CDK Overlay.
- SSE infrastructure already exists from Story 1.9 (Redis Pub/Sub backbone).
- All UI must be mobile-first and responsive per project UX standards.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
