"""Report endpoints (Story 5-5: Simplified DRE + Epic 8: Reports)."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import date
from decimal import Decimal

import structlog
from fastapi import APIRouter, Query, Body
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, text

from app.api.deps import CurrentUserDep, SessionDep
from app.api.v1.schemas.payables import (
    DreDetalhamentoCategoria,
    DreResponse,
    DreSecao,
)
from app.api.v1.schemas.dashboard import (
    CustomReportRequest,
    ReportColumn,
    ReportResponse,
    ReportRow,
    SavedReportCreate,
    SavedReportOut,
)
from app.infrastructure.db.models.asset import Asset
from app.infrastructure.db.models.contract import Contract, Installment
from app.infrastructure.db.models.customer import Customer
from app.infrastructure.db.models.payable import ExpenseCategory, Payable
from app.infrastructure.db.repositories.payable_repo import PayableRepository  # noqa: F401

log = structlog.get_logger()

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/dre", response_model=DreResponse)
async def get_dre(
    session: SessionDep,
    current_user: CurrentUserDep,
    period_start: date = Query(...),
    period_end: date = Query(...),
    asset_id: str | None = Query(None),
    category_id: str | None = Query(None),
) -> DreResponse:
    """Simplified DRE (Demonstrativo de Resultado do Exercicio).

    Aggregates receivables (income) and payables (expenses) by category.
    """
    # ── Income: paid installments in period ──
    income_query = (
        select(
            func.coalesce(func.sum(Installment.paid_value), Decimal("0")).label("total"),
        )
        .join(Contract, Installment.contract_id == Contract.id)
        .where(Contract.excluido_em.is_(None))
        .where(Installment.status.in_(["pago", "pago_aguardando_verificacao"]))
        .where(Installment.payment_date >= period_start)
        .where(Installment.payment_date <= period_end)
    )

    if asset_id:
        income_query = income_query.where(Contract.asset_id == uuid.UUID(asset_id))

    income_result = await session.execute(income_query)
    income_total = income_result.scalar_one() or Decimal("0")

    # Income by contract (no category concept for receivables, group by contract)
    income_by_contract_query = (
        select(
            Contract.id.label("group_id"),
            Contract.contract_number.label("group_name"),
            func.coalesce(func.sum(Installment.paid_value), Decimal("0")).label("total"),
        )
        .join(Contract, Installment.contract_id == Contract.id)
        .where(Contract.excluido_em.is_(None))
        .where(Installment.status.in_(["pago", "pago_aguardando_verificacao"]))
        .where(Installment.payment_date >= period_start)
        .where(Installment.payment_date <= period_end)
        .group_by(Contract.id, Contract.contract_number)
    )

    if asset_id:
        income_by_contract_query = income_by_contract_query.where(
            Contract.asset_id == uuid.UUID(asset_id)
        )

    income_breakdown_result = await session.execute(income_by_contract_query)
    income_breakdown = [
        DreDetalhamentoCategoria(
            categoria_id=str(row.group_id),
            categoria_nome=row.group_name,
            total=row.total,
        )
        for row in income_breakdown_result.all()
    ]

    # ── Expenses: paid payables in period ──
    expense_query = (
        select(
            func.coalesce(func.sum(Payable.amount), Decimal("0")).label("total"),
        )
        .where(Payable.excluido_em.is_(None))
        .where(Payable.status == "pago")
        .where(Payable.payment_date >= period_start)
        .where(Payable.payment_date <= period_end)
    )

    cat_id = uuid.UUID(category_id) if category_id else None
    if cat_id:
        expense_query = expense_query.where(Payable.category_id == cat_id)

    expense_result = await session.execute(expense_query)
    expense_total = expense_result.scalar_one() or Decimal("0")

    # Expenses by category
    expense_by_cat_query = (
        select(
            Payable.category_id,
            func.coalesce(func.sum(Payable.amount), Decimal("0")).label("total"),
        )
        .where(Payable.excluido_em.is_(None))
        .where(Payable.status == "pago")
        .where(Payable.payment_date >= period_start)
        .where(Payable.payment_date <= period_end)
        .group_by(Payable.category_id)
    )

    if cat_id:
        expense_by_cat_query = expense_by_cat_query.where(Payable.category_id == cat_id)

    expense_breakdown_result = await session.execute(expense_by_cat_query)
    expense_rows = expense_breakdown_result.all()

    # Fetch category names
    cat_ids = [row.category_id for row in expense_rows if row.category_id]
    cat_names: dict[str, str] = {}
    if cat_ids:
        cat_result = await session.execute(
            select(ExpenseCategory.id, ExpenseCategory.name).where(
                ExpenseCategory.id.in_(cat_ids)
            )
        )
        cat_names = {str(r.id): r.name for r in cat_result.all()}

    expense_breakdown = [
        DreDetalhamentoCategoria(
            categoria_id=str(row.category_id) if row.category_id else None,
            categoria_nome=cat_names.get(str(row.category_id), "Sem categoria") if row.category_id else "Sem categoria",
            total=row.total,
        )
        for row in expense_rows
    ]

    net_result = income_total - expense_total

    return DreResponse(
        periodo_inicio=period_start,
        periodo_fim=period_end,
        receitas=DreSecao(total=income_total, por_categoria=income_breakdown),
        despesas=DreSecao(total=expense_total, por_categoria=expense_breakdown),
        resultado_liquido=net_result,
    )


# ── Epic 8: Additional report endpoints ──


def _build_csv_response(columns: list[ReportColumn], rows: list[ReportRow], filename: str) -> StreamingResponse:
    """Build a CSV StreamingResponse from report data."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([c.label for c in columns])
    for row in rows:
        writer.writerow([row.values.get(c.key, "") for c in columns])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/receivables", response_model=ReportResponse)
