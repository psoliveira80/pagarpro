---
epic: 11
story: 7
title: "Detecção de Out-of-Scope e Aprendizado pelo Gerente"
type: "Core"
status: ready-for-dev
---

# Story 11.7: Detecção de Out-of-Scope e Aprendizado pelo Gerente

## História de Usuário
Como Gerente,
quero ver mensagens de clientes que o sistema não conseguiu classificar e facilmente transformar minha resposta manual em uma regra permanente,
para que o autopilot fique cada vez mais inteligente ao longo do tempo.

## Critérios de Aceite

1. Definição de "out-of-scope":
   - `IntentMatcher.match()` retorna `intent_name='unknown'` (hit no catch-all), OU
   - Em ia-eco, classifier LLM retornou 'unknown', OU
   - A mensagem foi explicitamente roteada para `handover_human` por alguma regra
2. Quando out-of-scope é detectado:
   - Conversation marcada com `needs-attention` (badge amarelo no inbox — Story 6.7 já tem)
   - Em `ia-zero`/`ia-eco`, sistema responde com `main_menu` (Story 11.3) imediatamente
   - Mensagem de entrada salva com `metadata.out_of_scope=true`
3. Tabela `out_of_scope_log` (view materializada de `intent_match_log` onde `intent_name='unknown' OR matched_rule_id IS NULL` nos últimos 30 dias):
   - Agrupa por mensagem normalizada (remove acentos, lowercase, tira pontuação)
   - Contador por grupo + mensagens de amostra
   - Top 50 mensagens não classificadas mais frequentes
4. Página de frontend **Configurações → Autoatendimento → Aprendizado**:
   - Lista das top mensagens out-of-scope (últimos 30 dias)
   - Para cada: contagem, primeira/última ocorrência, mensagem de amostra clicável (abre a conversa no inbox)
   - Botão "Criar Regra" abre wizard pré-preenchido (vai para o editor de regras da Story 11.4 com `pattern` sugerido)
5. **Aprendizado pelo Gerente inline no Inbox** (Story 6.7):
   - Quando uma mensagem da conversation está marcada com `out_of_scope=true`, aparece um botão ⚡ "Salvar como regra" ao lado dela
   - Clique abre um quick-form (não o wizard inteiro): `intent_name`, `match_type` (default keyword, sugere palavras-chave da mensagem), `action_type`, `action_payload`
   - Submit cria a `intent_rule`. Próximas mensagens iguais batem na regra e nunca mais caem em out-of-scope
6. Suggestion engine (heurística leve, sem LLM):
   - Ao abrir o quick-form, o sistema sugere keywords extraindo palavras com IDF alto da mensagem (excluindo stop words PT-BR: artigos, preposições etc.)
   - Lista das top 3 keywords pré-selecionadas; gerente pode des/selecionar antes de salvar
   - Stop words em `app/domain/intents/stop_words_ptbr.py` (lista committada, ~150 palavras)
7. Endpoints do backend:
   - `GET /api/v1/intent-rules/out-of-scope-suggestions?limit=50&since=30d` — top mensagens não classificadas agrupadas
   - `POST /api/v1/intent-rules/extract-keywords` — body `{text}` → retorna top keywords (sem LLM)
   - `POST /api/v1/intent-rules/from-message/{message_id}` — endpoint de conveniência para criar regra a partir de mensagem específica
8. Métrica Prometheus `out_of_scope_messages_total{tenant}` — gestor pode monitorar a evolução
9. Widget no Dashboard: "X mensagens não classificadas nos últimos 7 dias — Treinar agora" (link para Aprendizado)
10. Testes:
    - Detecção de out-of-scope em todos os modos
    - Extração de keywords não retorna stop words
    - Quick-form do inbox cria a regra corretamente
    - Stats agrupa mensagens similares (mesmo após normalização) corretamente

## Contexto Técnico

### Referências de Arquitetura
- View materializada por performance (refresh horário via Celery)
- `intent_match_log` da Story 11.4 é a fonte
- Botão inline no inbox = adição ao componente da Story 6.7

### Arquivos a Criar/Modificar
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

### Dependências
- Story 11.4 (`intent_match_log`, IntentMatcher, CRUD de regras)
- Story 6.7 (Inbox — extensão)
- Story 11.3 (Menu Interativo — fallback em out-of-scope)

### Notas Técnicas
- **Cache de IDF**: pré-computar IDF sobre o corpus dos últimos 30 dias de mensagens, com refresh diário. Persistir em hash Redis `idf:{tenant_id}` para lookup O(1) na extração.
- **Stop words** podem ser tenant-overridable em V2 (hoje committed)
- **Anti-spam**: o agrupador de out-of-scope deduplica em janela de 30s — se o cliente repete a mesma mensagem 10x, não vira 10 entradas
- **Privacidade**: o log de out-of-scope é truncado por compliance — não armazenar mensagens com mais de 90 dias (limpeza por task Celery)

## Checklist do Dev
- [ ] Todos os critérios de aceite atendidos
- [ ] Testes escritos e passando
- [ ] Sem regressões
- [ ] Code review (`bmad-code-review`) executado e aprovado
