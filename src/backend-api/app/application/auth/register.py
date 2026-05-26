from __future__ import annotations

import hashlib
import re
import secrets

import structlog
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.shared.audit_logger import AuditLogger
from app.core.correlation import get_correlation_id
from app.domain.ports.email_sender import IEmailSender
from app.infrastructure.db.models.user import User
from app.infrastructure.security.password_hasher import hash_password
from app.infrastructure.settings import get_settings

log = structlog.get_logger()

VERIFY_TOKEN_TTL = 3600  # 1 hour
RESEND_RATE_LIMIT_MAX = 3
RESEND_RATE_LIMIT_TTL = 3600  # 1 hour

PASSWORD_PATTERN = re.compile(r"^(?=.*[A-Z])(?=.*\d).{8,}$")


class EmailAlreadyRegisteredError(Exception):
    pass


class WeakPasswordError(Exception):
    pass


class PasswordMismatchError(Exception):
    pass


class RegisterUseCase:
    def __init__(
        self, session: AsyncSession, redis: Redis, email_sender: IEmailSender
    ):
        self.session = session
        self.redis = redis
        self.email_sender = email_sender
        self.audit = AuditLogger(session)

    async def execute(
        self,
        *,
        full_name: str,
        email: str,
        password: str,
        password_confirmation: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        settings = get_settings()

        # Validate password confirmation
        if password != password_confirmation:
            raise PasswordMismatchError()

        # Validate password strength
        if not PASSWORD_PATTERN.match(password):
            raise WeakPasswordError()

        # Check email uniqueness
        stmt = select(User).where(User.email == email, User.excluido_em.is_(None))
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            raise EmailAlreadyRegisteredError()

        # Create user with is_active=false
        pw_hash = hash_password(password)
        user = User(
            email=email,
            nome_completo=full_name,
            senha_hash=pw_hash,
            ativo=False,
        )
        self.session.add(user)
        await self.session.flush()

        # Generate verification token
        raw_token = secrets.token_hex(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        # Store in Redis
        await self.redis.setex(
            f"email_verify:{token_hash}",
            VERIFY_TOKEN_TTL,
            str(user.id),
        )

        # Send verification email
        verify_url = f"{settings.FRONTEND_URL}/auth/verify-email?token={raw_token}"
        await self.email_sender.send(
            to=email,
            subject=f"{settings.PRODUCT_NAME} — Verificação de e-mail",
            body_html=(
                f"<p>Olá {full_name},</p>"
                f"<p>Clique no link para verificar seu e-mail:</p>"
                f'<p><a href="{verify_url}">{verify_url}</a></p>'
                f"<p>Este link expira em 1 hora.</p>"
                f"<p>{settings.PRODUCT_NAME}</p>"
            ),
            body_text=(
                f"Olá {full_name},\n\n"
                f"Acesse o link para verificar seu e-mail:\n{verify_url}\n\n"
                f"Este link expira em 1 hora.\n\n"
                f"{settings.PRODUCT_NAME}"
            ),
        )

        # Audit
        await self.audit.record(
            action="auth.register",
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
        log.info("user_registered", user_id=str(user.id), email=email)


class ResendVerificationUseCase:
    def __init__(
        self, session: AsyncSession, redis: Redis, email_sender: IEmailSender
    ):
        self.session = session
        self.redis = redis
        self.email_sender = email_sender

    async def execute(self, *, email: str) -> None:
        settings = get_settings()

        # Rate limit: max 3 per email per hour
        rate_key = f"resend_verify_rate:{email.lower()}"
        count = await self.redis.incr(rate_key)
        if count == 1:
            await self.redis.expire(rate_key, RESEND_RATE_LIMIT_TTL)
        if count > RESEND_RATE_LIMIT_MAX:
            return  # Silently ignore

        # Find user
        stmt = select(User).where(
            User.email == email,
            User.excluido_em.is_(None),
            User.ativo.is_(False),
        )
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            return  # Always 200 — no enumeration

        # Generate new verification token
        raw_token = secrets.token_hex(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        await self.redis.setex(
            f"email_verify:{token_hash}",
            VERIFY_TOKEN_TTL,
            str(user.id),
        )

        # Send email
        verify_url = f"{settings.FRONTEND_URL}/auth/verify-email?token={raw_token}"
        await self.email_sender.send(
            to=user.email,
            subject=f"{settings.PRODUCT_NAME} — Verificação de e-mail",
            body_html=(
                f"<p>Olá {user.nome_completo},</p>"
                f"<p>Clique no link para verificar seu e-mail:</p>"
                f'<p><a href="{verify_url}">{verify_url}</a></p>'
                f"<p>Este link expira em 1 hora.</p>"
                f"<p>{settings.PRODUCT_NAME}</p>"
            ),
            body_text=(
                f"Olá {user.nome_completo},\n\n"
                f"Acesse o link para verificar seu e-mail:\n{verify_url}\n\n"
                f"Este link expira em 1 hora.\n\n"
                f"{settings.PRODUCT_NAME}"
            ),
        )

        log.info("verification_email_resent", user_id=str(user.id))
