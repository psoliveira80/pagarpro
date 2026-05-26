"""Bank accounts, bank transactions, reconciliation sessions

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- bank_accounts ---
    op.create_table(
        "bank_accounts",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("bank_code", sa.String(5), nullable=True),
        sa.Column("bank_name", sa.Text(), nullable=True),
        sa.Column("agency", sa.String(10), nullable=True),
        sa.Column("account_number", sa.String(20), nullable=True),
        sa.Column("account_type", sa.Text(), nullable=False, server_default=sa.text("'corrente'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- bank_transactions ---
    op.create_table(
        "bank_transactions",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fitid", sa.Text(), nullable=False),
        sa.Column("posted_at", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("description_raw", sa.Text(), nullable=True),
        sa.Column("description_clean", sa.Text(), nullable=True),
        sa.Column("type", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pendente'")),
        sa.Column("reconciled_to_kind", sa.Text(), nullable=True),
        sa.Column("reconciled_to_id", sa.Uuid(), nullable=True),
        sa.Column("imported_from", sa.Text(), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("raw_data", JSONB, nullable=True),
        sa.Column("imported_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("account_id", "fitid", name="uq_bank_tx_account_fitid"),
    )

    op.create_index("idx_btx_status", "bank_transactions", ["status"], postgresql_where=sa.text("status='pendente'"))
    op.create_index("idx_btx_posted", "bank_transactions", [sa.text("posted_at DESC")])

    # --- reconciliation_sessions ---
    op.create_table(
        "reconciliation_sessions",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("bank_account_id", sa.Uuid(), sa.ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("reconciliation_sessions")
    op.drop_index("idx_btx_posted", table_name="bank_transactions")
    op.drop_index("idx_btx_status", table_name="bank_transactions")
    op.drop_table("bank_transactions")
    op.drop_table("bank_accounts")
