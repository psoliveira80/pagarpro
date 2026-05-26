"""Fix multi-tenant unique constraints on webhooks_brutos and mensagens.

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-24

Epic 12 Story 2 — Code Review Follow-up.

Two HIGH-severity multi-tenant isolation bugs identified in code review of
SQLAlchemy models. UniqueConstraints in two tables did not include empresa_id,
which would cause inserts from tenant B to fail when tenant A had already
recorded a row with the same external identifier (legitimate, since external
identifiers from upstream providers — webhooks, WhatsApp gateways — are not
guaranteed unique across tenants).

Fixes:
  1. notificacoes.webhooks_brutos: (provedor, external_id) → (empresa_id, provedor, external_id)
  2. cobranca.mensagens: (external_id) → (empresa_id, external_id)

Note: Usuario.email is intentionally LEFT global-unique. Project decision
(2026-05-24) adopts Model A multi-tenancy: each user belongs to exactly one
empresa. Email uniqueness is therefore a global identity constraint, not a
tenant-scoped one.
"""

from alembic import op


revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def _exec(sql: str) -> None:
    op.execute(sql)


def upgrade() -> None:
    # ---------------------------------------------------------------------
    # 1. notificacoes.webhooks_brutos
    # ---------------------------------------------------------------------
    _exec("""
        ALTER TABLE notificacoes.webhooks_brutos
        DROP CONSTRAINT IF EXISTS uq_webhooks_provedor_external
    """)
    _exec("""
        ALTER TABLE notificacoes.webhooks_brutos
        ADD CONSTRAINT uq_webhooks_empresa_provedor_external
        UNIQUE (empresa_id, provedor, external_id)
    """)

    # ---------------------------------------------------------------------
    # 2. cobranca.mensagens
    # ---------------------------------------------------------------------
    _exec("""
        ALTER TABLE cobranca.mensagens
        DROP CONSTRAINT IF EXISTS uq_conv_messages_external_id
    """)
    _exec("""
        ALTER TABLE cobranca.mensagens
        ADD CONSTRAINT uq_mensagens_empresa_external
        UNIQUE (empresa_id, external_id)
    """)


def downgrade() -> None:
    # Reverse: webhooks_brutos
    _exec("""
        ALTER TABLE notificacoes.webhooks_brutos
        DROP CONSTRAINT IF EXISTS uq_webhooks_empresa_provedor_external
    """)
    _exec("""
        ALTER TABLE notificacoes.webhooks_brutos
        ADD CONSTRAINT uq_webhooks_provedor_external
        UNIQUE (provedor, external_id)
    """)

    # Reverse: mensagens
    _exec("""
        ALTER TABLE cobranca.mensagens
        DROP CONSTRAINT IF EXISTS uq_mensagens_empresa_external
    """)
    _exec("""
        ALTER TABLE cobranca.mensagens
        ADD CONSTRAINT uq_conv_messages_external_id
        UNIQUE (external_id)
    """)
