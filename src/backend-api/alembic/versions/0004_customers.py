"""Customers and customer_attachments tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("cpf_cnpj", sa.Text(), unique=True, nullable=False),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), unique=True, nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("photo_url", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'ativo'")),
        sa.Column("address_street", sa.Text(), nullable=True),
        sa.Column("address_number", sa.Text(), nullable=True),
        sa.Column("address_complement", sa.Text(), nullable=True),
        sa.Column("address_neighborhood", sa.Text(), nullable=True),
        sa.Column("address_city", sa.Text(), nullable=True),
        sa.Column("address_state", sa.Text(), nullable=True),
        sa.Column("address_zip", sa.Text(), nullable=True),
        sa.Column("tags", JSONB(), nullable=True),
        sa.Column("metadata_extensions", JSONB(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("idx_customers_cpf_cnpj", "customers", ["cpf_cnpj"])
    op.create_index("idx_customers_status", "customers", ["status"])
    op.create_index("idx_customers_full_name_trgm", "customers", ["full_name"],
                    postgresql_using="gin",
                    postgresql_ops={"full_name": "gin_trgm_ops"})

    op.create_table(
        "customer_attachments",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("mime", sa.Text(), nullable=True),
        sa.Column("size", sa.BigInteger(), nullable=True),
        sa.Column("uploaded_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_attachments_customer", "customer_attachments", ["customer_id"])


def downgrade() -> None:
    op.drop_table("customer_attachments")
    op.drop_table("customers")
