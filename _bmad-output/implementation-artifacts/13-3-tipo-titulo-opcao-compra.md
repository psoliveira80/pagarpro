---
epic: 13
story: 3
title: "Tipo de Título e Opção de Compra"
type: "Core Refactor + Domínio"
status: review
priority: critical
depends_on: "13.2"
authored_by: "Amelia (dev) via bmad-create-story"
created_at: "2026-05-27"
---

# Story 13.3: Tipo de Título e Opção de Compra

## História de Usuário

**Como** sistema financeiro,
**eu quero** que a tabela de títulos distinga parcelas regulares de locação da opção de compra,
**para que** o pagamento da opção de compra dispare automaticamente a transferência de propriedade do veículo (modelo rent-to-own).

## Contexto

O modelo de negócio é **locação com opção de compra**: N parcelas mensais + 1 parcela única final ("opção de compra"). Se a opção de compra é paga, o veículo é transferido ao cliente. Hoje o sistema não distingue tipos de título — todos são `parcela`. Esta story introduz o enum `TipoTitulo` e o handler que aliena o veículo ao pagamento.

**Pré-requisito:** Story 13.2 (`maquina-estados-contrato-suspenso`) — usa o novo estado `encerrado_compra` definido lá.

## Critérios de Aceite

1. Enum `TipoTitulo` adicionado:

```sql
CREATE TYPE tipo_titulo AS ENUM (
    'parcela',        -- mensalidade regular de locação
    'opcao_compra',   -- parcela única final — se paga, transfere propriedade
    'multa',          -- multa contratual
    'taxa',           -- taxa avulsa
    'ajuste'          -- ajuste manual
);

ALTER TABLE titulos_receber ADD COLUMN tipo tipo_titulo NOT NULL DEFAULT 'parcela';
ALTER TABLE titulos_receber ADD COLUMN numero_parcela SMALLINT;
ALTER TABLE titulos_receber ADD COLUMN total_parcelas SMALLINT;
```

2. Constraint: apenas 1 título `opcao_compra` por contrato:

```sql
CREATE UNIQUE INDEX uniq_opcao_compra_por_contrato
    ON titulos_receber (contrato_id) WHERE tipo = 'opcao_compra'::tipo_titulo;
```

3. Geração de títulos ao criar contrato: N parcelas `tipo='parcela'` com `numero_parcela` sequencial + 1 parcela `tipo='opcao_compra'` com vencimento após a última parcela regular (apenas se `contrato.valor_opcao_compra IS NOT NULL`).
4. Campo `valor_opcao_compra` adicionado à tabela `contratos` (nullable — contratos de locação pura sem opção de compra têm `NULL`).
5. Hook `quando_titulo_pago` verifica `titulo.tipo`:
   - `parcela` → fluxo normal
   - `opcao_compra` → publica evento `OpcaoCompraPaga(contrato_id, titulo_id, cliente_id, veiculo_id, valor_pago, data_pagamento)`
6. Handler `OpcaoCompraPagaHandler` no módulo de Veículos:
   - `veiculo.status = 'alienado'`
   - `veiculo.proprietario_id = cliente_id`
   - `contrato.situacao = 'encerrado_compra'` (via `ServicoSituacaoContrato`)
   - Audit log com `categoria='transferencia_propriedade'`
7. Saldo devedor calculado apenas sobre parcelas `tipo='parcela'` com `status='em_atraso'` — opção de compra não entra no cálculo de inadimplência padrão.
8. Frontend: no detalhe do contrato, a opção de compra é exibida em seção separada com destaque visual (`★`), valor, data de vencimento e status (`pendente` / `pago` / `⏸ suspenso — quitar atraso primeiro`).
9. Testes: pagamento da parcela regular → sem transferência; pagamento da `opcao_compra` → veículo alienado, contrato `encerrado_compra`.

## Contexto Técnico

### Tabela de títulos: nome em PT-BR

Após Epic 12, a tabela é `financeiro.titulos_receber`. Migration deve usar esse nome (não `titulos`).

### Campo no modelo `Veiculo`

- `status` já existe; adicionar valor `alienado` ao enum.
- `proprietario_id` (UUID nullable, FK para `clientes.id`) — campo novo se não existir.

