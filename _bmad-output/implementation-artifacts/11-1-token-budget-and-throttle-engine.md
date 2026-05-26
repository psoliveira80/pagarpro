---
epic: 11
story: 1
title: "Token Budget, Tracking & Throttle Engine"
type: "Core"
status: ready-for-dev
---

# Story 11.1: Token Budget, Tracking & Throttle Engine

## User Story
As a Tenant Manager,
I want a monthly LLM token budget with live tracking, alerts, and automatic mode downgrade,
So that I never get a surprise bill and the WhatsApp operation never stops when IA runs out.

## Acceptance Criteria

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
2. New table `token_usage_monthly`: `id`, `tenant_id`, `period` (YYYY-MM), `prompt_tokens` BIGINT, `completion_tokens` BIGINT, `cost_usd` NUMERIC(10,4), `last_updated_at`. Unique constraint on `(tenant_id, period)`. Single row per tenant per month.
3. After every `agent_runs` insert, a trigger (or application-layer hook) upserts `token_usage_monthly` for the current period.
4. Celery task `evaluate_token_throttle` runs every 5 min: for each tenant, compares `token_usage_monthly` against `thresholds`. If a threshold is crossed AND `auto_throttle_enabled=true`, calls `set_operation_mode(tenant_id, new_mode, reason='auto_throttle')` (mode service from Story 11.2).
5. SSE event `token_budget_alert` published to manager when `warn_at_pct`, `downgrade_to_eco_at_pct`, or `downgrade_to_zero_at_pct` is crossed. Payload: `{pct_used, current_mode, action_taken}`.
6. Monthly reset: Celery task `reset_token_budget_month` runs on `reset_day_of_month` at 00:05. Creates new `token_usage_monthly` row for the new period and restores `configured_mode` (from Story 11.2).
7. Backend endpoints:
   - `GET /api/v1/system/token-usage/current` — returns `{period, used, limit, pct_used, projected_end_of_month, current_mode, configured_mode}`
   - `GET /api/v1/system/token-usage/history?months=6` — last N months
   - `PUT /api/v1/system/token-budget` — manager updates limits/thresholds
8. Frontend widget on **Dashboard**: token usage gauge (green <50%, yellow 50–95%, red >95%), with current mode badge and "Configurar" link.
9. Frontend page **Settings → IA & WhatsApp → Orçamento de Tokens**: form to edit `monthly_limit_tokens`, toggle `auto_throttle_enabled`, edit thresholds with slider (validates downgrade thresholds are monotonic), reset day.
10. Banner permanente no header quando estiver em modo degradado por throttle: "⚠️ IA em modo {ia-eco|ia-zero} (atingido X% do orçamento). Reseta em DD dias." com botão "Aumentar plano".
11. Tests:
    - Threshold crossing fires SSE + calls mode service
    - Monthly reset creates new row and restores configured_mode
    - Projection calculation is correct given current usage rate
    - Manual override (manager sets mode while throttled) persists until next threshold crossing

## Technical Context

### Architecture References
- Builds on `agent_runs` table (Story 6.4) — fonte da verdade de uso de tokens
- Channel registry from Story 6.1 — `IMessageChannel`
- SSE infrastructure from Story 1.9
- Mode service definido em Story 11.2 (esta story depende daquela existir conceitualmente)

### Files to Create/Modify
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

### Dependencies
- Story 6.4 (`agent_runs` table — fonte de tokens)
- Story 1.9 (SSE infrastructure)
- Story 11.2 (operation mode service — set_operation_mode chamado por esta)

### Technical Notes
- **Projection algorithm**: `projected = used_so_far / day_of_period * 30`. Mostrar como dica visual no widget.
- **Idempotência**: o throttle só dispara se o modo atual NÃO é o modo alvo (evita re-trigger a cada 5 min)
- **Audit log**: toda mudança automática de modo grava em `audit_log` com `actor='system_throttle'`
- **Anti-flap**: se manager fez override manual em <1h, não re-aplicar auto-throttle até reset mensal
- Custo USD por provider já calculado em `agent_runs.cost_usd` (Story 6.4) — sum agregado

### Session Context
- Esta story usa o `set_operation_mode` que a 11.2 expõe. Ordem de implementação: 11.2 primeiro, depois 11.1
- Considerar `cost_usd` E `total_tokens` como métricas paralelas — manager pode preferir budget em USD em vez de tokens

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] No regressions
- [ ] Code review (`bmad-code-review`) executed and approved
