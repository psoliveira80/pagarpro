---
epic: 13
story: 22
title: "State Machine do Número Rígido + Menu Adaptativo por Estado e Score"
type: "Domínio + Integração"
status: ready-for-dev
priority: critical
depends_on: "13.21, 13.4, 13.10"
authored_by: "Amelia (dev) + Pablo (PO)"
created_at: "2026-05-28"
---

# Story 13.22: State Machine do Número Rígido

## História de Usuário

**Como** cliente da empresa que recebe WhatsApp do sistema,
**eu quero** um menu rígido com opções pré-definidas adaptadas ao meu estado (adimplente ou inadimplente) e ao meu score,
**para que** eu resolva minha demanda sem depender de conversa aberta (custo zero de IA) e o sistema funcione 100% autônomo.

## Contexto

Quando IA está desativada (default), o número rígido **não responde a texto livre**. Apenas reage a:
1. Comandos pré-definidos da state machine (botões interativos).
2. Mídia enviada após cliente clicar `📎 Enviar comprovante` (timer ativo).

Qualquer texto livre fora desses casos recebe resposta padrão: *"Use os botões abaixo para continuar."* + reenvio do menu.

O menu se adapta em tempo real ao estado do cliente:
- **Adimplente** → opções de consulta e pagamento.
- **Inadimplente** → adicional de ações condicionais por score (adiar / desbloqueio em confiança / pagamento parcial).
- **Blacklist ativa** → bypassa score, sem ações de confiança disponíveis.

## Critérios de Aceite

1. **Migration**:
   - `cobranca.conversas` ganha:
     - `estado_maquina` (varchar, default `'idle'`).
     - `aguardando_comprovante_ate` (timestamptz, null) — Story 13.23 usa.
     - `confirmacao_recebimento_em` (timestamptz, null) — Story 13.25 usa.
   - `cadastro.clientes` ganha:
     - `na_blacklist_comprovantes` (boolean, default false).
     - `motivo_blacklist` (text).
     - `adiamentos_usados_no_periodo` (integer, default 0).
     - `desbloqueios_confianca_usados_no_periodo` (integer, default 0).
     - `inicio_periodo_acoes` (date) — quando o período corrente começou (reset automático).

2. **State machine** em `app/domain/comunicacao/maquina_numero_rigido.py`:
   - Estados: `idle`, `aguardando_comprovante`, `confirmando_adiamento`, `confirmando_desbloqueio_confianca`, `confirmando_pagamento_parcial`.
   - Transições disparadas por: clique em botão, recebimento de mídia, timeout, comando do gestor.
   - Função pura, sem I/O.

3. **`ServicoMenuAdaptativo`** em `application/services/`:
   - `montar_menu(cliente_id) -> Menu` — calcula menu apropriado baseado em:
     - Adimplência (existe título vencido?).
     - Score do cliente.
     - Configurações do tenant (`score_minimo_*` por ação).
     - Blacklist (se ativa, oculta ações de confiança).
     - Limites usados no período (`adiamentos_usados_no_periodo` vs `limite_usos_periodo_adiar`).
   - Menu sempre inclui: `📋 Meu extrato e saldo`, `💰 Gerar QR Code`, `📎 Enviar comprovante`.
   - Inadimplente + score suficiente + não-blacklist + dentro do limite: adiciona `⏰ Adiar`, `🔓 Desbloqueio em confiança`, `💸 Pagar parcial`.

4. **Configurações novas** (em `configuracoes_sistema`, módulo `cobranca`):
   - `score_minimo_adiar_vencimento` (decimal, default 80).
   - `score_minimo_desbloqueio_confianca` (decimal, default 65).
   - `score_minimo_pagamento_parcial` (decimal, default 50).
   - `dias_maximos_adiamento` (inteiro, default 5).
   - `valor_minimo_pagamento_parcial_pct` (decimal, default 40.0).
   - `limite_usos_periodo_adiar` (inteiro, default 1).
   - `limite_usos_periodo_desbloqueio_confianca` (inteiro, default 1).
   - `periodo_limite_acoes_cliente` (string, default `'mensal'`, aceita: `semanal`, `quinzenal`, `mensal`, `5d`, `Nd`).

5. **Worker `reset_contadores_periodo_clientes`** (Celery Beat, diariamente às 02:30 UTC):
   - Para cada cliente, verifica se passou um período completo desde `inicio_periodo_acoes`.
   - Se passou, zera contadores (`adiamentos_usados_no_periodo`, `desbloqueios_confianca_usados_no_periodo`) e atualiza `inicio_periodo_acoes = hoje`.

