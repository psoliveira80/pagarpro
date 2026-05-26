from __future__ import annotations

import hashlib
from uuid import UUID

import structlog
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.shared.audit_logger import AuditLogger
from app.core.correlation import get_correlation_id
from app.infrastructure.db.models.user import User

log = structlog.get_logger()


class InvalidVerifyTokenError(Exception):
    pass


class VerifyEmailUseCase:
    def __init__(self, session: AsyncSession, redis: Redis):
        self.session = session
        self.redis = redis
        self.audit = AuditLogger(session)

    async def execute(
        self,
        *,
        token: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        redis_key = f"email_verify:{token_hash}"

        # Look up token
        user_id_str = await self.redis.get(redis_key)
        if user_id_str is None:
            raise InvalidVerifyTokenError()

        # Single-use: delete immediately
        await self.redis.delete(redis_key)

        # Find user
        user_id = UUID(user_id_str)
        stmt = select(User).where(User.id == user_id, User.excluido_em.is_(None))
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            raise InvalidVerifyTokenError()

        # Activate user
        user.ativo = True

        # Audit
        await self.audit.record(
            action="auth.email_verified",
            user_id=str(user.id),
            entity="user",
            entity_id=str(user.id),
            ip=ip,
            user_agent=user_agent,
            correlation_id=get_correlation_id(),
            module="auth",
            category="security",
            severity="info",
        )

        await self.session.commit()
        log.info("email_verified", user_id=str(user.id))
