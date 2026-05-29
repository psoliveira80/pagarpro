"""Cliente.desbloqueio_confianca_ate — Story 13.22 A1 (code review).

Revision ID: 0031
Revises: 0030
Create Date: 2026-05-28

Persiste a data até a qual o desbloqueio em confiança é válido. Worker
periódico varre clientes com `desbloqueio_confianca_ate < now()` e
re-suspende o contrato. Sem isso o cliente burla bloqueio indefinidamente.
"""

import sqlalchemy as sa
from alembic import op


revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "clientes",
        sa.Column("desbloqueio_confianca_ate", sa.Date(), nullable=True),
        schema="cadastro",
    )
    op.create_index(
        "ix_clientes_desbloqueio_confianca_ate",
        "clientes",
        ["desbloqueio_confianca_ate"],
        schema="cadastro",
        postgresql_where=sa.text("desbloqueio_confianca_ate IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_clientes_desbloqueio_confianca_ate",
        table_name="clientes",
        schema="cadastro",
    )
    op.drop_column("clientes", "desbloqueio_confianca_ate", schema="cadastro")
