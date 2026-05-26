"""Row Level Security (RLS) — isolamento multi-tenant no nível do banco.

Revision ID: 0020
Revises: 0019
Create Date: 2026-05-25

Epic 12, Story 12-5.

Adiciona uma segunda camada de defesa para isolamento entre empresas. A
aplicação JÁ filtra por `empresa_id` em todos os repos (story 12-4), mas
RLS garante que mesmo se uma query nova esquecer o filtro, o banco recusa
retornar linhas de outro tenant.

Como funciona:

- Cada request define `app.empresa_id` na transação atual via
  `SELECT set_config('app.empresa_id', '{uuid}', true)`. O `true` é
  `is_local` — o setting expira no fim da transação, não vaza pro pool.

- Cada tabela tenant-scoped tem uma policy `tenant_isolation`:
  `USING (empresa_id = NULLIF(current_setting('app.empresa_id', true), '')::uuid)`

- Tabelas com `empresa_id NULLABLE` (logs, webhooks, categorias_despesa)
  têm policy permissiva: `empresa_id IS NULL OR empresa_id = ...`.

- `ALTER TABLE ... FORCE ROW LEVEL SECURITY` aplica RLS até pro owner da
  tabela (defesa em profundidade — sem `FORCE`, superuser bypassa).

- Migrations rodam com `SET row_security = off` (configurado em env.py)
  para que `INSERT`/`UPDATE` não sejam bloqueados pelas policies.

- Refresh de materialized views: o worker `refresh_materialized_views`
  precisa rodar com role privilegiada OU setar `row_security = off` na
  conexão. Hoje roda como `app` (mesma role da aplicação), então adicionamos
  `SET LOCAL row_security = off` no início da task.
"""

from alembic import op


revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


# Tabelas com empresa_id NOT NULL — RLS estrita
TENANT_TABLES_STRICT: list[tuple[str, str]] = [
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

# Tabelas com empresa_id NULLABLE — RLS permissiva (linhas system NULL visíveis a todos)
TENANT_TABLES_NULLABLE: list[tuple[str, str]] = [
    ("cadastro", "categorias_despesa"),
    ("logs", "log_auditoria"),
    ("logs", "log_eventos"),
    ("notificacoes", "webhooks_brutos"),
]


def upgrade() -> None:
    for schema, table in TENANT_TABLES_STRICT:
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

    for schema, table in TENANT_TABLES_NULLABLE:
        op.execute(f"ALTER TABLE {schema}.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {schema}.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {schema}.{table}
            USING (
                empresa_id IS NULL
                OR
                empresa_id = NULLIF(
                    current_setting('app.empresa_id', true), ''
                )::uuid
            )
        """)


def downgrade() -> None:
    for schema, table in reversed(TENANT_TABLES_NULLABLE + TENANT_TABLES_STRICT):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {schema}.{table}")
        op.execute(f"ALTER TABLE {schema}.{table} DISABLE ROW LEVEL SECURITY")
