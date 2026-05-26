"""Add observacoes column to contrato.contratos.

Revision ID: 0019
Revises: 0018
Create Date: 2026-05-24

Migration 0015 lost the `notes` column on contracts. Restored as `observacoes`
so the API can store free-form notes distinct from formal clauses (`clausulas_md`).
"""

from alembic import op


revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE contrato.contratos ADD COLUMN IF NOT EXISTS observacoes TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE contrato.contratos DROP COLUMN IF EXISTS observacoes")
