from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.infrastructure.db.session import get_engine
from app.infrastructure.security.password_hasher import hash_password
from app.main import app

BASE_URL = "http://test"
LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
LOGOUT_URL = "/api/v1/auth/logout"

TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "SecureP@ss123"


async def _seed_user(
    *,
    email: str = TEST_EMAIL,
    password: str = TEST_PASSWORD,
    is_active: bool = True,
    is_mfa_enabled: bool = False,
) -> str:
    """Create a test user via raw SQL and return its UUID as string."""
    user_id = str(uuid4())
    pw_hash = hash_password(password)
    engine = get_engine()
    async with engine.begin() as conn:
        # Fetch the seed empresa created by migration 0015
        empresa_row = (await conn.execute(text(
            "SELECT id FROM comercial.empresas LIMIT 1"
        ))).first()
        empresa_id = str(empresa_row[0]) if empresa_row else str(uuid4())
        await conn.execute(text(
            "INSERT INTO acesso.usuarios "
            "(id, empresa_id, email, senha_hash, nome_completo, ativo, mfa_ativo) "
            "VALUES (:id, :empresa_id, :email, :pw, :name, :active, :mfa)"
        ), {"id": user_id, "empresa_id": empresa_id, "email": email,
            "pw": pw_hash, "name": "Test User", "active": is_active, "mfa": is_mfa_enabled})
    return user_id


async def _cleanup_user(email: str = TEST_EMAIL) -> None:
    """Remove test user and related data via raw SQL."""
    engine = get_engine()
    async with engine.begin() as conn:
        row = (await conn.execute(text(
            "SELECT id FROM acesso.usuarios WHERE email = :email"
        ), {"email": email})).first()
        if not row:
            return
        uid = str(row[0])
        # Disable append-only trigger, nullify audit FK, re-enable
        await conn.execute(text(
            "ALTER TABLE logs.log_auditoria DISABLE TRIGGER trg_log_auditoria_immutable"
        ))
        await conn.execute(text(
            "UPDATE logs.log_auditoria SET user_id = NULL WHERE user_id = :uid"
        ), {"uid": uid})
        await conn.execute(text(
            "ALTER TABLE logs.log_auditoria ENABLE TRIGGER trg_log_auditoria_immutable"
        ))
        await conn.execute(text(
            "DELETE FROM acesso.refresh_tokens WHERE usuario_id = :uid"
        ), {"uid": uid})
        await conn.execute(text(
            "DELETE FROM acesso.usuarios WHERE id = :uid"
        ), {"uid": uid})


async def _clear_all_rate_limits() -> None:
    """Clear all Redis rate limit keys."""
    from redis.asyncio import Redis

    from app.infrastructure.settings import get_settings

    settings = get_settings()
    redis = Redis.from_url(settings.REDIS_URL)
    try:
        keys = []
        async for key in redis.scan_iter("login_attempts:*"):
            keys.append(key)
        async for key in redis.scan_iter("login_lockout:*"):
            keys.append(key)
        if keys:
            await redis.delete(*keys)
    finally:
        await redis.aclose()


@pytest.fixture(autouse=True)
async def setup_teardown():
    """Seed test user before each test and clean up after."""
    await _cleanup_user()
    await _clear_all_rate_limits()
    await _seed_user()
    yield
    await _cleanup_user()
    await _clear_all_rate_limits()


# ---------- AC1: Successful login ----------

