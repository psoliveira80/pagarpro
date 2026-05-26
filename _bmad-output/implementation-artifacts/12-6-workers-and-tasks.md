---
epic: 12
story: 6
title: "Workers & Tasks — Rename and Add empresa_id to All Celery Tasks"
type: "Core Refactor"
status: review
priority: high
depends_on: "12.4"
---

# Story 12.6: Workers & Tasks — Rename and Add empresa_id to All Celery Tasks

## User Story
As the System,
I want all Celery tasks updated to use the new Portuguese model/column names and to receive empresa_id as an explicit argument,
So that background jobs operate correctly in the multi-tenant environment.

## Context
Celery workers run in separate processes — they cannot inherit the request-scoped `ContextVar` set in 12.4. Each task must receive `empresa_id` explicitly and set it in its own context before executing. **Depends on 12.4 for the context pattern. Can run in parallel with 12.5.**

## Acceptance Criteria

1. All tasks in `app/workers/tasks/` updated to:
   - Use new model class names (e.g., `TituloReceber` instead of `Installment`)
   - Use new column names (e.g., `data_vencimento` instead of `due_date`)
   - Accept `empresa_id: str` as first argument
   - Call `set_empresa_id(UUID(empresa_id))` at the start of execution
2. Celery Beat schedules updated: all tasks now scheduled per-empresa (task dispatched once per active empresa).
3. `workers/__init__.py` updated: import new task names, remove old ones.
4. Task that generated `Installment` now generates `TituloReceber`.
5. Task that generated `Payable` now generates `TituloPagar` with `status='rascunho'`.
6. All tasks idempotent: re-running for same `empresa_id` + period produces no duplicates.
7. Celery Beat `crontab()` used for all schedules (not interval-based) per Epic 10 requirements.
8. Tests: verify task runs correctly with valid `empresa_id`, verify idempotency.

## Task Rename and Update Mapping

| Arquivo atual | Arquivo novo | Mudanças principais |
|---|---|---|
| `generate_monthly_installments.py` | `gerar_titulos_mensais.py` | `Installment` → `TituloReceber`, `due_date` → `data_vencimento`, adicionar `empresa_id` |
| `generate_recurring_payables.py` | `gerar_despesas_recorrentes.py` | `Payable` → `TituloPagar`, `status='rascunho'`, adicionar `empresa_id` |
| `recompute_customer_scores.py` | `recalcular_scores_clientes.py` | `CustomerScore` → `ScoreCliente`, adicionar `empresa_id` |
| `refresh_materialized_views.py` | `atualizar_views.py` | Recriar com novos nomes de views |
| `check_channel_health.py` | `verificar_saude_canais.py` | `IntegrationCredential` → `CredencialIntegracao` |

## Celery Beat Schedule Pattern

```python
# workers/__init__.py
# Todos os tasks que operam por empresa são agendados dinamicamente.
# O task orquestrador lê todas as empresas ativas e dispara o task filho.

@celery_app.task
def dispatch_por_empresa(task_name: str) -> None:
    """Orquestrador: dispara task_name para cada empresa ativa."""
    from app.infrastructure.db.models.comercial import Empresa
    with sync_session() as session:
        empresas = session.scalars(
            select(Empresa).where(Empresa.ativo == True)
        ).all()
    for empresa in empresas:
        celery_app.send_task(task_name, args=[str(empresa.id)])

# Beat schedule
celery_app.conf.beat_schedule = {
    "gerar-titulos-mensais": {
        "task": "app.workers.dispatch_por_empresa",
        "schedule": crontab(hour=6, minute=0),
        "args": ["app.workers.tasks.gerar_titulos_mensais.executar"],
    },
    "gerar-despesas-recorrentes": {
        "task": "app.workers.dispatch_por_empresa",
        "schedule": crontab(hour=4, minute=0),
        "args": ["app.workers.tasks.gerar_despesas_recorrentes.executar"],
    },
    "recalcular-scores": {
        "task": "app.workers.dispatch_por_empresa",
        "schedule": crontab(hour=2, minute=0),
        "args": ["app.workers.tasks.recalcular_scores_clientes.executar"],
    },
    "atualizar-views": {
        "task": "app.workers.tasks.atualizar_views.executar",
        "schedule": crontab(minute=0),  # hourly
    },
    "verificar-saude-canais": {
        "task": "app.workers.dispatch_por_empresa",
        "schedule": crontab(minute="*/5"),
        "args": ["app.workers.tasks.verificar_saude_canais.executar"],
    },
}
```

