---
epic: 13
story: 8
title: "Motor `processar_titulos_vencidos` (encargos + escalonamento até suspensão)"
type: "Worker + Domínio Financeiro"
status: ready-for-dev
priority: critical
depends_on: "13.5, 13.4, 13.10, 13.2"
authored_by: "Amelia (dev) via bmad-create-story"
created_at: "2026-05-27"
---

# Story 13.8: Motor `processar_titulos_vencidos`

## História de Usuário

**Como** sistema financeiro,
**eu quero** processar automaticamente títulos vencidos com aplicação de encargos e escalonamento até suspensão do contrato,
**para que** a inadimplência seja tratada sem intervenção manual.

## Contexto

Motor central de cobrança — calcula multa+juros, envia mensagens em régua, suspende contratos quando atinge limite. **A história mais complexa do épico** porque integra: 13.4 (configs), 13.5 (infra), 13.10 (templates), 13.2 (máquina de estados).

## Critérios de Aceite

1. Task Celery `processar_titulos_vencidos` com schedule `crontab(hour=9, minute=0)`.
2. Busca títulos `tipo='parcela'`, `situacao='pendente'`, `data_vencimento < hoje - ServicoConfiguracao.obter_inteiro('dias_carencia', 'financeiro', padrao=0)`.
3. Para cada título: calcula `valor_atualizado = valor_nominal + multa + juros`:
   - `multa = valor × ServicoConfiguracao.obter_decimal('percentual_multa', 'financeiro', padrao=Decimal('2.00')) / 100` no D+1
   - `juros = valor × ServicoConfiguracao.obter_decimal('percentual_juros_dia', 'financeiro', padrao=Decimal('0.0333')) / 100 × dias_atraso`

   Atualiza `situacao = 'em_atraso'`, persiste encargos.
4. Envia mensagem de cobrança via `renderizador_template` respeitando `limite_tentativas_cobranca` e `intervalo_tentativas_horas` (lidos via `ServicoConfiguracao`). Registra em `lembretes_enviados`.
5. Ao atingir `limite_dias_suspensao` (config `financeiro`): chama `ServicoSituacaoContrato.transicionar(contrato_id, 'suspenso', motivo=...)`.
6. Ao atingir `limite_dias_encerramento` (config `financeiro`): chama `ServicoSituacaoContrato.transicionar(contrato_id, 'encerrado_com_pendencia', motivo=...)` → hook gera passivo inoperante para cada título `em_atraso`.
7. Publica `EventoTituloVencido` para cada título processado.
8. Idempotente: encargos calculados com base na data atual (sobrescreve, não acumula). Contratos `suspenso` ou terminais ignorados.
9. Testes: D+1 → multa aplicada, mensagem enviada; D+`limite_dias_suspensao+1` → contrato suspenso, veículo bloqueado; D+`limite_dias_encerramento+1` → contrato encerrado, passivo gerado.

## Contexto Técnico

### Cálculo de encargos

```python
def calcular_valor_atualizado(titulo: TituloReceber, hoje: date, config: ServicoConfiguracao) -> Decimal:
    dias_atraso = (hoje - titulo.data_vencimento).days
    if dias_atraso <= config.obter_inteiro('dias_carencia', 'financeiro', 0):
        return titulo.valor
    pct_multa = config.obter_decimal('percentual_multa', 'financeiro', Decimal('2.00'))
    pct_juros_dia = config.obter_decimal('percentual_juros_dia', 'financeiro', Decimal('0.0333'))
    multa = titulo.valor * pct_multa / 100
    juros = titulo.valor * pct_juros_dia / 100 * dias_atraso
    return titulo.valor + multa + juros
```

### Régua de cobrança

`limite_tentativas_cobranca` (default 3) + `intervalo_tentativas_horas` (default 24). Worker consulta `lembretes_enviados` para contagem.

### Hooks de bloqueio

Suspensão dispara `quando_contrato_suspenso` (Story 13.2) que bloqueia veículo via `IGatewayRastreador`.

## Arquivos a Criar/Modificar

```
src/backend-api/app/
├── domain/finance/
│   └── calculos_encargos.py                             # CRIAR — funções puras
├── workers/tasks/
│   └── processar_titulos_vencidos.py                    # CRIAR
└── tests/
    └── test_processar_vencidos.py                       # CRIAR
```

## Checklist do Dev

- [ ] 13.5, 13.4, 13.10, 13.2 concluídas.
- [ ] Cálculo de multa/juros bate com fórmula manual (validar com exemplos).
- [ ] Régua de cobrança respeita `limite_tentativas` e `intervalo_horas`.
- [ ] Suspensão automática ao atingir `limite_dias_suspensao`.
- [ ] Encerramento automático ao atingir `limite_dias_encerramento` + passivo gerado.
- [ ] Idempotência: rodar 2x no mesmo dia não duplica encargos nem cobrança.
- [ ] Eventos publicados (`EventoTituloVencido`).

## Notas

- Story mais complexa do épico — pode ser quebrada em sub-tarefas internas:
  - 13.8-a: cálculo de encargos isolado
  - 13.8-b: régua de cobrança
  - 13.8-c: escalonamento (suspensão/encerramento)
- Testar com fixtures que simulam datas (use `freezegun`).
