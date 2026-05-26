"""Tests for payables, suppliers, expense categories endpoints (Epic 5)."""

from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.infrastructure.db.session import get_engine
from app.infrastructure.security.password_hasher import hash_password
from app.infrastructure.security.jwt_service import create_access_token
from app.main import app

BASE_URL = "http://test"
PAYABLES_URL = "/api/v1/payables"
SUPPLIERS_URL = "/api/v1/suppliers"
CATEGORIES_URL = "/api/v1/expense-categories"
RECURRING_URL = "/api/v1/recurring-payables"
REPORTS_URL = "/api/v1/reports"
TEST_EMAIL = "payable-test@example.com"
TEST_PASSWORD = "PayableTest@123"

_user_id: str = ""
_token: str = ""


async def _setup_test_user() -> tuple[str, str]:
    global _user_id, _token
    user_id = str(uuid4())
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM acesso.usuarios WHERE email = :e"), {"e": TEST_EMAIL})
        empresa_row = (await conn.execute(text("SELECT id FROM comercial.empresas LIMIT 1"))).first()
        assert empresa_row is not None, "No empresa found — run seed first"
        empresa_id = str(empresa_row[0])
        await conn.execute(text(
            "INSERT INTO acesso.usuarios (id, email, senha_hash, nome_completo, ativo, mfa_ativo, empresa_id) "
            "VALUES (:id, :email, :pw, :name, true, false, :eid)"
        ), {"id": user_id, "email": TEST_EMAIL, "pw": hash_password(TEST_PASSWORD), "name": "Payable Tester", "eid": empresa_id})
    token = create_access_token(sub=user_id, email=TEST_EMAIL, roles=["Admin"], empresa_id=empresa_id)
    _user_id = user_id
    _token = token
    return user_id, token


async def _cleanup() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text(
            "DELETE FROM financeiro.titulos_pagar WHERE criado_por_id = :uid"
        ), {"uid": _user_id})
        await conn.execute(text(
            "DELETE FROM financeiro.despesas_recorrentes WHERE criado_por_id = :uid"
        ), {"uid": _user_id})
        # Don't delete seeded categories — only test-created suppliers
        await conn.execute(text(
            "DELETE FROM cadastro.fornecedores WHERE nome LIKE 'Test Supplier%'"
        ))
        await conn.execute(text(
            "ALTER TABLE logs.log_auditoria DISABLE TRIGGER trg_log_auditoria_immutable"
        ))
        await conn.execute(text(
            "UPDATE logs.log_auditoria SET user_id = NULL WHERE user_id = :uid"
        ), {"uid": _user_id})
        await conn.execute(text(
            "ALTER TABLE logs.log_auditoria ENABLE TRIGGER trg_log_auditoria_immutable"
        ))
        await conn.execute(text("DELETE FROM acesso.usuarios WHERE id = :uid"), {"uid": _user_id})


@pytest.fixture(autouse=True)
async def setup_teardown():
    await _setup_test_user()
    yield
    await _cleanup()


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {_token}"}


# ── Tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_expense_categories():
    """Seeded categories should exist."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        resp = await client.get(CATEGORIES_URL, headers=_auth_headers())

    assert resp.status_code == 200
    data = resp.json()
    names = [c["nome"] for c in data]
    assert "Administrativo" in names
    assert "Operacional" in names


@pytest.mark.asyncio
async def test_create_and_get_supplier():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        resp = await client.post(
            SUPPLIERS_URL,
            json={"nome": f"Test Supplier {uuid4().hex[:6]}", "cpf_cnpj": f"{uuid4().int % 10**11:011d}"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 201
        supplier = resp.json()
        sid = supplier["id"]

        resp = await client.get(f"{SUPPLIERS_URL}/{sid}", headers=_auth_headers())
        assert resp.status_code == 200
        assert resp.json()["id"] == sid


@pytest.mark.asyncio
async def test_create_payable():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        resp = await client.post(
            PAYABLES_URL,
            json={
                "descricao": "Office supplies",
                "valor": "250.00",
                "data_vencimento": "2026-07-15",
            },
            headers=_auth_headers(),
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pendente"
    assert Decimal(data["valor"]) == Decimal("250.00")


@pytest.mark.asyncio
async def test_pay_payable():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        # Create
        resp = await client.post(
            PAYABLES_URL,
            json={"descricao": "Electric bill", "valor": "500.00", "data_vencimento": "2026-07-10"},
            headers=_auth_headers(),
        )
        pid = resp.json()["id"]

        # Pay
        resp = await client.post(
            f"{PAYABLES_URL}/{pid}/pay",
            json={"data_pagamento": "2026-07-08", "forma_pagamento": "transfer"},
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "pago"
    assert resp.json()["data_pagamento"] == "2026-07-08"


@pytest.mark.asyncio
async def test_quick_pay():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        resp = await client.post(
            f"{PAYABLES_URL}/quick-pay",
            json={
                "descricao": "Taxi receipt",
                "valor": "45.00",
                "data_vencimento": "2026-07-01",
                "data_pagamento": "2026-07-01",
                "forma_pagamento": "cash",
            },
            headers=_auth_headers(),
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pago"
    assert Decimal(data["valor"]) == Decimal("45.00")


@pytest.mark.asyncio
async def test_create_recurring_payable():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        resp = await client.post(
            RECURRING_URL,
            json={
                "descricao": "Monthly rent",
                "valor": "3000.00",
                "periodicidade": "mensal",
                "dia_do_mes": 5,
                "proxima_geracao_em": "2026-08-05",
            },
            headers=_auth_headers(),
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["periodicidade"] == "mensal"
    assert data["ativo"] is True


@pytest.mark.asyncio
async def test_dre_report():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        resp = await client.get(
            f"{REPORTS_URL}/dre",
            params={"period_start": "2026-01-01", "period_end": "2026-12-31"},
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "receitas" in data
    assert "despesas" in data
    assert "resultado_liquido" in data
    assert data["periodo_inicio"] == "2026-01-01"
    assert data["periodo_fim"] == "2026-12-31"


@pytest.mark.asyncio
async def test_delete_supplier():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        resp = await client.post(
            SUPPLIERS_URL,
            json={"nome": f"Test Supplier Del {uuid4().hex[:6]}"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 201
        sid = resp.json()["id"]

        resp = await client.delete(f"{SUPPLIERS_URL}/{sid}", headers=_auth_headers())
        assert resp.status_code == 204

        # Should be gone (soft deleted)
        resp = await client.get(f"{SUPPLIERS_URL}/{sid}", headers=_auth_headers())
        assert resp.status_code == 404
