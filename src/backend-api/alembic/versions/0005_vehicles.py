"""Vehicles, vehicle_acquisitions, tracker_devices tables + seed vehicle module and permissions

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- vehicles ---
    op.create_table(
        "vehicles",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("plate", sa.Text(), unique=True, nullable=False),
        sa.Column("brand", sa.Text(), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=False),
        sa.Column("model_year", sa.Integer(), nullable=False),
        sa.Column("fab_year", sa.Integer(), nullable=False),
        sa.Column("color", sa.Text(), nullable=True),
        sa.Column("chassi", sa.Text(), nullable=True),
        sa.Column("renavam", sa.Text(), nullable=True),
        sa.Column("fipe_code", sa.Text(), nullable=True),
        sa.Column("fipe_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'disponivel'")),
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("asset_id", sa.Uuid(), sa.ForeignKey("assets.id"), unique=True, nullable=True),
        sa.Column("tracker_id", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB(), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("idx_vehicles_plate", "vehicles", ["plate"])
    op.create_index("idx_vehicles_customer_id", "vehicles", ["customer_id"])
    op.create_index("idx_vehicles_status", "vehicles", ["status"])

    # --- vehicle_acquisitions ---
    op.create_table(
        "vehicle_acquisitions",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("vehicle_id", sa.Uuid(), sa.ForeignKey("vehicles.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("acquisition_type", sa.Text(), nullable=False),
        sa.Column("purchase_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("purchase_date", sa.Date(), nullable=True),
        sa.Column("financing_bank", sa.Text(), nullable=True),
        sa.Column("financing_contract", sa.Text(), nullable=True),
        sa.Column("financing_installments", sa.Integer(), nullable=True),
        sa.Column("financing_monthly_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- tracker_devices ---
    op.create_table(
        "tracker_devices",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("vehicle_id", sa.Uuid(), sa.ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("config", JSONB(), nullable=True),
        sa.Column("last_position", JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("provider", "device_id", name="uq_tracker_provider_device"),
    )
    op.create_index("idx_tracker_devices_vehicle_id", "tracker_devices", ["vehicle_id"])

    # --- seed active_modules row for vehicle ---
    op.execute(
        "INSERT INTO active_modules (module_id, is_active, config) "
        "VALUES ('vehicle', true, '{}'::jsonb) "
        "ON CONFLICT (module_id) DO NOTHING"
    )

    # --- seed permissions for vehicle module ---
    op.execute(
        "INSERT INTO permissions (id, code, description) VALUES "
        "(gen_random_uuid(), 'vehicles.read', 'View vehicles'), "
        "(gen_random_uuid(), 'vehicles.create', 'Create vehicles'), "
        "(gen_random_uuid(), 'vehicles.update', 'Update vehicles'), "
        "(gen_random_uuid(), 'vehicles.delete', 'Delete vehicles'), "
        "(gen_random_uuid(), 'vehicles.block', 'Block vehicle via GPS'), "
        "(gen_random_uuid(), 'vehicles.unblock', 'Unblock vehicle via GPS'), "
        "(gen_random_uuid(), 'vehicles.import', 'Import vehicles from Excel') "
        "ON CONFLICT (code) DO NOTHING"
    )


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE code LIKE 'vehicles.%'")
    op.execute("DELETE FROM active_modules WHERE module_id = 'vehicle'")
    op.drop_table("tracker_devices")
    op.drop_table("vehicle_acquisitions")
    op.drop_table("vehicles")
