from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email, User.excluido_em.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> User | None:
        stmt = select(User).where(User.id == user_id, User.excluido_em.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_last_login(self, user: User) -> None:
        from datetime import datetime, timezone

        user.ultimo_login_em = datetime.now(timezone.utc)
        await self.session.flush()