@pytest.mark.asyncio
async def test_login_success():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post(
            LOGIN_URL,
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "user" in data
    assert data["user"]["email"] == TEST_EMAIL
    assert isinstance(data["user"]["roles"], list)

    # Refresh token should be in HttpOnly cookie
    cookies = response.cookies
    assert "refresh_token" in cookies


# ---------- AC2: Wrong password returns 401 ----------

@pytest.mark.asyncio
async def test_login_wrong_password():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post(
            LOGIN_URL,
            json={"email": TEST_EMAIL, "password": "WrongPassword123"},
        )

    assert response.status_code == 401


# ---------- AC2: Nonexistent user returns 401 ----------

@pytest.mark.asyncio
async def test_login_nonexistent_user():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post(
            LOGIN_URL,
            json={"email": "nobody@example.com", "password": "whatever"},
        )

    assert response.status_code == 401


# ---------- AC2: Inactive user returns 403 ----------

@pytest.mark.asyncio
async def test_login_inactive_user():
    inactive_email = "inactive@example.com"
    await _cleanup_user(inactive_email)
    await _seed_user(email=inactive_email, is_active=False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post(
            LOGIN_URL,
            json={"email": inactive_email, "password": TEST_PASSWORD},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "Verifique seu e-mail antes de entrar"
    await _cleanup_user(inactive_email)


# ---------- AC4: MFA path ----------

@pytest.mark.asyncio
async def test_login_mfa_required():
    mfa_email = "mfa@example.com"
    await _cleanup_user(mfa_email)
    await _seed_user(email=mfa_email, is_mfa_enabled=True)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post(
            LOGIN_URL,
            json={"email": mfa_email, "password": TEST_PASSWORD},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["mfa_required"] is True
    assert "mfa_token" in data
    await _cleanup_user(mfa_email)


# ---------- AC5: Refresh token rotation ----------

@pytest.mark.asyncio
async def test_refresh_token_rotation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        # Login first
        login_resp = await client.post(
            LOGIN_URL,
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        )
        assert login_resp.status_code == 200

        # Extract refresh token from Set-Cookie and send manually
        refresh_cookie = login_resp.cookies.get("refresh_token")
        assert refresh_cookie is not None

        refresh_resp = await client.post(
            REFRESH_URL,
            cookies={"refresh_token": refresh_cookie},
        )

    assert refresh_resp.status_code == 200
    data = refresh_resp.json()
    assert "access_token" in data


# ---------- AC6: Logout invalidates refresh token ----------

@pytest.mark.asyncio
async def test_logout():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        # Login
        login_resp = await client.post(
            LOGIN_URL,
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        )
        refresh_cookie = login_resp.cookies.get("refresh_token")

        # Logout
        logout_resp = await client.post(
            LOGOUT_URL,
            cookies={"refresh_token": refresh_cookie},
        )
        assert logout_resp.status_code == 200

        # Refresh should fail after logout
        refresh_resp = await client.post(
            REFRESH_URL,
            cookies={"refresh_token": refresh_cookie},
        )
        assert refresh_resp.status_code == 401


# ---------- AC7: Rate limiting ----------

@pytest.mark.asyncio
async def test_rate_limiting():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        # Make 5 failed attempts
        for _ in range(5):
            await client.post(
                LOGIN_URL,
                json={"email": TEST_EMAIL, "password": "wrong"},
            )

        # 6th attempt should be rate limited
        response = await client.post(
            LOGIN_URL,
            json={"email": TEST_EMAIL, "password": "wrong"},
        )

    assert response.status_code == 429


# ---------- Refresh without cookie returns 401 ----------

@pytest.mark.asyncio
async def test_refresh_without_cookie():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post(REFRESH_URL)

    assert response.status_code == 401


# ---------- AC3: JWT claims validation ----------

@pytest.mark.asyncio
async def test_jwt_claims():
    import jwt as pyjwt

    from app.infrastructure.security.jwt_service import _load_keys
    from app.infrastructure.settings import get_settings

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post(
            LOGIN_URL,
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        )

    data = response.json()
    settings = get_settings()
    _, public_key = _load_keys()

    payload = pyjwt.decode(
        data["access_token"],
        public_key,
        algorithms=[settings.JWT_ALGORITHM],
        audience=f"{settings.PRODUCT_NAME}-api",
    )

    assert "sub" in payload
    assert payload["email"] == TEST_EMAIL
    assert "roles" in payload
    assert "iat" in payload
    assert "exp" in payload
    assert payload["iss"] == settings.PRODUCT_NAME
    assert payload["aud"] == f"{settings.PRODUCT_NAME}-api"
    # Story 12.4: empresa_id é claim obrigatório no JWT multi-tenant
    assert "empresa_id" in payload, "empresa_id deve estar no JWT (multi-tenant)"
    from uuid import UUID
    UUID(payload["empresa_id"])  # raise se não for UUID válido


# ---------- Story 12.4: rotas autenticadas exigem empresa_id no JWT ----------

@pytest.mark.asyncio
async def test_authenticated_route_rejects_jwt_without_empresa_id():
    """Token forjado sem empresa_id deve receber 403, não 200."""
    import jwt as pyjwt
    from datetime import datetime, timedelta, timezone

    from app.infrastructure.security.jwt_service import _load_keys
    from app.infrastructure.settings import get_settings

    unique_email = f"no-empresa-{uuid4().hex[:8]}@example.com"
    user_id = await _seed_user(email=unique_email)
    settings = get_settings()
    private_key, _ = _load_keys()
    now = datetime.now(timezone.utc)

    # Token VÁLIDO em assinatura mas SEM o claim empresa_id
    token_sem_empresa = pyjwt.encode(
        {
            "sub": user_id,
            "email": "no-empresa@example.com",
            "roles": ["user"],
            "iat": now,
            "exp": now + timedelta(minutes=15),
            "iss": settings.PRODUCT_NAME,
            "aud": f"{settings.PRODUCT_NAME}-api",
            # empresa_id ausente de propósito
        },
        private_key,
        algorithm=settings.JWT_ALGORITHM,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.get(
            "/api/v1/customers",
            headers={"Authorization": f"Bearer {token_sem_empresa}"},
        )

    assert response.status_code == 403, (
        f"Esperado 403 para JWT sem empresa_id, recebeu {response.status_code}"
    )
    # Mensagem deve ser genérica — motivo específico vai apenas para o log.
    assert response.json().get("detail") == "Acesso negado"


@pytest.mark.asyncio
async def test_authenticated_route_rejects_jwt_with_mismatched_empresa_id():
    """Token com empresa_id que não corresponde ao usuário deve receber 403."""
    import jwt as pyjwt
    from datetime import datetime, timedelta, timezone
    from uuid import uuid4

    from app.infrastructure.security.jwt_service import _load_keys
    from app.infrastructure.settings import get_settings

    unique_email = f"mismatch-{uuid4().hex[:8]}@example.com"
    user_id = await _seed_user(email=unique_email)
    settings = get_settings()
    private_key, _ = _load_keys()
    now = datetime.now(timezone.utc)

    # Token com empresa_id de outra empresa (UUID aleatório)
    token_forjado = pyjwt.encode(
        {
            "sub": user_id,
            "email": "mismatch@example.com",
            "empresa_id": str(uuid4()),
            "roles": ["user"],
            "iat": now,
            "exp": now + timedelta(minutes=15),
            "iss": settings.PRODUCT_NAME,
            "aud": f"{settings.PRODUCT_NAME}-api",
        },
        private_key,
        algorithm=settings.JWT_ALGORITHM,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.get(
            "/api/v1/customers",
            headers={"Authorization": f"Bearer {token_forjado}"},
        )

    assert response.status_code == 403
    # Mensagem deve ser genérica — motivo específico vai apenas para o log.
    assert response.json().get("detail") == "Acesso negado"