async def get_receivables_report(
    session: SessionDep,
    current_user: CurrentUserDep,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    status: str | None = Query(None),
    customer_id: str | None = Query(None),
    export: str | None = Query(None),
) -> ReportResponse | StreamingResponse:
    """Detailed receivables report with filters."""
    q = (
        select(
            Installment.id,
            Customer.nome_completo.label("customer_name"),
            Contract.contract_number,
            Installment.due_date,
            Installment.current_value,
            Installment.paid_value,
            Installment.status,
            Installment.payment_date,
        )
        .join(Contract, Installment.contract_id == Contract.id)
        .join(Customer, Contract.customer_id == Customer.id)
        .where(Contract.excluido_em.is_(None), Customer.excluido_em.is_(None))
    )

    if date_from:
        q = q.where(Installment.due_date >= date_from)
    if date_to:
        q = q.where(Installment.due_date <= date_to)
    if status and status != "todos":
        q = q.where(Installment.status == status)
    if customer_id:
        q = q.where(Contract.customer_id == uuid.UUID(customer_id))

    q = q.order_by(Installment.due_date.desc()).limit(500)
    result = await session.execute(q)
    rows_raw = result.all()

    columns = [
        ReportColumn(key="customer_name", label="Cliente"),
        ReportColumn(key="contract_number", label="Contrato"),
        ReportColumn(key="due_date", label="Vencimento", format="date"),
        ReportColumn(key="current_value", label="Valor", format="currency"),
        ReportColumn(key="paid_value", label="Pago", format="currency"),
        ReportColumn(key="status", label="Status"),
        ReportColumn(key="payment_date", label="Data Pagamento", format="date"),
    ]

    rows = [
        ReportRow(values={
            "customer_name": r.customer_name,
            "contract_number": r.contract_number,
            "due_date": str(r.due_date) if r.due_date else "",
            "current_value": str(r.current_value),
            "paid_value": str(r.paid_value),
            "status": r.status,
            "payment_date": str(r.payment_date) if r.payment_date else "",
        })
        for r in rows_raw
    ]

    if export == "csv":
        return _build_csv_response(columns, rows, "receivables.csv")

    return ReportResponse(columns=columns, rows=rows, total=len(rows))


