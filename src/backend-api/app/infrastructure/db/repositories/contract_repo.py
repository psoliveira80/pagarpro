from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, or_, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.tenant_context import UNSET, _Unset, resolve_empresa_id
from app.infrastructure.db.models.contract import (
    Contract,
    ContractEvent,
    Installment,
    InstallmentAdjustment,
    InstallmentGeneration,
)


class ContractRepository:
    """Tenant-scoped: every read query filters by empresa_id.

    `empresa_id` é opcional no construtor — quando omitido, é lido do
    contexto da requisição (ver `app.core.tenant_context`). Em rotas HTTP,
    `get_current_user` já seta o contexto; em workers Celery a task deve
    chamar `set_empresa_id` no início. `None` explícito é erro (ValueError).
    """

    def __init__(self, session: AsyncSession, empresa_id: UUID | _Unset = UNSET):
        self.session = session
        self.empresa_id = resolve_empresa_id(empresa_id)

    def _base_query(self):  # type: ignore[no-untyped-def]
        return select(Contract).where(
            Contract.excluido_em.is_(None),
            Contract.empresa_id == self.empresa_id,
        )

    async def create(self, contract: Contract) -> Contract:
        self.session.add(contract)
        await self.session.flush()
        return contract

    async def get_by_id(self, contract_id: UUID) -> Contract | None:
        result = await self.session.execute(
            self._base_query()
            .options(
                selectinload(Contract.titulos).selectinload(Installment.movimentos),
                selectinload(Contract.eventos),
                selectinload(Contract.lotes),
            )
            .where(Contract.id == contract_id)
        )
        return result.scalar_one_or_none()

    async def get_by_contract_number(self, contract_number: str) -> Contract | None:
        result = await self.session.execute(
            self._base_query().where(Contract.numero == contract_number)
        )
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        *,
        search: str | None = None,
        status: str | None = None,
        customer_id: UUID | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[Contract], int]:
        query = self._base_query()

        if status:
            query = query.where(Contract.status == status)
        if customer_id:
            query = query.where(Contract.cliente_id == customer_id)
        if search:
            term = f"%{search}%"
            query = query.where(
                or_(
                    Contract.numero.ilike(term),
                )
            )

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        query = query.order_by(Contract.criado_em.desc())
        query = query.offset((page - 1) * size).limit(size)
        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def add_installments(self, installments: list[Installment]) -> None:
        self.session.add_all(installments)
        await self.session.flush()

    async def add_event(self, event: ContractEvent) -> ContractEvent:
        self.session.add(event)
        await self.session.flush()
        return event

    async def add_adjustment(self, adjustment: InstallmentAdjustment) -> InstallmentAdjustment:
        self.session.add(adjustment)
        await self.session.flush()
        return adjustment

    async def add_generation(self, generation: InstallmentGeneration) -> InstallmentGeneration:
        self.session.add(generation)
        await self.session.flush()
        return generation

    async def get_installment(self, installment_id: UUID) -> Installment | None:
        result = await self.session.execute(
            select(Installment).where(
                Installment.id == installment_id,
                Installment.empresa_id == self.empresa_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_installments_by_contract(self, contract_id: UUID) -> list[Installment]:
        result = await self.session.execute(
            select(Installment)
            .where(
                Installment.contrato_id == contract_id,
                Installment.empresa_id == self.empresa_id,
            )
            .order_by(Installment.sequencia)
        )
        return list(result.scalars().all())

    async def get_events_paginated(
        self,
        contract_id: UUID,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[ContractEvent], int]:
        base = select(ContractEvent).where(
            ContractEvent.contrato_id == contract_id,
            ContractEvent.empresa_id == self.empresa_id,
        )

        count_q = select(func.count()).select_from(base.subquery())
        total = (await self.session.execute(count_q)).scalar_one()

        query = base.order_by(ContractEvent.criado_em.desc())
        query = query.offset((page - 1) * size).limit(size)
        result = await self.session.execute(query)
        items = list(result.scalars().all())
        return items, total

    async def get_generations(self, contract_id: UUID) -> list[InstallmentGeneration]:
        result = await self.session.execute(
            select(InstallmentGeneration)
            .where(
                InstallmentGeneration.contrato_id == contract_id,
                InstallmentGeneration.empresa_id == self.empresa_id,
            )
            .order_by(InstallmentGeneration.criado_em)
        )
        return list(result.scalars().all())

    async def get_generation(self, generation_id: UUID) -> InstallmentGeneration | None:
        result = await self.session.execute(
            select(InstallmentGeneration).where(
                InstallmentGeneration.id == generation_id,
                InstallmentGeneration.empresa_id == self.empresa_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_installments_by_generation(self, generation_id: UUID) -> list[Installment]:
        result = await self.session.execute(
            select(Installment)
            .where(
                Installment.lote_id == generation_id,
                Installment.empresa_id == self.empresa_id,
            )
            .order_by(Installment.sequencia)
        )
        return list(result.scalars().all())

    async def hard_delete_installments(self, installment_ids: list[UUID]) -> None:
        if not installment_ids:
            return
        await self.session.execute(
            sa_delete(InstallmentAdjustment).where(
                InstallmentAdjustment.titulo_id.in_(installment_ids),
                InstallmentAdjustment.empresa_id == self.empresa_id,
            )
        )
        await self.session.execute(
            sa_delete(Installment).where(
                Installment.id.in_(installment_ids),
                Installment.empresa_id == self.empresa_id,
            )
        )
        await self.session.flush()

    async def soft_delete(self, contract: Contract) -> None:
        contract.excluido_em = datetime.now(timezone.utc)
        await self.session.flush()