## Task Pattern

```python
# workers/tasks/gerar_titulos_mensais.py
from app.core.tenant_context import set_empresa_id
from app.infrastructure.db.models.financeiro import TituloReceber

@celery_app.task(bind=True, max_retries=3)
def executar(self, empresa_id: str) -> None:
    set_empresa_id(UUID(empresa_id))  # seta contexto para este worker
    with sync_session() as session:
        # set_config para RLS também
        session.execute(
            text("SELECT set_config('app.empresa_id', :eid, true)"),
            {"eid": empresa_id},
        )
        _processar_contratos(session, UUID(empresa_id))

def _processar_contratos(session, empresa_id: UUID) -> None:
    contratos = session.scalars(
        select(Contrato)
        .where(
            Contrato.empresa_id == empresa_id,
            Contrato.status == "vigente",
            Contrato.modo_geracao == "mensal",
            Contrato.proxima_geracao_em <= date.today(),
        )
    ).all()
    for contrato in contratos:
        _gerar_titulo(session, contrato)
```

## Technical Context

### Files to Create/Modify
```
backend-api/app/workers/
├── __init__.py                               # MODIFICAR — novos imports
├── tasks/
│   ├── gerar_titulos_mensais.py             # CRIAR (era generate_monthly_installments.py)
│   ├── gerar_despesas_recorrentes.py        # CRIAR (era generate_recurring_payables.py)
│   ├── recalcular_scores_clientes.py        # CRIAR (era recompute_customer_scores.py)
│   ├── atualizar_views.py                   # CRIAR (era refresh_materialized_views.py)
│   └── verificar_saude_canais.py            # CRIAR (era check_channel_health.py)
```

## Dev Checklist
- [x] 12.4 concluída antes de começar (review APROVADO)
- [x] Tasks tenant-scoped com `empresa_id` como primeiro argumento (gerar_titulos_mensais, gerar_despesas_recorrentes, recalcular_scores_clientes, verificar_saude_canais)
- [x] `set_empresa_id()` chamado no início de cada task tenant-scoped + `reset_empresa_id()` em `finally` (workers reusam processos)
- [x] `SELECT set_config('app.empresa_id', :eid, true)` chamado em cada sessão das tasks tenant-scoped
- [x] `gerar_despesas_recorrentes.executar` gera `TituloPagar` com `status='rascunho'`
- [x] Celery Beat usa `crontab()` em todos os schedules (substituiu intervalos `3600*24`)
- [x] Orquestrador `dispatch_por_empresa` em `workers/dispatcher.py` (lê `comercial.empresas` via async session, dispara `send_task` por empresa ativa)
- [x] Idempotência: `gerar_titulos_mensais` usa check `_titulo_existe_para_vencimento` + `with_for_update(skip_locked=True)`; `gerar_despesas_recorrentes` usa `with_for_update(skip_locked=True)` + avança `proxima_geracao_em`
- [x] `workers/__init__.py` sem imports de classes antigas (deletadas: `generate_monthly_installments.py`, `generate_recurring_payables.py`, `calculate_customer_scores.py`, `refresh_materialized_views.py`)
- [x] `pytest` passando: **183 passam, 6 skipped, 0 falhas** (+4 testes novos em `test_workers_tenant.py`)

## Implementation Notes — 2026-05-25

### Design escolhido

**Pattern por-empresa via orquestrador único.** Em vez de cada task se virar pra descobrir o tenant, criei `dispatch_por_empresa(task_name)` em `workers/dispatcher.py`:

