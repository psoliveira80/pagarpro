---
epic: 10
story: 3
title: "Motor de Cobrança Automatizada (Lembretes Pré-vencimento + Escalonamento de Vencidos)"
type: "Core"
status: ready-for-dev
---

# Story 10.3: Motor de Cobrança Automatizada

## História de Usuário
Como Sistema,
quero enviar automaticamente lembretes de pagamento antes da data de vencimento e escalar parcelas vencidas,
para que a cobrança aconteça sem intervenção manual.

## Critérios de Aceite

1. Configuração `collection_policy` em `system_settings`: `reminder_days_before`, `overdue_escalation` (array de {days, action, template_id}), `agent_can_negotiate`, `agent_max_grace_days`, taxas de juros/multa, `updated_value_in_message`.
2. Task Celery `check_upcoming_due_dates` (diária 08:00): encontra parcelas que vencem em N dias, envia lembrete via canal WhatsApp usando template.
3. Task Celery `check_overdue_installments` (diária 09:00): encontra parcelas vencidas, atualiza status para `vencido`, executa ação de escalonamento conforme política (reminder → warn_block → block → notify_manager).
4. Task Celery `check_paid_installments` (a cada 30 min): detecta parcelas pagas, envia confirmação, dispara desbloqueio se aplicável.
5. Templates de mensagem armazenados em `system_settings` com variáveis: {nome}, {valor}, {valor_atualizado}, {data_vencimento}, {dias_atraso}, {placa}, {contrato}.
6. Todas as mensagens enviadas via `IMessageChannel` (channel registry), não pelo adapter direto do WhatsApp.
7. Agent orchestrator trata respostas do cliente com autonomia de negociação (configurável).
8. Frontend: página de configuração de política de cobrança em `/system/settings/collection`.
9. Testes: verifica timing dos lembretes, progressão de escalonamento, renderização de templates.

## Contexto Técnico

### Referências de Arquitetura
- `docs/architecture-recurrence-and-collection.md` Seções 3, 4, 5

### Arquivos a Criar/Modificar
```
backend-api/
├── app/workers/tasks/check_upcoming_due_dates.py
├── app/workers/tasks/check_overdue_installments.py
├── app/workers/tasks/check_paid_installments.py
├── app/domain/finance/template_renderer.py      # Renderiza templates de mensagem com variáveis
├── app/api/v1/admin_routes.py                   # Adiciona endpoints da política de cobrança
frontend/
├── src/app/features/settings/collection-settings.component.ts/html/css
├── src/app/features/system/system.routes.ts     # Adiciona rota /settings/collection
```

### Dependências
- Epic 6 (WhatsApp gateway, agent orchestrator, conversation store)
- Story 10-1 (cálculo de valor atualizado com correção)
- Port `IMessageChannel` + channel registry

### Notas Técnicas
- Ações de escalonamento: "reminder" (envia template), "warn_block" (envia aviso), "block" (publica InstallmentOverdueEvent → hook de veículo), "notify_manager" (notificação SSE)
- Negociação do agente: quando o cliente responde, AgentOrchestrator processa com system prompt de cobrança. Agente pode conceder até `agent_max_grace_days` de extensão.
- Toda atividade de cobrança logada em `conversation_messages` para trilha de auditoria

### Contexto da Sessão
- Registrar 3 novas tasks Celery em workers/__init__.py
- Adicionar entradas no beat_schedule com crontab

## Checklist do Dev
- [ ] Todos os critérios de aceite atendidos
- [ ] Testes escritos e passando
- [ ] Sem regressões
