---
epic: 11
story: 8
title: "UI de Tiers de Plano e Quotas"
type: "Core"
status: ready-for-dev
---

# Story 11.8: UI de Tiers de Plano e Quotas

## História de Usuário
Como Gerente do Tenant,
quero ver em qual plano estou, o que cada plano inclui e o que destravaria fazendo upgrade,
para que eu possa decidir se aumento meu orçamento quando atingir os limites.

## Critérios de Aceite

1. Nova tabela `plan_tiers` (system-wide, não tenant-scoped): `id`, `slug` ('starter' | 'pro' | 'business' | 'enterprise'), `display_name`, `monthly_token_limit` BIGINT, `whatsapp_msg_limit` INT (taxa por dia, nullable=ilimitado), `included_features` JSONB array, `excluded_features` JSONB array, `monthly_price_brl` NUMERIC, `display_order` INT, `is_public` BOOL (default true), timestamps.
2. Nova coluna `tenants.plan_tier_id` (FK para `plan_tiers`, nullable até que o billing esteja modelado).
3. Seed inicial dos 4 tiers:
   - **Starter**: 100k tokens/mês, 500 msgs WhatsApp/dia, modo default `ia-zero`, features: menus + intent rules + OCR Tesseract + dedupe
   - **Pro**: 500k tokens/mês, 2k msgs/dia, modo default `ia-eco`, +features: classifier LLM, transcrição de áudio
   - **Business**: 2M tokens/mês, 10k msgs/dia, modo default `ia-full`, +features: IA conversacional, fallback LLM Vision, negociação
   - **Enterprise**: 10M tokens/mês, sem limite de msg, +features: suporte dedicado, integrações customizadas, SSO
4. `PlanService`:
   - `get_current_plan(tenant_id) -> PlanTier`
   - `is_feature_included(tenant_id, feature_key) -> bool` — usado por feature gates (ex.: tentou ativar `ia-full` sendo Starter → bloqueia com mensagem "Upgrade para Business")
   - `effective_token_limit(tenant_id) -> int` — combina `plan_tier.monthly_token_limit` com override de `system_settings.token_budget.monthly_limit_tokens` (gerente pode setar mais baixo que o teto do plano, nunca mais alto)
5. Feature gates aplicados em:
   - Story 11.2 `set_configured_mode` → valida que o modo está em `plan_tier.included_features`
   - Story 11.1 `PUT /system/token-budget` → valida que `monthly_limit_tokens ≤ plan_tier.monthly_token_limit`
   - Story 6.4 seleção de provider LLM → planos baixos limitados a providers baratos (configurável)
6. Página de frontend **Configurações → Plano**:
   - Card grande com o plano atual: nome, preço, recursos incluídos, próxima cobrança
   - Comparador horizontal de tiers (Starter | Pro | Business | Enterprise) com checkmarks por feature
   - Botão "Fazer Upgrade" em planos superiores (V1: abre modal "Entre em contato com vendas" com link mailto:; billing real fica para outro epic)
   - Mostra utilização atual (tokens + msgs WhatsApp) com gauge e projeção
7. Widget de upsell no frontend:
   - Em telas de configuração de feature bloqueada por plano (ex.: gestor abre Configurações → Modo de Operação e clica em IA Full sendo Starter): mostra modal "Esta feature está disponível no plano Business" com CTA
8. Endpoints do backend:
   - `GET /api/v1/plans` — lista pública dos tiers (para o comparador)
   - `GET /api/v1/plans/current` — plano do tenant atual + utilização
   - `POST /api/v1/plans/upgrade-request` — body `{target_slug, message?}` → envia email para vendas (placeholder V1)
9. Audit log: toda mudança de plano (mesmo manual via admin) gera entrada com `category='billing'`.
10. Testes:
    - Feature gate bloqueia tier inferior ao tentar usar feature exclusiva
    - `effective_token_limit` retorna o menor entre plano e setting
    - Endpoint `/plans/current` calcula a utilização corretamente

## Contexto Técnico

### Referências de Arquitetura
- Os plan tiers são **read-only via UI** em V1 (admin do produto faz seed/edita via migration ou endpoint admin-only)
- Integração com billing real (Stripe/etc) é V2 — separado deste epic
- Feature flags continuam separadas dos planos (Epic 9.3) — planos habilitam features, feature flags ativam/desativam rollout

### Arquivos a Criar/Modificar
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

### Dependências
- Story 11.1 (orçamento de tokens — o limite efetivo combina com o plano)
- Story 11.2 (modo de operação — features de modo gated por plano)
- Epic 9.3 (UI de Gestão de Módulos — sinergia, não bloqueio)
- Story 10.8 (`<app-modal>` para o modal de upgrade)

### Notas Técnicas
- **Feature matrix** vive em `app/domain/plans/features.py` como dict — mesmo padrão da matriz de capability da Story 11.2
- **Não confundir** com `agent_config` (Story 6.4), que é persona/tom, ou com `system_settings`, que é configurável pelo gestor
- **V2**: billing real, downgrade automático ao expirar o pagamento, proração
- **i18n**: nomes dos tiers e features em PT-BR por enquanto; estrutura permite locale futuro
- **A/B test V2**: posicionamento do modal de upsell

## Checklist do Dev
- [ ] Todos os critérios de aceite atendidos
- [ ] Testes escritos e passando
- [ ] Sem regressões
- [ ] Code review (`bmad-code-review`) executado e aprovado
