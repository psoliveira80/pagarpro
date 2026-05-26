"""Asset abstraction layer: assets, active_modules, module_hooks_config, event_log

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # active_modules (must come first — referenced by FK)
    op.create_table(
        "active_modules",
        sa.Column("module_id", sa.Text(), primary_key=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("config", JSONB(), nullable=True),
        sa.Column("registered_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # assets
    op.create_table(
        "assets",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("module_id", sa.Text(), nullable=False),
        sa.Column("external_ref", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'disponivel'")),
        sa.Column("metadata", JSONB(), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("idx_assets_module_id", "assets", ["module_id"])
    op.create_index("idx_assets_external_ref", "assets", ["module_id", "external_ref"], unique=True)

    # module_hooks_config
    op.create_table(
        "module_hooks_config",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("module_id", sa.Text(), sa.ForeignKey("active_modules.module_id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("policy", JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("idx_hooks_module_event", "module_hooks_config", ["module_id", "event_type"])

    # event_log
    op.create_table(
        "event_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.Uuid(), unique=True, nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("asset_type", sa.Text(), nullable=False),
        sa.Column("payload", JSONB(), nullable=True),
        sa.Column("dispatched_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("processing_status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("idx_event_log_status", "event_log", ["processing_status"])


def downgrade() -> None:
    op.drop_table("event_log")
    op.drop_table("module_hooks_config")
    op.drop_table("assets")
    op.drop_table("active_modules")
