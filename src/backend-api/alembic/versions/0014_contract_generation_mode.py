"""Add generation_mode columns to contracts for monthly installment generation.

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-20

Story 10.1: Monthly Installment Generation with Correction Index.

Adds five columns to the contracts table:
- generation_mode: 'upfront' (all installments created at signing, default)
  or 'monthly' (generated month-by-month by Celery task)
- correction_index: 'igpm' | 'ipca' | 'inpc' | NULL (no correction if null)
- generation_day: 1-28, day of month when the task generates the next installment
- next_generation_date: DATE, when the next installment is generated (advanced)
- monthly_base_value: NUMERIC(15,2), base value the correction index applies to

Constraints enforce: monthly mode requires generation_day, next_generation_date
and monthly_base_value.
"""

import sqlalchemy as sa

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contracts",
        sa.Column(
            "generation_mode",
            sa.Text(),
            server_default=sa.text("'upfront'"),
            nullable=False,
        ),
    )
    op.add_column(
        "contracts", sa.Column("correction_index", sa.Text(), nullable=True)
    )
    op.add_column(
        "contracts", sa.Column("generation_day", sa.SmallInteger(), nullable=True)
    )
    op.add_column(
        "contracts", sa.Column("next_generation_date", sa.Date(), nullable=True)
    )
    op.add_column(
        "contracts", sa.Column("monthly_base_value", sa.Numeric(15, 2), nullable=True)
    )

    op.create_check_constraint(
        "ck_contracts_generation_mode",
        "contracts",
        "generation_mode IN ('upfront', 'monthly')",
    )
    op.create_check_constraint(
        "ck_contracts_correction_index",
        "contracts",
        "correction_index IS NULL OR correction_index IN ('igpm', 'ipca', 'inpc')",
    )
    op.create_check_constraint(
        "ck_contracts_generation_day_range",
        "contracts",
        "generation_day IS NULL OR (generation_day BETWEEN 1 AND 28)",
    )
    op.create_check_constraint(
        "ck_contracts_monthly_requires_fields",
        "contracts",
        "generation_mode <> 'monthly' OR ("
        "  generation_day IS NOT NULL"
        "  AND next_generation_date IS NOT NULL"
        "  AND monthly_base_value IS NOT NULL"
        ")",
    )

    op.create_index(
        "idx_contracts_next_generation",
        "contracts",
        ["next_generation_date"],
        postgresql_where=sa.text(
            "generation_mode = 'monthly' AND deleted_at IS NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index("idx_contracts_next_generation", table_name="contracts")
    op.drop_constraint(
        "ck_contracts_monthly_requires_fields", "contracts", type_="check"
    )
    op.drop_constraint(
        "ck_contracts_generation_day_range", "contracts", type_="check"
    )
    op.drop_constraint(
        "ck_contracts_correction_index", "contracts", type_="check"
    )
    op.drop_constraint("ck_contracts_generation_mode", "contracts", type_="check")
    op.drop_column("contracts", "monthly_base_value")
    op.drop_column("contracts", "next_generation_date")
    op.drop_column("contracts", "generation_day")
    op.drop_column("contracts", "correction_index")
    op.drop_column("contracts", "generation_mode")
