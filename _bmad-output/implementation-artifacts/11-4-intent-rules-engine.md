---
epic: 11
story: 4
title: "Intent Rules Engine (flashtext + rapidfuzz + regex)"
type: "Core"
status: ready-for-dev
---

# Story 11.4: Intent Rules Engine

## User Story
As a System,
I want to classify customer messages deterministically without LLM,
So that we can route to templates/menus/functions in ia-eco and ia-zero modes with zero token cost.

## Acceptance Criteria

1. New table `intent_rules`: `id`, `tenant_id`, `intent_name` (snake_case, e.g., `pedido_segunda_via`, `comprovante_enviado`), `match_type` ('keyword' | 'regex' | 'fuzzy'), `pattern` (text — palavras separadas por vírgula, regex, ou frase para fuzzy), `min_score` (NUMERIC, only for fuzzy, 0-100, default 80), `priority` INT (default 100, lower = higher priority), `action_type` ('send_template' | 'show_menu' | 'call_function' | 'classify_only'), `action_payload` JSONB (`{template_id}`, `{menu_slug}`, `{function_name, args}`), `enabled` BOOL, timestamps, soft delete.
2. `IntentMatcher` service:
   - Loads enabled rules for tenant from cache (Redis, key `intent_rules:{tenant_id}`, TTL 60s, invalidated on rule CRUD)
   - `match(text: str, tenant_id) -> Optional[IntentMatch]` where `IntentMatch = {intent_name, score, rule_id, action_type, action_payload}`
   - Evaluation order: priority ASC, then match_type ('regex' > 'keyword' > 'fuzzy' for same priority)
   - Returns first match where score ≥ threshold (regex/keyword = 100, fuzzy = `min_score`)
3. **Tech stack** (não usar Rasa):
   - `flashtext` para `match_type=keyword` — KeywordProcessor por tenant, case-insensitive, com unicode normalization (remove acentos)
   - `re` (builtin) para `match_type=regex` — pattern compilado e cacheado
   - `rapidfuzz` (`fuzz.partial_ratio`) para `match_type=fuzzy` — handle de typos comuns em WhatsApp
4. Seed de regras padrão em português:
   ```
   intent_name              match_type  pattern (exemplos)                                  priority  action
   ---------------------------------------------------------------------------------------------------------
   saudacao                 keyword     oi, ola, bom dia, boa tarde, boa noite, hey         200       show_menu(main_menu)
   pedido_boletos           keyword     boletos, 2 via, segunda via, pix, pagar             150       call_function(generate_overdue_summary)
   pedido_2via              fuzzy       segunda via boleto                                  150       call_function(send_pix_qr)
   negociacao               keyword     negociar, parcelar, desconto, acordo                100       handover_human or send_template(neg_template) (depende do modo)
   comprovante_enviado      regex       (?i)\b(comprovante|paguei|pagamento\s+feito)\b     50        call_function(check_for_receipt_media)
   falar_humano             keyword     atendente, humano, falar com alguem, ajuda          50        handover_human
   reclamacao               keyword     reclamar, problema, errado, absurdo                 50        handover_human
   unknown                  regex       .*                                                  9999      show_menu(main_menu)  # catch-all
   ```
5. Inbound pipeline em `ia-zero` ou quando `OperationModeService.is_allowed('llm_classify') == False`:
   - Chama `IntentMatcher.match()` direto
   - Executa `action_payload` via dispatcher comum (mesmo da Story 11.3)
   - Nenhuma chamada de LLM acontece
6. Inbound pipeline em `ia-eco`: primeiro tenta `IntentMatcher`; se `intent_name == 'unknown'`, então chama LLM com prompt curto: "classifique em uma das intents X, Y, Z. Responda só o nome ou 'unknown'." (~50 tokens). Se LLM retorna conhecida, executa ação; se 'unknown', fallback para menu.
7. Backend endpoints:
   - `GET /api/v1/intent-rules` — list com filtros
   - `POST /api/v1/intent-rules` — create
   - `PUT /api/v1/intent-rules/{id}` — update
   - `DELETE /api/v1/intent-rules/{id}` — soft delete
   - `POST /api/v1/intent-rules/test` — body `{text, tenant_id}` → retorna `{matched_intent, matched_rule, score, all_candidates: [...]}`
   - `POST /api/v1/intent-rules/import` — bulk import JSON/CSV
   - `GET /api/v1/intent-rules/stats` — para cada rule, quantas vezes foi match nos últimos 30 dias (de `intent_match_log`)
