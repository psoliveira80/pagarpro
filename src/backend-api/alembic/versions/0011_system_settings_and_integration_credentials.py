"""system_settings and integration_credentials enhancements

Revision ID: 0011
Revises: 0010
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # system_settings table (key-value store for all platform settings)
    op.create_table(
        "system_settings",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_by_user_id", postgresql.UUID(), nullable=True),
    )

    # integration_credentials table (if not already exists — add missing columns)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS integration_credentials (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            category TEXT NOT NULL,
            provider TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT true,
            config JSONB NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'unknown',
            last_health_check TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    # Indexes for audit_log search
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log (action);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log (entity);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log (user_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log (created_at DESC);"
    )

    # pg_trgm extension for global fuzzy search
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")

    # GIN trigram indexes for global search
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_customers_fullname_trgm ON customers USING gin (full_name gin_trgm_ops);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_customers_cpf_trgm ON customers USING gin (cpf_cnpj gin_trgm_ops);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_contracts_number_trgm ON contracts USING gin (contract_number gin_trgm_ops);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_contracts_number_trgm;")
    op.execute("DROP INDEX IF EXISTS idx_customers_cpf_trgm;")
    op.execute("DROP INDEX IF EXISTS idx_customers_fullname_trgm;")
    op.execute("DROP INDEX IF EXISTS idx_audit_log_created_at;")
    op.execute("DROP INDEX IF EXISTS idx_audit_log_user_id;")
    op.execute("DROP INDEX IF EXISTS idx_audit_log_entity;")
    op.execute("DROP INDEX IF EXISTS idx_audit_log_action;")
    op.execute("DROP TABLE IF EXISTS integration_credentials;")
    op.drop_table("system_settings")
