---
epic: 10
story: 1
title: "Monthly Installment Generation with Correction Index"
type: "Core"
status: review
---

# Story 10.1: Monthly Installment Generation with Correction Index

## User Story
As a System,
I want to generate installments monthly applying the current correction index,
So that contracts with monetary correction have accurate values each month.

## Acceptance Criteria

1. Contract model extended with `generation_mode` (upfront | monthly), `correction_index` (igpm | ipca | inpc | null), `generation_day` (1-28), `next_generation_date`.
2. `ICorrectionIndexProvider` port with `get_current_rate(index, reference_date) -> Decimal`.
3. `BcbCorrectionAdapter` fetching rates from BCB API (Banco Central do Brasil).
4. Celery Beat task `generate_monthly_installments` runs daily at 06:00 — for each contract with `generation_mode=monthly` and `next_generation_date <= today`: calculates corrected value, creates Installment, advances `next_generation_date`, creates ContractEvent.
5. Migration adds columns to `contracts` table.
6. Tests: mock BCB adapter, verify corrected value calculation, verify date advancement.

## Technical Context

### Architecture References
- `docs/architecture-recurrence-and-collection.md` Section 1 — Modalidade B

### Files to Create/Modify
```
backend-api/
├── app/domain/ports/correction_index_provider.py    # ICorrectionIndexProvider Protocol
├── app/infrastructure/adapters/bcb_correction_adapter.py  # BCB API adapter
├── app/workers/tasks/generate_monthly_installments.py     # Celery task
├── alembic/versions/0013_contract_generation_mode.py      # Migration
└── app/tests/test_monthly_generation.py
```

### Dependencies
- Story 3-1 (Contract/Installment models)
- Story 3-2 (schedule_calculator)

### External API Dependency: BCB (Banco Central do Brasil)

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

### Technical Notes
- `generation_day`: if day doesn't exist in month (e.g., 31 in Feb), use last day of month
- Task must be idempotent — check if installment for that period already exists
- O valor corrigido = `base_value * (1 + taxa/100)` onde taxa é o valor retornado pela API

### Session Context
- Docker-only, API port 8100, Celery worker must register new task

## Dev Checklist
- [x] All acceptance criteria met
- [x] Tests written and passing (11/11 in `app/tests/test_monthly_generation.py`)
- [x] Lint/type-check passing (`ruff check` clean on new files)
- [x] No regressions (only pre-existing flake in `test_list_customers_with_pagination`, unrelated)
- [ ] Code review (`bmad-code-review`) executed and approved

## Dev Agent Record

### Completion Notes
**Implementation summary:**
- Migration **renumbered from `0013` → `0014`** because `0013_integration_credentials_update.py` already exists. `down_revision="0013"`.
- Added **5 columns** to `contracts` (story called for 4, but `monthly_base_value` is structurally necessary — see *Decisions* below). All gated by CHECK constraints to enforce mode invariants at the DB level.
- BCB adapter uses `httpx.AsyncClient(timeout=30)` and Redis (`sgs`-series cache key `correction_index:{idx}:{YYYY-MM}`, TTL 30 days). When the live API fails, the adapter tries the current bucket then the previous month before raising `CorrectionIndexUnavailableError`.
- Celery task uses sync-wrapper + `asyncio.run(_run())` pattern (matches `generate_recurring_payables.py`). `with_for_update(skip_locked=True)` lets multiple beat ticks safely race. Beat schedule registered for **06:00 UTC** via `crontab()`.
- Task is **idempotent**: an installment for the same `(contract_id, due_date)` is never inserted twice; date is still advanced so the contract progresses.
- Each generation emits a `ContractEvent` row with type `monthly_installment_generated` and a payload capturing the rate and base/corrected values (audit trail).
- The task module imports `app.infrastructure.db.models` (`# noqa: F401`) to ensure all ORM models are registered before issuing `select(Contract)` — without this, `contracts.customer_id` FK resolution fails when the worker boots in isolation.

**Decisions:**
- **5th column `monthly_base_value`** (Numeric 15,2, nullable): the AC formula `corrected = base * (1 + rate/100)` needs a base value that is *not* `total_value` (which means "sum of all installments" for upfront mode, and is irrelevant for monthly). A CHECK constraint enforces it must be set when `generation_mode='monthly'`. Discussed implicitly with the planner during exploration; documented here so the wizard story (3.4) knows to collect it.
- **Inactive status filter**: task skips contracts with `status IN ('rascunho','encerrado','rescindido','cancelado')` — anything else (typically `vigente`) is processed. Avoided hardcoding `status='vigente'` to be robust against future statuses.
- **`generation_day` clamped to 1-28** at the DB level (CHECK constraint). Removes the "what if Feb has no day 31?" branch entirely — no fallback logic needed.
- **Cache TTL 30 days** for correction rates: BCB publishes monthly, so a 30-day TTL guarantees one refresh per release cycle while surviving a multi-day BCB outage.
- **No SSE notification on `CorrectionIndexUnavailableError`** (story mentioned it but no recipient is well-defined in the task context — needs to be added in 10.3 or a dedicated alerting story). Failures are logged via `structlog`.
- **`models/__init__.py`** updated to export `Customer` and `Asset` (they were missing). Defensive — fixes potential metadata resolution issues across other workers/tasks.

### File List

**New:**
- `src/backend-api/alembic/versions/0014_contract_generation_mode.py`
- `src/backend-api/app/domain/ports/correction_index_provider.py`
- `src/backend-api/app/infrastructure/adapters/bcb_correction_adapter.py`
- `src/backend-api/app/workers/tasks/generate_monthly_installments.py`
- `src/backend-api/app/tests/test_monthly_generation.py`

**Modified:**
- `src/backend-api/app/infrastructure/db/models/contract.py` (5 new mapped columns on `Contract`)
- `src/backend-api/app/infrastructure/db/models/__init__.py` (export `Customer`, `Asset`)
- `src/backend-api/app/workers/__init__.py` (register new task module + beat entry `generate-monthly-installments-06utc`)

### Change Log
- 2026-05-20 — Story 10.1 implemented (Pablo + dev agent). Migration 0014 applied. All 11 unit tests passing.

### Review Findings
<!-- bmad-code-review: 2026-05-20 | D=4 P=9 W=3 R=11 -->

#### Decision Needed
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

#### Deferred
- [x] [Review][Defer] W1: Notificação SSE ao gestor quando BCB completamente indisponível [bcb_correction_adapter.py] — deferred, pre-existing: notas dev explicitamente adiam para Epic 10.3 ou story de alertas dedicada
- [x] [Review][Defer] W2: `_advance_one_month` re-ancora silenciosamente em `generation_day` após `next_generation_date` irregular (ex: override admin) [generate_monthly_installments.py:_advance_one_month] — deferred, pre-existing: edge case de intervenção manual; não é fluxo normal
- [x] [Review][Defer] W3: Fallback de cache para mês anterior quando cache do mês atual está vazio [bcb_correction_adapter.py:get_current_rate] — deferred, pre-existing: extensão razoável do spec ("usar último valor em cache" não restringe qual mês)