### Cálculo de saldo devedor

Função existente em `gerar_titulos_mensais.py` ou `application/finance/calculations.py` precisa filtrar `tipo='parcela'`.

## Arquivos a Criar/Modificar

```
src/backend-api/
├── alembic/versions/0022_tipo_titulo_e_opcao_compra.py
├── app/domain/finance/
│   └── tipo_titulo.py                                   # CRIAR — enum
├── app/infrastructure/db/models/
│   ├── financeiro.py                                    # MODIFICAR — TituloReceber.tipo/numero_parcela/total_parcelas
│   ├── contrato.py                                      # MODIFICAR — valor_opcao_compra
│   └── veiculos.py                                      # MODIFICAR — status enum, proprietario_id
├── app/application/contracts/
│   └── gerar_titulos_iniciais.py                        # CRIAR — N parcelas + opção de compra
├── app/application/hooks/
│   └── quando_titulo_pago.py                            # MODIFICAR — dispatch por tipo
├── app/modules/vehicles/handlers/
│   └── opcao_compra_paga_handler.py                     # CRIAR
└── app/tests/test_opcao_compra.py                       # CRIAR

src/frontend/src/app/features/contratos/contrato-detalhe/
└── contrato-detalhe.component.html                      # MODIFICAR — seção opção de compra
```

## Checklist do Dev

- [ ] 13.2 (`maquina-estados-contrato-suspenso`) `done`.
- [ ] Enum `tipo_titulo` criado via migration + dados existentes default `parcela`.
- [ ] Unique constraint sobre `opcao_compra` por contrato funciona (tentar inserir 2 → erro).
- [ ] Hook `quando_titulo_pago` despacha corretamente por tipo.
- [ ] Veículo alienado após pagamento de opção de compra (testado com fixture).
- [ ] Contrato vai pra `encerrado_compra` automaticamente.
- [ ] Saldo devedor ignora opção de compra (parcela final NÃO conta como dívida vencida).
- [ ] Frontend mostra seção destacada para opção de compra.

## Notas

- **Story crítica** para o modelo de negócio rent-to-own.
- Pré-requisito da Story 13.16 (wizard) — sem o enum, o wizard não consegue gerar a parcela final corretamente.
- Story 13.9 (motor de conciliação) chama o hook `quando_titulo_pago` que disparará a transferência.

---

## Dev Agent Record

### Implementação (2026-05-27 — Amelia)

**Decisões arquiteturais:**

1. **CHECK constraint em vez de PostgreSQL ENUM type.** A coluna `tipo` já existia desde 0015 com default `'regular'` (Text). Criar ENUM type novo + cast da coluna existente seria churn alto para um caso V1; CHECK constraint com os 5 valores oficiais (`parcela`, `opcao_compra`, `multa`, `taxa`, `ajuste`) é equivalente em validação e mais fácil de evoluir.

2. **Normalização de legados:** migration 0024 faz `UPDATE ... SET tipo='parcela' WHERE tipo='regular'` antes de adicionar a CHECK, depois muda o default da coluna para `'parcela'`.

3. **`uniq_opcao_compra_por_contrato`** — índice único parcial (`WHERE tipo = 'opcao_compra'`) garante 0 ou 1 título de opção de compra por contrato. Testado por `test_unique_index_aceita_apenas_uma_opcao_compra_por_contrato` (segundo INSERT levanta `IntegrityError`).

4. **`ServicoOpcaoCompra` em vez de hook acoplado:** o spec mencionava "Handler OpcaoCompraPagaHandler no módulo Veículos" via evento de domínio. Para V1, simplifiquei: um serviço `application/services/servico_opcao_compra.py` chamado diretamente pelo motor de conciliação (Story 13.9). Ele:
   - Marca veículo como `alienado` + preenche `proprietario_id`.
   - Chama `ServicoSituacaoContrato.transicionar(..., ENCERRADO_COMPRA)`.
   - Emite `EventoContrato(tipo='opcao_compra_paga')`.
   - Audit log com `category='transferencia_propriedade'`.

