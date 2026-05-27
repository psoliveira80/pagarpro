---
epic: 13
story: 17
title: "Serviço de Boleto Proporcional ao Suspender/Cancelar Contrato"
type: "Domínio Financeiro + Application Service"
status: ready-for-dev
priority: high
depends_on: "13.2, 13.3, 13.4, 13.16"
authored_by: "Amelia (dev) por solicitação direta do Pablo (PO) — emergente em 2026-05-27"
created_at: "2026-05-27"
---

# Story 13.17: Serviço de Boleto Proporcional ao Suspender/Cancelar Contrato

## História de Usuário

**Como** gestor de contratos,
**eu quero** que ao suspender ou cancelar um contrato com pagamento periódico (semanal/mensal/personalizado) no meio de um ciclo de cobrança, o sistema gere automaticamente um título proporcional ao tempo de uso (ou um crédito de devolução, se o cliente pagou adiantado),
**para que** ninguém pague pelo que não usou e ninguém deixe de pagar pelo que usou — sem cálculo manual nem disputa.

## Contexto

Regra de negócio levantada pelo PO em 2026-05-27 após smoke-test:

> "Se o sujeito paga pelo contrato um valor semanal, e pede a interrupção do contrato (seja a suspensão temporária ou o cancelamento) isso deve gerar um boleto proporcional do tempo de atividade, de acordo com valores e regras."

Esta story implementa o **ServicoBoletoProporcional** — domínio puro + application service — invocado pelos hooks `quando_contrato_suspenso` (Story 13.2) e `quando_contrato_encerrado` (já existe via rescisão manual ou Story 13.8 — encerramento automático por inadimplência crônica).

Formalizado no PRD como **FR-CORE-CTR-11** (v3.1, 27/05/2026).

**Por que story própria (e não diluído nas 13.2/13.8/13.9):**
- Lógica de proporcionalidade é **regra puramente financeira** — funções puras testáveis sem mockar workers.
- 3 cenários distintos com regras diferentes (parcela em aberto/já paga, suspensão vs cancelamento, contrato com correção/sem).
- Reusável: pode ser disparado também por outros caminhos no futuro (ex: rescisão por iniciativa do operador via tela, novas regras comerciais).
- Configurável via `ServicoConfiguracao` (Story 13.4) — 3 parâmetros novos.
- Justifica code review próprio sem misturar com regras de máquina de estados ou worker.

## Critérios de Aceite

### Lógica de domínio (funções puras)

