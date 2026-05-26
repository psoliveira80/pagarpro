"""Fleet/vehicle tools for the agent."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent.tool_interface import ToolResult
from app.infrastructure.db.models.contract import Contract, Installment

log = structlog.get_logger()


async def get_vehicle_position(
    session: AsyncSession,
    vehicle_id: str,
    **kwargs: Any,
) -> ToolResult:
    """Get the latest GPS position for a vehicle.

    Delegates to ITrackerGateway in production. Returns stub data for now.
    """
    try:
        # In production, this would call ITrackerGateway.get_last_position()
        # For now, return a structured response indicating tracker status
        return ToolResult(
            data={
                "vehicle_id": vehicle_id,
                "message": "Tracker integration not configured. Configure a tracker provider in Settings > Integrations.",
            },
            confidence="low",
        )
    except Exception as exc:
        log.error("get_vehicle_position_error", error=str(exc))
        return ToolResult(error=str(exc), confidence="low")


async def get_contract_status(
    session: AsyncSession,
    contract_id: str,
    empresa_id: UUID | None = None,
    **kwargs: Any,
) -> ToolResult:
    """Get detailed contract status with installment summary (tenant-scoped)."""
    if empresa_id is None:
        return ToolResult(
            error="empresa_id ausente no contexto do agente — execução bloqueada",
            confidence="low",
        )
    try:
        stmt = select(Contract).where(
            Contract.id == UUID(contract_id),
            Contract.empresa_id == empresa_id,
        )
        result = await session.execute(stmt)
        contract = result.scalar_one_or_none()

        if contract is None:
            return ToolResult(error="Contract not found", confidence="low")

        # Get installment summary
        installments = contract.installments or []
        paid = sum(1 for i in installments if i.status == "pago")
        overdue = sum(1 for i in installments if i.status in ("vencido",))
        pending = sum(1 for i in installments if i.status in ("em_aberto",))

        total_value = float(sum(i.current_value for i in installments))
        total_paid = float(sum(i.paid_value for i in installments))

        return ToolResult(
            data={
                "contract_id": str(contract.id),
                "contract_number": contract.contract_number,
                "customer_id": str(contract.customer_id),
                "status": contract.status,
                "start_date": contract.start_date.isoformat(),
                "end_date": contract.end_date.isoformat(),
                "total_value": total_value,
                "total_paid": total_paid,
                "installments_total": len(installments),
                "installments_paid": paid,
                "installments_overdue": overdue,
                "installments_pending": pending,
            },
            confidence="high",
        )

    except Exception as exc:
        log.error("get_contract_status_error", error=str(exc))
        return ToolResult(error=str(exc), confidence="low")
