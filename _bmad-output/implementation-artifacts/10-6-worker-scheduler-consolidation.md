---
epic: 10
story: 6
title: "Consolidação e Monitoramento do Scheduler de Workers"
type: "Core"
status: ready-for-dev
---

# Story 10.6: Consolidação e Monitoramento do Scheduler de Workers

## História de Usuário
Como Administrador do Sistema,
quero todas as tasks agendadas consolidadas com timing crontab apropriado e um painel de monitoramento,
para que eu possa verificar se todas as automações estão rodando corretamente.

## Critérios de Aceite

1. Todas as tasks Celery Beat usam `crontab()` com horários exatos (não intervalos):
   - 03:00 daily-backup
   - 04:00 generate-recurring-payables
   - 05:00 calculate-customer-scores
   - 06:00 generate-monthly-installments
   - 08:00 check-upcoming-due-dates
   - 09:00 check-overdue-installments
   - */30 check-paid-installments
   - */5 check-channel-health
   - */60 refresh-materialized-views
2. Endpoint admin GET `/api/v1/admin/scheduled-tasks` — lista todas as tasks agendadas com última execução, próxima execução, status.
3. Frontend: página "Tarefas Agendadas" em `/system/settings/scheduler` — tabela mostrando cada task, agendamento, última execução, badge de status (ok/falhou/nunca rodou).
4. Task que falhou envia alerta SSE ao admin.
5. Testes: verifica que a configuração crontab é válida.

## Contexto Técnico

### Arquivos a Criar/Modificar
```
backend-api/
├── app/workers/__init__.py                    # Consolida todo o beat_schedule com crontab
├── app/api/v1/admin_routes.py                 # Adiciona endpoint de scheduled-tasks
frontend/
├── src/app/features/settings/scheduler.component.ts/html/css
├── src/app/features/system/system.routes.ts   # Adiciona rota /settings/scheduler
```

### Notas Técnicas
- Usar `celery.schedules.crontab` em vez de intervalos inteiros
- Resultados das tasks armazenados em Redis (Celery result backend) — ler informação da última execução
- Adicionar "Tarefas Agendadas" ao menu da sidebar de configurações

## Checklist do Dev
- [ ] Todos os critérios de aceite atendidos
- [ ] Testes escritos e passando
- [ ] Sem regressões
