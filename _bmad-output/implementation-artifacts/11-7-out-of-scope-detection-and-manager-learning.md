---
epic: 11
story: 7
title: "Out-of-Scope Detection & Manager Learning"
type: "Core"
status: ready-for-dev
---

# Story 11.7: Out-of-Scope Detection & Manager Learning

## User Story
As a Manager,
I want to see customer messages the system couldn't classify and easily turn my manual reply into a permanent rule,
So that the autopilot keeps getting smarter over time.

## Acceptance Criteria

1. Definição de "out-of-scope":
   - `IntentMatcher.match()` retorna `intent_name='unknown'` (catch-all hit), OU
   - Em ia-eco, LLM classifier retornou 'unknown', OU
   - Mensagem foi explicitamente roteada para `handover_human` por alguma rule
2. Quando out-of-scope detectado:
   - Conversation flagged `needs-attention` (yellow badge no inbox — Story 6.7 já tem)
   - Em `ia-zero`/`ia-eco`, sistema responde com `main_menu` (Story 11.3) imediatamente
   - Mensagem inbound salva com `metadata.out_of_scope=true`
3. Tabela `out_of_scope_log` (view materializada de `intent_match_log` onde `intent_name='unknown' OR matched_rule_id IS NULL` nos últimos 30 dias):
   - Agrupa por mensagem normalizada (remove acentos, lowercase, strip pontuação)
   - Contador por grupo + sample messages
   - Top 50 mensagens mais frequentes não classificadas
4. Frontend page **Settings → Autoatendimento → Aprendizado**:
   - Lista das top mensagens out-of-scope (últimos 30 dias)
   - Para cada: count, primeira/última ocorrência, sample message clicável (abre a conversa no inbox)
   - Botão "Criar Regra" abre wizard pré-preenchido (vai pra Story 11.4 rule editor com `pattern` sugerido)
5. **Manager Learning inline no Inbox** (Story 6.7):
   - Quando uma mensagem da conversation está marcada `out_of_scope=true`, aparece um botão ⚡ "Salvar como regra" ao lado dela
   - Click abre quick-form (não wizard inteiro): `intent_name`, `match_type` (default keyword, sugere palavras-chave da mensagem), `action_type`, `action_payload`
   - Submit cria a `intent_rule`. Próximas mensagens iguais batem na rule e nunca mais caem em out-of-scope
6. Suggestion engine (heurística leve, sem LLM):
   - Ao abrir quick-form, sistema sugere keywords extraindo palavras com IDF alto da mensagem (excluindo stop words PT-BR: artigos, preposições, etc.)
   - Lista das top 3 keywords pré-selecionadas; manager pode des/selecionar antes de salvar
   - Stop words em `app/domain/intents/stop_words_ptbr.py` (lista commitada, ~150 palavras)
7. Backend endpoints:
   - `GET /api/v1/intent-rules/out-of-scope-suggestions?limit=50&since=30d` — top mensagens não classificadas agrupadas
   - `POST /api/v1/intent-rules/extract-keywords` — body `{text}` → retorna top keywords (sem LLM)
   - `POST /api/v1/intent-rules/from-message/{message_id}` — convenience endpoint para criar rule a partir de mensagem específica
8. Métrica Prometheus `out_of_scope_messages_total{tenant}` — gestor pode monitorar evolução
9. Widget no Dashboard: "X mensagens não classificadas nos últimos 7 dias — Treinar agora" (link para Aprendizado)
10. Tests:
    - Out-of-scope detection em todos os modos
    - Keyword extraction não retorna stop words
    - Quick-form do inbox cria rule corretamente
    - Stats agrupa mensagens similares (mesmo após normalização) corretamente

## Technical Context

### Architecture References
- View materializada para performance (refresh hourly via Celery)
- `intent_match_log` da Story 11.4 é a fonte
- Inline button no inbox = adição ao componente da Story 6.7

### Files to Create/Modify
```
backend-api/
├── app/domain/intents/
│   ├── keyword_extractor.py             # IDF-based extraction
│   └── stop_words_ptbr.py
├── app/application/intents/
│   ├── out_of_scope_stats.py
│   └── create_rule_from_message.py
├── app/api/v1/intent_rules_routes.py    # add endpoints
├── alembic/versions/xxxx_out_of_scope_view.py
frontend/
├── src/app/features/settings/intent-rules/learning-page.component.ts/.html/.css
├── src/app/features/settings/intent-rules/quick-rule-form.component.ts/.html/.css
├── src/app/features/inbox/components/chat-message/save-as-rule-button.component.ts/.html/.css
└── src/app/features/dashboard/widgets/learning-prompt-widget.component.ts/.html/.css
```

### Dependencies
- Story 11.4 (`intent_match_log`, IntentMatcher, rule CRUD)
- Story 6.7 (Inbox — extensão)
- Story 11.3 (Interactive Menu — fallback em out-of-scope)

### Technical Notes
- **IDF cache**: precomputar IDF sobre corpus de últimos 30 dias de mensagens, refresh diário. Persistir em Redis hash `idf:{tenant_id}` para lookup O(1) na extração.
- **Stop words** podem ser tenant-overridable em V2 (hoje commitada)
- **Anti-spam**: agrupador de out-of-scope dedupes em janela 30s — se cliente repete mesma mensagem 10x não vira 10 entries
- **Privacy**: out-of-scope log truncado por compliance — não armazenar mensagens há mais de 90 dias (limpeza por Celery task)

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] No regressions
- [ ] Code review (`bmad-code-review`) executed and approved
