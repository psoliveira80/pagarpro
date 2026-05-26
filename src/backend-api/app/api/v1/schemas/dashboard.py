"""Dashboard response schemas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class KpiCard(BaseModel):
    label: str
    value: Decimal | int | float
    previous_value: Decimal | int | float | None = None
    delta_percent: float | None = None
    format: str = "currency"  # currency, number, percent


class DashboardSummary(BaseModel):
    total_receivable: Decimal
    total_overdue: Decimal
    received_this_month: Decimal
    active_contracts: int
    fleet_value: Decimal
    overdue_percent: float


class ReceivablesTrendPoint(BaseModel):
    period: str  # YYYY-MM
    total_due: Decimal
    total_received: Decimal
    total_overdue: Decimal


class ReceivablesTrendResponse(BaseModel):
    data: list[ReceivablesTrendPoint]


class AgingBucket(BaseModel):
    bucket: str
    count: int
    amount: Decimal


class AgingResponse(BaseModel):
    buckets: list[AgingBucket]


class TopDefaulter(BaseModel):
    customer_id: str
    customer_name: str
    overdue_amount: Decimal
    overdue_count: int
    score: int


class TopDefaultersResponse(BaseModel):
    items: list[TopDefaulter]


class CustomerDashboard(BaseModel):
    customer_id: str
    customer_name: str
    total_contracted: Decimal
    total_paid: Decimal
    total_open: Decimal
    total_overdue: Decimal
    score: int
    punctuality_percent: float
    active_contracts: int


class VehicleDashboard(BaseModel):
    vehicle_id: str
    display_name: str
    purchase_value: Decimal
    fipe_value: Decimal
    total_revenue: Decimal
    total_expenses: Decimal
    roi_percent: float
    accumulated_profit: Decimal
    in_service_since: str | None = None


# ── Report schemas ──

class ReportFilter(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    customer_id: str | None = None
    status: str | None = None
    asset_id: str | None = None


class ReportColumn(BaseModel):
    key: str
    label: str
    format: str = "text"  # text, currency, number, date, percent


class ReportRow(BaseModel):
    values: dict


class ReportResponse(BaseModel):
    columns: list[ReportColumn]
    rows: list[ReportRow]
    total: int


class CustomReportRequest(BaseModel):
    dimensions: list[str]
    measures: list[str]
    filters: ReportFilter | None = None
    limit: int = 100


class SavedReportCreate(BaseModel):
    name: str
    description: str | None = None
    is_shared: bool = False
    definition: dict


class SavedReportOut(BaseModel):
    id: str
    name: str
    description: str | None
    is_shared: bool
    definition: dict
    created_at: str