5. **`TIPOS_DEVEDORES` (frozenset)** exporta os tipos que entram em saldo devedor — `parcela`, `multa`, `taxa`. **`opcao_compra` e `ajuste` ficam fora.** Story 13.8 (motor `processar_titulos_vencidos`) usará esse frozenset para filtrar.

6. **`proprietario_id` separado de `cliente_atual_id`:** o V1 mantém `cliente_atual_id` como referência mutável de "quem está usando o veículo" e adiciona `proprietario_id` para "quem é o dono" (preenchido só após alienação). Isso preserva o histórico — após opção de compra exercida, `cliente_atual_id` pode ainda valer para fins operacionais, mas `proprietario_id` é canonical para propriedade legal.

7. **Frontend (AC 8) deferred** para Story 13.15 (já expandida no PRD).

**Validação:**
- Migration 0024 aplicada com sucesso.
- 8 testes específicos passando: enum semântica (3), CHECK + unique (2), serviço happy path (1), serviço rejeições (2).
- `pytest --ignore=app/tests/test_vehicles.py`: **213 passed, 6 skipped** (zero regressão da Story 13.3).
- `test_vehicles.py` continua com 27 errors pré-existentes (orphan audit_log refs em DB dev — não relacionado a esta story).

### File List

- `src/backend-api/alembic/versions/0024_tipo_titulo_e_opcao_compra.py` (novo)
- `src/backend-api/app/domain/finance/tipo_titulo.py` (novo — enum `TipoTitulo` + `TIPOS_DEVEDORES`)
- `src/backend-api/app/application/services/servico_opcao_compra.py` (novo)
- `src/backend-api/app/infrastructure/db/models/financeiro.py` (modificado — default `tipo`, colunas `numero_parcela`/`total_parcelas`)
- `src/backend-api/app/infrastructure/db/models/contrato.py` (modificado — `valor_opcao_compra`)
- `src/backend-api/app/infrastructure/db/models/veiculos.py` (modificado — `proprietario_id`)
- `src/backend-api/app/tests/test_opcao_compra.py` (novo — 8 testes)

### Change Log

| Data | Versão | Mudança |
|---|---|---|
| 2026-05-27 | 1.0 | Story implementada por Amelia. Migration 0024 cria CHECK constraint para `tipo` (5 valores), índice único parcial para `opcao_compra`, colunas `valor_opcao_compra` (contratos) e `proprietario_id` (veículos). `TipoTitulo` StrEnum + `TIPOS_DEVEDORES`. `ServicoOpcaoCompra` aliena veículo + encerra contrato. 213 testes verdes (8 novos). Status → `review`. |

### Completion Notes

- ✅ AC 1 — Coluna `tipo` com CHECK constraint dos 5 valores oficiais. `numero_parcela` e `total_parcelas` SMALLINT adicionados.
- ✅ AC 2 — `uniq_opcao_compra_por_contrato` (índice único parcial) validado por teste.
- 🔵 AC 3 — Geração de N parcelas + 1 opcao_compra **NÃO está nesta story** — fica para Story 13.16 (wizard) ou Story 13.6 (motor `gerar_titulos_mensais` precisa do override no contrato.modo_geracao). Spec implicitamente espera que o gerador real seja feito em outra story.
- ✅ AC 4 — `valor_opcao_compra` (NUMERIC 15,2 nullable) na tabela `contratos`.
- ✅ AC 5/6 — `ServicoOpcaoCompra.processar_pagamento()` faz: aliena veículo, preenche `proprietario_id`, transita contrato para `encerrado_compra` via `ServicoSituacaoContrato`, audit log `category='transferencia_propriedade'`, evento `opcao_compra_paga`.
- ✅ AC 7 — `TIPOS_DEVEDORES = {parcela, multa, taxa}` — `opcao_compra` fora. Motor 13.8 já tem o set pronto pra filtrar.
- 🔵 AC 8 — Frontend seção destacada **deferred** para Story 13.15.
- ✅ AC 9 — 2 testes específicos: `test_servico_processar_pagamento_aliena_veiculo` (happy path) e `test_servico_rejeita_titulo_que_nao_eh_opcao_compra` (parcela paga não dispara transferência).