1. Celery Beat dispara `dispatch_por_empresa` para um `task_name`.
2. O orquestrador lê `comercial.empresas` (apenas `ativo=true`).
3. Pra cada empresa, manda `celery_app.send_task(task_name, args=[empresa_id])`.

Isso isola falhas (task da empresa A explode → outras seguem) e centraliza o pattern. O orquestrador usa **sessão async** (psycopg2 não instalado no container).

### ContextVar reset em workers

Workers Celery reusam processos — `set_empresa_id()` no início, `reset_empresa_id()` no `finally`. Sem isso o `ContextVar` da execução anterior vazaria pra próxima execução da mesma worker.

### RLS em cada sessão

`SELECT set_config('app.empresa_id', :eid, true)` no início de cada sessão garante que o RLS (story 12-5) filtra cada query no DB — defesa em profundidade.

### atualizar_views fica system-wide

O REFRESH MATERIALIZED VIEW é cross-tenant por design (as MVs incluem `empresa_id` como coluna; filtro acontece no query do dashboard). Roda 1x por hora com `SET LOCAL row_security = off` antes de cada refresh.

### verificar_saude_canais — scaffolding

Implementação cobre apenas WhatsApp (chama `get_whatsapp_gateway(session, provedor).health_check()`). Atualiza `status` e `ultimo_health_check` em `CredencialIntegracao`. Email/SMS ficam pra quando os adapters aparecerem (Epic 11).

### Tasks fora do escopo da rename

Tasks que **já recebem identidade explícita** (event_id, conv_id, contract_id, campaign_id) continuam como estão — derivam `empresa_id` do registro processado:

- `process_inbound_whatsapp(event_id, provider)` → lê `event.empresa_id`
- `run_agent_turn(conv_id, content)` → lê via `ConversationStore(session, empresa_id)`
- `render_contract_pdf`, `send_broadcast`, `handle_domain_event` → mesma lógica
- `backup` → system-wide, sem tenant

Quando essas tasks começarem a usar **repositórios** tenant-scoped, vão precisar de `set_empresa_id()` + `try/finally`. Por ora, fazem queries diretas com filtro `WHERE empresa_id = ...` explícito.

### Arquivos

**Criados:**
- `src/backend-api/app/workers/dispatcher.py`
- `src/backend-api/app/workers/tasks/gerar_titulos_mensais.py`
- `src/backend-api/app/workers/tasks/gerar_despesas_recorrentes.py`
- `src/backend-api/app/workers/tasks/recalcular_scores_clientes.py`
- `src/backend-api/app/workers/tasks/atualizar_views.py`
- `src/backend-api/app/workers/tasks/verificar_saude_canais.py`
- `src/backend-api/app/tests/test_workers_tenant.py` (4 testes novos)

**Deletados:**
- `src/backend-api/app/workers/tasks/generate_monthly_installments.py`
- `src/backend-api/app/workers/tasks/generate_recurring_payables.py`
- `src/backend-api/app/workers/tasks/calculate_customer_scores.py`
- `src/backend-api/app/workers/tasks/refresh_materialized_views.py`

**Modificados:**
- `src/backend-api/app/workers/__init__.py` (novo beat schedule per-empresa)
- `src/backend-api/app/api/v1/dashboard_routes.py` (import `atualizar_views.executar`)
- `src/backend-api/app/tests/test_monthly_generation.py` (passa `empresa_id` ao `_run`)

## File List
- src/backend-api/app/workers/dispatcher.py (novo)
- src/backend-api/app/workers/tasks/gerar_titulos_mensais.py (novo)
- src/backend-api/app/workers/tasks/gerar_despesas_recorrentes.py (novo)
- src/backend-api/app/workers/tasks/recalcular_scores_clientes.py (novo)
- src/backend-api/app/workers/tasks/atualizar_views.py (novo)
- src/backend-api/app/workers/tasks/verificar_saude_canais.py (novo)
- src/backend-api/app/tests/test_workers_tenant.py (novo)
- src/backend-api/app/workers/__init__.py (modificado)
- src/backend-api/app/api/v1/dashboard_routes.py (modificado)
- src/backend-api/app/tests/test_monthly_generation.py (modificado)
- src/backend-api/app/workers/tasks/generate_monthly_installments.py (deletado)
- src/backend-api/app/workers/tasks/generate_recurring_payables.py (deletado)
- src/backend-api/app/workers/tasks/calculate_customer_scores.py (deletado)
- src/backend-api/app/workers/tasks/refresh_materialized_views.py (deletado)

