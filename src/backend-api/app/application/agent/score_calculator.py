"""Customer score calculation logic."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.agent import CustomerScore
from app.infrastructure.db.models.contract import Contract, Installment
from app.infrastructure.db.models.customer import Customer

log = structlog.get_logger()

# Default weights (can be overridden via admin settings)
DEFAULT_WEIGHTS = {
    "punctuality_12m": 0.60,
    "avg_overdue_ratio": 0.20,
    "tenure_bonus": 0.10,
    "paid_amount_bonus": 0.10,
}


async def compute_customer_score(
    session: AsyncSession,
    customer_id: UUID,
    weights: dict[str, float] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Compute a 0-100 score for a customer.

    Returns (score, factors_dict).
    """
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    today = date.today()
    twelve_months_ago = today - timedelta(days=365)

    factors: dict[str, Any] = {}

    # 1. Punctuality over last 12 months (ratio of on-time payments)
    all_stmt = (
        select(func.count())
        .select_from(Installment)
        .join(Contract, Installment.contract_id == Contract.id)
        .where(
            Contract.customer_id == customer_id,
            Installment.due_date >= twelve_months_ago,
            Installment.due_date <= today,
            Installment.status.in_(["pago", "pago_aguardando_verificacao", "vencido"]),
        )
    )
    total_installments = (await session.execute(all_stmt)).scalar() or 0

    on_time_stmt = (
        select(func.count())
        .select_from(Installment)
        .join(Contract, Installment.contract_id == Contract.id)
        .where(
            Contract.customer_id == customer_id,
            Installment.due_date >= twelve_months_ago,
            Installment.due_date <= today,
            Installment.status.in_(["pago", "pago_aguardando_verificacao"]),
            Installment.payment_date <= Installment.due_date,
        )
    )
    on_time = (await session.execute(on_time_stmt)).scalar() or 0

    punctuality = on_time / max(total_installments, 1)
    factors["punctuality_12m"] = round(punctuality, 4)
    factors["total_installments_12m"] = total_installments
    factors["on_time_12m"] = on_time

    # 2. Average overdue days (inverted — fewer days = higher score)
    overdue_stmt = (
        select(func.avg(func.greatest(0, func.extract("day", func.current_date() - Installment.due_date))))
        .select_from(Installment)
        .join(Contract, Installment.contract_id == Contract.id)
        .where(
            Contract.customer_id == customer_id,
            Installment.status.in_(["vencido"]),
        )
    )
    avg_overdue_result = await session.execute(overdue_stmt)
    avg_overdue_days = float(avg_overdue_result.scalar() or 0)

    # Normalize: 0 days = 1.0, 90+ days = 0.0
    overdue_ratio = max(0.0, 1.0 - (avg_overdue_days / 90.0))
    factors["avg_overdue_days"] = round(avg_overdue_days, 1)
    factors["overdue_ratio"] = round(overdue_ratio, 4)

    # 3. Tenure bonus (capped at 1.0 after 24 months)
    customer_stmt = select(Customer.criado_em).where(Customer.id == customer_id)
    customer_result = await session.execute(customer_stmt)
    created_at = customer_result.scalar_one_or_none()

    if created_at:
        tenure_days = (today - created_at.date()).days if hasattr(created_at, 'date') else (today - created_at).days
        tenure_months = tenure_days / 30.0
        tenure_bonus = min(1.0, tenure_months / 24.0)
    else:
        tenure_months = 0
        tenure_bonus = 0.0

    factors["tenure_months"] = round(tenure_months, 1)
    factors["tenure_bonus"] = round(tenure_bonus, 4)

    # 4. Paid amount bonus (ratio of paid vs billed, capped at 1.0)
    billed_stmt = (
        select(func.sum(Installment.current_value))
        .select_from(Installment)
        .join(Contract, Installment.contract_id == Contract.id)
        .where(Contract.customer_id == customer_id)
    )
    total_billed = float((await session.execute(billed_stmt)).scalar() or 0)

    paid_stmt = (
        select(func.sum(Installment.paid_value))
        .select_from(Installment)
        .join(Contract, Installment.contract_id == Contract.id)
        .where(Contract.customer_id == customer_id)
    )
    total_paid = float((await session.execute(paid_stmt)).scalar() or 0)

    paid_ratio = min(1.0, total_paid / max(total_billed, 1))
    factors["total_billed"] = total_billed
    factors["total_paid"] = total_paid
    factors["paid_amount_bonus"] = round(paid_ratio, 4)

    # Calculate weighted score
    raw_score = (
        punctuality * w["punctuality_12m"]
        + overdue_ratio * w["avg_overdue_ratio"]
        + tenure_bonus * w["tenure_bonus"]
        + paid_ratio * w["paid_amount_bonus"]
    )

    score = max(0, min(100, int(round(raw_score * 100))))
    factors["raw_score"] = round(raw_score, 4)
    factors["weights"] = w

    return score, factors


async def compute_and_save_score(
    session: AsyncSession,
    customer_id: UUID,
) -> CustomerScore:
    """Compute score and persist to customer_scores table.

    `empresa_id` é derivado do próprio `Customer` — story 12-5 (RLS) exige que
    todo INSERT em tabela tenant-scoped carregue o empresa_id explícito, senão
    o policy WITH CHECK rejeita. Sem esse passo, recálculo de score quebrava
    silenciosamente (story 12-6 code review).
    """
    score, factors = await compute_customer_score(session, customer_id)

    # Load customer and reuse its empresa_id for the score record.
    customer_stmt = select(Customer).where(Customer.id == customer_id)
    customer_result = await session.execute(customer_stmt)
    customer = customer_result.scalar_one_or_none()
    if customer is None:
        raise ValueError(f"Cliente {customer_id} não encontrado para cálculo de score")

    customer.score = score
    score_record = CustomerScore(
        empresa_id=customer.empresa_id,
        customer_id=customer_id,
        score=score,
        factors=factors,
    )
    session.add(score_record)
    await session.flush()

    return score_record
