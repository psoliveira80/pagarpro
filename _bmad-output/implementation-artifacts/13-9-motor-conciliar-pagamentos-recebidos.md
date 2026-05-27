---
epic: 13
story: 9
title: "Motor `conciliar_pagamentos_recebidos` (com Fusão de Pagamento Parcial)"
type: "Worker + Domínio Financeiro"
status: review
priority: critical
depends_on: "13.5, 13.4, 13.3, 13.13"
authored_by: "Amelia (dev) via bmad-create-story"
created_at: "2026-05-27"
---

# Story 13.9: Motor `conciliar_pagamentos_recebidos`

## História de Usuário

**Como** sistema financeiro,
**eu quero** verificar automaticamente pagamentos recebidos, reconciliá-los e tratar pagamentos parciais com regra de fusão,
**para que** o ciclo financeiro seja autônomo e diferenças pequenas sejam fundidas na próxima parcela em vez de gerar título novo desnecessariamente.

## Contexto

Esta story implementa a **lógica de conciliação inteligente** — pagamento integral, parcial fundido, ou parcial separado. Também dispara a transferência de propriedade quando opção de compra é paga.

**Pré-requisitos:** 13.5 (infra), 13.4 (configs), 13.3 (tipo título), 13.13 (desbloqueio em confiança para reativar contrato suspenso).

## Critérios de Aceite

1. Task Celery `conciliar_pagamentos_recebidos` com schedule `crontab(minute='*/15')`.
2. Busca pagamentos com `situacao='pendente_verificacao'`. Para cada um: localiza título por `titulo_id` ou por `(empresa_id, valor, competencia)` como fallback.
3. Hook `quando_titulo_pago(titulo_id, pagamento_id)`: atualiza título (`situacao='pago'`), verifica `titulo.tipo`:
   - `parcela` → fluxo normal: verifica se contrato `suspenso` pode ser reativado
   - `opcao_compra` → publica `OpcaoCompraPaga`
4. Ao reativar contrato suspenso: chama `ServicoDesbloqueioConfianca.verificar()` (História 13.13). Se elegível, `ServicoSituacaoContrato.transicionar(contrato_id, 'ativo', motivo='Pagamento confirmado')`.
5. **Pagamento parcial com fusão automática**: se `valor_pago < valor_titulo`:
   - Calcula `restante = valor_titulo - valor_pago`
   - Lê `limite_fusao_parcial_pct` via `ServicoConfiguracao` (default 20.00%)
   - Se `restante <= valor_titulo × limite_fusao_parcial_pct / 100`:
     - **Funde**: marca título original como `pago_parcial`, adiciona `restante` ao próximo título em aberto do contrato (com nota de auditoria), sem criar título novo
   - Caso contrário:
     - **Separa**: cria título novo `tipo='parcela'`, `valor=restante`, `parent_titulo_id=titulo.id`, vencimento = hoje + `dias_carencia`
   - Publica `EventoPagamentoParcialRecebido` em ambos os casos
6. Pagamentos sem identificação → tabela `pagamentos_nao_identificados` + alerta operacional.
7. Webhook externo `POST /api/v1/webhooks/pagamento` cria pagamento e dispara task com `countdown=5s`.
8. Idempotente: pagamento já `conciliado` ignorado sem erro.
9. Testes:
   - Pagamento integral → título `pago`
   - Pagamento parcial dentro do threshold (ex: paga 95% de R$800, restam R$40 = 5% < 20%) → funde no próximo título
   - Pagamento parcial fora do threshold (ex: paga 50%, restam R$400 = 50% > 20%) → cria título novo com `parent_titulo_id`
   - Opção de compra paga → `OpcaoCompraPaga` publicado, veículo alienado

## Contexto Técnico

### Estratégia de localização do título

1. **Match direto:** `pagamento.titulo_id` preenchido (gateway ou cliente informou).
2. **Match heurístico:** `(empresa_id, valor exato, mês/ano)` → se 1 resultado, vincula; se múltiplos, vai para `pagamentos_nao_identificados`.

### Fusão parcial

```python
def conciliar_parcial(titulo, valor_pago, config, repo):
    restante = titulo.valor - valor_pago
    limite_pct = config.obter_decimal('limite_fusao_parcial_pct', 'financeiro', Decimal('20.00'))
    if restante <= titulo.valor * limite_pct / 100:
        proximo = repo.proximo_titulo_em_aberto(titulo.contrato_id)
        if proximo:
            proximo.valor += restante
            proximo.notas_auditoria.append(f"Fusão de R${restante} do título {titulo.id}")
            titulo.situacao = 'pago_parcial'
            return 'fundido'
    novo = TituloReceber(parent_titulo_id=titulo.id, valor=restante, ...)
    titulo.situacao = 'pago_parcial'
    return 'separado'
```

## Arquivos a Criar/Modificar

```
src/backend-api/app/
├── workers/tasks/
│   └── conciliar_pagamentos_recebidos.py                # CRIAR
├── application/hooks/
│   └── quando_titulo_pago.py                            # MODIFICAR — fluxo por tipo + fusão parcial
├── api/v1/
│   └── webhooks_pagamento_routes.py                     # CRIAR — POST /webhooks/pagamento
├── infrastructure/db/models/
│   └── pagamento_nao_identificado.py                    # CRIAR
└── tests/
    └── test_conciliar_pagamentos.py                     # CRIAR
```

## Checklist do Dev

- [ ] 13.5, 13.4, 13.3, 13.13 concluídas.
- [ ] Task roda a cada 15 min via Beat.
- [ ] Match heurístico funciona quando `titulo_id` ausente.
- [ ] Fusão parcial dentro do threshold testada.
- [ ] Separação fora do threshold testada (cria `parent_titulo_id`).
- [ ] Opção de compra dispara alienação do veículo.
- [ ] Webhook externo gera pagamento + dispara task em 5s.
- [ ] Idempotência: pagamento `conciliado` ignorado.

## Notas

- Hook `quando_titulo_pago` é central — também é chamado quando comprovante OCR é validado manualmente (Story 4.5 já done).
- Story complexa — boa candidata a code review duplo (`bmad-code-review`).