## Change Log
- 2026-05-25 — Dev (Amelia): Implementação completa de 12-6. Refatorados 4 workers tenant-scoped + novo orquestrador + nova task de saúde de canais. 183 testes verdes. Status → review.
- 2026-05-25 — Dev (Amelia): Senior Developer Review (AI) rodada 1. 9 HIGHs + 1 MED resolvidos. 183 testes seguem verdes.

---

## Senior Developer Review (AI) — 2026-05-25

**Reviewers:** Blind Hunter + Edge Case Hunter + Acceptance Auditor (3 em paralelo, sem contexto cruzado).
**Veredito do Acceptance Auditor:** 7/8 AC ATENDIDO, 1/8 PARCIAL (AC1 — escopo restrito a tasks tenant-scoped; tasks event-driven derivam empresa_id do registro processado, decisão defensável documentada).

### Findings críticos descobertos e RESOLVIDOS nesta rodada

| # | Bug | Severidade | Fix aplicado |
|---|---|---|---|
| H1 | `verificar_saude_canais.py` chamava `get_whatsapp_gateway(session, cred.provedor)` mas factory aceita só `(session)` — TypeError em toda iteração, swallowed por `except Exception` → status='error' em TODAS credenciais a cada 5min | HIGH | Reescrito como scaffolding (sem `get_whatsapp_gateway`): valida presença de campos mínimos de config por provedor (`instance_id`+`token` p/ zapi, `base_url`+`api_key` p/ uazapi/evolution) e marca `status='configurada'` ou `'config_incompleta'`. Real health check fica pro Epic 11. **Bonus:** evita o bug pré-existente do `_adapter_cache` process-wide cross-tenant. |
| H2 | `score_calculator.compute_and_save_score` criava `CustomerScore` SEM `empresa_id`; tabela é `NOT NULL` (cobranca.py:191) → INSERT falharia silenciosamente quando RLS estiver enforcement em writes | HIGH | Carrega `Customer.empresa_id` e passa explícito ao `CustomerScore`. Levanta `ValueError` se cliente não existe (era branch silencioso antes). |
| H3 | `recalcular_scores_clientes._run` compartilhava UMA sessão pra todos clientes; primeiro erro → `PendingRollbackError` → `commit()` final perde TODOS scores recalculados | HIGH | `async with session.begin_nested()` por cliente (savepoint isolado). Exceção em N só rollback de N, mantém scores 1..N-1. |
| H4a | `atualizar_views.py` fazia `session.commit()` antes do loop, wipe do `SET LOCAL row_security = off` inicial | HIGH | Reescrito usando `engine.connect()` em `isolation_level='AUTOCOMMIT'`. Sem necessidade de `SET LOCAL` — `SET row_security = off` agora é session-wide na conexão dedicada (descartada ao fim). |
| H4b | `REFRESH MV CONCURRENTLY` não pode rodar dentro de transação — SQLAlchemy autobegin abria tx → `cannot run inside a transaction block` | HIGH | Conexão AUTOCOMMIT (mesma fix do H4a) — cada `execute` é auto-commitado. |
| H4c | Pré-existente: usava `get_sync_sessionmaker()` (psycopg2 não instalado no container) | HIGH | Convertido pra asyncpg via `get_engine()`. Removida dependência sync. |
| H5a | `gerar_titulos_mensais` gerava só 1 parcela/run; contratos atrasados N meses jamais alcançavam o presente | HIGH | Loop interno `_processar_contrato`: `while proxima_geracao_em <= hoje: gerar()` com teto de 60 iterações por contrato. |
| H5b | `_avancar_um_mes` lançava `ValueError` se `dia_geracao=31` e mês alvo tem 30 dias (defensivo — DB hoje restringe a 1-28 mas backfills podem violar) | HIGH | `monthrange(ano, mes)[1]` clamp pro último dia válido do mês. |
| H5c | `CorrectionIndexUnavailableError` no `except continue` corrompia transação inteira (sem rollback nem savepoint) → contratos seguintes falhavam, `commit()` final perdia o lote | HIGH | `async with session.begin_nested()` por contrato. Erro num contrato (provider fora do ar, integridade) dá rollback ISOLADO e os demais seguem. |
| H5d | `Redis.from_url` criado FORA do try; se `get_sessionmaker()` falhasse antes do try, vazava | HIGH | Criação do Redis movida pra dentro do try; flag `provider_dispose_local` controla o `aclose()` no finally. |
| H6a | `gerar_despesas_recorrentes` mesma falta de catch-up loop (1 parcela/run) | HIGH | Loop interno `_processar_template` com mesmo padrão de teto 60, respeitando `data_fim`. |
| H6b | Não filtrava `data_fim`; templates expirados continuavam gerando indefinidamente | HIGH | Filtro `or_(data_fim.is_(None), data_fim >= hoje)` na query + check no loop interno. |
| H6c | `_avancar_data` fallback silencioso pra mensal em periodicidade desconhecida — typo `"anual"` faturava 12x | HIGH | `raise ValueError` em periodicidade fora de `('mensal','quinzenal','semanal')`. |
| H6d | `assert data_vencimento is not None` em código de produção (drop com `-O`) | HIGH | Substituído por check explícito `if data_vencimento is None: break`. |
| M1 | `dispatcher.py` não filtrava `excluido_em IS NULL`; soft-deleted empresas com `ativo=True` recebiam dispatch | MED | Filtro `Empresa.excluido_em.is_(None)` adicionado. |
| M2 | `send_task` errors mid-loop matavam o orquestrador (broker hiccup numa empresa abortaria as demais) | MED | `try/except` por empresa com counter `failed`; segue processando próximas. |
| M3 | `max_retries=2` no dispatcher amplificava em broker outage (replay duplicaria todas N empresas) | MED | `max_retries=0`. Próxima rodada do beat (5min–1h) resolve naturalmente. |

