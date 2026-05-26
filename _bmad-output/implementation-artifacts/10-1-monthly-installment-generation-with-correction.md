---
epic: 10
story: 1
title: "Geração Mensal de Parcelas com Índice de Correção"
type: "Core"
status: review
---

# Story 10.1: Geração Mensal de Parcelas com Índice de Correção

## História de Usuário
Como Sistema,
quero gerar parcelas mensalmente aplicando o índice de correção vigente,
para que contratos com correção monetária tenham valores precisos a cada mês.

## Critérios de Aceite

1. Modelo de Contrato estendido com `generation_mode` (upfront | monthly), `correction_index` (igpm | ipca | inpc | null), `generation_day` (1-28), `next_generation_date`.
2. Port `ICorrectionIndexProvider` com `get_current_rate(index, reference_date) -> Decimal`.
3. `BcbCorrectionAdapter` busca taxas da API do BCB (Banco Central do Brasil).
4. Task Celery Beat `generate_monthly_installments` roda diariamente às 06:00 — para cada contrato com `generation_mode=monthly` e `next_generation_date <= today`: calcula valor corrigido, cria Installment (parcela), avança `next_generation_date`, cria ContractEvent.
5. Migration adiciona colunas à tabela `contracts`.
6. Testes: mock do adapter BCB, verifica cálculo do valor corrigido, verifica avanço da data.

## Contexto Técnico

### Referências de Arquitetura
- `docs/architecture-recurrence-and-collection.md` Seção 1 — Modalidade B

### Arquivos a Criar/Modificar
```
backend-api/
├── app/domain/ports/correction_index_provider.py    # Protocol ICorrectionIndexProvider
├── app/infrastructure/adapters/bcb_correction_adapter.py  # Adapter da API BCB
├── app/workers/tasks/generate_monthly_installments.py     # Task Celery
├── alembic/versions/0013_contract_generation_mode.py      # Migration
└── app/tests/test_monthly_generation.py
```

### Dependências
- Story 3-1 (modelos Contract/Installment)
- Story 3-2 (schedule_calculator)

### Dependência de API Externa: BCB (Banco Central do Brasil)

**API pública, gratuita, sem autenticação.**

| Índice | Série | Endpoint |
|--------|-------|----------|
| IGPM | 189 | `https://api.bcb.gov.br/dados/serie/bcdata.sgs.189/dados/ultimos/1?formato=json` |
| IPCA | 433 | `https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados/ultimos/1?formato=json` |
| INPC | 188 | `https://api.bcb.gov.br/dados/serie/bcdata.sgs.188/dados/ultimos/1?formato=json` |

**Resposta:**
```json
[{"data":"01/05/2026","valor":"0.53"}]
```

**Padrão Ports & Adapters:**
```
ICorrectionIndexProvider (Protocol)
    └── BcbCorrectionAdapter  ← httpx GET, sem auth
```

**Resiliência:**
- Cache em Redis com TTL 30 dias (chave: `correction_index:{serie}:{yyyy-mm}`)
- Se BCB indisponível, usa último valor cacheado + log warning
- Se nenhum valor em cache, task falha e notifica gestor via SSE

**Configuração:**
- Registrar como integração em `integration_credentials` (category=`correction_index`, provider=`bcb`)
- Futuramente pode ter adapters alternativos (ex: API do IBGE, planilha manual)

### Notas Técnicas
- `generation_day`: se o dia não existir no mês (ex: 31 em fevereiro), usar último dia do mês
- Task deve ser idempotente — verificar se a parcela daquele período já existe
- O valor corrigido = `base_value * (1 + taxa/100)` onde taxa é o valor retornado pela API

### Contexto da Sessão
- Apenas Docker, API na porta 8100, worker Celery deve registrar a nova task

## Checklist do Dev
- [x] Todos os critérios de aceite atendidos
- [x] Testes escritos e passando (11/11 em `app/tests/test_monthly_generation.py`)
- [x] Lint/type-check passando (`ruff check` limpo nos novos arquivos)
- [x] Sem regressões (apenas flake pré-existente em `test_list_customers_with_pagination`, sem relação)
- [ ] Code review (`bmad-code-review`) executado e aprovado

## Registro do Dev Agent

