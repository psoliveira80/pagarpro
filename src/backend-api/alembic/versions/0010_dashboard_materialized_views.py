"""Dashboard materialized views and saved_reports table

Revision ID: 0010
Revises: 0008
Create Date: 2026-05-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision = "0010"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── mv_receivables_summary ──
    op.execute("""
        CREATE MATERIALIZED VIEW mv_receivables_summary AS
        SELECT
            date_trunc('month', i.due_date)::date AS period,
            COALESCE(SUM(i.current_value), 0) AS total_due,
            COALESCE(SUM(CASE WHEN i.status IN ('pago', 'pago_aguardando_verificacao') THEN i.paid_value ELSE 0 END), 0) AS total_received,
            COALESCE(SUM(CASE WHEN i.status = 'vencido' THEN i.current_value ELSE 0 END), 0) AS total_overdue,
            COUNT(*) AS installment_count
        FROM installments i
        JOIN contracts c ON i.contract_id = c.id
        WHERE c.deleted_at IS NULL
        GROUP BY date_trunc('month', i.due_date)::date
        ORDER BY period DESC
    """)
    op.execute("""
        CREATE UNIQUE INDEX idx_mv_receivables_summary_period
        ON mv_receivables_summary (period)
    """)

    # ── mv_customer_metrics ──
    op.execute("""
        CREATE MATERIALIZED VIEW mv_customer_metrics AS
        SELECT
            c2.id AS customer_id,
            c2.full_name AS customer_name,
            COUNT(DISTINCT c.id) AS total_contracts,
            COALESCE(SUM(i.paid_value), 0) AS total_revenue,
            COALESCE(
                AVG(
                    CASE WHEN i.payment_date IS NOT NULL AND i.payment_date > i.due_date
                    THEN i.payment_date - i.due_date
                    ELSE 0 END
                ), 0
            )::numeric(10,1) AS avg_delay_days,
            COUNT(CASE WHEN i.status = 'vencido' THEN 1 END) AS overdue_count,
            COALESCE(SUM(CASE WHEN i.status = 'vencido' THEN i.current_value ELSE 0 END), 0) AS overdue_amount,
            c2.score AS score
        FROM customers c2
        LEFT JOIN contracts c ON c.customer_id = c2.id AND c.deleted_at IS NULL
        LEFT JOIN installments i ON i.contract_id = c.id
        WHERE c2.deleted_at IS NULL
        GROUP BY c2.id, c2.full_name, c2.score
    """)
    op.execute("""
        CREATE UNIQUE INDEX idx_mv_customer_metrics_customer_id
        ON mv_customer_metrics (customer_id)
    """)

    # ── mv_vehicle_metrics (asset ROI) ──
    op.execute("""
        CREATE MATERIALIZED VIEW mv_vehicle_metrics AS
        SELECT
            a.id AS vehicle_id,
            a.display_name,
            COALESCE((a.metadata->>'fipe_value')::numeric, 0) AS fipe_value,
            COALESCE((a.metadata->>'purchase_value')::numeric, 0) AS purchase_value,
            COALESCE(SUM(i.paid_value), 0) AS total_revenue,
            COALESCE(
                (SELECT SUM(p.amount) FROM payables p WHERE p.status = 'pago' AND p.deleted_at IS NULL AND p.notes LIKE '%' || a.id::text || '%'),
                0
            ) AS total_expenses,
            CASE
                WHEN COALESCE((a.metadata->>'purchase_value')::numeric, 0) > 0
                THEN ROUND(
                    (COALESCE(SUM(i.paid_value), 0) - COALESCE((SELECT SUM(p.amount) FROM payables p WHERE p.status = 'pago' AND p.deleted_at IS NULL AND p.notes LIKE '%' || a.id::text || '%'), 0))
                    / (a.metadata->>'purchase_value')::numeric * 100, 2
                )
                ELSE 0
            END AS roi_percent,
            a.created_at AS in_service_since
        FROM assets a
        LEFT JOIN contracts c ON c.asset_id = a.id AND c.deleted_at IS NULL
        LEFT JOIN installments i ON i.contract_id = c.id AND i.status IN ('pago', 'pago_aguardando_verificacao')
        WHERE a.deleted_at IS NULL
        GROUP BY a.id, a.display_name, a.metadata, a.created_at
    """)
    op.execute("""
        CREATE UNIQUE INDEX idx_mv_vehicle_metrics_vehicle_id
        ON mv_vehicle_metrics (vehicle_id)
    """)

    # ── saved_reports table ──
    op.create_table(
        "saved_reports",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("is_shared", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("definition", JSONB, nullable=False),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("saved_reports")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_vehicle_metrics CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_customer_metrics CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_receivables_summary CASCADE")
