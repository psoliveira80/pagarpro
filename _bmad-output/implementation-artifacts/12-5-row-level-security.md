---
epic: 12
story: 5
title: "Row Level Security — PostgreSQL Tenant Isolation as Safety Net"
type: "Core Refactor"
status: ready-for-dev
priority: high
depends_on: "12.4"
---

# Story 12.5: Row Level Security — PostgreSQL Tenant Isolation as Safety Net

## User Story
As the System,
I want PostgreSQL Row Level Security policies on all tenant-scoped tables,
So that even if application code forgets to filter by empresa_id, the database itself prevents cross-tenant data leakage.

## Context
Story 12.4 enforces tenant isolation at the application layer. This story adds a second layer of defense at the database level. RLS is a safety net — it should never be the only enforcement, but it must exist. **Depends on 12.4.**

## Acceptance Criteria

1. Alembic migration `0016_row_level_security.py` created.
2. RLS enabled on all tables with `empresa_id NOT NULL` (see full list in 12.1).
3. Policy created: `USING (empresa_id = current_setting('app.empresa_id', true)::uuid)`.
4. `current_setting('app.empresa_id', true)` returns `NULL` when setting not defined (second arg `true` = missing-ok).
5. When `app.empresa_id` is NULL (e.g., Alembic migrations, admin scripts), RLS policy is bypassed via BYPASSRLS role or `SET LOCAL row_security = off`.
6. Application sets `SET LOCAL app.empresa_id = '{empresa_id}'` at the start of every database transaction.
7. `BYPASSRLS` granted to migration role / superuser only — never to the application role.
8. Tests: query from empresa A cannot return rows from empresa B even without WHERE clause.
9. Materialized view refreshes bypass RLS (use SECURITY DEFINER function or superuser role).
10. `down()` in migration disables RLS and drops all policies cleanly.

## Implementation

### Migration Structure
```python
# 0016_row_level_security.py

TENANT_TABLES = [
    ("acesso", "usuarios"),
    ("acesso", "usuario_perfis"),
    ("acesso", "refresh_tokens"),
    ("cadastro", "clientes"),
    ("cadastro", "anexos_cliente"),
    ("cadastro", "fornecedores"),
    ("financeiro", "titulos_receber"),
    ("financeiro", "movimentos_titulo_receber"),
    ("financeiro", "titulos_pagar"),
    ("financeiro", "despesas_recorrentes"),
    ("veiculos", "veiculos"),
    ("veiculos", "aquisicoes_veiculo"),
    ("veiculos", "dispositivos_rastreamento"),
    ("contrato", "contratos"),
    ("contrato", "eventos_contrato"),
    ("contrato", "lotes_geracao"),
    ("conta_bancaria", "contas_bancarias"),
    ("conta_bancaria", "transacoes_bancarias"),
    ("conta_bancaria", "sessoes_conciliacao"),
    ("cobranca", "conversas"),
    ("cobranca", "mensagens"),
    ("cobranca", "configuracoes_agente"),
    ("cobranca", "execucoes_agente"),
    ("cobranca", "scores_clientes"),
    ("cobranca", "campanhas_disparo"),
    ("config", "configuracoes_sistema"),
    ("config", "politicas_eventos_modulo"),
    ("config", "credenciais_integracao"),
    ("relatorios", "relatorios_salvos"),
]

def upgrade():
    for schema, table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {schema}.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {schema}.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {schema}.{table}
            USING (
                empresa_id = NULLIF(
                    current_setting('app.empresa_id', true), ''
                )::uuid
            )
        """)

def downgrade():
    for schema, table in reversed(TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {schema}.{table}")
        op.execute(f"ALTER TABLE {schema}.{table} DISABLE ROW LEVEL SECURITY")
```

### SQLAlchemy Session — Set empresa_id per Transaction
```python
# backend-api/app/infrastructure/db/session.py
from app.core.tenant_context import get_empresa_id

@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            empresa_id = get_empresa_id()
            # Seta o app.empresa_id para esta transação
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(empresa_id)},
            )
        except RuntimeError:
            # Contexto sem empresa_id (migrations, scripts admin)
            # RLS não será aplicado — usar com cuidado
            pass
        yield session
```

### Alembic env.py — Bypass RLS for Migrations
```python
# alembic/env.py
def run_migrations_online():
    with engine.connect() as connection:
        connection.execute(text("SET row_security = off"))  # bypass RLS
        context.configure(connection=connection, ...)
        with context.begin_transaction():
            context.run_migrations()
```

### categorias_despesa — RLS com empresa_id nullable
```sql
-- Categorias globais (empresa_id IS NULL) visíveis para todos;
-- categorias da empresa visíveis apenas para a empresa dona.
CREATE POLICY tenant_isolation ON cadastro.categorias_despesa
USING (
    empresa_id IS NULL  -- categoria global, visível para todos
    OR
    empresa_id = NULLIF(current_setting('app.empresa_id', true), '')::uuid
);
```

### logs e notificacoes — empresa_id nullable
```sql
-- Linhas com empresa_id NULL (eventos de sistema) visíveis para admins do sistema.
-- Por ora, policy permissiva: qualquer empresa vê apenas suas linhas + linhas sem empresa.
CREATE POLICY tenant_isolation ON logs.log_auditoria
USING (
    empresa_id IS NULL
    OR
    empresa_id = NULLIF(current_setting('app.empresa_id', true), '')::uuid
);
```

## Technical Context

### Files to Create/Modify
```
backend-api/
├── alembic/versions/0016_row_level_security.py   # CRIAR
├── alembic/env.py                                 # MODIFICAR — SET row_security = off
└── app/infrastructure/db/session.py              # MODIFICAR — set_config por transação
```

### Performance Note
RLS adds a predicate to every query. With `empresa_id` indexed on every table (feito em 12.1), the performance impact é mínimo — o índice é usado normalmente pelo planner.

## Dev Checklist
- [ ] 12.4 concluída antes de começar
- [ ] Migration 0016 criada e `alembic upgrade head` passa
- [ ] RLS habilitado em todas as tabelas da lista TENANT_TABLES
- [ ] `categorias_despesa` com policy especial (empresa_id IS NULL OR empresa_id = ...)
- [ ] `alembic/env.py` com `SET row_security = off` para migrations
- [ ] `session.py` seta `app.empresa_id` por transação
- [ ] Teste: SELECT sem WHERE retorna apenas dados da empresa corrente
- [ ] Teste: empresa A não vê dados de empresa B em NENHUMA tabela
- [ ] Teste: migration roda com `row_security = off` sem falha
- [ ] `pytest -x` passando