@router.get("/customers", response_model=ReportResponse)
async def get_customers_report(
    session: SessionDep,
    current_user: CurrentUserDep,
    export: str | None = Query(None),
) -> ReportResponse | StreamingResponse:
    """Customer report with aggregated metrics."""
    try:
        mv_q = text("""
            SELECT customer_id, customer_name, total_contracts, total_revenue,
                   avg_delay_days, overdue_count, overdue_amount, score
            FROM mv_customer_metrics
            ORDER BY total_revenue DESC
            LIMIT 200
        """)
        result = await session.execute(mv_q)
        rows_raw = result.all()
    except Exception:
        # Fallback
        q = (
            select(
                Customer.id.label("customer_id"),
                Customer.nome_completo.label("customer_name"),
                func.count(func.distinct(Contract.id)).label("total_contracts"),
                func.coalesce(func.sum(Installment.paid_value), Decimal("0")).label("total_revenue"),
                Customer.score,
            )
            .outerjoin(Contract, Contract.customer_id == Customer.id)
            .outerjoin(Installment, Installment.contract_id == Contract.id)
            .where(Customer.excluido_em.is_(None))
            .group_by(Customer.id, Customer.nome_completo, Customer.score)
            .order_by(func.sum(Installment.paid_value).desc().nulls_last())
            .limit(200)
        )
        result = await session.execute(q)
        rows_raw = result.all()

    columns = [
        ReportColumn(key="customer_name", label="Cliente"),
        ReportColumn(key="total_contracts", label="Contratos", format="number"),
        ReportColumn(key="total_revenue", label="Receita Total", format="currency"),
        ReportColumn(key="overdue_amount", label="Vencido", format="currency"),
        ReportColumn(key="score", label="Score", format="number"),
    ]

    rows = [
        ReportRow(values={
            "customer_name": r.customer_name,
            "total_contracts": str(r.total_contracts),
            "total_revenue": str(r.total_revenue),
            "overdue_amount": str(getattr(r, "overdue_amount", "0")),
            "score": str(r.score),
        })
        for r in rows_raw
    ]

    if export == "csv":
        return _build_csv_response(columns, rows, "customers.csv")

    return ReportResponse(columns=columns, rows=rows, total=len(rows))


@router.get("/vehicles", response_model=ReportResponse)
async def get_vehicles_report(
    session: SessionDep,
    current_user: CurrentUserDep,
    export: str | None = Query(None),
) -> ReportResponse | StreamingResponse:
    """Vehicle report with ROI metrics."""
    try:
        mv_q = text("""
            SELECT vehicle_id, display_name, fipe_value, purchase_value,
                   total_revenue, total_expenses, roi_percent
            FROM mv_vehicle_metrics
            ORDER BY roi_percent DESC
            LIMIT 200
        """)
        result = await session.execute(mv_q)
        rows_raw = result.all()
    except Exception:
        q = (
            select(
                Asset.id.label("vehicle_id"),
                Asset.display_name,
                func.coalesce(func.sum(Installment.paid_value), Decimal("0")).label("total_revenue"),
            )
            .outerjoin(Contract, Contract.asset_id == Asset.id)
            .outerjoin(Installment, Installment.contract_id == Contract.id)
            .where(Asset.excluido_em.is_(None))
            .group_by(Asset.id, Asset.display_name)
            .order_by(func.sum(Installment.paid_value).desc().nulls_last())
            .limit(200)
        )
        result = await session.execute(q)
        rows_raw = result.all()

    columns = [
        ReportColumn(key="display_name", label="Veículo"),
        ReportColumn(key="fipe_value", label="FIPE", format="currency"),
        ReportColumn(key="purchase_value", label="Compra", format="currency"),
        ReportColumn(key="total_revenue", label="Receita", format="currency"),
        ReportColumn(key="total_expenses", label="Despesas", format="currency"),
        ReportColumn(key="roi_percent", label="ROI %", format="percent"),
    ]

    rows = [
        ReportRow(values={
            "display_name": r.display_name,
            "fipe_value": str(getattr(r, "fipe_value", "0")),
            "purchase_value": str(getattr(r, "purchase_value", "0")),
            "total_revenue": str(r.total_revenue),
            "total_expenses": str(getattr(r, "total_expenses", "0")),
            "roi_percent": str(getattr(r, "roi_percent", "0")),
        })
        for r in rows_raw
    ]

    if export == "csv":
        return _build_csv_response(columns, rows, "vehicles.csv")

    return ReportResponse(columns=columns, rows=rows, total=len(rows))


