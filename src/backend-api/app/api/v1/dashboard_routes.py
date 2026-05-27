"""Dashboard endpoints (Epic 8: Dashboards & Reports).

Tenant-scoped: every query filters by current_user.empresa_id. Asset abstraction
layer was dropped in migration 0015; vehicle data comes from veiculos.veiculos
directly via the mv_metricas_veiculos materialized view.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import structlog
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select, case

from app.api.deps import CurrentUserDep, SessionDep
from app.api.v1.schemas.dashboard import (
    AgingBucket,
    AgingResponse,
    CustomerDashboard,
    DashboardSummary,
    ReceivablesTrendPoint,
    ReceivablesTrendResponse,
    TopDefaulter,
    TopDefaultersResponse,
    VehicleDashboard,
)
from app.infrastructure.db.models.contract import Contract, Installment
from app.infrastructure.db.models.customer import Customer
from app.infrastructure.db.models.veiculos import Veiculo

log = structlog.get_logger()

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    session: SessionDep,
    current_user: CurrentUserDep,
) -> DashboardSummary:
    """Main dashboard KPIs — escopo da empresa do usuário."""
    today = date.today()
    month_start = today.replace(day=1)
    empresa_id = current_user.empresa_id

    receivable_q = select(
        func.coalesce(func.sum(Installment.current_value), Decimal("0")),
    ).join(Contract, Installment.contract_id == Contract.id).where(
        Contract.excluido_em.is_(None),
        Installment.empresa_id == empresa_id,
        Installment.status.in_(["em_aberto", "vencido"]),
    )
    total_receivable = (await session.execute(receivable_q)).scalar_one()

    overdue_q = select(
        func.coalesce(func.sum(Installment.current_value), Decimal("0")),
    ).join(Contract, Installment.contract_id == Contract.id).where(
        Contract.excluido_em.is_(None),
        Installment.empresa_id == empresa_id,
        Installment.status == "vencido",
    )
    total_overdue = (await session.execute(overdue_q)).scalar_one()

    received_q = select(
        func.coalesce(func.sum(Installment.paid_value), Decimal("0")),
    ).join(Contract, Installment.contract_id == Contract.id).where(
        Contract.excluido_em.is_(None),
        Installment.empresa_id == empresa_id,
        Installment.status.in_(["pago", "pago_aguardando_verificacao"]),
        Installment.payment_date >= month_start,
        Installment.payment_date <= today,
    )
    received_month = (await session.execute(received_q)).scalar_one()

    contracts_q = select(func.count()).select_from(Contract).where(
        Contract.excluido_em.is_(None),
        Contract.empresa_id == empresa_id,
        Contract.status == "vigente",
    )
    active_contracts = (await session.execute(contracts_q)).scalar_one()

    fleet_q = select(
        func.coalesce(func.sum(Veiculo.fipe_valor_atual), Decimal("0")),
    ).where(
        Veiculo.excluido_em.is_(None),
        Veiculo.empresa_id == empresa_id,
    )
    fleet_value = (await session.execute(fleet_q)).scalar_one()

    overdue_pct = float(total_overdue / total_receivable * 100) if total_receivable > 0 else 0.0

    return DashboardSummary(
        total_receivable=total_receivable,
        total_overdue=total_overdue,
        received_this_month=received_month,
        active_contracts=active_contracts,
        fleet_value=fleet_value,
        overdue_percent=round(overdue_pct, 1),
    )


@router.get("/charts/receivables-trend", response_model=ReceivablesTrendResponse)
async def get_receivables_trend(
    session: SessionDep,
    current_user: CurrentUserDep,
    months: int = Query(12, ge=1, le=24),
) -> ReceivablesTrendResponse:
    """Tendência mensal de recebíveis dos últimos N meses (escopo da empresa)."""
    empresa_id = current_user.empresa_id
    cutoff = date.today().replace(day=1) - timedelta(days=months * 31)

    period_expr = func.date_trunc("month", Installment.due_date)

    q = (
        select(
            period_expr.label("period"),
            func.coalesce(func.sum(Installment.current_value), Decimal("0")).label("total_due"),
            func.coalesce(
                func.sum(
                    case(
                        (Installment.status.in_(["pago", "pago_aguardando_verificacao"]), Installment.paid_value),
                        else_=Decimal("0"),
                    )
                ),
                Decimal("0"),
            ).label("total_received"),
            func.coalesce(
                func.sum(
                    case(
                        (Installment.status == "vencido", Installment.current_value),
                        else_=Decimal("0"),
                    )
                ),
                Decimal("0"),
            ).label("total_overdue"),
        )
        .join(Contract, Installment.contract_id == Contract.id)
        .where(
            Contract.excluido_em.is_(None),
            Installment.empresa_id == empresa_id,
            Installment.due_date >= cutoff,
        )
        .group_by(period_expr)
        .order_by(period_expr.desc())
        .limit(months)
    )
    result = await session.execute(q)
    rows = result.all()

    data = [
        ReceivablesTrendPoint(
            period=str(row.period)[:7] if hasattr(row.period, "isoformat") else str(row.period)[:7],
            total_due=row.total_due,
            total_received=row.total_received,
            total_overdue=row.total_overdue,
        )
        for row in reversed(rows)
    ]
    return ReceivablesTrendResponse(data=data)


@router.get("/charts/overdue-aging", response_model=AgingResponse)
async def get_overdue_aging(
    session: SessionDep,
    current_user: CurrentUserDep,
) -> AgingResponse:
    """Faixas de aging das parcelas vencidas (escopo da empresa)."""
    today = date.today()
    q = (
        select(
            Installment.due_date,
            Installment.current_value,
        )
        .join(Contract, Installment.contract_id == Contract.id)
        .where(
            Contract.excluido_em.is_(None),
            Installment.empresa_id == current_user.empresa_id,
            Installment.status == "vencido",
        )
    )
    result = await session.execute(q)
    rows = result.all()

    buckets_def = [
        ("1-15 dias", 1, 15),
        ("16-30 dias", 16, 30),
        ("31-60 dias", 31, 60),
        ("60+ dias", 61, 9999),
    ]
    bucket_data = {b[0]: {"count": 0, "amount": Decimal("0")} for b in buckets_def}

    for row in rows:
        days = (today - row.due_date).days
        for label, lo, hi in buckets_def:
            if lo <= days <= hi:
                bucket_data[label]["count"] += 1
                bucket_data[label]["amount"] += row.current_value
                break

    return AgingResponse(
        buckets=[
            AgingBucket(bucket=label, count=d["count"], amount=d["amount"])
            for label, d in bucket_data.items()
        ]
    )


@router.get("/charts/top-defaulters", response_model=TopDefaultersResponse)
async def get_top_defaulters(
    session: SessionDep,
    current_user: CurrentUserDep,
    limit: int = Query(10, ge=1, le=50),
) -> TopDefaultersResponse:
    """Top N clientes por valor vencido (escopo da empresa)."""
    empresa_id = current_user.empresa_id

    q = (
        select(
            Customer.id.label("customer_id"),
            Customer.nome_completo.label("customer_name"),
            func.coalesce(func.sum(Installment.current_value), Decimal("0")).label("overdue_amount"),
            func.count(Installment.id).label("overdue_count"),
            Customer.score,
        )
        .join(Contract, Contract.customer_id == Customer.id)
        .join(Installment, Installment.contract_id == Contract.id)
        .where(
            Customer.excluido_em.is_(None),
            Customer.empresa_id == empresa_id,
            Contract.excluido_em.is_(None),
            Installment.empresa_id == empresa_id,
            Installment.status == "vencido",
        )
        .group_by(Customer.id, Customer.nome_completo, Customer.score)
        .order_by(func.sum(Installment.current_value).desc())
        .limit(limit)
    )
    result = await session.execute(q)
    rows = result.all()
    items = [
        TopDefaulter(
            customer_id=str(r.customer_id),
            customer_name=r.customer_name,
            overdue_amount=r.overdue_amount,
            overdue_count=r.overdue_count,
            score=r.score,
        )
        for r in rows
    ]

    return TopDefaultersResponse(items=items)


@router.get("/customer/{customer_id}", response_model=CustomerDashboard)
async def get_customer_dashboard(
    customer_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> CustomerDashboard:
    """KPIs específicos do cliente (somente se pertence à empresa do usuário)."""
    cid = uuid.UUID(customer_id)
    empresa_id = current_user.empresa_id

    cust = (await session.execute(
        select(Customer).where(
            Customer.id == cid,
            Customer.empresa_id == empresa_id,
            Customer.excluido_em.is_(None),
        )
    )).scalar_one_or_none()
    if not cust:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    contracted_q = select(
        func.coalesce(func.sum(Contract.total_value), Decimal("0"))
    ).where(
        Contract.customer_id == cid,
        Contract.empresa_id == empresa_id,
        Contract.excluido_em.is_(None),
    )
    total_contracted = (await session.execute(contracted_q)).scalar_one()

    base = (
        select(
            func.coalesce(
                func.sum(case((Installment.status.in_(["pago", "pago_aguardando_verificacao"]), Installment.paid_value), else_=Decimal("0"))),
                Decimal("0"),
            ).label("total_paid"),
            func.coalesce(
                func.sum(case((Installment.status == "em_aberto", Installment.current_value), else_=Decimal("0"))),
                Decimal("0"),
            ).label("total_open"),
            func.coalesce(
                func.sum(case((Installment.status == "vencido", Installment.current_value), else_=Decimal("0"))),
                Decimal("0"),
            ).label("total_overdue"),
        )
        .join(Contract, Installment.contract_id == Contract.id)
        .where(
            Contract.customer_id == cid,
            Contract.empresa_id == empresa_id,
            Contract.excluido_em.is_(None),
        )
    )
    agg = (await session.execute(base)).one()

    twelve_months_ago = date.today() - timedelta(days=365)
    punct_q = (
        select(
            func.count().label("total_paid_count"),
            func.count().filter(Installment.payment_date <= Installment.due_date).label("on_time"),
        )
        .join(Contract, Installment.contract_id == Contract.id)
        .where(
            Contract.customer_id == cid,
            Contract.empresa_id == empresa_id,
            Contract.excluido_em.is_(None),
            Installment.status.in_(["pago", "pago_aguardando_verificacao"]),
            Installment.payment_date >= twelve_months_ago,
        )
    )
    punct = (await session.execute(punct_q)).one()
    punct_pct = (punct.on_time / punct.total_paid_count * 100) if punct.total_paid_count > 0 else 100.0

    active_q = select(func.count()).select_from(Contract).where(
        Contract.customer_id == cid,
        Contract.empresa_id == empresa_id,
        Contract.excluido_em.is_(None),
        Contract.status == "vigente",
    )
    active = (await session.execute(active_q)).scalar_one()

    return CustomerDashboard(
        customer_id=str(cust.id),
        customer_name=cust.nome_completo,
        total_contracted=total_contracted,
        total_paid=agg.total_paid,
        total_open=agg.total_open,
        total_overdue=agg.total_overdue,
        score=cust.score,
        punctuality_percent=round(float(punct_pct), 1),
        active_contracts=active,
    )


@router.get("/vehicle/{vehicle_id}", response_model=VehicleDashboard)
async def get_vehicle_dashboard(
    vehicle_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> VehicleDashboard:
    """KPIs específicos do veículo (somente se pertence à empresa do usuário)."""
    vid = uuid.UUID(vehicle_id)
    empresa_id = current_user.empresa_id

    vehicle = (await session.execute(
        select(Veiculo).where(
            Veiculo.id == vid,
            Veiculo.empresa_id == empresa_id,
            Veiculo.excluido_em.is_(None),
        )
    )).scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Veículo não encontrado")

    display_name = (
        f"{vehicle.fipe_marca or ''} {vehicle.fipe_modelo or ''} ({vehicle.placa})".strip()
    )
    fipe_value = vehicle.fipe_valor_atual or Decimal("0")

    # Aquisição (valor de compra)
    from app.infrastructure.db.models.veiculos import AquisicaoVeiculo
    acq = (await session.execute(
        select(AquisicaoVeiculo).where(
            AquisicaoVeiculo.veiculo_id == vid,
            AquisicaoVeiculo.empresa_id == empresa_id,
        )
    )).scalar_one_or_none()
    purchase_value = acq.valor_aquisicao if acq and acq.valor_aquisicao else Decimal("0")

    # Receita: parcelas pagas de contratos deste veículo
    rev_q = select(
        func.coalesce(func.sum(Installment.paid_value), Decimal("0"))
    ).join(Contract, Installment.contract_id == Contract.id).where(
        Contract.veiculo_id == vid,
        Contract.empresa_id == empresa_id,
        Contract.excluido_em.is_(None),
        Installment.status.in_(["pago", "pago_aguardando_verificacao"]),
    )
    total_revenue = (await session.execute(rev_q)).scalar_one()

    total_expenses = Decimal("0")  # Despesas vinculadas ao veículo via titulos_pagar.veiculo_id (Epic 13)
    profit = total_revenue - total_expenses
    roi = float(profit / purchase_value * 100) if purchase_value > 0 else 0.0

    return VehicleDashboard(
        vehicle_id=str(vehicle.id),
        display_name=display_name,
        purchase_value=purchase_value,
        fipe_value=fipe_value,
        total_revenue=total_revenue,
        total_expenses=total_expenses,
        roi_percent=round(roi, 2),
        accumulated_profit=profit,
        in_service_since=str(vehicle.criado_em)[:10] if vehicle.criado_em else None,
    )


@router.post("/admin/refresh-views")
async def refresh_views(
    current_user: CurrentUserDep,
) -> dict:
    """Aciona refresh manual das materialized views.

    Restrito a usuários com role admin — o refresh é um REFRESH MATERIALIZED VIEW
    CONCURRENTLY global (cross-tenant), operação cara que não deve ser exposta a
    todos os usuários autenticados.
    """
    roles = [(p.nome or "").lower() for p in (current_user.perfis or [])]
    if "admin" not in roles:
        raise HTTPException(
            status_code=403,
            detail="Apenas administradores podem disparar refresh de views",
        )

    from app.workers.tasks.atualizar_views import executar as atualizar_views

    task = atualizar_views.delay()
    return {"status": "queued", "task_id": str(task.id)}