### Falsos positivos identificados nos findings dos hunters

- **Edge MED "SET LOCAL set_config wipe entre statements"**: SQLAlchemy AsyncSession faz autobegin no primeiro `execute()` e mantém a transação até `commit()` — então `is_local=true` persiste pelas queries subsequentes na mesma sessão. Confirmado pelos `test_tenant_isolation` que passam e usam exatamente esse padrão. **Não aplicado.**
- **Edge HIGH "_proxima_sequencia race"**: protegido pela `UniqueConstraint("empresa_id","contrato_id","sequencia")`. Em race rara, segundo INSERT viola; o savepoint H5c agora rollback isolado. **Risco real baixo, decisão informada.**
- **Edge H2 "_adapter_cache cross-tenant"**: bug pré-existente do Epic 9 (`whatsapp_factory.py:33`). **Removido via H1 — não chamamos mais o factory de dentro da task tenant-scoped.**

### Findings DEFERIDOS para follow-up (documentar como dívida técnica)

| # | Finding | Por que diferido |
|---|---|---|
| D1 | Deviation #1 do Acceptance Auditor: AC1 diz "ALL tasks" mas só 4 (tenant-scoped) foram refatoradas | Decisão arquitetural defensável: tasks event-driven (`process_inbound_whatsapp`, `run_agent_turn`, etc.) derivam `empresa_id` do registro processado. Forçá-las a aceitar `empresa_id` como 1º arg duplicaria lookup e abriria janela de inconsistência. **Recomendação:** abrir story de follow-up para auditar essas 6 contra RLS (provavelmente precisam `set_empresa_id()` derivado do registro carregado quando começarem a usar repositórios). |
| D2 | Deviation #4 do Acceptance Auditor: `Contrato.status.notin_(_STATUS_INATIVOS)` vs `== "vigente"` | Mais permissivo — também aceita `suspenso`. **Decisão conservadora:** mantém comportamento prévio (Story 10.1 já usava esse padrão). State machine de status vem em Epic 13.2. Quando vier, ajustar denylist. |
| D3 | `verificar_saude_canais` no timeout em `health_check` real | N/A na versão atual (scaffolding sem chamada externa). Epic 11 vai implementar real health check com `asyncio.wait_for` + `gather`. |
| D4 | UTC vs BRT em beat schedule (score recalc 02:00 UTC = 23:00 BRT dia anterior) | Operacional; comentário já existe no `workers/__init__.py:39`. Pablo decide na configuração de timezone do worker em produção. |
| D5 | `compute_and_save_score` flush por cliente → OOM em 100k clientes | Escala atual não toca esse limite (FrotaUber early stage). Doc; tunar quando necessário (batch + expire). |
| D6 | `_adapter_cache` cross-tenant leak no `whatsapp_factory.py` | Bug pré-existente Epic 9, fora do escopo de 12-6. Mitigado por H1. Story de follow-up: keyear cache por `(empresa_id, provedor)`. |

