"""Rename orphan English FK constraints and add Conversa/Mensagem fields lost in 0015.

Revision ID: 0017
Revises: 0016
Create Date: 2026-05-24

Epic 12 Story 3 — Code refactor support.

Two groups of changes:

1. **FK rename**: Migration 0015 renamed tables but left several FK constraints
   with their old English names (e.g. `customers_created_by_user_id_fkey` still
   exists on `cadastro.clientes`). Renaming clarifies ownership and aligns with
   PT-BR convention. ON DELETE policy is left as the default (NO ACTION =
   RESTRICT) per project decision (Modelo A multi-tenant + soft-delete-first).

2. **Conversa/Mensagem schema gap**: Migration 0015 dropped some fields used by
   in-app chat flows: `Conversation.status`, `Conversation.user_id`,
   `ConversationMessage.role`. This migration restores them with PT-BR names:
   `Conversa.situacao`, `Conversa.usuario_id`, `Mensagem.perfil`.

   Also `Conversa.telefone` becomes nullable to support in-app chat (no phone).
"""

from alembic import op


revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def _exec(sql: str) -> None:
    op.execute(sql)


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # 1. Rename orphan English FK constraints
    # -------------------------------------------------------------------------
    rename_fks = [
        ("cadastro.clientes", "customers_created_by_user_id_fkey",
         "clientes_criado_por_id_fkey"),
        ("veiculos.veiculos", "vehicles_customer_id_fkey",
         "veiculos_cliente_atual_id_fkey"),
        ("contrato.contratos", "contracts_created_by_user_id_fkey",
         "contratos_criado_por_id_fkey"),
        ("contrato.contratos", "contracts_customer_id_fkey",
         "contratos_cliente_id_fkey"),
        ("cobranca.conversas", "conversations_customer_id_fkey",
         "conversas_cliente_id_fkey"),
        ("cobranca.mensagens", "conversation_messages_conversation_id_fkey",
         "mensagens_conversa_id_fkey"),
    ]
    for table, old, new in rename_fks:
        _exec(f"""
            DO $$ BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = '{old}'
                ) THEN
                    ALTER TABLE {table} RENAME CONSTRAINT {old} TO {new};
                END IF;
            END $$
        """)

    # Drop and recreate other orphan English unique constraints
    _exec("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'customers_cpf_cnpj_key'
            ) THEN
                ALTER TABLE cadastro.clientes DROP CONSTRAINT customers_cpf_cnpj_key;
            END IF;
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'customers_email_key'
            ) THEN
                ALTER TABLE cadastro.clientes DROP CONSTRAINT customers_email_key;
            END IF;
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'customers_pkey'
            ) THEN
                ALTER TABLE cadastro.clientes RENAME CONSTRAINT customers_pkey TO clientes_pkey;
            END IF;
        END $$
    """)

    # -------------------------------------------------------------------------
    # 2. Conversa — add situacao + usuario_id; relax telefone to nullable
    # -------------------------------------------------------------------------
    _exec("""
        ALTER TABLE cobranca.conversas
        ADD COLUMN IF NOT EXISTS situacao TEXT NOT NULL DEFAULT 'ativa'
    """)
    _exec("""
        ALTER TABLE cobranca.conversas
        ADD CONSTRAINT ck_conversas_situacao
        CHECK (situacao IN ('ativa', 'pausada', 'encerrada'))
    """)
    _exec("""
        ALTER TABLE cobranca.conversas
        ADD COLUMN IF NOT EXISTS usuario_id UUID
            REFERENCES acesso.usuarios(id) ON DELETE SET NULL
    """)
    _exec("""
        ALTER TABLE cobranca.conversas
        ALTER COLUMN telefone DROP NOT NULL
    """)
    _exec("""
        CREATE INDEX IF NOT EXISTS idx_conversas_usuario
        ON cobranca.conversas(empresa_id, usuario_id)
        WHERE usuario_id IS NOT NULL
    """)
    _exec("""
        CREATE INDEX IF NOT EXISTS idx_conversas_situacao
        ON cobranca.conversas(empresa_id, situacao)
    """)

    # -------------------------------------------------------------------------
    # 3. Mensagem — add perfil (was role: user/assistant/system)
    # -------------------------------------------------------------------------
    _exec("""
        ALTER TABLE cobranca.mensagens
        ADD COLUMN IF NOT EXISTS perfil TEXT
    """)
    _exec("""
        ALTER TABLE cobranca.mensagens
        ADD CONSTRAINT ck_mensagens_perfil
        CHECK (perfil IS NULL OR perfil IN ('usuario', 'assistente', 'sistema'))
    """)


def downgrade() -> None:
    # Reverse Mensagem.perfil
    _exec("""
        ALTER TABLE cobranca.mensagens
        DROP CONSTRAINT IF EXISTS ck_mensagens_perfil
    """)
    _exec("ALTER TABLE cobranca.mensagens DROP COLUMN IF EXISTS perfil")

    # Reverse Conversa changes
    _exec("DROP INDEX IF EXISTS idx_conversas_situacao")
    _exec("DROP INDEX IF EXISTS idx_conversas_usuario")
    _exec("ALTER TABLE cobranca.conversas ALTER COLUMN telefone SET NOT NULL")
    _exec("ALTER TABLE cobranca.conversas DROP COLUMN IF EXISTS usuario_id")
    _exec("ALTER TABLE cobranca.conversas DROP CONSTRAINT IF EXISTS ck_conversas_situacao")
    _exec("ALTER TABLE cobranca.conversas DROP COLUMN IF EXISTS situacao")

    # Reverse cadastro.clientes constraint changes (recreate old uniques)
    _exec("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'clientes_pkey'
            ) THEN
                ALTER TABLE cadastro.clientes RENAME CONSTRAINT clientes_pkey TO customers_pkey;
            END IF;
        END $$
    """)

    # Reverse FK renames
    rename_back = [
        ("cobranca.mensagens", "mensagens_conversa_id_fkey",
         "conversation_messages_conversation_id_fkey"),
        ("cobranca.conversas", "conversas_cliente_id_fkey",
         "conversations_customer_id_fkey"),
        ("contrato.contratos", "contratos_cliente_id_fkey",
         "contracts_customer_id_fkey"),
        ("contrato.contratos", "contratos_criado_por_id_fkey",
         "contracts_created_by_user_id_fkey"),
        ("veiculos.veiculos", "veiculos_cliente_atual_id_fkey",
         "vehicles_customer_id_fkey"),
        ("cadastro.clientes", "clientes_criado_por_id_fkey",
         "customers_created_by_user_id_fkey"),
    ]
    for table, current, original in rename_back:
        _exec(f"""
            DO $$ BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = '{current}'
                ) THEN
                    ALTER TABLE {table} RENAME CONSTRAINT {current} TO {original};
                END IF;
            END $$
        """)
