---
epic: 10
story: 4
title: "Message Template Management"
type: "Core"
status: ready-for-dev
---

# Story 10.4: Message Template Management

## User Story
As a Manager,
I want to create and manage message templates for each collection stage,
So that I can customize the tone and content of automated messages.

## Acceptance Criteria

1. `message_templates` table: id, name, channel (whatsapp | email | sms), trigger (upcoming_due | overdue_d1 | overdue_d3 | overdue_d7 | warn_block | payment_confirmed | custom), body, variables (JSONB), is_active, created_at.
2. CRUD endpoints: GET/POST/PUT/DELETE `/api/v1/message-templates`.
3. Default templates seeded for each trigger (in Portuguese).
4. Template preview endpoint: POST `/api/v1/message-templates/preview` — renders template with sample data.
5. Frontend: template management page at `/system/settings/templates` — list, create/edit modal with live preview, variable insertion helper.
6. Variables: {nome}, {valor}, {valor_atualizado}, {data_vencimento}, {dias_atraso}, {placa}, {contrato}, {link_pagamento}.

## Technical Context

### Files to Create/Modify
```
backend-api/
├── app/infrastructure/db/models/message_template.py
├── app/api/v1/template_routes.py
├── alembic/versions/0014_message_templates.py
frontend/
├── src/app/features/settings/templates.component.ts/html/css
```

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] No regressions
