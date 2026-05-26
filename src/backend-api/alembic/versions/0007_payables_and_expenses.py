"""Expense categories, suppliers, payables, recurring templates, integration credentials, webhook events

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- expense_categories ---
    op.create_table(
        "expense_categories",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), sa.ForeignKey("expense_categories.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_expense_categories_parent_id", "expense_categories", ["parent_id"])

    # --- suppliers ---
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("cpf_cnpj", sa.Text(), unique=True, nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("idx_suppliers_cpf_cnpj", "suppliers", ["cpf_cnpj"])

    # --- payables ---
    op.create_table(
        "payables",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("supplier_id", sa.Uuid(), sa.ForeignKey("suppliers.id"), nullable=True),
        sa.Column("category_id", sa.Uuid(), sa.ForeignKey("expense_categories.id"), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=True),
        sa.Column("payment_method", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pendente'")),
        sa.Column("linked_installment_id", sa.Uuid(), sa.ForeignKey("installments.id"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("receipt_url", sa.Text(), nullable=True),
        sa.Column("recurring_template_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("idx_payables_supplier_id", "payables", ["supplier_id"])
    op.create_index("idx_payables_category_id", "payables", ["category_id"])
    op.create_index("idx_payables_status", "payables", ["status"])
    op.create_index("idx_payables_due_date", "payables", ["due_date"])
    op.create_index("idx_payables_linked_installment_id", "payables", ["linked_installment_id"])

    # --- recurring_payable_templates ---
    op.create_table(
        "recurring_payable_templates",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("supplier_id", sa.Uuid(), sa.ForeignKey("suppliers.id"), nullable=True),
        sa.Column("category_id", sa.Uuid(), sa.ForeignKey("expense_categories.id"), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("frequency", sa.Text(), nullable=False),
        sa.Column("day_of_month", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("next_generation_date", sa.Date(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- integration_credentials ---
    op.create_table(
        "integration_credentials",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("credential_type", sa.Text(), nullable=False),
        sa.Column("credentials_encrypted", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_integration_credentials_provider", "integration_credentials", ["provider"])

    # --- webhook_events_raw ---
    op.create_table(
        "webhook_events_raw",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=True),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("received_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_webhook_events_raw_provider", "webhook_events_raw", ["provider"])
    op.create_index("idx_webhook_events_raw_processed", "webhook_events_raw", ["processed"])

    # --- seed default expense categories ---
    op.execute(
        "INSERT INTO expense_categories (id, name) VALUES "
        "(gen_random_uuid(), 'Administrativo'), "
        "(gen_random_uuid(), 'Operacional'), "
        "(gen_random_uuid(), 'Financeiro'), "
        "(gen_random_uuid(), 'Manutenção'), "
        "(gen_random_uuid(), 'Pessoal') "
    )

    # --- seed permissions ---
    op.execute(
        "INSERT INTO permissions (id, code, description) VALUES "
        "(gen_random_uuid(), 'receivables.read', 'View receivables'), "
        "(gen_random_uuid(), 'receivables.write', 'Write-off receivables'), "
        "(gen_random_uuid(), 'receivables.validate', 'Validate receipts'), "
        "(gen_random_uuid(), 'receivables.renegotiate', 'Renegotiate installments'), "
        "(gen_random_uuid(), 'receivables.reverse', 'Reverse installments'), "
        "(gen_random_uuid(), 'payables.read', 'View payables'), "
        "(gen_random_uuid(), 'payables.create', 'Create payables'), "
        "(gen_random_uuid(), 'payables.update', 'Update payables'), "
        "(gen_random_uuid(), 'payables.delete', 'Delete payables'), "
        "(gen_random_uuid(), 'payables.pay', 'Pay payables'), "
        "(gen_random_uuid(), 'suppliers.read', 'View suppliers'), "
        "(gen_random_uuid(), 'suppliers.create', 'Create suppliers'), "
        "(gen_random_uuid(), 'suppliers.update', 'Update suppliers'), "
        "(gen_random_uuid(), 'suppliers.delete', 'Delete suppliers'), "
        "(gen_random_uuid(), 'expense_categories.read', 'View expense categories'), "
        "(gen_random_uuid(), 'expense_categories.manage', 'Manage expense categories'), "
        "(gen_random_uuid(), 'recurring_payables.read', 'View recurring payables'), "
        "(gen_random_uuid(), 'recurring_payables.manage', 'Manage recurring payables'), "
        "(gen_random_uuid(), 'reports.dre', 'View DRE report') "
        "ON CONFLICT (code) DO NOTHING"
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM permissions WHERE code LIKE 'receivables.%' "
        "OR code LIKE 'payables.%' OR code LIKE 'suppliers.%' "
        "OR code LIKE 'expense_categories.%' OR code LIKE 'recurring_payables.%' "
        "OR code LIKE 'reports.%'"
    )
    op.drop_table("webhook_events_raw")
    op.drop_table("integration_credentials")
    op.drop_table("recurring_payable_templates")
    op.drop_table("payables")
    op.drop_table("suppliers")
    op.execute("DELETE FROM expense_categories")
    op.drop_table("expense_categories")