@router.post("/custom", response_model=ReportResponse)
async def run_custom_report(
    session: SessionDep,
    current_user: CurrentUserDep,
    request: CustomReportRequest = Body(...),
) -> ReportResponse:
    """Custom report builder: accepts dimension/metric/filter params and returns tabular data."""
    # Map dimensions to table columns
    dimension_map = {
        "customer_name": ("cadastro.clientes", "nome_completo"),
        "contract_number": ("contrato.contratos", "numero"),
        "contract_status": ("contrato.contratos", "status"),
        "due_month": ("financeiro.titulos_receber", "date_trunc('month', data_vencimento)"),
        "asset_name": ("veiculos.veiculos", "fipe_marca || ' ' || fipe_modelo"),
        "installment_status": ("financeiro.titulos_receber", "status"),
    }

    measure_map = {
        "count": "COUNT(*)",
        "sum_value": "COALESCE(SUM(installments.current_value), 0)",
        "sum_paid": "COALESCE(SUM(installments.paid_value), 0)",
        "avg_value": "COALESCE(AVG(installments.current_value), 0)",
    }

    # Validate inputs
    valid_dims = [d for d in request.dimensions if d in dimension_map]
    valid_measures = [m for m in request.measures if m in measure_map]

    if not valid_dims and not valid_measures:
        return ReportResponse(columns=[], rows=[], total=0)

    # Build SELECT
    select_parts = []
    group_parts = []
    for d in valid_dims:
        tbl, col = dimension_map[d]
        if "(" in col:
            select_parts.append(f"{col} AS {d}")
        else:
            select_parts.append(f"{tbl}.{col} AS {d}")
        group_parts.append(f"{tbl}.{col}" if "(" not in col else col)

    for m in valid_measures:
        select_parts.append(f"{measure_map[m]} AS {m}")

    from_clause = """
        financeiro.titulos_receber
        JOIN contrato.contratos ON financeiro.titulos_receber.contrato_id = contrato.contratos.id
        JOIN cadastro.clientes ON contrato.contratos.cliente_id = cadastro.clientes.id
        LEFT JOIN veiculos.veiculos ON contrato.contratos.veiculo_id = veiculos.veiculos.id
    """

    where_parts = ["contrato.contratos.excluido_em IS NULL"]
    params: dict = {}
    if request.filters:
        if request.filters.date_from:
            where_parts.append("installments.due_date >= :date_from")
            params["date_from"] = request.filters.date_from
        if request.filters.date_to:
            where_parts.append("installments.due_date <= :date_to")
            params["date_to"] = request.filters.date_to
        if request.filters.status:
            where_parts.append("installments.status = :status")
            params["status"] = request.filters.status
        if request.filters.customer_id:
            where_parts.append("contracts.customer_id = :customer_id")
            params["customer_id"] = uuid.UUID(request.filters.customer_id)

    sql = f"""
        SELECT {', '.join(select_parts)}
        FROM {from_clause}
        WHERE {' AND '.join(where_parts)}
    """
    if group_parts:
        sql += f" GROUP BY {', '.join(group_parts)}"
    sql += f" LIMIT {min(request.limit, 500)}"

    result = await session.execute(text(sql), params)
    rows_raw = result.all()
    columns = [
        ReportColumn(key=k, label=k.replace("_", " ").title())
        for k in valid_dims + valid_measures
    ]

    rows = [
        ReportRow(values={k: str(v) for k, v in zip(valid_dims + valid_measures, r)})
        for r in rows_raw
    ]

    return ReportResponse(columns=columns, rows=rows, total=len(rows))


@router.post("/saved", response_model=SavedReportOut)
async def save_report(
    session: SessionDep,
    current_user: CurrentUserDep,
    payload: SavedReportCreate = Body(...),
) -> SavedReportOut:
    """Save a custom report definition."""
    from app.infrastructure.db.base import Base  # noqa: F811

    new_id = uuid.uuid4()
    await session.execute(
        text("""
            INSERT INTO saved_reports (id, name, description, owner_user_id, is_shared, definition)
            VALUES (:id, :name, :desc, :owner, :shared, :defn::jsonb)
        """),
        {
            "id": new_id,
            "name": payload.name,
            "desc": payload.description,
            "owner": current_user.id,
            "shared": payload.is_shared,
            "defn": __import__("json").dumps(payload.definition),
        },
    )
    await session.commit()

    return SavedReportOut(
        id=str(new_id),
        name=payload.name,
        description=payload.description,
        is_shared=payload.is_shared,
        definition=payload.definition,
        created_at=str(date.today()),
    )


@router.get("/saved", response_model=list[SavedReportOut])
async def list_saved_reports(
    session: SessionDep,
    current_user: CurrentUserDep,
) -> list[SavedReportOut]:
    """List saved reports for the current user (own + shared)."""
    result = await session.execute(
        text("""
            SELECT id, name, description, is_shared, definition, created_at
            FROM saved_reports
            WHERE owner_user_id = :uid OR is_shared = true
            ORDER BY created_at DESC
        """),
        {"uid": current_user.id},
    )
    rows = result.all()
    return [
        SavedReportOut(
            id=str(r.id),
            name=r.name,
            description=r.description,
            is_shared=r.is_shared,
            definition=r.definition if isinstance(r.definition, dict) else {},
            created_at=str(r.created_at)[:10],
        )
        for r in rows
    ]