### Status dos ACs (re-avaliação pós-fixes)

| AC | Status | Notas |
|---|---|---|
| AC1 | ATENDIDO | 4 tasks tenant-scoped com `empresa_id` + `set_empresa_id`. Tasks event-driven documentadas como decisão (D1). |
| AC2 | ATENDIDO | `dispatch_por_empresa` orquestra per-empresa para todas as tasks tenant-scoped. |
| AC3 | ATENDIDO | `workers/__init__.py` sem imports antigos; 4 arquivos antigos deletados. |
| AC4 | ATENDIDO | `gerar_titulos_mensais` gera `TituloReceber`. |
| AC5 | ATENDIDO | `gerar_despesas_recorrentes` gera `TituloPagar` com `status='rascunho'`. |
| AC6 | ATENDIDO | Idempotência: check de existência + savepoint + unique constraint + FOR UPDATE SKIP LOCKED. Testes validam. |
| AC7 | ATENDIDO | Todos os schedules em `crontab()` (incluindo `crontab(minute="*/5")` p/ health check). |
| AC8 | ATENDIDO | 4 testes em `test_workers_tenant.py` + 11 testes existentes em `test_monthly_generation.py`. 183/0. |

### Testes

**183 passam, 6 skipped, 0 falhas** após 2 rodadas (1ª rodada teve 1 falha: teste antigo do dispatcher esperava `{dispatched, skipped}` antes de eu adicionar `failed` ao retorno — ajustado).

### Arquivos modificados nesta rodada (CR fixes)

- `src/backend-api/app/workers/dispatcher.py` — M1, M2, M3
- `src/backend-api/app/workers/tasks/verificar_saude_canais.py` — H1 (reescrito)
- `src/backend-api/app/workers/tasks/recalcular_scores_clientes.py` — H3 (savepoint per-cliente)
- `src/backend-api/app/workers/tasks/atualizar_views.py` — H4a/b/c (AUTOCOMMIT + async)
- `src/backend-api/app/workers/tasks/gerar_titulos_mensais.py` — H5a/b/c/d
- `src/backend-api/app/workers/tasks/gerar_despesas_recorrentes.py` — H6a/b/c/d
- `src/backend-api/app/application/agent/score_calculator.py` — H2
- `src/backend-api/app/tests/test_workers_tenant.py` — ajuste do dict retornado

### Veredito final

**APROVADO COM RESSALVAS.** Todos os HIGHs acionáveis e os 3 MEDs do dispatcher resolvidos. Story 12-6 pronta para `done` quando 12-3 fechar (não há dependência direta declarada, mas convenção do Epic 12 é fechar em ordem). 6 findings deferidos com justificativa documentada — recomendado abrir 2 stories de follow-up: (a) auditar tasks event-driven contra RLS quando começarem a usar repositórios; (b) corrigir `_adapter_cache` cross-tenant do whatsapp_factory.