6. **Handler de inbound** atualizado:
   - Quando mensagem inbound chega e IA está desativada (config `comunicacao.ia_atendente_ativa = false`):
     - Se for clique em botão (interactive response) → state machine processa.
     - Se for mídia + estado da conversa é `aguardando_comprovante` + dentro do timeout → entrega para Story 13.23.
     - Se for texto livre OU mídia fora de timeout → responde com mensagem padrão + reenvia menu.
   - Quando IA está ativada → conduta diferente (Story 13.26).

7. **Ações da state machine** (handlers individuais):
   - `acao_extrato_saldo` — busca títulos abertos + vencidos, monta texto resumo, envia.
   - `acao_gerar_qr_pagamento` — gera BR Code PIX do menor título pendente, envia como mensagem QR.
   - `acao_iniciar_envio_comprovante` — seta `aguardando_comprovante_ate = now + timeout`, responde "Pode mandar a foto/PDF do comprovante agora 👍".
   - `acao_solicitar_adiamento` — confirma via botão "Confirmar adiar 5 dias?" → aplica adiamento ao próximo título, incrementa contador.
   - `acao_solicitar_desbloqueio_confianca` — confirma → libera veículo por N dias, agenda re-bloqueio, incrementa contador.
   - `acao_solicitar_pagamento_parcial` — pede valor → valida mínimo % → gera QR PIX com valor parcial.

8. **Endpoint REST** para gestor parametrizar a blacklist:
   - `PUT /api/v1/clientes/{id}/blacklist-comprovantes` — body: `{ "ativar": bool, "motivo": str }`. Audit log obrigatório.

## Contexto Técnico

### Como adapter de WhatsApp envia o menu

Botões interativos do WhatsApp permitem até 3 botões com payload customizado (callback ID). State machine usa esses payloads como gatilhos de transição:

```
buttons = [
  {"id": "menu_extrato",      "title": "📋 Meu extrato"},
  {"id": "menu_pagar",        "title": "💰 Gerar QR Code"},
  {"id": "menu_comprovante",  "title": "📎 Enviar comprovante"},
]
```

Para inadimplente com mais opções, usa **list message** (até 10 itens):

```
sections = [
  {"title": "Pagamento", "items": [
    {"id": "menu_pagar", "title": "Gerar QR Code"},
    {"id": "menu_comprovante", "title": "Enviar comprovante"},
    {"id": "menu_parcial", "title": "Pagar parcial"},
  ]},
  {"title": "Condições especiais", "items": [
    {"id": "menu_adiar", "title": "Adiar vencimento"},
    {"id": "menu_desbloqueio", "title": "Desbloqueio em confiança"},
  ]},
]
```

### Período parametrizável

Parser de período em utilitário separado: `periodo_para_dias("semanal") = 7`, `periodo_para_dias("5d") = 5`, etc.

## Arquivos a Criar/Modificar

```
src/backend-api/
├── alembic/versions/0029_state_machine_e_clientes.py
├── app/domain/comunicacao/
│   ├── __init__.py
│   └── maquina_numero_rigido.py                    # CRIAR — state machine pura
├── app/application/services/
│   ├── servico_menu_adaptativo.py                  # CRIAR
│   └── servico_acoes_cliente.py                    # CRIAR — adiar/desbloqueio/parcial
├── app/workers/tasks/
│   ├── reset_contadores_periodo_clientes.py        # CRIAR
│   └── process_inbound_whatsapp.py                 # MODIFICAR — chama menu adaptativo
├── app/api/v1/
│   └── customer_routes.py                          # MODIFICAR — endpoint blacklist
└── app/infrastructure/db/models/
    ├── cobranca.py                                 # MODIFICAR — Conversa ganha campos
    └── cadastro.py                                 # MODIFICAR — Cliente ganha campos
```

## Checklist do Dev

- [ ] Migration aplicada.
- [ ] State machine pura testada com matrix de transições.
- [ ] Menu adaptativo entrega opções corretas para 4 perfis (adimplente, inadimplente alto score, inadimplente baixo score, blacklist).
- [ ] Reset de período funciona em modos `semanal`, `quinzenal`, `mensal`, `5d`.
- [ ] Adapter Evolution Go envia botões e list message corretamente.
- [ ] Inbound texto livre responde com mensagem padrão sem chamar IA.
- [ ] Testes cobrem: cliente adimplente vê 3 botões; cliente inadimplente com score 90 vê 6 opções; cliente em blacklist nunca vê ações de confiança.

## Notas

- Esta story é o **coração da autonomia** — cobre todos os fluxos de cliente que não exigem IA.
- IA opcional (Story 13.26) só **adiciona** um botão extra; o resto da state machine permanece igual.
