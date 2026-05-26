"""Identity tables: users, roles, permissions, audit_log, refresh_tokens.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, INET, TIMESTAMP, BYTEA

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Users
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.Text, unique=True, nullable=False),  # CITEXT applied via raw SQL below
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("full_name", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_mfa_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("mfa_secret_enc", BYTEA, nullable=True),
        sa.Column("last_login_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", TIMESTAMP(timezone=True), nullable=True),
    )
    # Change email column to CITEXT for case-insensitive uniqueness
    op.execute("ALTER TABLE users ALTER COLUMN email TYPE citext")
    op.create_index("idx_users_active", "users", ["is_active"], postgresql_where=sa.text("deleted_at IS NULL"))

    # Roles
    op.create_table(
        "roles",
        sa.Column("id", sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text, unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Permissions
    op.create_table(
        "permissions",
        sa.Column("id", sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.Text, unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # User-Role join table
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", sa.Uuid, sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    )

    # Role-Permission join table
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Uuid, sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission_id", sa.Uuid, sa.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
    )

    # Refresh tokens
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.Text, unique=True, nullable=False),
        sa.Column("expires_at", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("revoked_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_refresh_user", "refresh_tokens", ["user_id"], postgresql_where=sa.text("revoked_at IS NULL"))

    # Audit log
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("entity", sa.Text, nullable=True),
        sa.Column("entity_id", sa.Text, nullable=True),
        sa.Column("payload_before", JSONB, nullable=True),
        sa.Column("payload_after", JSONB, nullable=True),
        sa.Column("ip", INET, nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("correlation_id", sa.Text, nullable=True),
        sa.Column("module", sa.Text, nullable=True),
        sa.Column("category", sa.Text, nullable=False, server_default=sa.text("'info'")),
        sa.Column("severity", sa.Text, nullable=False, server_default=sa.text("'info'")),
        sa.Column("signature_hmac", BYTEA, nullable=False),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_audit_user_created", "audit_log", ["user_id", sa.text("created_at DESC")])
    op.create_index("idx_audit_entity", "audit_log", ["entity", "entity_id"])

    # Append-only trigger for audit_log
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_log_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'audit_log is append-only'; END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_audit_log_immutable
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_mutation();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_immutable ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_mutation()")
    op.drop_table("audit_log")
    op.drop_table("refresh_tokens")
    op.drop_table("role_permissions")
    op.drop_table("user_roles")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("users")
