---
status: roadmap (não-priorizado)
tipo: feature-futura
proposto_por: Pablo
registrado_em: 2026-05-27
registrado_por: Amelia
---

# Roadmap — Workflow Parametrizado de Cobrança (régua visual configurável)

> **Status:** ideia registrada. Não é pra agora — implementar depois das Stories 13.19 (análise de comprovante) e 13.20 (conciliação) entregarem valor.

## Visão

Hoje a régua de cobrança do Epic 13 (Story 13.8 — `processar_titulos_vencidos`) é **linear e fixa**: aplica multa → envia mensagem → suspende → encerra, baseado em thresholds configuráveis (`limite_dias_suspensao`, `limite_dias_encerramento`, etc.).

O gestor quer mais — quer desenhar **fluxos condicionais** baseados em resposta do cliente, com pontos de decisão, ações automáticas e até diálogo com IA quando habilitada.

## Exemplo do Pablo (ditado literal)

```
título venceu e não pagou
  1. fiz a cobrança e não respondeu
  2. se respondeu, primeiro o sistema vê como ele parametrizou o uso da IA:
     - se IA habilitada: IA interage em linguagem natural oferecendo opções
       (ex.: "Olá Maria, vi que você está com a parcela em atraso. Posso te oferecer
       extensão de 5 dias?")
     - se IA desabilitada: sistema envia botões interativos via WhatsApp
       (ex.: [Pedir mais 5 dias] [Vou pagar amanhã] [Já paguei, vou enviar comprovante])
     - botões só aparecem se cliente tem direito (ex.: só ofere extensão se score
       de crédito > X, ou se já não usou extensão neste mês)
  3. se não respondeu em N dias: aviso final sobre bloqueio
  4. se ainda assim não respondeu: bloqueio automático do rastreador
```

## Como modelar (proposta inicial)

### Tabela: `cobranca.fluxos_cobranca` (templates de fluxo)

```yaml
nome: "Fluxo padrão de cobrança semanal"
empresa_id: null  # NULL = template global; preenchido = override do tenant
gatilho:
  evento: titulo_vencido
  dias_apos_vencimento: 1

etapas:
  - id: "etapa-1"
    tipo: mensagem
    template: cobranca_vencida
    canal: whatsapp
    aguardar_resposta:
      timeout_dias: 3
      proxima_etapa_se_responder: "etapa-2-com-resposta"
      proxima_etapa_se_timeout: "etapa-3-aviso-bloqueio"

  - id: "etapa-2-com-resposta"
    tipo: oferecer_opcoes
    usar_ia: "{configuracoes_sistema.cobranca.modo_ia}"  # nativo|ia
    opcoes:
      - rotulo: "Pedir extensão de 5 dias"
        condicao:
          - cliente_score >= 600
          - extensoes_usadas_no_mes < 1
        acao: criar_extensao
        parametros: { dias: 5 }
        proxima_etapa: "etapa-aguardar-novo-prazo"

      - rotulo: "Vou pagar amanhã"
        acao: marcar_promessa_pagamento
        parametros: { dias_prometidos: 1 }
        proxima_etapa: "etapa-aguardar-promessa"

      - rotulo: "Já paguei, enviarei comprovante"
        acao: nenhuma
        proxima_etapa: "etapa-aguardar-comprovante"

  - id: "etapa-3-aviso-bloqueio"
    tipo: mensagem
    template: aviso_bloqueio_iminente
    canal: whatsapp
    aguardar_resposta:
      timeout_dias: 2
      proxima_etapa_se_responder: "etapa-2-com-resposta"
      proxima_etapa_se_timeout: "etapa-4-bloqueio"

  - id: "etapa-4-bloqueio"
    tipo: acao_sistema
    acao: suspender_contrato_e_bloquear_veiculo
```

### Tabela: `cobranca.execucoes_fluxo` (instância em andamento por título)

- `id`, `titulo_id`, `fluxo_id`, `etapa_atual`, `iniciado_em`, `atualizado_em`,
  `historico_jsonb` (cada passo registrado com timestamp + resposta do cliente).

### Tabela: `cobranca.respostas_cliente` (audit de resposta)

