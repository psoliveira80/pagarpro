---
epic: 11
story: 4
title: "Motor de Intent Rules (flashtext + rapidfuzz + regex)"
type: "Core"
status: ready-for-dev
---

# Story 11.4: Motor de Intent Rules

## História de Usuário
Como Sistema,
quero classificar mensagens de clientes de forma determinística sem usar LLM,
para que possamos rotear para templates/menus/funções nos modos ia-eco e ia-zero com custo zero de tokens.

## Critérios de Aceite

1. Nova tabela `intent_rules`: `id`, `tenant_id`, `intent_name` (snake_case, ex.: `pedido_segunda_via`, `comprovante_enviado`), `match_type` ('keyword' | 'regex' | 'fuzzy'), `pattern` (text — palavras separadas por vírgula, regex, ou frase para fuzzy), `min_score` (NUMERIC, apenas para fuzzy, 0-100, default 80), `priority` INT (default 100, menor = maior prioridade), `action_type` ('send_template' | 'show_menu' | 'call_function' | 'classify_only'), `action_payload` JSONB (`{template_id}`, `{menu_slug}`, `{function_name, args}`), `enabled` BOOL, timestamps, soft delete.
2. Serviço `IntentMatcher`:
   - Carrega regras habilitadas do tenant a partir de cache (Redis, key `intent_rules:{tenant_id}`, TTL 60s, invalidado no CRUD de regra)
   - `match(text: str, tenant_id) -> Optional[IntentMatch]` onde `IntentMatch = {intent_name, score, rule_id, action_type, action_payload}`
   - Ordem de avaliação: priority ASC, depois match_type ('regex' > 'keyword' > 'fuzzy' para mesma prioridade)
   - Retorna o primeiro match onde score ≥ threshold (regex/keyword = 100, fuzzy = `min_score`)
3. **Tech stack** (não usar Rasa):
   - `flashtext` para `match_type=keyword` — KeywordProcessor por tenant, case-insensitive, com normalização unicode (remove acentos)
   - `re` (builtin) para `match_type=regex` — pattern compilado e cacheado
   - `rapidfuzz` (`fuzz.partial_ratio`) para `match_type=fuzzy` — lida com typos comuns no WhatsApp
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
5. Pipeline de entrada em `ia-zero` ou quando `OperationModeService.is_allowed('llm_classify') == False`:
   - Chama `IntentMatcher.match()` direto
   - Executa `action_payload` via dispatcher comum (o mesmo da Story 11.3)
   - Nenhuma chamada de LLM acontece
6. Pipeline de entrada em `ia-eco`: primeiro tenta `IntentMatcher`; se `intent_name == 'unknown'`, então chama LLM com prompt curto: "classifique em uma das intents X, Y, Z. Responda só o nome ou 'unknown'." (~50 tokens). Se o LLM retorna uma intent conhecida, executa a ação; se 'unknown', fallback para o menu.
7. Endpoints do backend:
   - `GET /api/v1/intent-rules` — lista com filtros
   - `POST /api/v1/intent-rules` — cria
   - `PUT /api/v1/intent-rules/{id}` — atualiza
   - `DELETE /api/v1/intent-rules/{id}` — soft delete
   - `POST /api/v1/intent-rules/test` — body `{text, tenant_id}` → retorna `{matched_intent, matched_rule, score, all_candidates: [...]}`
   - `POST /api/v1/intent-rules/import` — import em massa JSON/CSV
   - `GET /api/v1/intent-rules/stats` — para cada regra, quantas vezes deu match nos últimos 30 dias (a partir de `intent_match_log`)
8. Tabela `intent_match_log` (append-only, particionada por mês): `id`, `tenant_id`, `conversation_id`, `message_id`, `matched_rule_id` (nullable), `intent_name`, `score`, `created_at`. Index em `(tenant_id, matched_rule_id, created_at)`.
9. Página de frontend **Configurações → Autoatendimento → Regras**:
   - Tabela com regras, busca, filtro por `intent_name`/`action_type`/`enabled`
   - Drag-handle para reordenar (atualiza `priority`)
   - Botão "Nova Regra" abre wizard de 3 steps: 1) match (tipo + pattern + min_score), 2) ação (action_type + payload), 3) preview/teste
   - Aba "Testar": textarea + botão "Match" mostra qual regra bateu, score, top 5 candidatos
   - Para cada regra: badge "X matches nos últimos 30 dias" (de stats de `intent_match_log`)
10. Meta de performance: `IntentMatcher.match()` p99 < 10ms para até 500 regras por tenant. Benchmark incluído nos testes.
11. Testes:
    - Cada match_type funciona isolado
    - Tiebreak por priority + match_type funciona
    - Invalidação de cache no CRUD
    - Fuzzy ignora acentos e maiúsculas
    - Regex catastrófico é prevenido (re.compile com timeout via signal ou lib `regex`)

## Contexto Técnico

### Referências de Arquitetura
- `IntentMatcher` é um **serviço de domínio puro** (sem I/O exceto o load das regras) — facilmente testável em unitário
- Cache Redis por tenant + invalidação event-driven (não somente TTL)
- `intent_match_log` é base para stats e também para a Story 11.7 (manager learning)

### Arquivos a Criar/Modificar
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

### Novas dependências
- `flashtext==2.7` (Python)
- `rapidfuzz==3.x` (Python)
- `regex` (opcional — versão melhorada do `re`, suporta timeout)

### Dependências
- Story 10.4 (message templates — alvo de `action_type=send_template`)
- Story 11.2 (serviço de modo de operação — controla se o LLM é chamado)
- Story 11.3 (menus — alvo de `action_type=show_menu`)

### Notas Técnicas
- **Prevenção de ReDoS**: validar `pattern` no POST com `try compile + timeout 1s contra string longa de teste`. Rejeitar com 400 se compilação ou execução demorar.
- **Isolamento de tenant**: NUNCA carregar regras de outro tenant. A key de cache tem `tenant_id`.
- **Normalização**: aplicar antes do match tanto em keyword quanto em fuzzy. Regex respeita o pattern do usuário (que pode incluir flags).
- **Regra catch-all** com `pattern='.*'` priority 9999 garante que sempre há um match (fallback para menu)
- **Import em massa** valida cada linha; relatório por linha com erros/sucessos

## Checklist do Dev
- [ ] Todos os critérios de aceite atendidos
- [ ] Testes escritos e passando
- [ ] Sem regressões
- [ ] Code review (`bmad-code-review`) executado e aprovado