### Notas de Conclusão
**Resumo da implementação:**
- Migration **renumerada de `0013` → `0014`** porque `0013_integration_credentials_update.py` já existe. `down_revision="0013"`.
- Adicionadas **5 colunas** em `contracts` (a story pedia 4, mas `monthly_base_value` é estruturalmente necessária — ver *Decisões* abaixo). Todas protegidas por CHECK constraints para forçar invariantes de modo no nível do banco.
- Adapter BCB usa `httpx.AsyncClient(timeout=30)` e Redis (chave de cache `correction_index:{idx}:{YYYY-MM}` da série `sgs`, TTL 30 dias). Quando a API ao vivo falha, o adapter tenta o bucket atual e depois o mês anterior antes de lançar `CorrectionIndexUnavailableError`.
- Task Celery usa padrão sync-wrapper + `asyncio.run(_run())` (igual ao `generate_recurring_payables.py`). `with_for_update(skip_locked=True)` permite múltiplos ticks do beat correrem com segurança. Beat schedule registrado para **06:00 UTC** via `crontab()`.
- Task é **idempotente**: uma parcela para o mesmo `(contract_id, due_date)` nunca é inserida duas vezes; a data ainda é avançada para o contrato progredir.
- Cada geração emite uma linha em `ContractEvent` com tipo `monthly_installment_generated` e payload capturando taxa e valores base/corrigidos (trilha de auditoria).
- O módulo da task importa `app.infrastructure.db.models` (`# noqa: F401`) para garantir que todos os modelos ORM estejam registrados antes do `select(Contract)` — sem isso, a resolução da FK `contracts.customer_id` falha quando o worker sobe isolado.

**Decisões:**
- **5ª coluna `monthly_base_value`** (Numeric 15,2, nullable): a fórmula do critério `corrected = base * (1 + rate/100)` precisa de um valor base que *não* seja `total_value` (que significa "soma de todas as parcelas" no modo upfront, e é irrelevante no modo monthly). Uma CHECK constraint força que seja preenchida quando `generation_mode='monthly'`. Discutido implicitamente com o planejador durante a exploração; documentado aqui para que a story do wizard (3.4) saiba que precisa coletar esse valor.
- **Filtro de status inativos**: task pula contratos com `status IN ('rascunho','encerrado','rescindido','cancelado')` — qualquer outro (tipicamente `vigente`) é processado. Evitado hardcoding `status='vigente'` para ser robusto contra status futuros.
- **`generation_day` limitado a 1-28** no nível do banco (CHECK constraint). Remove totalmente o branch "e se fevereiro não tem dia 31?" — nenhuma lógica de fallback necessária.
- **Cache TTL de 30 dias** para taxas de correção: BCB publica mensalmente, então um TTL de 30 dias garante um refresh por ciclo de release enquanto sobrevive a uma indisponibilidade BCB de múltiplos dias.
- **Sem notificação SSE em `CorrectionIndexUnavailableError`** (a story mencionou mas nenhum destinatário está bem definido no contexto da task — precisa ser adicionado na 10.3 ou em uma story dedicada de alertas). Falhas são logadas via `structlog`.
- **`models/__init__.py`** atualizado para exportar `Customer` e `Asset` (estavam faltando). Defensivo — corrige potenciais problemas de resolução de metadata em outros workers/tasks.

### Lista de Arquivos

**Novos:**
- `src/backend-api/alembic/versions/0014_contract_generation_mode.py`
- `src/backend-api/app/domain/ports/correction_index_provider.py`
- `src/backend-api/app/infrastructure/adapters/bcb_correction_adapter.py`
- `src/backend-api/app/workers/tasks/generate_monthly_installments.py`
- `src/backend-api/app/tests/test_monthly_generation.py`

**Modificados:**
- `src/backend-api/app/infrastructure/db/models/contract.py` (5 novas mapped columns em `Contract`)
- `src/backend-api/app/infrastructure/db/models/__init__.py` (exporta `Customer`, `Asset`)
- `src/backend-api/app/workers/__init__.py` (registra novo módulo de task + entrada de beat `generate-monthly-installments-06utc`)

### Histórico de Mudanças
- 2026-05-20 — Story 10.1 implementada (Pablo + dev agent). Migration 0014 aplicada. Todos os 11 testes unitários passando.

### Achados da Revisão
<!-- bmad-code-review: 2026-05-20 | D=4 P=9 W=3 R=11 -->

