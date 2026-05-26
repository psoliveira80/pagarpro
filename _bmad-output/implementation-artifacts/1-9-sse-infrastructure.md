---
epic: 1
story: 9
title: "SSE Infrastructure"
type: "Core"
status: done
---

# Story 1.9: SSE Infrastructure

## User Story
As a Developer,
I want SSE endpoints with Redis Pub/Sub dispatch and token-based auth,
So that real-time notifications work across all features.

## Acceptance Criteria

1. SSE endpoint `GET /sse/notifications` implemented using `sse-starlette` with Redis Pub/Sub backend.
2. Auth via query param `?token=<jwt>` (EventSource doesn't support headers).
3. `SseService` in `backend-api/app/api/sse.py` subscribes to Redis channel `sse:user:{user_id}`.
4. Reconnection handled natively by EventSource; server sends `retry: 3000` directive.
5. Frontend `SseService` in `frontend/src/app/core/services/sse.service.ts` wraps EventSource with `connected` signal and `lastEvent` signal.
6. Unit test: publish to Redis channel, verify SSE client receives the event.

## Technical Context

### Architecture References
- **Architecture Section 5 (Real-time)**: SSE default; WebSocket only for chat; polling as degraded fallback.
- **Architecture Section 3.1**: Redis 7 for Pub/Sub.
- **PRD NFR-12**: Real-time updates in UI <= 2 s without refresh.

### Files to Create/Modify
```
backend-api/
├── app/
│   ├── api/
│   │   └── sse.py                              # SseService, SSE endpoint, Redis Pub/Sub subscriber
│   ├── core/
│   │   └── sse_auth.py                         # JWT validation from query param
│   └── tests/
│       └── test_sse.py                         # Unit/integration tests
frontend/
├── src/app/core/services/
│   └── sse.service.ts                          # EventSource wrapper with signals
```

### Dependencies
- Story 1.1 (Redis infrastructure)
- Story 1.4 (JWT auth — token validation)

### Technical Notes
- Use `sse-starlette` package for SSE endpoint implementation.
- Redis Pub/Sub channel pattern: `sse:user:{user_id}` for per-user notifications.
- JWT token passed as `?token=<jwt>` query parameter since EventSource API does not support custom headers.
- Server sends `retry: 3000` to instruct browser reconnection interval (3 seconds).
- Frontend service should expose `connected: Signal<boolean>` and `lastEvent: Signal<ServerEvent | null>`.
- Consider using `WritableSignal` for state management in the Angular service.
- Ensure graceful disconnection on component destroy / logout.

### Session Context (Pre-Implementation Notes)
- **Folder structure**: backend in `src/backend-api/`, frontend in `src/frontend/`
- **Docker external port for API**: 8100 — SSE EventSource URL in frontend must target `localhost:8100` (or use environment-configured `apiUrl`)
- **SSE auth via query param**: confirmed — `?token=<jwt>` is the only option since EventSource does not support custom headers
- **`ChangeDetectionStrategy.OnPush`** on the SSE-consuming component(s)
- **3-file component rule**: any new Angular component must have `.ts`, `.html`, `.css` (CSS nearly empty, all Tailwind)
- **Redis external port**: 6380 (non-default)

## Dev Checklist
- [x] All acceptance criteria met (AC1-5)
- [x] Tests written and passing (22/22)
- [x] Lint/type-check passing
- [x] No regressions

## File List
- `src/backend-api/pyproject.toml` — added sse-starlette
- `src/backend-api/app/core/sse_auth.py` — JWT validation from query param
- `src/backend-api/app/api/sse.py` — SSE endpoint + Redis Pub/Sub + publish_to_user helper
- `src/backend-api/app/main.py` — registered SSE router
- `src/frontend/src/app/core/services/sse.service.ts` — EventSource wrapper with signals

## Change Log
- 2026-05-12: SSE infrastructure — Redis Pub/Sub backend, JWT query param auth, Angular SseService with signals
