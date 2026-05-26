"""Repository for payables, suppliers, expense categories, and recurring templates.

All repositories are tenant-scoped: empresa_id is required in the constructor
and applied to every read query. ExpenseCategory keeps system-wide rows
(empresa_id NULL) accessible to all tenants — a default category set.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_context import UNSET, _Unset, resolve_empresa_id
from app.infrastructure.db.models.payable import (
    ExpenseCategory,
    Payable,
    RecurringPayableTemplate,
    Supplier,
)


class ExpenseCategoryRepository:
    """Tenant-scoped, but allows system rows (empresa_id IS NULL) visible to all.

    `empresa_id` é opcional — quando omitido, lê do contexto da requisição.
    `None` explícito é erro (ValueError).
    """

    def __init__(self, session: AsyncSession, empresa_id: UUID | _Unset = UNSET):
        self.session = session
        self.empresa_id = resolve_empresa_id(empresa_id)

    def _tenant_filter(self):
        return or_(
            ExpenseCategory.empresa_id == self.empresa_id,
            ExpenseCategory.empresa_id.is_(None),
        )

    async def create(self, cat: ExpenseCategory) -> ExpenseCategory:
        self.session.add(cat)
        await self.session.flush()
        return cat

    async def get_by_id(self, cat_id: UUID) -> ExpenseCategory | None:
        result = await self.session.execute(
            select(ExpenseCategory).where(
                ExpenseCategory.id == cat_id,
                self._tenant_filter(),
            )
        )
        return result.scalar_one_or_none()

    async def list_all(self, active_only: bool = True) -> list[ExpenseCategory]:
        q = select(ExpenseCategory).where(self._tenant_filter())
        if active_only:
            q = q.where(ExpenseCategory.ativo.is_(True))
        q = q.order_by(ExpenseCategory.name)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def update(self, cat: ExpenseCategory, data: dict) -> ExpenseCategory:
        for k, v in data.items():
            setattr(cat, k, v)
        await self.session.flush()
        return cat


class SupplierRepository:
    """Tenant-scoped: every read query filters by empresa_id.

    `empresa_id` é opcional — quando omitido, lê do contexto da requisição.
    `None` explícito é erro (ValueError).
    """

    def __init__(self, session: AsyncSession, empresa_id: UUID | _Unset = UNSET):
        self.session = session
        self.empresa_id = resolve_empresa_id(empresa_id)

    def _base_query(self):
        return select(Supplier).where(
            Supplier.excluido_em.is_(None),
            Supplier.empresa_id == self.empresa_id,
        )

    async def create(self, supplier: Supplier) -> Supplier:
        self.session.add(supplier)
        await self.session.flush()
        return supplier

    async def get_by_id(self, supplier_id: UUID) -> Supplier | None:
        result = await self.session.execute(
            self._base_query().where(Supplier.id == supplier_id)
        )
        return result.scalar_one_or_none()

    async def get_by_cpf_cnpj(self, cpf_cnpj: str) -> Supplier | None:
        result = await self.session.execute(
            self._base_query().where(Supplier.cpf_cnpj == cpf_cnpj)
        )
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        *,
        search: str | None = None,
        active_only: bool = True,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[Supplier], int]:
        q = self._base_query()
        if active_only:
            q = q.where(Supplier.ativo.is_(True))
        if search:
            term = f"%{search}%"
            q = q.where(
                or_(Supplier.name.ilike(term), Supplier.cpf_cnpj.ilike(term))
            )

        count_q = select(func.count()).select_from(q.subquery())
        total = (await self.session.execute(count_q)).scalar_one()

        q = q.order_by(Supplier.name).offset((page - 1) * size).limit(size)
        result = await self.session.execute(q)
        return list(result.scalars().all()), total

    async def update(self, supplier: Supplier, data: dict) -> Supplier:
        for k, v in data.items():
            setattr(supplier, k, v)
        await self.session.flush()
        return supplier

    async def soft_delete(self, supplier: Supplier) -> None:
        supplier.excluido_em = datetime.now(timezone.utc)
        await self.session.flush()


class PayableRepository:
    """Tenant-scoped: every read query filters by empresa_id.

    `empresa_id` é opcional — quando omitido, lê do contexto da requisição.
    `None` explícito é erro (ValueError).
    """

    def __init__(self, session: AsyncSession, empresa_id: UUID | _Unset = UNSET):
        self.session = session
        self.empresa_id = resolve_empresa_id(empresa_id)

    def _base_query(self):
        return select(Payable).where(
            Payable.excluido_em.is_(None),
            Payable.empresa_id == self.empresa_id,
        )

    async def create(self, payable: Payable) -> Payable:
        self.session.add(payable)
        await self.session.flush()
        return payable

    async def get_by_id(self, payable_id: UUID) -> Payable | None:
        result = await self.session.execute(
            self._base_query().where(Payable.id == payable_id)
        )
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        *,
        status: str | None = None,
        supplier_id: UUID | None = None,
        category_id: UUID | None = None,
        due_from: date | None = None,
        due_to: date | None = None,
        search: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[Payable], int]:
        q = self._base_query()
        if status:
            q = q.where(Payable.status == status)
        if supplier_id:
            q = q.where(Payable.supplier_id == supplier_id)
        if category_id:
            q = q.where(Payable.category_id == category_id)
        if due_from:
            q = q.where(Payable.due_date >= due_from)
        if due_to:
            q = q.where(Payable.due_date <= due_to)
        if search:
            term = f"%{search}%"
            q = q.where(Payable.description.ilike(term))

        count_q = select(func.count()).select_from(q.subquery())
        total = (await self.session.execute(count_q)).scalar_one()

        q = q.order_by(Payable.due_date.asc()).offset((page - 1) * size).limit(size)
        result = await self.session.execute(q)
        return list(result.scalars().all()), total

    async def update(self, payable: Payable, data: dict) -> Payable:
        for k, v in data.items():
            setattr(payable, k, v)
        await self.session.flush()
        return payable

    async def soft_delete(self, payable: Payable) -> None:
        payable.excluido_em = datetime.now(timezone.utc)
        await self.session.flush()

    async def get_paid_by_period_grouped(
        self,
        period_start: date,
        period_end: date,
        _asset_id: UUID | None = None,
        category_id: UUID | None = None,
    ) -> list:
        """Get paid payables grouped by category for DRE."""
        q = (
            select(
                Payable.category_id,
                func.sum(Payable.amount).label("total"),
            )
            .where(Payable.excluido_em.is_(None))
            .where(Payable.empresa_id == self.empresa_id)
            .where(Payable.status == "pago")
            .where(Payable.payment_date >= period_start)
            .where(Payable.payment_date <= period_end)
            .group_by(Payable.category_id)
        )
        if category_id:
            q = q.where(Payable.category_id == category_id)
        result = await self.session.execute(q)
        return list(result.all())


class RecurringPayableTemplateRepository:
    """Tenant-scoped (per-route reads). For worker scans across all tenants,
    use a system-scoped query directly — see app/workers/tasks/*.

    `empresa_id` é opcional — quando omitido, lê do contexto da requisição.
    `None` explícito é erro (ValueError).
    """

    def __init__(self, session: AsyncSession, empresa_id: UUID | _Unset = UNSET):
        self.session = session
        self.empresa_id = resolve_empresa_id(empresa_id)

    async def create(self, template: RecurringPayableTemplate) -> RecurringPayableTemplate:
        self.session.add(template)
        await self.session.flush()
        return template

    async def get_by_id(self, template_id: UUID) -> RecurringPayableTemplate | None:
        result = await self.session.execute(
            select(RecurringPayableTemplate).where(
                RecurringPayableTemplate.id == template_id,
                RecurringPayableTemplate.empresa_id == self.empresa_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_all(self, active_only: bool = True) -> list[RecurringPayableTemplate]:
        q = select(RecurringPayableTemplate).where(
            RecurringPayableTemplate.empresa_id == self.empresa_id
        )
        if active_only:
            q = q.where(RecurringPayableTemplate.ativo.is_(True))
        q = q.order_by(RecurringPayableTemplate.next_generation_date)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def update(self, template: RecurringPayableTemplate, data: dict) -> RecurringPayableTemplate:
        for k, v in data.items():
            setattr(template, k, v)
        await self.session.flush()
        return template

    async def get_due_templates(self, as_of: date) -> list[RecurringPayableTemplate]:
        """Worker-only entry: returns due templates across ALL tenants.
        Caller MUST be a worker (no HTTP request context), since this bypasses
        the tenant filter. Each returned template carries its own empresa_id."""
        result = await self.session.execute(
            select(RecurringPayableTemplate)
            .where(RecurringPayableTemplate.ativo.is_(True))
            .where(RecurringPayableTemplate.next_generation_date <= as_of)
        )
        return list(result.scalars().all())
