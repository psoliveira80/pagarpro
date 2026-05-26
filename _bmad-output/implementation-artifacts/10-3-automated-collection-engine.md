---
epic: 10
story: 3
title: "Automated Collection Engine (Pre-due Reminders + Overdue Escalation)"
type: "Core"
status: ready-for-dev
---

# Story 10.3: Automated Collection Engine

## User Story
As a System,
I want to automatically send payment reminders before due date and escalate overdue installments,
So that collection happens without manual intervention.

## Acceptance Criteria

1. `collection_policy` configuration in `system_settings`: `reminder_days_before`, `overdue_escalation` (array of {days, action, template_id}), `agent_can_negotiate`, `agent_max_grace_days`, interest/fine rates, `updated_value_in_message`.
2. Celery task `check_upcoming_due_dates` (daily 08:00): finds installments due in N days, sends reminder via WhatsApp channel using template.
3. Celery task `check_overdue_installments` (daily 09:00): finds overdue installments, updates status to `vencido`, executes escalation action per policy (reminder → warn_block → block → notify_manager).
4. Celery task `check_paid_installments` (every 30 min): detects paid installments, sends confirmation, triggers unblock if applicable.
5. Message templates stored in `system_settings` with variables: {nome}, {valor}, {valor_atualizado}, {data_vencimento}, {dias_atraso}, {placa}, {contrato}.
6. All messages sent via `IMessageChannel` (channel registry), not direct WhatsApp adapter.
7. Agent orchestrator handles customer replies with negotiation autonomy (configurable).
8. Frontend: collection policy configuration page at `/system/settings/collection`.
9. Tests: verify reminder timing, escalation progression, template rendering.

## Technical Context

### Architecture References
- `docs/architecture-recurrence-and-collection.md` Sections 3, 4, 5

### Files to Create/Modify
```
backend-api/
├── app/workers/tasks/check_upcoming_due_dates.py
├── app/workers/tasks/check_overdue_installments.py
├── app/workers/tasks/check_paid_installments.py
├── app/domain/finance/template_renderer.py      # Render message templates with variables
├── app/api/v1/admin_routes.py                   # Add collection policy endpoints
frontend/
├── src/app/features/settings/collection-settings.component.ts/html/css
├── src/app/features/system/system.routes.ts     # Add /settings/collection route
```

### Dependencies
- Epic 6 (WhatsApp gateway, agent orchestrator, conversation store)
- Story 10-1 (updated value calculation with correction)
- `IMessageChannel` port + channel registry

### Technical Notes
- Escalation actions: "reminder" (send template), "warn_block" (send warning), "block" (publish InstallmentOverdueEvent → vehicle hook), "notify_manager" (SSE notification)
- Agent negotiation: when customer replies, AgentOrchestrator processes with collection system prompt. Agent can grant up to `agent_max_grace_days` extension.
- All collection activity logged in `conversation_messages` for audit trail

### Session Context
- Register 3 new Celery tasks in workers/__init__.py
- Add beat_schedule entries with crontab

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] No regressions
