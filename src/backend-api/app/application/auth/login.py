from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.shared.audit_logger import AuditLogger
from app.core.correlation import get_correlation_id
from app.domain.identity.policies import lockout_seconds, max_login_attempts
from app.infrastructure.db.models.refresh_token import RefreshToken
from app.infrastructure.db.models.user import User
from app.infrastructure.db.repositories.user_repo import UserRepository
from app.infrastructure.security.jwt_service import create_access_token
from app.infrastructure.security.password_hasher import verify_password
from app.infrastructure.security.totp import generate_mfa_temp_token
from app.infrastructure.settings import get_settings

log = structlog.get_logger()


class LoginResult:
    def __init__(
        self,
        *,
        access_token: str | None = None,
        refresh_token_raw: str | None = None,
        user: "User | None" = None,
        mfa_required: bool = False,
        mfa_token: str | None = None,
    ):
        self.access_token = access_token
        self.refresh_token_raw = refresh_token_raw
        self.user = user
        self.mfa_required = mfa_required
        self.mfa_token = mfa_token


class LoginUseCase:
    def __init__(self, session: AsyncSession, redis: Redis):
        self.session = session
        self.redis = redis
        self.user_repo = UserRepository(session)
        self.audit = AuditLogger(session)

    async def execute(
        self,
        *,
        email: str,
        password: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> LoginResult:
        settings = get_settings()

        # Rate limiting check
        lockout_key = f"login_lockout:{email.lower()}"
        if await self.redis.exists(lockout_key):
            log.warning("login_rate_limited", email=email)
            raise RateLimitError()

        user = await self.user_repo.get_by_email(email)

        # Check active before spending CPU on Argon2
        if user is not None and not user.ativo:
            raise UserInactiveError()

        if user is None or not verify_password(password, user.senha_hash):
            # Track failed attempts
            attempts_key = f"login_attempts:{email.lower()}"
            attempts = await self.redis.incr(attempts_key)
            await self.redis.expire(attempts_key, lockout_seconds())

            if attempts >= max_login_attempts():
                await self.redis.setex(lockout_key, lockout_seconds(), "1")
                await self.redis.delete(attempts_key)
                log.warning("login_lockout_triggered", email=email, attempts=attempts)

            # Audit failed login
            if user:
                await self.audit.record(
                    action="auth.login_failed",
                    user_id=str(user.id),
                    entity="user",
                    entity_id=str(user.id),
                    ip=ip,
                    user_agent=user_agent,
                    correlation_id=get_correlation_id(),
                    module="auth",
                    category="security",
                    severity="warning",
                )
                await self.session.commit()

            raise InvalidCredentialsError()

        # MFA path
        if user.mfa_ativo:
            mfa_token = generate_mfa_temp_token()
            return LoginResult(mfa_required=True, mfa_token=mfa_token)

        # Clear failed attempts on success
        await self.redis.delete(
            f"login_attempts:{email.lower()}",
            f"login_lockout:{email.lower()}",
        )

        # Generate tokens
        roles = [r.nome for r in user.perfis]
        access_token = create_access_token(
            sub=str(user.id),
            email=user.email,
            roles=roles,
            empresa_id=str(user.empresa_id),
        )

        # Generate refresh token
        raw_token = secrets.token_bytes(64)
        token_hash = hashlib.sha256(raw_token).hexdigest()
        refresh_token = RefreshToken(
            usuario_id=user.id,
            empresa_id=user.empresa_id,
            token_hash=token_hash,
            expira_em=datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
        )
        self.session.add(refresh_token)

        # Update last login
        await self.user_repo.update_last_login(user)

        # Audit successful login
        await self.audit.record(
            action="auth.login",
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

        return LoginResult(
            access_token=access_token,
            refresh_token_raw=raw_token.hex(),
            user=user,
        )


class InvalidCredentialsError(Exception):
    pass


class RateLimitError(Exception):
    pass


class UserInactiveError(Exception):
    pass
