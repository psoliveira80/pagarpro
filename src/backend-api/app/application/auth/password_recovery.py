from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

import structlog
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.shared.audit_logger import AuditLogger
from app.core.correlation import get_correlation_id
from app.domain.ports.email_sender import IEmailSender
from app.infrastructure.db.models.refresh_token import RefreshToken
from app.infrastructure.db.models.user import User
from app.infrastructure.security.password_hasher import hash_password
from app.infrastructure.settings import get_settings

log = structlog.get_logger()

RESET_TOKEN_TTL = 3600  # 1 hour
RATE_LIMIT_MAX = 3
RATE_LIMIT_TTL = 3600  # 1 hour


class ForgotPasswordUseCase:
    def __init__(
        self, session: AsyncSession, redis: Redis, email_sender: IEmailSender
    ):
        self.session = session
        self.redis = redis
        self.email_sender = email_sender

    async def execute(self, *, email: str) -> None:
        settings = get_settings()

        # Rate limit: max 3 per email per hour
        rate_key = f"password_reset_rate:{email.lower()}"
        count = await self.redis.incr(rate_key)
        if count == 1:
            await self.redis.expire(rate_key, RATE_LIMIT_TTL)
        if count > RATE_LIMIT_MAX:
            return  # Silently ignore — no enumeration

        # Find user
        stmt = select(User).where(User.email == email, User.excluido_em.is_(None))
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            return  # Always 200 — no enumeration

        # Generate reset token
        raw_token = secrets.token_hex(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        # Store in Redis
        await self.redis.setex(
            f"password_reset:{token_hash}",
            RESET_TOKEN_TTL,
            str(user.id),
        )

        # Send email
        reset_url = f"{settings.FRONTEND_URL}/auth/reset-password?token={raw_token}"
        await self.email_sender.send(
            to=user.email,
            subject=f"{settings.PRODUCT_NAME} — Redefinir senha",
            body_html=(
                f"<p>Olá {user.nome_completo},</p>"
                f"<p>Clique no link para redefinir sua senha:</p>"
                f'<p><a href="{reset_url}">{reset_url}</a></p>'
                f"<p>Este link expira em 1 hora.</p>"
                f"<p>{settings.PRODUCT_NAME}</p>"
            ),
            body_text=(
                f"Olá {user.nome_completo},\n\n"
                f"Acesse o link para redefinir sua senha:\n{reset_url}\n\n"
                f"Este link expira em 1 hora.\n\n"
                f"{settings.PRODUCT_NAME}"
            ),
        )

        log.info("password_reset_requested", user_id=str(user.id))


class ResetPasswordUseCase:
    def __init__(self, session: AsyncSession, redis: Redis):
        self.session = session
        self.redis = redis
        self.audit = AuditLogger(session)

    async def execute(
        self,
        *,
        token: str,
        new_password: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        redis_key = f"password_reset:{token_hash}"

        # Look up token
        user_id_str = await self.redis.get(redis_key)
        if user_id_str is None:
            raise InvalidResetTokenError()

        # Single-use: delete immediately
        await self.redis.delete(redis_key)

        # Find user
        from uuid import UUID

        user_id = UUID(user_id_str)
        stmt = select(User).where(User.id == user_id, User.excluido_em.is_(None))
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            raise InvalidResetTokenError()

        # Update password
        user.senha_hash = hash_password(new_password)

        # Invalidate all refresh tokens (force re-login)
        now = datetime.now(timezone.utc)
        await self.session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.usuario_id == user_id,
                RefreshToken.revogado_em.is_(None),
            )
            .values(revogado_em=now)
        )

        # Audit
        await self.audit.record(
            action="auth.password_reset",
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
        log.info("password_reset_completed", user_id=str(user.id))


class InvalidResetTokenError(Exception):
    pass