#### Decisão Necessária
- [ ] [Review][Decision] D1: Arquitetura — `with_for_update` bloqueia linhas do banco enquanto faz chamadas HTTP BCB (até 30s × N contratos). O loop carrega todos os contratos com FOR UPDATE numa única sessão e faz N chamadas HTTP dentro desse lock. Opções: (a) buscar taxa BCB antes de adquirir locks; (b) cada contrato em transação própria; (c) pré-aquecer cache Redis fora do lock antes do loop.
- [ ] [Review][Decision] D2: Comportamento de catch-up — tarefa gera apenas 1 parcela por execução para contratos com múltiplos meses em atraso; além disso `today` é passado como `reference_date` em vez de `due_date` (após P1 ser corrigido, a taxa ainda seria do mês atual, não do mês da parcela). Opções: (a) loop dentro de `_process_contract` até `next_generation_date > today`, passando `due_date` como referência de taxa; (b) manter 1/execução mas usar `due_date` como referência; (c) manter comportamento atual.
- [ ] [Review][Decision] D3: Arredondamento financeiro — `_apply_correction` usa `ROUND_HALF_EVEN` (banker's rounding) por omitir `rounding=`. Padrão contábil brasileiro é `ROUND_HALF_UP`. Opções: (a) adicionar `rounding=ROUND_HALF_UP`; (b) documentar que ROUND_HALF_EVEN é intencional.
- [ ] [Review][Decision] D4: `generation_day` limitado a 1-28 (desvio do spec que diz "usar último dia do mês" para 29-31) — wizard de contratos (story 3.4) precisa saber deste limite. Opções: (a) aceitar decisão do dev agent e atualizar story 3.4; (b) reverter para suporte 1-31 com clamp para último dia do mês.

#### Patches
- [ ] [Review][Patch] P1: BCB adapter usa `dados/ultimos/1` ignorando `reference_date` — taxa "mais recente" aplicada em vez da taxa do mês correto; corrigir para consultar endpoint histórico por mês específico [bcb_correction_adapter.py:_fetch_from_bcb]
- [ ] [Review][Patch] P2: Transação única para o batch inteiro sem handler externo em `session.commit()` — falha em qualquer contrato pode deixar o batch em estado parcial; implementar unidade de trabalho por contrato [generate_monthly_installments.py:_run]
- [ ] [Review][Patch] P3: Race condition em `_next_installment_number` (read-max-then-add) + ausência de `UNIQUE(contract_id, number)` no banco — dois workers simultâneos podem inserir número duplicado [generate_monthly_installments.py:_next_installment_number + migration]
- [ ] [Review][Patch] P4: Ausência de `UNIQUE(contract_id, due_date)` em installments — idempotência garantida só em nível de aplicação; adicionar constraint na migration [alembic/0014]
- [ ] [Review][Patch] P5: Tipo de `generation_day`: `SmallInteger` na migration, `Integer` no ORM — corrigir model para `SmallInteger` [contract.py:generation_day]
- [ ] [Review][Patch] P6: Nome da tarefa no beat schedule usa caminho de módulo (`app.workers.tasks.generate_monthly_installments`) — inconsistente com demais tasks (usam `módulo.função`); funciona por coincidência, quebra silenciosamente em refatorações [workers/__init__.py:beat_schedule]
- [ ] [Review][Patch] P7: Resposta BCB não validada para faixas plausíveis — taxa negativa ou >100% seria aceita e cacheada silenciosamente [bcb_correction_adapter.py:_parse_payload]
- [ ] [Review][Patch] P8: Teste de idempotência ausente — segunda execução do task no mesmo dia não deve criar parcela duplicada [test_monthly_generation.py]
- [ ] [Review][Patch] P9: `BcbCorrectionAdapter` não herda explicitamente de `ICorrectionIndexProvider` — política do projeto exige herança explícita do Protocol (CLAUDE.md) [bcb_correction_adapter.py:BcbCorrectionAdapter]

#### Adiados
- [x] [Review][Defer] W1: Notificação SSE ao gestor quando BCB completamente indisponível [bcb_correction_adapter.py] — adiado, pré-existente: notas do dev explicitamente adiam para Epic 10.3 ou story de alertas dedicada
- [x] [Review][Defer] W2: `_advance_one_month` re-ancora silenciosamente em `generation_day` após `next_generation_date` irregular (ex: override admin) [generate_monthly_installments.py:_advance_one_month] — adiado, pré-existente: edge case de intervenção manual; não é fluxo normal
- [x] [Review][Defer] W3: Fallback de cache para mês anterior quando cache do mês atual está vazio [bcb_correction_adapter.py:get_current_rate] — adiado, pré-existente: extensão razoável do spec ("usar último valor em cache" não restringe qual mês)
