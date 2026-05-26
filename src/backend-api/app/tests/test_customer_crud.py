from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.infrastructure.db.session import get_engine
from app.infrastructure.security.password_hasher import hash_password
from app.infrastructure.security.jwt_service import create_access_token
from app.main import app

BASE_URL = "http://test"
CUSTOMERS_URL = "/api/v1/customers"
TEST_EMAIL = "crud-test@example.com"
TEST_PASSWORD = "CrudTest@123"

_user_id: str = ""
_token: str = ""


async def _setup_test_user() -> tuple[str, str]:
    """Create test user and return (user_id, jwt_token)."""
    global _user_id, _token
    user_id = str(uuid4())
    engine = get_engine()
    async with engine.begin() as conn:
        # Clean up first
        await conn.execute(text("DELETE FROM acesso.usuarios WHERE email = :e"), {"e": TEST_EMAIL})
        empresa_row = (await conn.execute(text("SELECT id FROM comercial.empresas LIMIT 1"))).first()
        assert empresa_row is not None, "No empresa found — run seed first"
        empresa_id = str(empresa_row[0])
        await conn.execute(text(
            "INSERT INTO acesso.usuarios (id, email, senha_hash, nome_completo, ativo, mfa_ativo, empresa_id) "
            "VALUES (:id, :email, :pw, :name, true, false, :eid)"
        ), {"id": user_id, "email": TEST_EMAIL, "pw": hash_password(TEST_PASSWORD), "name": "CRUD Tester", "eid": empresa_id})

    token = create_access_token(sub=user_id, email=TEST_EMAIL, roles=["Admin"], empresa_id=empresa_id)
    _user_id = user_id
    _token = token
    return user_id, token


async def _cleanup() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM cadastro.anexos_cliente WHERE cliente_id IN (SELECT id FROM cadastro.clientes WHERE criado_por_id = :uid)"), {"uid": _user_id})
        await conn.execute(text(
            "ALTER TABLE logs.log_auditoria DISABLE TRIGGER trg_log_auditoria_immutable"
        ))
        await conn.execute(text(
            "UPDATE logs.log_auditoria SET user_id = NULL WHERE user_id = :uid"
        ), {"uid": _user_id})
        await conn.execute(text(
            "ALTER TABLE logs.log_auditoria ENABLE TRIGGER trg_log_auditoria_immutable"
        ))
        await conn.execute(text("DELETE FROM cadastro.clientes WHERE criado_por_id = :uid"), {"uid": _user_id})
        await conn.execute(text("DELETE FROM acesso.usuarios WHERE id = :uid"), {"uid": _user_id})


@pytest.fixture(autouse=True)
async def setup_teardown():
    await _setup_test_user()
    yield
    await _cleanup()


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {_token}"}


@pytest.mark.asyncio
async def test_create_customer():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post(
            CUSTOMERS_URL,
            json={
                "nome_completo": "João Silva",
                "cpf_cnpj": "123.456.789-09",
                "telefone": "(71) 99999-8888",
                "email": "joao@example.com",
                "endereco": {"cidade": "Salvador", "estado": "BA"},
            },
            headers=_auth_headers(),
        )

    assert response.status_code == 201
    data = response.json()
    assert data["nome_completo"] == "João Silva"
    assert data["cpf_cnpj"] == "12345678909"
    assert data["telefone"] == "+5571999998888"
    assert data["endereco"]["cidade"] == "Salvador"
    assert data["score"] == 100
    assert data["status"] == "ativo"


@pytest.mark.asyncio
async def test_create_duplicate_cpf():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        await client.post(
            CUSTOMERS_URL,
            json={"nome_completo": "A", "cpf_cnpj": "11111111111"},
            headers=_auth_headers(),
        )
        response = await client.post(
            CUSTOMERS_URL,
            json={"nome_completo": "B", "cpf_cnpj": "11111111111"},
            headers=_auth_headers(),
        )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_list_customers_with_pagination():
    # Pre-clean: delete customers left by earlier tests (same empresa) so the
    # count assertion is deterministic.
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "DELETE FROM cadastro.clientes WHERE empresa_id IN "
                "(SELECT empresa_id FROM acesso.usuarios WHERE email = :e)"
            ),
            {"e": TEST_EMAIL},
        )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        # Create 3 customers
        for i in range(3):
            await client.post(
                CUSTOMERS_URL,
                json={"nome_completo": f"Customer {i}", "cpf_cnpj": f"0000000000{i}"},
                headers=_auth_headers(),
            )

        response = await client.get(
            CUSTOMERS_URL,
            params={"page": 1, "size": 2},
            headers=_auth_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["pages"] == 2


@pytest.mark.asyncio
async def test_list_customers_search():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        await client.post(
            CUSTOMERS_URL,
            json={"nome_completo": "Maria Oliveira", "cpf_cnpj": "22222222222"},
            headers=_auth_headers(),
        )
        await client.post(
            CUSTOMERS_URL,
            json={"nome_completo": "Pedro Santos", "cpf_cnpj": "33333333333"},
            headers=_auth_headers(),
        )

        response = await client.get(
            CUSTOMERS_URL,
            params={"search": "Maria"},
            headers=_auth_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["nome_completo"] == "Maria Oliveira"


@pytest.mark.asyncio
async def test_get_customer():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        create_resp = await client.post(
            CUSTOMERS_URL,
            json={"nome_completo": "Get Test", "cpf_cnpj": "44444444444"},
            headers=_auth_headers(),
        )
        cid = create_resp.json()["id"]

        response = await client.get(
            f"{CUSTOMERS_URL}/{cid}",
            headers=_auth_headers(),
        )

    assert response.status_code == 200
    assert response.json()["nome_completo"] == "Get Test"


@pytest.mark.asyncio
async def test_update_customer():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        create_resp = await client.post(
            CUSTOMERS_URL,
            json={"nome_completo": "Before Update", "cpf_cnpj": "55555555555"},
            headers=_auth_headers(),
        )
        cid = create_resp.json()["id"]

        response = await client.patch(
            f"{CUSTOMERS_URL}/{cid}",
            json={"nome_completo": "After Update", "status": "bloqueado"},
            headers=_auth_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["nome_completo"] == "After Update"
    assert data["status"] == "bloqueado"


@pytest.mark.asyncio
async def test_soft_delete_customer():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        create_resp = await client.post(
            CUSTOMERS_URL,
            json={"nome_completo": "To Delete", "cpf_cnpj": "66666666666"},
            headers=_auth_headers(),
        )
        cid = create_resp.json()["id"]

        delete_resp = await client.delete(
            f"{CUSTOMERS_URL}/{cid}",
            headers=_auth_headers(),
        )
        assert delete_resp.status_code == 204

        # Should not be found after soft delete
        get_resp = await client.get(
            f"{CUSTOMERS_URL}/{cid}",
            headers=_auth_headers(),
        )
        assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_get_nonexistent_customer():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.get(
            f"{CUSTOMERS_URL}/{uuid4()}",
            headers=_auth_headers(),
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_unauthenticated_returns_401():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.get(CUSTOMERS_URL)

    assert response.status_code == 401
