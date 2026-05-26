"""Repository for bank accounts and bank transactions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, or_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.bank import BankAccount, BankTransaction, ReconciliationSession


class BankAccountRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, account: BankAccount) -> BankAccount:
        self.session.add(account)
        await self.session.flush()
        return account

    async def get_by_id(self, account_id: UUID) -> BankAccount | None:
        result = await self.session.execute(
            select(BankAccount).where(BankAccount.id == account_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self, active_only: bool = True) -> list[BankAccount]:
        q = select(BankAccount)
        if active_only:
            q = q.where(BankAccount.ativo.is_(True))
        q = q.order_by(BankAccount.nome)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def update(self, account: BankAccount, data: dict) -> BankAccount:
        for k, v in data.items():
            setattr(account, k, v)
        await self.session.flush()
        return account


class BankTransactionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def bulk_upsert_skip(self, rows: list[dict]) -> int:
        """Insert rows, skip on (empresa_id, conta_id, fitid) conflict. Return inserted count."""
        if not rows:
            return 0
        stmt = pg_insert(BankTransaction).values(rows)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_bank_tx_account_fitid")
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount  # type: ignore[return-value]

    async def list_by_account(
        self,
        account_id: UUID,
        *,
        status: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        page: int = 1,
        size: int = 50,
    ) -> tuple[list[BankTransaction], int]:
        q = select(BankTransaction).where(BankTransaction.conta_id == account_id)
        if status:
            q = q.where(BankTransaction.status == status)
        if date_from:
            q = q.where(BankTransaction.lancado_em >= date_from)
        if date_to:
            q = q.where(BankTransaction.lancado_em <= date_to)

        count_q = select(func.count()).select_from(q.subquery())
        total = (await self.session.execute(count_q)).scalar_one()

        q = q.order_by(BankTransaction.lancado_em.desc()).offset((page - 1) * size).limit(size)
        result = await self.session.execute(q)
        return list(result.scalars().all()), total

    async def list_pending(
        self,
        account_id: UUID | None = None,
        *,
        page: int = 1,
        size: int = 50,
    ) -> tuple[list[BankTransaction], int]:
        q = select(BankTransaction).where(BankTransaction.status == "pendente")
        if account_id:
            q = q.where(BankTransaction.conta_id == account_id)

        count_q = select(func.count()).select_from(q.subquery())
        total = (await self.session.execute(count_q)).scalar_one()

        q = q.order_by(BankTransaction.lancado_em.desc()).offset((page - 1) * size).limit(size)
        result = await self.session.execute(q)
        return list(result.scalars().all()), total

    async def get_by_id(self, tx_id: UUID) -> BankTransaction | None:
        result = await self.session.execute(
            select(BankTransaction).where(BankTransaction.id == tx_id)
        )
        return result.scalar_one_or_none()

    async def get_orphan_transactions(self, days_old: int = 3) -> list[BankTransaction]:
        """Pending transactions older than days_old days with no match."""
        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_old)
        q = (
            select(BankTransaction)
            .where(BankTransaction.status == "pendente")
            .where(BankTransaction.importado_em < cutoff)
            .order_by(BankTransaction.lancado_em.desc())
            .limit(100)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def count_by_status(self, account_id: UUID | None = None) -> dict[str, int]:
        q = select(
            BankTransaction.status,
            func.count().label("cnt"),
        ).group_by(BankTransaction.status)
        if account_id:
            q = q.where(BankTransaction.conta_id == account_id)
        result = await self.session.execute(q)
        return {row[0]: row[1] for row in result.all()}


class ReconciliationSessionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, rec_session: ReconciliationSession) -> ReconciliationSession:
        self.session.add(rec_session)
        await self.session.flush()
        return rec_session

    async def get_by_id(self, session_id: UUID) -> ReconciliationSession | None:
        result = await self.session.execute(
            select(ReconciliationSession).where(ReconciliationSession.id == session_id)
        )
        return result.scalar_one_or_none()
