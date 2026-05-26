"""Contracts, installments, contract_events, installment_adjustments, installment_generations

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- contracts ---
    op.create_table(
        "contracts",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("asset_id", sa.Uuid(), sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("contract_number", sa.Text(), unique=True, nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'rascunho'")),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("total_value", sa.Numeric(15, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("pdf_url", sa.Text(), nullable=True),
        sa.Column("pdf_version", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("clauses", sa.Text(), nullable=True),
        sa.Column("terms", JSONB(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("idx_contracts_customer_id", "contracts", ["customer_id"])
    op.create_index("idx_contracts_status", "contracts", ["status"])
    op.create_index("idx_contracts_contract_number", "contracts", ["contract_number"])

    # --- installments ---
    op.create_table(
        "installments",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("contract_id", sa.Uuid(), sa.ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("generation_id", sa.Uuid(), nullable=True),
        sa.Column("parent_installment_id", sa.Uuid(), sa.ForeignKey("installments.id"), nullable=True),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("original_value", sa.Numeric(15, 2), nullable=False),
        sa.Column("current_value", sa.Numeric(15, 2), nullable=False),
        sa.Column("paid_value", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'aberto'")),
        sa.Column("payment_date", sa.Date(), nullable=True),
        sa.Column("payment_method", sa.Text(), nullable=True),
        sa.Column("receipt_url", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_installments_contract_id", "installments", ["contract_id"])
    op.create_index("idx_installments_status", "installments", ["status"])
    op.create_index("idx_installments_due_date", "installments", ["due_date"])
    op.create_index("idx_installments_generation_id", "installments", ["generation_id"])

    # --- contract_events ---
    op.create_table(
        "contract_events",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("contract_id", sa.Uuid(), sa.ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("payload", JSONB(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_contract_events_contract_id", "contract_events", ["contract_id"])

    # --- installment_adjustments ---
    op.create_table(
        "installment_adjustments",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("installment_id", sa.Uuid(), sa.ForeignKey("installments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("old_value", sa.Numeric(15, 2), nullable=False),
        sa.Column("new_value", sa.Numeric(15, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_installment_adjustments_installment_id", "installment_adjustments", ["installment_id"])

    # --- installment_generations ---
    op.create_table(
        "installment_generations",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("contract_id", sa.Uuid(), sa.ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("generation_number", sa.Integer(), nullable=False),
        sa.Column("generated_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("generated_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("config", JSONB(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
    )
    op.create_index("idx_installment_generations_contract_id", "installment_generations", ["contract_id"])

    # --- seed permissions for contract module ---
    op.execute(
        "INSERT INTO permissions (id, code, description) VALUES "
        "(gen_random_uuid(), 'contracts.read', 'View contracts'), "
        "(gen_random_uuid(), 'contracts.create', 'Create contracts'), "
        "(gen_random_uuid(), 'contracts.update', 'Update contracts'), "
        "(gen_random_uuid(), 'contracts.delete', 'Delete contracts'), "
        "(gen_random_uuid(), 'contracts.activate', 'Activate contracts'), "
        "(gen_random_uuid(), 'contracts.terminate', 'Terminate contracts'), "
        "(gen_random_uuid(), 'contracts.pdf', 'Generate contract PDF'), "
        "(gen_random_uuid(), 'installments.read', 'View installments'), "
        "(gen_random_uuid(), 'installments.edit', 'Edit installments') "
        "ON CONFLICT (code) DO NOTHING"
    )


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE code LIKE 'contracts.%' OR code LIKE 'installments.%'")
    op.drop_table("installment_generations")
    op.drop_table("installment_adjustments")
    op.drop_table("contract_events")
    op.drop_table("installments")
    op.drop_table("contracts")
