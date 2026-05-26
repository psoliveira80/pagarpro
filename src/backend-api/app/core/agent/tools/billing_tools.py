"""Billing and collection BI tools for the agent."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent.tool_interface import ToolResult
from app.infrastructure.db.models.contract import Contract, Installment
from app.infrastructure.db.models.customer import Customer

log = structlog.get_logger()

ROW_LIMIT = 200
QUERY_TIMEOUT = 10.0


def _serialize_decimal(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    return obj


def _row_to_dict(row: Any, keys: list[str]) -> dict[str, Any]:
    result = {}
    for i, key in enumerate(keys):
        val = row[i] if hasattr(row, "__getitem__") else getattr(row, key, None)
        result[key] = _serialize_decimal(val)
    return result


async def get_overdue_installments(
    session: AsyncSession,
    days_min: int = 1,
    days_max: int = 365,
    customer_id: str | None = None,
    limit: int = 50,
    **kwargs: Any,
) -> ToolResult:
    """Get overdue installments with optional filters."""
    try:
        today = date.today()
        min_date = today - timedelta(days=days_max)
        max_date = today - timedelta(days=days_min)

        stmt = (
            select(
                Installment.id,
                Installment.contrato_id,
                Installment.sequencia,
                Installment.data_vencimento,
                Installment.valor,
                Installment.valor_pago,
                Installment.status,
            )
            .where(
                Installment.status.in_(["vencido", "em_aberto"]),
                Installment.data_vencimento <= max_date,
                Installment.data_vencimento >= min_date,
            )
        )

        if customer_id:
            stmt = stmt.join(Contract, Installment.contrato_id == Contract.id).where(
                Contract.cliente_id == UUID(customer_id)
            )

        effective_limit = min(limit, ROW_LIMIT)
        stmt = stmt.order_by(Installment.data_vencimento).limit(effective_limit + 1)

        result = await asyncio.wait_for(
            session.execute(stmt), timeout=QUERY_TIMEOUT
        )
        rows = result.all()

        truncated = len(rows) > effective_limit
        data = []
        keys = [
            "id", "contrato_id", "sequencia", "data_vencimento",
            "valor", "valor_pago", "status",
        ]
        for row in rows[:effective_limit]:
            item = _row_to_dict(row, keys)
            due = row[3]  # data_vencimento
            item["days_overdue"] = (today - due).days
            data.append(item)

        confidence = "high" if customer_id else ("medium" if truncated else "high")

        return ToolResult(
            data=data,
            confidence=confidence,
            truncated=truncated,
            total_count=len(data),
        )

    except asyncio.TimeoutError:
        return ToolResult(
            data=[],
            error="Query timed out. Try narrowing your filters.",
            confidence="low",
        )
    except Exception as exc:
        log.error("get_overdue_installments_error", error=str(exc))
        return ToolResult(data=[], error=str(exc), confidence="low")


async def get_collection_summary(
    session: AsyncSession,
    start_date: str | None = None,
    end_date: str | None = None,
    **kwargs: Any,
) -> ToolResult:
    """Get collection summary for a period."""
    try:
        today = date.today()
        s_date = date.fromisoformat(start_date) if start_date else today - timedelta(days=30)
        e_date = date.fromisoformat(end_date) if end_date else today

        total_stmt = select(func.sum(Installment.valor)).where(
            Installment.data_vencimento.between(s_date, e_date)
        )
        total_result = await asyncio.wait_for(
            session.execute(total_stmt), timeout=QUERY_TIMEOUT
        )
        total_receivable = total_result.scalar() or Decimal(0)

        collected_stmt = select(func.sum(Installment.valor_pago)).where(
            Installment.data_vencimento.between(s_date, e_date),
            Installment.status == "pago",
        )
        collected_result = await asyncio.wait_for(
            session.execute(collected_stmt), timeout=QUERY_TIMEOUT
        )
        total_collected = collected_result.scalar() or Decimal(0)

        overdue_stmt = select(func.count()).where(
            Installment.status.in_(["vencido"]),
            Installment.data_vencimento.between(s_date, e_date),
        )
        overdue_result = await asyncio.wait_for(
            session.execute(overdue_stmt), timeout=QUERY_TIMEOUT
        )
        overdue_count = overdue_result.scalar() or 0

        collection_rate = (
            float(total_collected / total_receivable * 100)
            if total_receivable > 0
            else 0.0
        )

        return ToolResult(
            data={
                "period_start": s_date.isoformat(),
                "period_end": e_date.isoformat(),
                "total_receivable": float(total_receivable),
                "total_collected": float(total_collected),
                "total_overdue": float(total_receivable - total_collected),
                "overdue_count": overdue_count,
                "collection_rate_pct": round(collection_rate, 2),
            },
            confidence="high",
        )

    except asyncio.TimeoutError:
        return ToolResult(data={}, error="Query timed out.", confidence="low")
    except Exception as exc:
        log.error("get_collection_summary_error", error=str(exc))
        return ToolResult(data={}, error=str(exc), confidence="low")


async def get_revenue_by_period(
    session: AsyncSession,
    start_date: str | None = None,
    end_date: str | None = None,
    group_by: str = "month",
    **kwargs: Any,
) -> ToolResult:
    """Get revenue breakdown by time period."""
    try:
        today = date.today()
        s_date = date.fromisoformat(start_date) if start_date else today - timedelta(days=180)
        e_date = date.fromisoformat(end_date) if end_date else today

        if group_by == "day":
            trunc_fn = func.date_trunc("day", Installment.data_vencimento)
        elif group_by == "week":
            trunc_fn = func.date_trunc("week", Installment.data_vencimento)
        else:
            trunc_fn = func.date_trunc("month", Installment.data_vencimento)

        stmt = (
            select(
                trunc_fn.label("period"),
                func.sum(Installment.valor_pago).label("revenue"),
                func.count().label("count"),
            )
            .where(
                Installment.status == "pago",
                Installment.data_vencimento.between(s_date, e_date),
            )
            .group_by("period")
            .order_by("period")
        )

        result = await asyncio.wait_for(
            session.execute(stmt), timeout=QUERY_TIMEOUT
        )
        rows = result.all()

        data = [
            {
                "period": row[0].isoformat() if row[0] else None,
                "revenue": float(row[1] or 0),
                "count": row[2],
            }
            for row in rows
        ]

        return ToolResult(data=data, confidence="high")

    except asyncio.TimeoutError:
        return ToolResult(data=[], error="Query timed out.", confidence="low")
    except Exception as exc:
        log.error("get_revenue_by_period_error", error=str(exc))
        return ToolResult(data=[], error=str(exc), confidence="low")


async def get_customer_payment_history(
    session: AsyncSession,
    customer_id: str,
    months_back: int = 12,
    **kwargs: Any,
) -> ToolResult:
    """Get payment history for a specific customer."""
    try:
        cutoff = date.today() - timedelta(days=months_back * 30)

        stmt = (
            select(
                Installment.id,
                Installment.sequencia,
                Installment.data_vencimento,
                Installment.valor,
                Installment.valor_pago,
                Installment.status,
                Installment.pago_em,
                Installment.forma_pagamento,
            )
            .join(Contract, Installment.contrato_id == Contract.id)
            .where(
                Contract.cliente_id == UUID(customer_id),
                Installment.data_vencimento >= cutoff,
            )
            .order_by(Installment.data_vencimento.desc())
            .limit(ROW_LIMIT + 1)
        )

        result = await asyncio.wait_for(
            session.execute(stmt), timeout=QUERY_TIMEOUT
        )
        rows = result.all()

        truncated = len(rows) > ROW_LIMIT
        keys = [
            "id", "sequencia", "data_vencimento", "valor",
            "valor_pago", "status", "pago_em", "forma_pagamento",
        ]
        data = [_row_to_dict(row, keys) for row in rows[:ROW_LIMIT]]

        return ToolResult(
            data=data,
            confidence="high",
            truncated=truncated,
            total_count=len(data),
        )

    except asyncio.TimeoutError:
        return ToolResult(data=[], error="Query timed out.", confidence="low")
    except Exception as exc:
        log.error("get_customer_payment_history_error", error=str(exc))
        return ToolResult(data=[], error=str(exc), confidence="low")


async def list_defaulters(
    session: AsyncSession,
    min_days_overdue: int = 1,
    limit: int = 50,
    **kwargs: Any,
) -> ToolResult:
    """List customers with overdue installments, sorted by total debt."""
    try:
        today = date.today()
        cutoff = today - timedelta(days=min_days_overdue)
        effective_limit = min(limit, ROW_LIMIT)

        stmt = (
            select(
                Customer.id.label("customer_id"),
                Customer.nome_completo,
                Customer.telefone,
                func.count(Installment.id).label("overdue_count"),
                func.sum(Installment.valor - Installment.valor_pago).label("total_debt"),
                func.min(Installment.data_vencimento).label("oldest_due_date"),
            )
            .join(Contract, Contract.cliente_id == Customer.id)
            .join(Installment, Installment.contrato_id == Contract.id)
            .where(
                Installment.status.in_(["vencido", "em_aberto"]),
                Installment.data_vencimento <= cutoff,
            )
            .group_by(Customer.id, Customer.nome_completo, Customer.telefone)
            .order_by(func.sum(Installment.valor - Installment.valor_pago).desc())
            .limit(effective_limit + 1)
        )

        result = await asyncio.wait_for(
            session.execute(stmt), timeout=QUERY_TIMEOUT
        )
        rows = result.all()

        truncated = len(rows) > effective_limit
        data = [
            {
                "customer_id": str(row[0]),
                "nome_completo": row[1],
                "telefone": row[2],
                "overdue_count": row[3],
                "total_debt": float(row[4] or 0),
                "oldest_due_date": row[5].isoformat() if row[5] else None,
                "days_overdue": (today - row[5]).days if row[5] else 0,
            }
            for row in rows[:effective_limit]
        ]

        return ToolResult(
            data=data,
            confidence="medium" if truncated else "high",
            truncated=truncated,
            total_count=len(data),
        )

    except asyncio.TimeoutError:
        return ToolResult(data=[], error="Query timed out.", confidence="low")
    except Exception as exc:
        log.error("list_defaulters_error", error=str(exc))
        return ToolResult(data=[], error=str(exc), confidence="low")


async def generate_pix_qr(
    session: AsyncSession,
    installment_id: str,
    **kwargs: Any,
) -> ToolResult:
    """Generate a Pix QR code for an installment."""
    try:
        stmt = select(Installment).where(Installment.id == UUID(installment_id))
        result = await session.execute(stmt)
        installment = result.scalar_one_or_none()

        if installment is None:
            return ToolResult(error="Installment not found", confidence="low")

        paid = installment.valor_pago or Decimal(0)
        amount = float(installment.valor - paid)
        br_code = (
            f"00020126580014br.gov.bcb.pix0136{installment_id}"
            f"520400005303986540{amount:.2f}5802BR"
            f"6009SAO PAULO62070503***6304"
        )

        return ToolResult(
            data={
                "installment_id": str(installment.id),
                "amount": amount,
                "due_date": installment.data_vencimento.isoformat(),
                "br_code": br_code,
                "status": installment.status,
            },
            confidence="high",
        )

    except Exception as exc:
        log.error("generate_pix_qr_error", error=str(exc))
        return ToolResult(error=str(exc), confidence="low")


async def register_writeoff(
    session: AsyncSession,
    installment_id: str,
    amount: float | None = None,
    payment_method: str = "pix",
    **kwargs: Any,
) -> ToolResult:
    """Register a primary write-off for an installment."""
    try:
        stmt = select(Installment).where(Installment.id == UUID(installment_id))
        result = await session.execute(stmt)
        installment = result.scalar_one_or_none()

        if installment is None:
            return ToolResult(error="Installment not found", confidence="low")

        paid = installment.valor_pago or Decimal(0)
        pay_amount = Decimal(str(amount)) if amount else installment.valor
        remaining = installment.valor - paid

        if pay_amount > remaining:
            return ToolResult(
                error=f"Payment amount ({pay_amount}) exceeds remaining ({remaining})",
                confidence="low",
            )

        previous_status = installment.status
        previous_paid = float(paid)

        new_paid = paid + pay_amount
        installment.valor_pago = new_paid
        installment.forma_pagamento = payment_method
        installment.pago_em = date.today()

        if new_paid >= installment.valor:
            installment.status = "pago_aguardando_verificacao"
        else:
            installment.status = "pago_parcial"

        await session.flush()

        log.info(
            "writeoff_registered",
            installment_id=installment_id,
            amount=float(pay_amount),
            payment_method=payment_method,
            previous_status=previous_status,
            new_status=installment.status,
            previous_paid=previous_paid,
            total_paid=float(new_paid),
            triggered_by=kwargs.get("triggered_by", "agent"),
        )

        return ToolResult(
            data={
                "installment_id": str(installment.id),
                "paid_amount": float(pay_amount),
                "total_paid": float(new_paid),
                "remaining": float(installment.valor - new_paid),
                "status": installment.status,
            },
            confidence="high",
        )

    except Exception as exc:
        log.error("register_writeoff_error", error=str(exc))
        return ToolResult(error=str(exc), confidence="low")
