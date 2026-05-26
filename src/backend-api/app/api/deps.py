from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_context import set_empresa_id
from app.infrastructure.db.models.user import User
from app.infrastructure.db.repositories.user_repo import UserRepository
from app.infrastructure.db.session import get_sessionmaker
from app.infrastructure.security.jwt_service import decode_access_token

log = structlog.get_logger()

_bearer = HTTPBearer(auto_error=False)

# Detalhe genérico devolvido ao cliente em qualquer falha de autorização
# multi-tenant. Os motivos específicos (claim ausente, formato inválido,
# divergência com o user) vão SOMENTE para o log estruturado — devolver
# mensagens diferentes daria ao atacante um oráculo de enumeração.
_FORBIDDEN_DETAIL = "Acesso negado"


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: SessionDep,
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    try:
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError, TypeError):
        log.warning("jwt_invalid_sub", payload_keys=list(payload.keys()))
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)

    if user is None or not user.ativo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    # Extrai empresa_id do JWT (claim obrigatório multi-tenant). Mensagem
    # genérica em todas as falhas — motivo específico vai apenas para o log.
    empresa_id_claim = payload.get("empresa_id")
    if empresa_id_claim is None:
        log.warning("jwt_missing_empresa_id_claim", user_id=str(user_id))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_FORBIDDEN_DETAIL,
        )
    try:
        empresa_id = UUID(str(empresa_id_claim))
    except (ValueError, TypeError):
        log.warning(
            "jwt_invalid_empresa_id_format",
            user_id=str(user_id),
            empresa_id_claim=str(empresa_id_claim),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_FORBIDDEN_DETAIL,
        )

    # Defesa em profundidade: o empresa_id do JWT deve casar com o do usuário
    # no banco. Se divergem, o token foi forjado ou o usuário trocou de empresa
    # desde a emissão. Em ambos os casos, recusa.
    if user.empresa_id != empresa_id:
        log.warning(
            "jwt_empresa_id_mismatch",
            user_id=str(user_id),
            empresa_id_token=str(empresa_id),
            empresa_id_user=str(user.empresa_id),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_FORBIDDEN_DETAIL,
        )

    # Seta o tenant no contexto desta request — fica acessível em qualquer
    # camada (services, repositories, tools de agente) via get_empresa_id().
    set_empresa_id(empresa_id)

    # Seta também o `app.empresa_id` no PostgreSQL para que as policies de
    # Row Level Security (migration 0020) filtrem cada query no banco. O
    # terceiro argumento `true` (is_local) garante que o setting expira no
    # fim da transação atual — não vaza para outras requests via pool.
    await session.execute(
        text("SELECT set_config('app.empresa_id', :eid, true)"),
        {"eid": str(empresa_id)},
    )

    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


async def require_empresa_id(
    current_user: CurrentUserDep,
) -> UUID:
    """Dependency que retorna o empresa_id do tenant atual.

    `get_current_user` já seta o contexto via `set_empresa_id`; esta dependency
    expõe o valor para handlers que querem usá-lo explicitamente (passar para
    construtores de repos, por exemplo).
    """
    return current_user.empresa_id


EmpresaIdDep = Annotated[UUID, Depends(require_empresa_id)]
