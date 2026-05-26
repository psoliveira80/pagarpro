---
epic: 11
story: 8
title: "Plan Tiers UI & Quotas"
type: "Core"
status: ready-for-dev
---

# Story 11.8: Plan Tiers UI & Quotas

## User Story
As a Tenant Manager,
I want to see which plan I'm on, what each plan includes, and what I'd unlock by upgrading,
So that I can decide whether to increase my budget when I hit limits.

## Acceptance Criteria

1. New table `plan_tiers` (system-wide, not tenant-scoped): `id`, `slug` ('starter' | 'pro' | 'business' | 'enterprise'), `display_name`, `monthly_token_limit` BIGINT, `whatsapp_msg_limit` INT (rate per day, nullable=unlimited), `included_features` JSONB array, `excluded_features` JSONB array, `monthly_price_brl` NUMERIC, `display_order` INT, `is_public` BOOL (default true), timestamps.
2. New column `tenants.plan_tier_id` (FK to `plan_tiers`, nullable until billing está modelado).
3. Seed inicial dos 4 tiers:
   - **Starter**: 100k tokens/mês, 500 msgs WhatsApp/dia, modo default `ia-zero`, features: menus + intent rules + OCR Tesseract + dedupe
   - **Pro**: 500k tokens/mês, 2k msgs/dia, modo default `ia-eco`, +features: LLM classifier, audio transcription
   - **Business**: 2M tokens/mês, 10k msgs/dia, modo default `ia-full`, +features: conversational AI, LLM Vision fallback, negotiation
   - **Enterprise**: 10M tokens/mês, sem limite msg, +features: dedicated support, custom integrations, SSO
4. `PlanService`:
   - `get_current_plan(tenant_id) -> PlanTier`
   - `is_feature_included(tenant_id, feature_key) -> bool` — usado por feature gates (ex.: tentou ativar `ia-full` sendo Starter → bloqueia com mensagem "Upgrade para Business")
   - `effective_token_limit(tenant_id) -> int` — combina `plan_tier.monthly_token_limit` com override de `system_settings.token_budget.monthly_limit_tokens` (manager pode setar mais baixo que o teto do plano, nunca mais alto)
5. Feature gates aplicados em:
   - Story 11.2 `set_configured_mode` → valida que o modo está em `plan_tier.included_features`
   - Story 11.1 `PUT /system/token-budget` → valida que `monthly_limit_tokens ≤ plan_tier.monthly_token_limit`
   - Story 6.4 LLM provider selection → planos baixos limitados a providers baratos (configurável)
6. Frontend page **Settings → Plano**:
   - Card grande com plano atual: nome, preço, recursos incluídos, próxima cobrança
   - Comparador horizontal de tiers (Starter | Pro | Business | Enterprise) com checkmarks por feature
   - Botão "Fazer Upgrade" em planos superiores (V1: abre modal "Entre em contato com vendas" com link mailto:; billing real fica para outro epic)
   - Mostra utilização atual (token + msgs WhatsApp) com gauge e projeção
7. Frontend widget de upsell:
   - Em telas de configuração de feature bloqueada por plano (ex.: gestor abre Settings → Modo de Operação e clica em IA Full sendo Starter): mostra modal "Esta feature está disponível no plano Business" com CTA
8. Backend endpoints:
   - `GET /api/v1/plans` — lista pública dos tiers (para comparador)
   - `GET /api/v1/plans/current` — plano do tenant atual + utilização
   - `POST /api/v1/plans/upgrade-request` — body `{target_slug, message?}` → envia email para vendas (placeholder V1)
9. Audit log: toda mudança de plano (mesmo manual via admin) gera entry com `category='billing'`.
10. Tests:
    - Feature gate bloqueia tier inferior ao tentar usar feature exclusiva
    - effective_token_limit retorna o menor entre plan e setting
    - Endpoint /plans/current calcula utilização corretamente

## Technical Context

### Architecture References
- Plan tiers são **read-only via UI** em V1 (admin do produto seed/edita via migration ou admin-only endpoint)
- Integração com billing real (Stripe/etc) é V2 — separado deste epic
- Feature flags continuam separadas de plans (Epic 9.3) — plans habilitam features, feature flags ativam/desativam rollout

### Files to Create/Modify
```
backend-api/
├── app/domain/plans/
│   ├── entities.py                      # PlanTier
│   ├── service.py                       # PlanService
│   └── features.py                      # FeatureKey enum + matrix
├── app/application/plans/
│   ├── upgrade_request.py
│   └── feature_gate.py                  # decorator + DI helper
├── app/api/v1/plan_routes.py
├── alembic/versions/xxxx_plan_tiers.py
├── alembic/versions/xxxx_seed_plan_tiers.py
frontend/
├── src/app/features/settings/plan/plan-page.component.ts/.html/.css
├── src/app/features/settings/plan/tier-comparator.component.ts/.html/.css
├── src/app/features/settings/plan/usage-gauge.component.ts/.html/.css
├── src/app/shared/components/upgrade-modal/upgrade-modal.component.ts/.html/.css
└── src/app/core/services/plan.service.ts
```

### Dependencies
- Story 11.1 (token budget — limite efetivo combina com plan)
- Story 11.2 (operation mode — features de modo gated por plano)
- Epic 9.3 (Module Management UI — sinergia, não bloqueio)
- Story 10.8 (`<app-modal>` para upgrade modal)

### Technical Notes
- **Feature matrix** vive em `app/domain/plans/features.py` como dict — mesmo padrão da capability matrix da Story 11.2
- **Não confundir** com `agent_config` (Story 6.4) que é persona/tom, ou com `system_settings` que é configurável pelo gestor
- **V2**: billing real, downgrade automático ao expirar pagamento, proração
- **i18n**: nomes de tiers e features em PT-BR por enquanto; estrutura permite locale futuro
- **A/B test V2**: posicionamento de upsell modal

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] No regressions
- [ ] Code review (`bmad-code-review`) executed and approved
