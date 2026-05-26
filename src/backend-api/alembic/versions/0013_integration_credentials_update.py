"""Add category, config, status, last_health_check to integration_credentials

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns
    op.add_column("integration_credentials",
        sa.Column("category", sa.Text(), nullable=True))
    op.add_column("integration_credentials",
        sa.Column("config", JSONB(), server_default=sa.text("'{}'"), nullable=True))
    op.add_column("integration_credentials",
        sa.Column("status", sa.Text(), server_default=sa.text("'unknown'"), nullable=True))
    op.add_column("integration_credentials",
        sa.Column("last_health_check", TIMESTAMP(timezone=True), nullable=True))

    # Migrate existing data: copy credential_type → category
    op.execute("UPDATE integration_credentials SET category = credential_type WHERE category IS NULL")

    # Make category not null now that data is migrated
    op.alter_column("integration_credentials", "category", nullable=False)

    # Make old columns nullable (backward compat)
    op.alter_column("integration_credentials", "credential_type", nullable=True)
    op.alter_column("integration_credentials", "credentials_encrypted", nullable=True)

    # Add index on category
    op.create_index("idx_integration_credentials_category", "integration_credentials", ["category"])


def downgrade() -> None:
    op.drop_index("idx_integration_credentials_category")
    op.drop_column("integration_credentials", "last_health_check")
    op.drop_column("integration_credentials", "status")
    op.drop_column("integration_credentials", "config")
    op.drop_column("integration_credentials", "category")
    op.alter_column("integration_credentials", "credential_type", nullable=False)
    op.alter_column("integration_credentials", "credentials_encrypted", nullable=False)