- `execucao_id`, `etapa_id`, `tipo_resposta` (botao_clicado / texto_livre / sem_resposta),
  `payload`, `recebido_em`.

## Componentes técnicos

### 1. Worker `executar_fluxos_cobranca`
- Roda a cada 30 min.
- Para cada `execucoes_fluxo` ativa, verifica se chegou a hora de avançar etapa.
- Dispara ação da etapa atual (envia mensagem, oferece opções, bloqueia, etc.).
- Substitui a régua linear atual da Story 13.8 quando habilitado.

### 2. Frontend: Editor visual de fluxo
- Tela `/sistema/configuracoes/fluxos-cobranca`.
- Canvas estilo Figma/Lucidchart com drag-and-drop.
- Cada etapa = card; conexões entre etapas = setas.
- Sidebar com paleta de tipos (mensagem, oferecer_opcoes, acao_sistema).
- Validador: garante que todo caminho leva a um nó terminal (sem loops infinitos não-intencionais).
- Export/import em YAML pra backup e versionamento.

### 3. Integração com IA Conversacional
- Quando `usar_ia=true` numa etapa de `oferecer_opcoes`:
  - Chama LLM com prompt: "Você é um assistente de cobrança da empresa X. O cliente Maria tem parcela vencida há 3 dias no valor de R$ 800. As opções que você pode oferecer são: [extensão 5 dias, promessa 1 dia, recebimento de comprovante]. Aborde de forma empática e ofereça as opções."
  - IA conversa em linguagem natural via WhatsApp.
  - Quando cliente "aceita" uma opção em texto livre, LLM faz classificação intent → ação do fluxo.
- Quando `usar_ia=false`: envia mensagem com botões interativos do WhatsApp Business API.

### 4. Reusos do que já existe
- `RenderizadorTemplate` (Story 13.10) renderiza mensagens parametrizadas.
- `ServicoConfiguracao` (Story 13.4) carrega flags de IA.
- `ServicoSituacaoContrato` (Story 13.2) executa transições de estado.
- Hooks `quando_titulo_pago` (Story 13.9) detectam pagamento e avançam fluxo.

## Decisões arquiteturais pendentes

- [ ] **Engine de fluxo:** state machine própria (XState-like em Python) ou usar lib existente (`transitions`, `automat`)?
  - **Recomendação:** state machine própria (~200 linhas), evita dependência e dá controle total para extensões futuras.
- [ ] **Storage do fluxo:** YAML no banco ou JSON com schema versionado?
  - **Recomendação:** JSONB no banco com schema versionado em código (Pydantic models). YAML só pra import/export.
- [ ] **Como evitar "duplo motor":** Story 13.8 já tem régua linear. Quando fluxo customizado existe, ele substitui ou complementa?
  - **Recomendação:** se contrato/empresa tem fluxo customizado ativo, 13.8 não roda pra esse contrato (delega pro novo motor). Backward-compat preservado.

## Dependências e pré-requisitos

- Stories 13.19 (comprovante) e 13.20 (conciliação) **completas** — porque o fluxo confia em "comprovante recebido" como sinal de pagamento.
- Templates expandidos (Story 13.10) para mensagens de cada etapa do fluxo.
- WhatsApp Business API com suporte a botões interativos (já temos via Z-API).
- LLM provider configurado (já temos infra de `IProvedorIA` proposto para 13.19).

## Estimativa grossa quando priorizar

- 4–6 stories.
- 2 sprints (1 backend + 1 frontend do editor visual).
- Maior risco técnico: editor visual no frontend (drag-and-drop com validação de grafo).

## Próximos passos (quando o momento chegar)

1. Pablo decide as 3 decisões arquiteturais marcadas com `[ ]`.
2. Validar UX do editor visual com 1 sketch antes de codar (Sally UX).
3. Implementar backend primeiro: schema, engine, worker, 1 fluxo padrão hardcoded.
4. Editor visual no frontend.
5. Migração do fluxo linear da 13.8 → primeiro fluxo customizado (default global).
6. Habilitar IA conversacional em sub-fase.

---

**Última atualização:** 2026-05-27 — Amelia (dev) registrou a pedido do Pablo durante refinamento das Stories 13.19/13.20.
