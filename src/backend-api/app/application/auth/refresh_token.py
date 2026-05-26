import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.refresh_token import RefreshToken
from app.infrastructure.db.models.user import User
from app.infrastructure.security.jwt_service import create_access_token
from app.infrastructure.settings import get_settings

log = structlog.get_logger()


class RefreshResult:
    def __init__(self, *, access_token: str, refresh_token_raw: str):
        self.access_token = access_token
        self.refresh_token_raw = refresh_token_raw


class RefreshTokenUseCase:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def execute(self, *, raw_token_hex: str) -> RefreshResult:
        settings = get_settings()
        token_hash = hashlib.sha256(bytes.fromhex(raw_token_hex)).hexdigest()

        stmt = select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revogado_em.is_(None),
        )
        result = await self.session.execute(stmt)
        stored = result.scalar_one_or_none()

        if stored is None:
            raise InvalidRefreshTokenError()

        now = datetime.now(timezone.utc)
        if stored.expira_em < now:
            raise InvalidRefreshTokenError()

        # Revoke old token (rotation)
        stored.revogado_em = now

        # Load user
        user_stmt = select(User).where(User.id == stored.usuario_id, User.excluido_em.is_(None))
        user_result = await self.session.execute(user_stmt)
        user = user_result.scalar_one_or_none()

        if user is None or not user.ativo:
            raise InvalidRefreshTokenError()

        # Defesa em profundidade multi-tenant: o empresa_id armazenado no
        # refresh token (snapshot do momento do login) deve casar com o
        # empresa_id atual do usuário. Se admin moveu o usuário entre empresas
        # desde a emissão, o refresh é invalidado — exige re-login para que
        # o novo JWT seja emitido com o tenant correto.
        if stored.empresa_id != user.empresa_id:
            log.warning(
                "refresh_token_tenant_mismatch",
                usuario_id=str(user.id),
                empresa_id_token=str(stored.empresa_id),
                empresa_id_user=str(user.empresa_id),
            )
            raise InvalidRefreshTokenError()

        # Create new refresh token
        new_raw = secrets.token_bytes(64)
        new_hash = hashlib.sha256(new_raw).hexdigest()
        new_refresh = RefreshToken(
            usuario_id=user.id,
            empresa_id=user.empresa_id,
            token_hash=new_hash,
            expira_em=now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
        )
        self.session.add(new_refresh)

        # Create new access token
        roles = [r.nome for r in user.perfis]
        access_token = create_access_token(
            sub=str(user.id),
            email=user.email,
            roles=roles,
            empresa_id=str(user.empresa_id),
        )

        await self.session.commit()

        return RefreshResult(
            access_token=access_token,
            refresh_token_raw=new_raw.hex(),
        )


class LogoutUseCase:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def execute(self, *, raw_token_hex: str) -> None:
        token_hash = hashlib.sha256(bytes.fromhex(raw_token_hex)).hexdigest()

        stmt = select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revogado_em.is_(None),
        )
        result = await self.session.execute(stmt)
        stored = result.scalar_one_or_none()

        if stored is not None:
            stored.revogado_em = datetime.now(timezone.utc)

        await self.session.commit()


class InvalidRefreshTokenError(Exception):
    pass
