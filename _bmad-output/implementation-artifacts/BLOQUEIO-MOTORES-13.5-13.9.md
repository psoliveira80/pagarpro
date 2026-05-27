# Bloqueio dos Motores (Stories 13.5–13.9)

**Data:** 2026-05-27
**Autor:** Amelia (dev)
**Status:** Não implementadas — requerem decisão do PO (Pablo).

## Stories afetadas

| Story | Título | Justificativa do bloqueio |
|---|---|---|
| 13.5 | Infraestrutura base dos workers (Celery groups/chord, locks, idempotência) | Refactor estrutural cross-cutting — afeta TODOS os workers existentes. Risco de regressão silenciosa em workers já em produção (`gerar_titulos_mensais`, `processar_titulos_vencidos`, etc.). |
| 13.6 | Motor `gerar_titulos_mensais` (consolidação) | Worker já existe e está em uso. Story 13.6 propõe reescrita para usar a nova infraestrutura da 13.5 + ler de `ServicoConfiguracao` (13.4). Sem 13.5 estabilizada, o refactor não tem chão. |
| 13.7 | Motor `alertar_vencimentos_proximos` (NOVO) | Worker novo que depende de Story 13.4 (`ServicoConfiguracao`) ✅ e 13.10 (`RenderizadorTemplate`) ✅. **Tecnicamente pronto para começar**, mas exige integração com canal real de envio WhatsApp (`IMessageChannel`) que tem débito documentado na Story 13.1 (interfaces ainda em EN). |
| 13.8 | Motor `processar_titulos_vencidos` (NOVO) | Mesma situação da 13.7 — depende de 13.4 ✅, 13.2 (state machine) ✅, 13.10 ✅. Adicionalmente, depende de `IGatewayRastreador` para bloqueio GPS — também débito da 13.1. |
| 13.9 | Motor `conciliar_pagamentos_recebidos` (NOVO) | Depende de 13.4 ✅, 13.3 (tipo de título) ✅, integração bancária (`IPaymentGateway`) — interface também em débito. |

## Razões para não rodar autonomamente

1. **Risco de regressão alto em workers ativos.** Workers já estão rodando em ambiente de desenvolvimento, gerando títulos e processando vencimentos. Um refactor mal calibrado pode parar o pipeline mensal de geração de parcelas.

2. **Decisões de arquitetura abertas em Story 13.5:**
   - Estratégia de fan-out: `group()` vs `chord()` vs `chain()` — cada uma com trade-offs diferentes em retry e visibility.
   - Idempotência: `SELECT FOR UPDATE SKIP LOCKED` no banco vs lock distribuído em Redis vs híbrido — Pablo precisa escolher.
   - Estratégia de retry: tenacity vs Celery retry nativo vs custom — afeta observabilidade.

3. **Interfaces em débito.** Hooks (`on_installment_paid`, etc.) e Ports (`IMessageChannel`, `IPaymentGateway`, `ITrackerGateway`) ainda estão com nomes em inglês (documentado como débito na Story 13.1). Os motores 13.7–13.9 usariam essas interfaces ativamente; renomear AGORA evita refactor duplo.

4. **Story 13.18 (sugerida) — rename de Interfaces** seria pré-requisito coerente antes das 13.7–13.9.

## Caminho recomendado para a próxima sessão

1. **Pablo decide a arquitetura da 13.5** (fan-out + idempotência + retry) em discussão dirigida, antes de codar.
2. Implementar 13.5 com testes que cubram fluxo coordinator → worker → result.
3. Criar Story 13.18 — "Rename de Interfaces e Hooks (Ports)" — e implementar.
4. Implementar 13.6 (refactor do `gerar_titulos_mensais` usando 13.5 + ServicoConfiguracao).
5. Implementar 13.7, 13.8, 13.9 em paralelo (não dependem entre si após 13.5 + 13.18).
6. Reabrir Story 13.15 para incluir aba "Motor" com status real das tasks.

## O que JÁ está pronto para 13.7–13.9

- `ServicoConfiguracao` (13.4) — leitura tipada de `limite_dias_suspensao`, `percentual_multa`, `intervalo_tentativas_horas`, etc.
- `RenderizadorTemplate` (13.10) — render dos 5 templates seedados (`lembrete_vencimento`, `cobranca_vencida`, `aviso_suspensao`, `pagamento_confirmado`, `opcao_compra_exercida`).
- `ServicoSituacaoContrato` (13.2) — única porta de mudança de status; motores 13.7/13.8 chamam aqui.
- `TipoTitulo` + `TIPOS_DEVEDORES` (13.3) — saldo devedor filtra `opcao_compra` corretamente.
- `ServicoOpcaoCompra` (13.3) — chamado pela 13.9 quando `titulo.tipo='opcao_compra'` é pago.

A fundação está sólida. Falta a infraestrutura de workers (13.5) e o rename das Ports (13.18) antes de plugar os motores.