1. Função `calcular_valor_proporcional(valor_parcela: Decimal, dias_usados: int, dias_totais_ciclo: int) -> Decimal` em `domain/finance/boleto_proporcional.py`:
   - Retorna `valor_parcela × (dias_usados / dias_totais_ciclo)`, arredondado para 2 casas (banker's rounding — `Decimal.quantize(..., ROUND_HALF_EVEN)`).
   - Validação: `dias_usados ≥ 0`, `dias_totais_ciclo > 0`. `dias_usados > dias_totais_ciclo` lança `ValueError`.
   - Edge case: `dias_usados == 0` retorna `Decimal('0')` (interrupção no mesmo dia de início do ciclo).

2. Função `calcular_dias_ciclo(tipo_intervalo: str, dia_semana: int | None, dia_mes: int | None, intervalo_dias: int | None, data_referencia: date) -> int`:
   - `semanal` → 7
   - `personalizado_dias` → `intervalo_dias`
   - `mensal` → dias do mês de `data_referencia` (28, 29, 30, 31)
   - Outros tipos no futuro → mapping extensível.

3. Função `calcular_dias_usados(data_inicio_ciclo: date, data_interrupcao: date) -> int`:
   - Retorna `(data_interrupcao - data_inicio_ciclo).days`.
   - Negativo → `ValueError`.

### Application Service

4. `ServicoBoletoProporcional` em `application/services/servico_boleto_proporcional.py`:

```python
class ServicoBoletoProporcional:
    def __init__(self, repo_contratos, repo_titulos, repo_config, repo_audit):
        ...

    def gerar(self, contrato_id: UUID, data_interrupcao: date, motivo: str, tipo_interrupcao: str) -> ResultadoProporcional:
        """
        tipo_interrupcao ∈ {'suspensao', 'cancelamento'}
        Retorna ResultadoProporcional com: acao ('cobranca' | 'credito' | 'pulado'), titulo_id, valor.
        """
```

5. **Lógica de decisão (dentro de `gerar`):**
   - Lê config `cobrar_proporcional_ao_{tipo_interrupcao}` via `ServicoConfiguracao`. Se `false`, retorna `acao='pulado'` sem efeito.
   - Lê config `dia_base_calculo_proporcional` (`data_pagamento` | `data_vencimento_anterior`, default `data_vencimento_anterior`).
   - Localiza o ciclo de cobrança atual usando `dia_base_calculo_proporcional`:
     - `data_vencimento_anterior` → última parcela cujo vencimento foi ≤ `data_interrupcao`.
     - `data_pagamento` → última parcela paga (`pago` ou `pago_parcial`).
   - Calcula `dias_totais_ciclo` (via `calcular_dias_ciclo` usando `contrato.tipo_intervalo`).
   - Calcula `dias_usados` = `data_interrupcao - data_inicio_ciclo`.
   - Calcula `valor_proporcional` = `calcular_valor_proporcional(contrato.valor_parcela, dias_usados, dias_totais_ciclo)`.
   - **Decide ação:**
     - **A — Parcela do ciclo ainda em aberto:** cancela o título original (`status='cancelado'`, motivo registrado), cria novo título `tipo='taxa'` com `valor=valor_proporcional`, `data_vencimento=data_interrupcao + dias_carencia` (lido de config), `parent_titulo_id=titulo_original.id`, `observacoes='Boleto proporcional gerado por suspensão/cancelamento do contrato em DD/MM/YYYY (X de Y dias usados)'`. → `acao='cobranca'`.
     - **B — Parcela do ciclo já paga, valor_proporcional < valor_parcela:** gera título `tipo='ajuste'` com `valor=-(valor_parcela - valor_proporcional)` (negativo, representa crédito), `data_vencimento=data_interrupcao`, observação explicativa. → `acao='credito'`. Crédito fica pendente de processamento manual (futuro: aplicar em próximo contrato do cliente OU emitir reembolso).
     - **C — `valor_proporcional == valor_parcela`** (interrompeu no exato vencimento): `acao='pulado'`, nada muda.
6. **Persistência atômica:** todas as alterações (cancelar título original, criar novo título, audit log) em **uma transação SQLAlchemy**.

### Configurações novas

7. Adicionar 3 entradas no seed de `config.configuracoes_sistema` (módulo `financeiro`, Story 13.4):

| slug | tipo | default | descrição |
|---|---|---|---|
| `cobrar_proporcional_ao_suspender` | booleano | `true` | Gera boleto proporcional quando contrato é suspenso |
| `cobrar_proporcional_ao_cancelar` | booleano | `true` | Gera boleto proporcional quando contrato é cancelado |
| `dia_base_calculo_proporcional` | string | `data_vencimento_anterior` | Base do ciclo: `data_pagamento` ou `data_vencimento_anterior` |

### Integração com hooks

8. Hook `quando_contrato_suspenso` (Story 13.2) chama `ServicoBoletoProporcional.gerar(contrato_id, hoje, motivo, tipo_interrupcao='suspensao')`.
9. Hook `quando_contrato_encerrado` (handlers de rescisão manual + Story 13.8 encerramento automático) chama `ServicoBoletoProporcional.gerar(..., tipo_interrupcao='cancelamento')`.

### Audit

10. Cada chamada de `gerar` produz audit log com `categoria='financeiro'` contendo:
    - `contrato_id`, `data_interrupcao`, `tipo_interrupcao`, `motivo`
    - `dias_usados`, `dias_totais_ciclo`, `valor_parcela`, `valor_proporcional`
    - `acao` resultante, `titulo_id_cancelado` (se A), `titulo_id_criado` (se A ou B)

### Testes

11. Testes de domínio (funções puras):
    - `calcular_valor_proporcional` — 10 casos cobrindo arredondamento, edge cases, valores negativos.
    - `calcular_dias_ciclo` — semanal (7), mensal (28/29/30/31 em meses diferentes), personalizado_dias (15, 30, 45).
12. Testes de application service:
    - Cenário A: parcela em aberto, cancela e cria proporcional — verifica valores e transação atômica.
    - Cenário B: parcela paga, gera crédito — verifica valor negativo correto.
    - Cenário C: interrupção exata no vencimento, nada muda.
    - Config `cobrar_proporcional_ao_suspender=false` — pulado.
    - Config `dia_base_calculo_proporcional=data_pagamento` — usa data correta.
    - Audit log gerado com todos os campos.
13. Testes de integração:
    - Suspender contrato (via `ServicoSituacaoContrato`) → boleto proporcional automaticamente criado via hook.
    - Cancelar contrato manualmente → mesmo comportamento.

## Contexto Técnico

### Resumo arquitetural

```
ServicoSituacaoContrato.transicionar(contrato_id, nova_situacao='suspenso')
  → persist status mudou
  → publica EventoContratoSuspenso
       ↓
  → handler quando_contrato_suspenso (Story 13.2)
       ↓
  → ServicoBoletoProporcional.gerar(...) ← ESTA STORY
       ↓
  → atomic: cancel parcela cheia + insert título proporcional + audit
```

### Decisão sobre `data_inicio_ciclo`

A config `dia_base_calculo_proporcional` permite escolher entre duas abordagens:
- **`data_vencimento_anterior`** (default) — modelo de "ciclo financeiro" (pré-pago). Mais comum em locação. Cliente paga na quarta, ciclo vai de quarta a próxima quarta.
- **`data_pagamento`** — modelo de "ciclo de uso" (pós-pago). Cliente paga retroativo. Cliente que pagou atrasado tem ciclo deslocado.

Para a maioria dos casos do FrotaUber (rent-to-own), `data_vencimento_anterior` é o correto.

### Tipo do título proporcional

Cenário A → `tipo='taxa'` (e não `parcela`) porque:
- Não é parte do plano de parcelamento.
- Não conta para `numero_parcela`/`total_parcelas`.
- Saldo devedor (FR-CORE-CR-3) já ignora `tipo != 'parcela'` em alguns cálculos — verificar e ajustar se necessário.

Cenário B → `tipo='ajuste'` com valor negativo. Não é "título a receber" no sentido tradicional — é registro contábil de crédito. UI deve renderizar com formatação distinta (cor verde, prefixo "Crédito de").

### Tabela de títulos — campo `parent_titulo_id`

Já existe no modelo? Verificar `src/backend-api/app/infrastructure/db/models/financeiro.py`. Se não existir, esta story deve adicionar (migration). Já é mencionado em outras stories (13.9 — pagamento parcial separado).

### Idempotência

Repetir a chamada `gerar()` com mesmo `contrato_id` + `data_interrupcao` deve ser **no-op** se o título proporcional já foi gerado para aquele ciclo. Implementação: verificar existência de título com `parent_titulo_id=titulo_original.id` antes de criar.

## Arquivos a Criar/Modificar

```
src/backend-api/
├── alembic/versions/0030_parent_titulo_id_e_seed_proporcional.py   # CRIAR (se parent_titulo_id não existe + seed das 3 configs)
├── app/domain/finance/
│   └── boleto_proporcional.py                                       # CRIAR — funções puras
├── app/application/services/
│   └── servico_boleto_proporcional.py                              # CRIAR
├── app/application/hooks/
│   ├── quando_contrato_suspenso.py                                 # MODIFICAR — chamar serviço
│   └── quando_contrato_encerrado.py                                # MODIFICAR — chamar serviço
├── app/cli/seed.py                                                  # MODIFICAR — 3 configs novas
└── app/tests/test_boleto_proporcional.py                           # CRIAR — 20+ testes
```

## Checklist do Dev

- [ ] 13.2 (máquina de estados — hooks `quando_contrato_suspenso/encerrado`) `done` ou em paralelo.
- [ ] 13.3 (`tipo_titulo` enum com `taxa` e `ajuste`) `done`.
- [ ] 13.4 (`ServicoConfiguracao`) `done`.
- [ ] 13.16 (wizard com `valor_parcela`, `tipo_intervalo`, sub-campos) `done` — o serviço lê esses campos.
- [ ] Funções puras 100% testadas (sem mocks, sem DB).
- [ ] 3 cenários (A, B, C) cobertos por testes de application service.
- [ ] Idempotência testada (chamar `gerar()` 2× não duplica).
- [ ] Audit log persistido com todos os campos da AC 10.
- [ ] Migration aplicada (com `parent_titulo_id` se ausente).
- [ ] Seed das 3 configs novas.
- [ ] Cobertura ≥ 70% no diretório `application/services/servico_boleto_proporcional.py`.

## Notas

- **Posição no épico:** entra **depois** das stories 13.2 (hooks), 13.3 (tipos), 13.4 (config), 13.16 (campos do contrato) — todas pré-requisito. **Antes** de 13.15 (UI de configurações) — UI precisa conhecer os 3 parâmetros novos pra exibir.
- **Sequência atualizada do épico:** `13.1 → 13.4 → 13.2 → 13.3 → 13.5 → 13.10 → 13.6 → 13.7 → 13.8 → 13.9 → 13.16 → 13.17 → 13.11 → 13.13 → 13.12 → 13.14 → 13.15`.
- **FR de referência:** FR-CORE-CTR-11 (PRD v3.1).
- **Considerações futuras (não nesta story):**
  - Aplicação automática de crédito (Cenário B) em próximo contrato do mesmo cliente — story própria.
  - UI no detalhe do cliente mostrando saldo de crédito disponível.
  - Política de expiração de créditos (90 dias?).
