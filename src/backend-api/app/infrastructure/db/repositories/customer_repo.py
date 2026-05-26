from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_context import UNSET, _Unset, resolve_empresa_id
from app.infrastructure.db.models.customer import Customer


class CustomerRepository:
    """Tenant-scoped: every read query filters by empresa_id.

    `empresa_id` é opcional — quando omitido, lê do contexto da requisição.
    `None` explícito é erro (ValueError).
    """

    def __init__(self, session: AsyncSession, empresa_id: UUID | _Unset = UNSET):
        self.session = session
        self.empresa_id = resolve_empresa_id(empresa_id)

    def _base_query(self):  # type: ignore[no-untyped-def]
        return select(Customer).where(
            Customer.excluido_em.is_(None),
            Customer.empresa_id == self.empresa_id,
        )

    async def create(self, customer: Customer) -> Customer:
        self.session.add(customer)
        await self.session.flush()
        return customer

    async def get_by_id(self, customer_id: UUID) -> Customer | None:
        result = await self.session.execute(
            self._base_query().where(Customer.id == customer_id)
        )
        return result.scalar_one_or_none()

    async def get_by_cpf_cnpj(self, cpf_cnpj: str) -> Customer | None:
        result = await self.session.execute(
            self._base_query().where(Customer.cpf_cnpj == cpf_cnpj)
        )
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        *,
        search: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[Customer], int]:
        query = self._base_query()

        if status:
            query = query.where(Customer.status == status)

        if search:
            term = f"%{search}%"
            query = query.where(
                or_(
                    Customer.nome_completo.ilike(term),
                    Customer.email.ilike(term),
                    Customer.cpf_cnpj.ilike(term),
                )
            )

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        # Paginate
        query = query.order_by(Customer.criado_em.desc())
        query = query.offset((page - 1) * size).limit(size)
        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def soft_delete(self, customer: Customer) -> None:
        customer.excluido_em = datetime.now(timezone.utc)
        await self.session.flush()
