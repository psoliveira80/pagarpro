"""Add columns lost in migration 0015 still used by legacy consumers.

Revision ID: 0018
Revises: 0017
Create Date: 2026-05-24

Epic 12 Story 3 — Code refactor support.

The DDL restructure (0015) consolidated several fields into JSONB or removed
them. Legacy consumer code (routes, agent, repositories) still references the
flat columns. This migration restores the columns so that the codebase keeps
working while we incrementally refactor consumers.

Columns restored:

* `cadastro.fornecedores.observacoes` — notes field for suppliers
* `cadastro.fornecedores.email` — separated from `contato` (was merged in 0015)
* `cobranca.mensagens.tool_call_id` — function-calling tool execution id
* `cobranca.mensagens.tool_name` — function-calling tool name
* `financeiro.movimentos_titulo_receber.valor_anterior` — old_value
* `financeiro.movimentos_titulo_receber.valor_posterior` — new_value
* `financeiro.movimentos_titulo_receber.criado_por_id` — created_by_user_id
"""

from alembic import op


revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def _exec(sql: str) -> None:
    op.execute(sql)


def upgrade() -> None:
    # ---------------------------------------------------------------------
    # cadastro.fornecedores — add observacoes, email
    # ---------------------------------------------------------------------
    _exec("ALTER TABLE cadastro.fornecedores ADD COLUMN IF NOT EXISTS observacoes TEXT")
    _exec("ALTER TABLE cadastro.fornecedores ADD COLUMN IF NOT EXISTS email TEXT")

    # ---------------------------------------------------------------------
    # cobranca.mensagens — add tool_call_id, tool_name
    # ---------------------------------------------------------------------
    _exec("ALTER TABLE cobranca.mensagens ADD COLUMN IF NOT EXISTS tool_call_id TEXT")
    _exec("ALTER TABLE cobranca.mensagens ADD COLUMN IF NOT EXISTS tool_name TEXT")

    # ---------------------------------------------------------------------
    # financeiro.movimentos_titulo_receber — add valor_anterior, valor_posterior, criado_por_id
    # ---------------------------------------------------------------------
    _exec("""
        ALTER TABLE financeiro.movimentos_titulo_receber
        ADD COLUMN IF NOT EXISTS valor_anterior NUMERIC(15, 2)
    """)
    _exec("""
        ALTER TABLE financeiro.movimentos_titulo_receber
        ADD COLUMN IF NOT EXISTS valor_posterior NUMERIC(15, 2)
    """)
    _exec("""
        ALTER TABLE financeiro.movimentos_titulo_receber
        ADD COLUMN IF NOT EXISTS criado_por_id UUID
            REFERENCES acesso.usuarios(id)
    """)


def downgrade() -> None:
    _exec("""
        ALTER TABLE financeiro.movimentos_titulo_receber
        DROP COLUMN IF EXISTS criado_por_id
    """)
    _exec("""
        ALTER TABLE financeiro.movimentos_titulo_receber
        DROP COLUMN IF EXISTS valor_posterior
    """)
    _exec("""
        ALTER TABLE financeiro.movimentos_titulo_receber
        DROP COLUMN IF EXISTS valor_anterior
    """)
    _exec("ALTER TABLE cobranca.mensagens DROP COLUMN IF EXISTS tool_name")
    _exec("ALTER TABLE cobranca.mensagens DROP COLUMN IF EXISTS tool_call_id")
    _exec("ALTER TABLE cadastro.fornecedores DROP COLUMN IF EXISTS email")
    _exec("ALTER TABLE cadastro.fornecedores DROP COLUMN IF EXISTS observacoes")
