---
epic: 11
story: 1
title: "Orçamento, Rastreamento e Motor de Throttle de Tokens"
type: "Core"
status: ready-for-dev
---

# Story 11.1: Orçamento, Rastreamento e Motor de Throttle de Tokens

## História de Usuário
Como Gerente do Tenant,
quero um orçamento mensal de tokens de LLM com rastreamento em tempo real, alertas e rebaixamento automático de modo,
para que eu nunca receba uma conta surpresa e a operação no WhatsApp nunca pare quando a IA acabar.

## Critérios de Aceite

1. `system_settings.token_budget` JSONB column with shape:
   ```json
   {
     "monthly_limit_tokens": 1000000,
     "auto_throttle_enabled": true,
     "thresholds": {
       "warn_at_pct": 50,
       "downgrade_to_eco_at_pct": 75,
       "downgrade_to_zero_at_pct": 95
     },
     "reset_day_of_month": 1
   }
   ```
2. Nova tabela `token_usage_monthly`: `id`, `tenant_id`, `period` (YYYY-MM), `prompt_tokens` BIGINT, `completion_tokens` BIGINT, `cost_usd` NUMERIC(10,4), `last_updated_at`. Constraint UNIQUE em `(tenant_id, period)`. Uma linha por tenant por mês.
3. Após cada insert em `agent_runs`, um trigger (ou hook em camada de aplicação) faz upsert em `token_usage_monthly` para o período atual.
4. Task Celery `evaluate_token_throttle` roda a cada 5 min: para cada tenant, compara `token_usage_monthly` contra `thresholds`. Se um threshold for cruzado E `auto_throttle_enabled=true`, chama `set_operation_mode(tenant_id, new_mode, reason='auto_throttle')` (serviço de modo da Story 11.2).
5. Evento SSE `token_budget_alert` publicado para o gerente quando `warn_at_pct`, `downgrade_to_eco_at_pct` ou `downgrade_to_zero_at_pct` for cruzado. Payload: `{pct_used, current_mode, action_taken}`.
6. Reset mensal: task Celery `reset_token_budget_month` roda no `reset_day_of_month` às 00:05. Cria nova linha em `token_usage_monthly` para o novo período e restaura `configured_mode` (da Story 11.2).
7. Endpoints do backend:
   - `GET /api/v1/system/token-usage/current` — retorna `{period, used, limit, pct_used, projected_end_of_month, current_mode, configured_mode}`
   - `GET /api/v1/system/token-usage/history?months=6` — últimos N meses
   - `PUT /api/v1/system/token-budget` — gerente atualiza limites/thresholds
8. Widget no **Dashboard**: medidor de uso de tokens (verde <50%, amarelo 50–95%, vermelho >95%), com badge do modo atual e link "Configurar".
9. Página de frontend **Configurações → IA & WhatsApp → Orçamento de Tokens**: formulário para editar `monthly_limit_tokens`, toggle `auto_throttle_enabled`, editar thresholds com slider (valida que os thresholds de downgrade são monotônicos), dia de reset.
10. Banner permanente no header quando estiver em modo degradado por throttle: "⚠️ IA em modo {ia-eco|ia-zero} (atingido X% do orçamento). Reseta em DD dias." com botão "Aumentar plano".
11. Testes:
    - Cruzamento de threshold dispara SSE + chama serviço de modo
    - Reset mensal cria nova linha e restaura configured_mode
    - Cálculo de projeção está correto dada a taxa de uso atual
    - Override manual (gerente define modo enquanto sob throttle) persiste até o próximo cruzamento de threshold

## Contexto Técnico

### Referências de Arquitetura
- Construído em cima da tabela `agent_runs` (Story 6.4) — fonte da verdade de uso de tokens
- Channel registry da Story 6.1 — `IMessageChannel`
- Infraestrutura SSE da Story 1.9
- Serviço de modo definido na Story 11.2 (esta story depende daquela existir conceitualmente)

### Arquivos a Criar/Modificar
```
backend-api/
├── app/domain/ports/token_budget.py
├── app/application/token_budget/
│   ├── service.py                       # check_budget, evaluate_throttle, reset_month
│   ├── projection.py                    # linear projection of end-of-month spend
│   └── events.py                        # TokenThresholdCrossedEvent
├── app/workers/tasks/evaluate_token_throttle.py
├── app/workers/tasks/reset_token_budget_month.py
├── app/api/v1/system_routes.py          # add /system/token-usage/* endpoints
├── alembic/versions/xxxx_token_usage_monthly.py
frontend/
├── src/app/features/dashboard/widgets/token-usage-widget.component.ts/.html/.css
├── src/app/features/settings/ai-budget/ai-budget.component.ts/.html/.css
├── src/app/core/services/token-budget.service.ts
└── src/app/shared/components/throttle-banner/throttle-banner.component.ts/.html/.css
```

### Dependências
- Story 6.4 (tabela `agent_runs` — fonte de tokens)
- Story 1.9 (infraestrutura SSE)
- Story 11.2 (serviço de modo de operação — `set_operation_mode` chamado por esta)

### Notas Técnicas
- **Algoritmo de projeção**: `projected = used_so_far / day_of_period * 30`. Mostrar como dica visual no widget.
- **Idempotência**: o throttle só dispara se o modo atual NÃO é o modo alvo (evita re-trigger a cada 5 min)
- **Audit log**: toda mudança automática de modo grava em `audit_log` com `actor='system_throttle'`
- **Anti-flap**: se gerente fez override manual em <1h, não re-aplicar auto-throttle até o reset mensal
- Custo em USD por provider já calculado em `agent_runs.cost_usd` (Story 6.4) — soma agregada

### Contexto de Sessão
- Esta story usa o `set_operation_mode` que a 11.2 expõe. Ordem de implementação: 11.2 primeiro, depois 11.1
- Considerar `cost_usd` E `total_tokens` como métricas paralelas — gerente pode preferir orçamento em USD em vez de tokens

## Checklist do Dev
- [ ] Todos os critérios de aceite atendidos
- [ ] Testes escritos e passando
- [ ] Sem regressões
- [ ] Code review (`bmad-code-review`) executado e aprovado
