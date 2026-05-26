import hashlib
import secrets

import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis

from app.infrastructure.db.session import get_engine
from app.infrastructure.security.password_hasher import hash_password
from app.infrastructure.settings import get_settings
from app.main import app
from sqlalchemy import text

# NOTE 2026-05-24: Self-registration disabled by product decision (Modelo A
# multi-tenant). Empresa + usuario admin sao criados pelo dev/script de seed.
# Admin convida demais usuarios via email. Estes testes ficam pulados ate a
# story de "convite por email" ser implementada.
pytestmark = pytest.mark.skip(reason="Self-registration disabled; refactor to invite-flow pending")

BASE_URL = "http://test"
REGISTER_URL = "/api/v1/auth/register"
VERIFY_URL = "/api/v1/auth/verify-email"
RESEND_URL = "/api/v1/auth/resend-verification"
LOGIN_URL = "/api/v1/auth/login"

REG_EMAIL = "newuser@example.com"
REG_PASSWORD = "StrongPass1"


async def _cleanup_user(email: str) -> None:
    """Remove test user and related data via raw SQL."""
    engine = get_engine()
    async with engine.begin() as conn:
        row = (await conn.execute(text(
            "SELECT id FROM acesso.usuarios WHERE email = :email"
        ), {"email": email})).first()
        if not row:
            return
        uid = str(row[0])
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


async def _clear_redis_keys(pattern: str) -> None:
    settings = get_settings()
    redis = Redis.from_url(settings.REDIS_URL)
    try:
        keys = []
        async for key in redis.scan_iter(pattern):
            keys.append(key)
        if keys:
            await redis.delete(*keys)
    finally:
        await redis.aclose()


@pytest.fixture(autouse=True)
async def setup_teardown():
    await _cleanup_user(REG_EMAIL)
    await _clear_redis_keys("email_verify:*")
    await _clear_redis_keys("resend_verify_rate:*")
    yield
    await _cleanup_user(REG_EMAIL)
    await _clear_redis_keys("email_verify:*")
    await _clear_redis_keys("resend_verify_rate:*")


# ---------- Register success ----------

@pytest.mark.asyncio
async def test_register_success():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post(
            REGISTER_URL,
            json={
                "full_name": "Novo Usuário",
                "email": REG_EMAIL,
                "password": REG_PASSWORD,
                "password_confirmation": REG_PASSWORD,
            },
        )

    assert response.status_code == 201
    assert "Verifique seu e-mail" in response.json()["detail"]


# ---------- Duplicate email returns 409 ----------

@pytest.mark.asyncio
async def test_register_duplicate_email():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        # Register first
        await client.post(
            REGISTER_URL,
            json={
                "full_name": "Novo Usuário",
                "email": REG_EMAIL,
                "password": REG_PASSWORD,
                "password_confirmation": REG_PASSWORD,
            },
        )
        # Try again
        response = await client.post(
            REGISTER_URL,
            json={
                "full_name": "Outro Usuário",
                "email": REG_EMAIL,
                "password": REG_PASSWORD,
                "password_confirmation": REG_PASSWORD,
            },
        )

    assert response.status_code == 409
    assert "já cadastrado" in response.json()["detail"]


# ---------- Login before verify returns 403 ----------

@pytest.mark.asyncio
async def test_login_before_verify_returns_403():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        # Register
        await client.post(
            REGISTER_URL,
            json={
                "full_name": "Novo Usuário",
                "email": REG_EMAIL,
                "password": REG_PASSWORD,
                "password_confirmation": REG_PASSWORD,
            },
        )
        # Try login
        response = await client.post(
            LOGIN_URL,
            json={"email": REG_EMAIL, "password": REG_PASSWORD},
        )

    assert response.status_code == 403
    assert "Verifique seu e-mail" in response.json()["detail"]


# ---------- Verify email success ----------

@pytest.mark.asyncio
async def test_verify_email_success():
    settings = get_settings()
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        # Register
        await client.post(
            REGISTER_URL,
            json={
                "full_name": "Novo Usuário",
                "email": REG_EMAIL,
                "password": REG_PASSWORD,
                "password_confirmation": REG_PASSWORD,
            },
        )

        # Find the token in Redis
        raw_token = None
        async for key in redis.scan_iter("email_verify:*"):
            # We stored the hash as key, user_id as value
            # We need the raw token — in tests we can retrieve the stored hash
            # and use it to verify the flow works via the API
            pass

        # Since we can't retrieve raw token from Redis (only hash stored),
        # we'll create a known token manually for this user
        from sqlalchemy import text as sql_text
        engine = get_engine()
        async with engine.begin() as conn:
            row = (await conn.execute(sql_text(
                "SELECT id FROM acesso.usuarios WHERE email = :email"
            ), {"email": REG_EMAIL})).first()
            assert row is not None
            user_id = str(row[0])

        # Clear any existing verify keys and create a known one
        keys = []
        async for key in redis.scan_iter("email_verify:*"):
            keys.append(key)
        if keys:
            await redis.delete(*keys)

        raw_token = secrets.token_hex(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        await redis.setex(f"email_verify:{token_hash}", 3600, user_id)

        # Verify
        response = await client.post(
            VERIFY_URL,
            json={"token": raw_token},
        )

    await redis.aclose()

    assert response.status_code == 200
    assert "verificado" in response.json()["detail"]

    # Now login should work
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        login_resp = await client.post(
            LOGIN_URL,
            json={"email": REG_EMAIL, "password": REG_PASSWORD},
        )
    assert login_resp.status_code == 200


# ---------- Resend verification returns 200 ----------

@pytest.mark.asyncio
async def test_resend_verification():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        # Register
        await client.post(
            REGISTER_URL,
            json={
                "full_name": "Novo Usuário",
                "email": REG_EMAIL,
                "password": REG_PASSWORD,
                "password_confirmation": REG_PASSWORD,
            },
        )
        # Resend
        response = await client.post(
            RESEND_URL,
            json={"email": REG_EMAIL},
        )

    assert response.status_code == 200


# ---------- Weak password returns 422 ----------

@pytest.mark.asyncio
async def test_register_weak_password():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post(
            REGISTER_URL,
            json={
                "full_name": "Novo Usuário",
                "email": REG_EMAIL,
                "password": "weak",
                "password_confirmation": "weak",
            },
        )

    assert response.status_code == 422
