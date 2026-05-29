---
epic: 13
story: 26
title: "IA Atendente Opcional (Toggle por Tenant) com Botão Adicional no Menu Rígido"
type: "Integração + Domínio"
status: ready-for-dev
priority: medium
depends_on: "13.22, 13.4"
authored_by: "Amelia (dev) + Pablo (PO)"
created_at: "2026-05-28"
---

# Story 13.26: IA Atendente Opcional

## História de Usuário

**Como** empresa cliente que paga pelo plano premium do SaaS,
**eu quero** ativar uma IA atendente que conversa com meus clientes via WhatsApp em linguagem natural quando eles clicarem em "Falar com atendente",
**para que** demandas simples sejam resolvidas sem intervenção humana, com custo controlado e claro.

## Contexto

Decisões consolidadas:
- IA é **toggle boolean** por tenant (`ia_atendente_ativa`). Sem 3 níveis.
- Sem IA = menu rígido fixo (Story 13.22).
- Com IA = adiciona botão `💬 Falar com atendente` no menu. Quando cliente clica, abre conversa com `AgentOrchestrator` existente.
- IA pode escalar para humano (transitar `conversa.agente_ativo = false` + notificar gestor).

Esta story **não cria** o AgentOrchestrator — ele já existe (`app/core/agent/`). Esta story:
1. Adiciona toggle.
2. Adiciona botão no menu quando ativo.
3. Roteia clique do botão para o orchestrator.
4. Implementa escalonamento para humano.
5. Faz tela de configuração admin do toggle + provedor IA + credencial.

## Critérios de Aceite

1. **Configuração nova** em `comunicacao`:
   - `ia_atendente_ativa` (boolean, default `false`).
   - `provedor_ia_atendente` (string, opcional — `openai`/`anthropic`/`gemini`).
   - `credencial_ia_atendente_id` (FK opcional para `credenciais_integracao`).
   - `prompt_sistema_ia_atendente` (text, default template — instrui IA sobre tom, escopo, escalação).

2. **`ServicoMenuAdaptativo` modificado** (Story 13.22):
   - Quando `ia_atendente_ativa = true`, adiciona botão `💬 Falar com atendente` ao menu.
   - ID do botão: `iniciar_atendimento_ia`.

3. **Handler do botão** em `process_inbound_whatsapp`:
   - Quando inbound é interactive button com id `iniciar_atendimento_ia`:
     - Seta `conversa.modo_atendimento = 'ia'` (campo novo via migration).
     - Carrega `AgentOrchestrator` com prompt do sistema configurado.
     - Envia primeira mensagem da IA: "Olá {{nome}}! Estou aqui pra ajudar. O que você precisa?"
   - Próximas mensagens do cliente nesta conversa enquanto `modo_atendimento = 'ia'`:
     - Vão direto para `AgentOrchestrator.run_turn`.
     - Resposta da IA é enviada via Evolution Go.

4. **Escalonamento para humano**:
   - IA tem tool `escalar_para_humano(motivo)` no `AgentToolRegistry`:
     - Seta `conversa.modo_atendimento = 'humano'`.
     - Seta `conversa.agente_ativo = false`.
     - Notifica gestor (cria registro em `logs.log_eventos`).
     - Envia mensagem ao cliente: "Vou te passar para um atendente humano. Em breve alguém responde por aqui."
   - IA usa essa tool quando detectar:
     - Cliente reclamando seriamente.
     - Pergunta fora do escopo (ex.: questões legais).
     - Solicitação que exige autoridade (cancelar contrato, reduzir valor, etc.).

5. **Migration**:
   - `cobranca.conversas.modo_atendimento` (varchar, default `'state_machine'`, aceita: `state_machine`, `ia`, `humano`).

6. **Saída do modo IA**:
   - Cliente pode pedir "voltar ao menu" → IA chama tool `voltar_menu_rigido` → seta `conversa.modo_atendimento = 'state_machine'` + reenvia menu.
   - Timeout de inatividade: após 30min sem mensagem, volta automaticamente para `state_machine` (configurável).

7. **Endpoint REST para configurar IA**:
   - `PUT /api/v1/configuracoes/ia-atendente` — body: `{ ativa: bool, provedor: str, credencial_id: uuid, prompt_sistema: str }`. Role admin.

8. **Tela admin** (frontend):
   - Estende a tela de Configurações de Motor (Story 13.15) com seção "Atendimento Virtual":
     - Toggle "Atendimento por IA ativo" (default off).
     - Quando ativo:
       - Select de provedor (OpenAI / Anthropic / Gemini).
       - Select de credencial (lista de `credenciais_integracao` da categoria `llm` da empresa).
       - Textarea para prompt do sistema com placeholder padrão sugerido.
       - Botão "Testar" — abre modal com chat de teste real.

9. **Testes obrigatórios**:
   - Toggle off → menu sem botão "Falar com atendente".
   - Toggle on → menu com botão.
   - Cliente clica botão → conversa entra em `modo_atendimento='ia'`.
   - Próxima mensagem do cliente vai para AgentOrchestrator (mock).
   - Tool `escalar_para_humano` muda modo e notifica gestor.
   - Timeout volta para state machine.

## Contexto Técnico

### Por que reusar AgentOrchestrator existente

Já está pronto e testado. ReAct loop, tool execution, persistência de turns. Esta story só **integra**.

### Custo controlado

Cliente só consome IA quando **explicitamente clica** no botão. Outras 95% das interações são state machine (custo zero). Empresa que paga pela IA controla o quanto consome via outras configurações futuras (limite de turns por cliente/mês, etc. — fora do escopo desta story).

### Prompt do sistema configurável

Cada empresa pode adaptar o tom da IA. Default sugerido:

> "Você é um assistente virtual da empresa {empresa_nome}. Ajude o cliente com dúvidas sobre seus pagamentos, contrato e veículo. Seja educado, claro e objetivo. Quando não souber, use a ferramenta `escalar_para_humano`. Nunca prometa o que não pode cumprir. Nunca invente políticas de cobrança — use as configuradas no sistema."

## Arquivos a Criar/Modificar

```
src/backend-api/
├── alembic/versions/0032_ia_atendente_opcional.py
├── app/workers/tasks/
│   └── process_inbound_whatsapp.py                 # MODIFICAR — handler botão IA + roteamento por modo
├── app/core/agent/tools/
│   ├── escalar_para_humano.py                      # CRIAR — tool de escalação
│   └── voltar_menu_rigido.py                       # CRIAR — tool de retorno ao menu
├── app/application/services/
│   └── servico_menu_adaptativo.py                  # MODIFICAR — adiciona botão IA quando ativo
├── app/api/v1/
│   └── configuracoes_routes.py                     # MODIFICAR — endpoint IA
├── app/cli/seed.py                                  # MODIFICAR — configs e prompt default
└── app/tests/test_ia_atendente_opcional.py         # CRIAR

src/frontend/src/app/features/configuracoes/
└── parametros-motor/                                # MODIFICAR — seção IA Atendente
```

## Checklist do Dev

- [ ] Migration aplicada.
- [ ] Toggle no menu funcional.
- [ ] Cliente conversa com IA via Evolution Go.
- [ ] Tool de escalação registra estado e notifica gestor.
- [ ] Timeout de inatividade volta ao menu.
- [ ] Tela admin permite configurar e testar IA.

## Notas

- IA é **upsell explícito** — empresa que paga pelo plano premium recebe esse botão pro cliente. Empresa que não paga, sistema funciona 100% sem custo IA.
