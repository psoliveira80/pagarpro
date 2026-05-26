"""Repository for receivable (installment) queries."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, or_, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.tenant_context import UNSET, _Unset, resolve_empresa_id
from app.infrastructure.db.models.contract import (
    Contract,
    Installment,
    InstallmentAdjustment,
)


class ReceivableRepository:
    """Tenant-scoped: every read query filters by empresa_id.

    `empresa_id` é opcional — quando omitido, lê do contexto da requisição.
    `None` explícito é erro (ValueError).
    """

    def __init__(self, session: AsyncSession, empresa_id: UUID | _Unset = UNSET):
        self.session = session
        self.empresa_id = resolve_empresa_id(empresa_id)

    async def list_paginated(
        self,
        *,
        status: str | None = None,
        customer_id: UUID | None = None,
        due_from: date | None = None,
        due_to: date | None = None,
        search: str | None = None,
        page: int = 1,
        size: int = 20,
        sort_by: str = "due_date",
        sort_dir: str = "asc",
    ) -> tuple[list[Installment], int]:
        query = (
            select(Installment)
            .join(Contract, Installment.contract_id == Contract.id)
            .where(
                Contract.excluido_em.is_(None),
                Installment.empresa_id == self.empresa_id,
            )
        )

        if status:
            query = query.where(Installment.status == status)
        if customer_id:
            query = query.where(Contract.customer_id == customer_id)
        if due_from:
            query = query.where(Installment.due_date >= due_from)
        if due_to:
            query = query.where(Installment.due_date <= due_to)
        if search:
            term = f"%{search}%"
            query = query.where(
                or_(
                    Contract.contract_number.ilike(term),
                    Installment.notes.ilike(term),
                )
            )

        # Count
        count_q = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_q)).scalar_one()

        # Sorting
        sort_col = getattr(Installment, sort_by, Installment.due_date)
        if sort_dir == "desc":
            query = query.order_by(sort_col.desc())
        else:
            query = query.order_by(sort_col.asc())

        query = query.offset((page - 1) * size).limit(size)
        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def get_aggregates(
        self,
        *,
        customer_id: UUID | None = None,
        due_from: date | None = None,
        due_to: date | None = None,
        search: str | None = None,
    ) -> dict:
        """Compute footer aggregates for the receivables list."""
        base = (
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (Installment.status.in_(["em_aberto", "vencido", "pago_parcial"]),
                             Installment.current_value - Installment.paid_value),
                            else_=Decimal("0"),
                        )
                    ),
                    Decimal("0"),
                ).label("total_due"),
                func.coalesce(
                    func.sum(
                        case(
                            (Installment.status == "vencido",
                             Installment.current_value - Installment.paid_value),
                            else_=Decimal("0"),
                        )
                    ),
                    Decimal("0"),
                ).label("total_overdue"),
                func.coalesce(
                    func.sum(
                        case(
                            (Installment.status.in_(["pago", "pago_aguardando_verificacao"]),
                             Installment.paid_value),
                            else_=Decimal("0"),
                        )
                    ),
                    Decimal("0"),
                ).label("total_paid"),
            )
            .select_from(Installment)
            .join(Contract, Installment.contract_id == Contract.id)
            .where(
                Contract.excluido_em.is_(None),
                Installment.empresa_id == self.empresa_id,
            )
        )

        if customer_id:
            base = base.where(Contract.customer_id == customer_id)
        if due_from:
            base = base.where(Installment.due_date >= due_from)
        if due_to:
            base = base.where(Installment.due_date <= due_to)
        if search:
            term = f"%{search}%"
            base = base.where(
                or_(
                    Contract.contract_number.ilike(term),
                    Installment.notes.ilike(term),
                )
            )

        row = (await self.session.execute(base)).one()
        return {
            "total_due": row.total_due,
            "total_overdue": row.total_overdue,
            "total_paid": row.total_paid,
        }

    async def get_validation_queue(
        self,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[Installment], int]:
        """Get installments with status=pago_aguardando_verificacao."""
        query = select(Installment).where(
            Installment.status == "pago_aguardando_verificacao",
            Installment.empresa_id == self.empresa_id,
        )
        count_q = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_q)).scalar_one()

        query = query.order_by(Installment.payment_date.asc())
        query = query.offset((page - 1) * size).limit(size)
        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def get_installment(self, installment_id: UUID) -> Installment | None:
        result = await self.session.execute(
            select(Installment)
            .options(selectinload(Installment.adjustments))
            .where(
                Installment.id == installment_id,
                Installment.empresa_id == self.empresa_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_installments_by_ids(self, ids: list[UUID]) -> list[Installment]:
        if not ids:
            return []
        result = await self.session.execute(
            select(Installment)
            .where(
                Installment.id.in_(ids),
                Installment.empresa_id == self.empresa_id,
            )
            .order_by(Installment.due_date.asc())
        )
        return list(result.scalars().all())

    async def add_adjustment(self, adj: InstallmentAdjustment) -> None:
        self.session.add(adj)
        await self.session.flush()

    async def add_installment(self, inst: Installment) -> None:
        self.session.add(inst)
        await self.session.flush()

    async def add_installments(self, installments: list[Installment]) -> None:
        self.session.add_all(installments)
        await self.session.flush()