8. Tabela `intent_match_log` (append-only, particionada por mês): `id`, `tenant_id`, `conversation_id`, `message_id`, `matched_rule_id` (nullable), `intent_name`, `score`, `created_at`. Index em `(tenant_id, matched_rule_id, created_at)`.
9. Frontend page **Settings → Autoatendimento → Regras**:
   - Tabela com regras, search, filtro por intent_name/action_type/enabled
   - Drag-handle para reordenar (atualiza `priority`)
   - Botão "Nova Regra" abre wizard 3 steps: 1) match (tipo + pattern + min_score), 2) ação (action_type + payload), 3) preview/teste
   - Aba "Testar": textarea + botão "Match" mostra qual rule bateu, score, top 5 candidates
   - Para cada regra: badge "X matches nos últimos 30 dias" (de `intent_match_log` stats)
10. Performance target: `IntentMatcher.match()` p99 < 10ms para até 500 rules por tenant. Benchmark incluído nos testes.
11. Tests:
    - Cada match_type funciona isolado
    - Priority + match_type tiebreak funciona
    - Cache invalidation no CRUD
    - Fuzzy ignora acentos e maiúsculas
    - Regex catastrófico é prevenido (re.compile com timeout via signal ou `regex` lib)

## Technical Context

### Architecture References
- IntentMatcher é um **service de domínio puro** (sem I/O exceto load de rules) — facilmente unitestável
- Cache Redis por tenant + invalidation event-driven (não TTL apenas)
- `intent_match_log` é base para stats e também para Story 11.7 (manager learning)

### Files to Create/Modify
```
backend-api/
├── app/domain/intents/
│   ├── entities.py                      # IntentRule, IntentMatch
│   ├── matcher.py                       # IntentMatcher service
│   ├── enums.py                         # MatchType, ActionType
│   └── unicode_normalize.py             # strip accents helper
├── app/application/intents/
│   ├── load_rules.py                    # load + cache
│   ├── test_rule.py
│   └── stats.py
├── app/application/collections/handle_inbound_message.py # plumbing
├── app/api/v1/intent_rules_routes.py
├── alembic/versions/xxxx_intent_rules_and_log.py
├── alembic/versions/xxxx_seed_default_intent_rules.py
frontend/
├── src/app/features/settings/intent-rules/intent-rules-list.component.ts/.html/.css
├── src/app/features/settings/intent-rules/rule-editor-wizard.component.ts/.html/.css
├── src/app/features/settings/intent-rules/rule-tester.component.ts/.html/.css
└── src/app/core/services/intent-rules.service.ts
```

### New dependencies
- `flashtext==2.7` (Python)
- `rapidfuzz==3.x` (Python)
- `regex` (opcional — versão melhorada do `re`, suporta timeout)

### Dependencies
- Story 10.4 (message templates — alvo de `action_type=send_template`)
- Story 11.2 (operation mode service — gates whether LLM is called)
- Story 11.3 (menus — alvo de `action_type=show_menu`)

### Technical Notes
- **ReDoS prevention**: validar `pattern` no POST com `try compile + timeout 1s contra string longa de teste`. Rejeitar 400 se compilação ou execução demora.
- **Tenant isolation**: NUNCA carregar rules de outro tenant. Cache key tem `tenant_id`.
- **Normalização**: aplicar antes de matchar tanto em keyword quanto em fuzzy. Regex respeita o pattern do usuário (que pode incluir flags).
- **Catch-all rule** com `pattern='.*'` priority 9999 garante que sempre há um match (fallback para menu)
- **Bulk import** valida cada linha; relatório por linha com erros/successos

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] No regressions
- [ ] Code review (`bmad-code-review`) executed and approved
