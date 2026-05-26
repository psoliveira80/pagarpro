---
epic: 10
story: 5
title: "Channel Health Monitoring and Auto-Discovery"
type: "Core"
status: ready-for-dev
---

# Story 10.5: Channel Health Monitoring and Auto-Discovery

## User Story
As a Manager,
I want to see which messaging channels are configured and healthy,
So that I know if my automated collection will work.

## Acceptance Criteria

1. Celery task `check_channel_health` runs every 5 minutes — calls `health_check()` on all registered channels, stores result in `integration_credentials.status` and `last_health_check`.
2. Dashboard widget showing channel status: green dot (healthy), yellow (degraded), red (down), gray (not configured).
3. SSE notification when a channel goes from healthy to unhealthy.
4. Settings > Integrações page shows real-time health status per channel with latency.
5. Channel registration at startup reads from `integration_credentials` table and wraps adapters via `WhatsAppChannelWrapper`.
6. Tests: mock health check, verify status persistence.

## Technical Context

### Architecture References
- `docs/architecture-messaging-channels.md`
- `app/core/channels/registry.py` (ChannelRegistry)
- `app/domain/ports/message_channel.py` (IMessageChannel.health_check)

### Files to Create/Modify
```
backend-api/
├── app/workers/tasks/check_channel_health.py
├── app/main.py                              # Register channels from DB at startup
frontend/
├── src/app/features/settings/integrations.component.html  # Add health badges
├── src/app/features/dashboard/dashboard.component.html    # Add channel widget
```

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] No regressions
