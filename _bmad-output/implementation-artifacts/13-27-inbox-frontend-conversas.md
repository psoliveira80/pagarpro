---
epic: 13
story: 27
title: "Inbox Frontend — Tela de Conversas com Timeline Unificada Multi-Número"
type: "Frontend + UX"
status: ready-for-dev
priority: high
depends_on: "13.21, 13.22"
authored_by: "Amelia (dev) + Sally (UX) + Pablo (PO)"
created_at: "2026-05-28"
---

# Story 13.27: Inbox Frontend (3 Colunas)

## História de Usuário

**Como** gestor da empresa cliente,
**eu quero** uma inbox visual de 3 colunas (sidebar · lista de conversas · chat ativo) que mostre todas as interações dos meus clientes em timeline unificada, mesmo quando vários números da minha empresa atenderam o mesmo cliente,
**para que** eu acompanhe a operação automatizada sem precisar disparar nada manualmente.

## Contexto

Inspiração visual: print do `evo-ai-crm-community` (Evo CRM) que o Pablo compartilhou. Padrão Chatwoot/Intercom clássico.

Decisões de UX consolidadas:
- **Gestor não dispara mensagens em massa pela inbox** — sistema cuida sozinho. Inbox é principalmente **monitoramento**.
- **Gestor pode mandar mensagem individual** para um cliente específico via inbox (raro, em casos pontuais).
- **Resposta vs Nota Privada**: toggle no campo de envio. Nota Privada é só interna (auditoria, contexto pra outros gestores), nunca vai pro cliente.
- **Timeline unificada por cliente**: mesmo que cliente tenha conversado com 3 números da empresa, gestor vê todas as mensagens na mesma timeline. Cada mensagem indica qual número usou (filtro opcional).
- **Status da conversa**: `aberta` / `aguardando_cliente` / `aguardando_gestor` / `arquivada` / `escalada_para_humano`.

Esta story **NÃO inclui** funcionalidades de disparo em massa, painel de campanhas, etc. — porque vai contra a filosofia (cobrança é autônoma).

## Critérios de Aceite

1. **Rota**: `/sistema/inbox` (já existe esboço — vai ser estendida).

2. **Layout 3 colunas mobile-first**:
   - **Sidebar** (sempre visível em desktop, oculta em mobile com hamburger): navegação principal já existente.
   - **Coluna 1** (lista de conversas): busca + filtros + lista vertical.
   - **Coluna 2** (chat ativo): header + mensagens + input.
   - Mobile: empilha — gestor escolhe conversa → tela inteira vira chat com botão voltar.

3. **Coluna 1 (lista)**:
   - Busca por nome ou telefone (debounce 300ms).
   - Abas: `Abertas`, `Aguardando cliente`, `Aguardando gestor`, `Arquivadas`, `Todas`.
   - Filtros: status, número de origem (multi-select), modo de atendimento (`state_machine` / `ia` / `humano`).
   - Cada item mostra: avatar/iniciais, nome cliente, telefone, snippet da última mensagem, hora, badge de não-lidas, badge do número atendente, badge de modo (🤖 IA / 👤 humano / 🤖 menu).
   - Click → carrega coluna 2.

4. **Coluna 2 (chat)**:
   - **Header**: nome cliente + telefone + selector "atendente atual" (state machine / IA / humano) + botões "Arquivar" / "Pausar agente" / "Marcar resolvido".
   - **Timeline** unificada: mensagens em bubbles, scroll automático para baixo na entrada.
     - Bubble cinza (esquerda) = inbound (cliente).
     - Bubble colorida (direita) = outbound (sistema/gestor/IA).
     - Tag em cada outbound: `🤖 Robô` / `💬 IA` / `👤 {nome do gestor}`.
     - Cada mensagem mostra timestamp + qual número (small tag).
     - Notas privadas em fundo amarelo claro com ícone de cadeado.
     - Mídia inline (preview de imagem, link de PDF).
   - **Input**:
     - Toggle `Resposta` / `Nota Privada` (igual ao Evo CRM).
     - Textarea + botões: anexar arquivo, emoji, **enviar template** (lista templates seedados), enviar.
     - Quando gestor digita em modo `Resposta`, mensagem sai pelo número atribuído ao cliente (Story 13.21).
   - **Indicador**: "🤖 Bot está respondendo automaticamente" quando `modo_atendimento != 'humano'` — alerta gestor que sua mensagem vai junto da automação.

5. **Endpoints REST necessários** (criar onde não existir):
   - `GET /api/v1/conversas` — lista paginada com filtros.
   - `GET /api/v1/conversas/{id}` — detalhe.
   - `GET /api/v1/conversas/{id}/mensagens` — mensagens paginadas.
   - `POST /api/v1/conversas/{id}/mensagens` — enviar mensagem (body: `{ texto, tipo: 'resposta'|'nota_privada' }`).
   - `PUT /api/v1/conversas/{id}/arquivar`, `/desarquivar`, `/pausar-agente`, `/retomar-agente`.

