---
epic: 10
story: 4
title: "Gerenciamento de Modelos de Mensagem"
type: "Core"
status: ready-for-dev
---

# Story 10.4: Gerenciamento de Modelos de Mensagem

## História de Usuário
Como Gestor,
quero criar e gerenciar modelos de mensagem para cada etapa de cobrança,
para que eu possa customizar o tom e o conteúdo das mensagens automáticas.

## Critérios de Aceite

1. Tabela `message_templates`: id, name, channel (whatsapp | email | sms), trigger (upcoming_due | overdue_d1 | overdue_d3 | overdue_d7 | warn_block | payment_confirmed | custom), body, variables (JSONB), is_active, created_at.
2. Endpoints CRUD: GET/POST/PUT/DELETE `/api/v1/message-templates`.
3. Modelos padrão semeados para cada trigger (em português).
4. Endpoint de preview de template: POST `/api/v1/message-templates/preview` — renderiza template com dados de exemplo.
5. Frontend: página de gerenciamento de modelos em `/system/settings/templates` — listagem, modal de criação/edição com preview ao vivo, helper de inserção de variáveis.
6. Variáveis: {nome}, {valor}, {valor_atualizado}, {data_vencimento}, {dias_atraso}, {placa}, {contrato}, {link_pagamento}.

## Contexto Técnico

### Arquivos a Criar/Modificar
```
backend-api/
├── app/infrastructure/db/models/message_template.py
├── app/api/v1/template_routes.py
├── alembic/versions/0014_message_templates.py
frontend/
├── src/app/features/settings/templates.component.ts/html/css
```

## Checklist do Dev
- [ ] Todos os critérios de aceite atendidos
- [ ] Testes escritos e passando
- [ ] Sem regressões