6. **Realtime via SSE** (já existe infra em `app/api/sse.py`):
   - Nova subscrição: `/api/v1/sse/conversas` — push de eventos:
     - `nova_mensagem`: mensagem nova chegou.
     - `conversa_atualizada`: status mudou (escalada, arquivada).
     - `novo_comprovante`: comprovante chegou via WhatsApp (linka pra tela da 13.19).
   - Frontend reconecta automaticamente em caso de queda.

7. **Notas privadas**:
   - Migration: tabela já existe (`cobranca.mensagens`), só usa campo novo `tipo_nota` (boolean ou enum). Adicionar coluna `eh_nota_privada` (boolean, default false).
   - Notas privadas:
     - Não vão pro cliente.
     - Aparecem na timeline de outros gestores.
     - Têm cor distinta (fundo amarelo claro).
     - Audit log de quem criou e quando.

8. **Filtros por modo de atendimento**:
   - Gestor pode filtrar lista de conversas mostrando apenas `escaladas_para_humano` (urgentes).
   - Badge contador na aba quando há conversas escaladas: "Atenção: 3 conversas aguardando você".

9. **Performance**:
   - Lista de conversas carrega últimas 50, scroll infinito.
   - Mensagens da conversa selecionada carregam últimas 30, paginação reversa.
   - Cache local com signals para evitar refetch desnecessário.

10. **Testes obrigatórios**:
    - Gestor abre inbox: vê lista de conversas com badge de não-lidas correto.
    - Filtro por número mostra só conversas atendidas por aquele número.
    - Click em conversa carrega timeline com todas as mensagens (mesmo de números diferentes).
    - Envio de Resposta vai para Evolution Go (mock) e aparece na timeline.
    - Envio de Nota Privada aparece com fundo amarelo, mas mock do Evolution Go **não** é chamado.
    - SSE push aparece em tempo real.

## Contexto Técnico

### Reuso de componentes existentes

- `app-shell` (sidebar + content) já cobre layout principal.
- `ToastService` para feedback.
- `ConfirmService` para "marcar como resolvido?".
- `CustomSelectComponent` para filtros (não usar `<select>` nativo).
- `<app-modal>` para preview de imagem em tamanho grande.

### Padrões visuais

CSS variables (`--surface`, `--accent`, `--success`, `--danger`, `--warning`). Sem cores hardcoded. Mobile-first. OnPush change detection. Signals para estado.

Inspiração do Evo CRM (Pablo aprovou):
- Bubbles diferenciadas (cinza esquerda / colorida direita).
- Toggle Resposta/Nota Privada no input.
- Tag de modo (🤖 / 👤) em cada outbound.
- Lista compacta com snippet da última mensagem.

### Per-component folder

Cada componente em sua própria pasta com `.ts`, `.html`, `.css`:

```
features/inbox/
├── inbox-lista-conversas/
├── inbox-chat/
├── inbox-mensagem-bubble/
├── inbox-input-resposta/
└── inbox-filtros/
```

## Arquivos a Criar/Modificar

```
src/backend-api/
├── alembic/versions/0033_inbox_notas_privadas.py
├── app/api/v1/
│   ├── conversation_routes.py                      # MODIFICAR — endpoints novos
│   └── sse.py                                      # MODIFICAR — canal `/sse/conversas`
├── app/infrastructure/db/models/
│   └── cobranca.py                                 # MODIFICAR — eh_nota_privada

src/frontend/src/app/
├── core/services/
│   └── conversation.service.ts                     # MODIFICAR — endpoints novos + SSE
└── features/inbox/
    ├── inbox.routes.ts                             # CRIAR
    ├── inbox-lista-conversas/                      # CRIAR per-component folder
    ├── inbox-chat/                                 # CRIAR
    ├── inbox-mensagem-bubble/                      # CRIAR
    ├── inbox-input-resposta/                       # CRIAR
    └── inbox-filtros/                              # CRIAR
```

## Checklist do Dev

- [ ] Migration aplicada.
- [ ] Endpoints REST funcionais com role-gate.
- [ ] SSE push em tempo real funcional.
- [ ] Layout 3 colunas responsivo.
- [ ] Filtros por status, número, modo.
- [ ] Resposta vs Nota Privada com toggle.
- [ ] Timeline unificada multi-número.
- [ ] Build sem erros.

## Notas

- Esta story **encerra** a frente WhatsApp do Epic 13.
- Próximo passo após esta: **conciliação visual (Story 13.20 frontend)** que ficou pra fila.
- Inbox é principalmente monitoramento, não disparo. Filosofia: gestor acompanha, sistema atua.
