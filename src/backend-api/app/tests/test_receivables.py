"""Tests for receivables endpoints (Epic 4)."""

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
CONTRACTS_URL = "/api/v1/contracts"
RECEIVABLES_URL = "/api/v1/receivables"
CUSTOMERS_URL = "/api/v1/customers"
TEST_EMAIL = "receivable-test@example.com"
TEST_PASSWORD = "ReceivableTest@123"

_user_id: str = ""
_token: str = ""
_customer_id: str = ""


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
        ), {"id": user_id, "email": TEST_EMAIL, "pw": hash_password(TEST_PASSWORD), "name": "Receivable Tester", "eid": empresa_id})
    token = create_access_token(sub=user_id, email=TEST_EMAIL, roles=["Admin"], empresa_id=empresa_id)
    _user_id = user_id
    _token = token
    return user_id, token


async def _setup_customer() -> str:
    global _customer_id
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        resp = await client.post(
            CUSTOMERS_URL,
            json={"nome_completo": "Receivable Test Customer", "cpf_cnpj": f"{uuid4().int % 10**11:011d}"},
            headers=_auth_headers(),
        )
    assert resp.status_code == 201, f"Failed to create customer: {resp.text}"
    _customer_id = resp.json()["id"]
    return _customer_id


async def _cleanup() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        # Clean payables created by this user (reversals create payables)
        await conn.execute(text(
            "DELETE FROM financeiro.titulos_pagar WHERE criado_por_id = :uid"
        ), {"uid": _user_id})
        await conn.execute(text(
            "DELETE FROM financeiro.movimentos_titulo_receber WHERE aplicado_por_id = :uid"
        ), {"uid": _user_id})
        await conn.execute(text(
            "DELETE FROM contrato.eventos_contrato WHERE criado_por_id = :uid"
        ), {"uid": _user_id})
        await conn.execute(text(
            "DELETE FROM financeiro.titulos_receber WHERE contrato_id IN "
            "(SELECT id FROM contrato.contratos WHERE criado_por_id = :uid)"
        ), {"uid": _user_id})
        await conn.execute(text(
            "DELETE FROM contrato.lotes_geracao WHERE criado_por_id = :uid"
        ), {"uid": _user_id})
        await conn.execute(text(
            "DELETE FROM contrato.contratos WHERE criado_por_id = :uid"
        ), {"uid": _user_id})
        await conn.execute(text(
            "ALTER TABLE logs.log_auditoria DISABLE TRIGGER trg_log_auditoria_immutable"
        ))
        await conn.execute(text(
            "UPDATE logs.log_auditoria SET user_id = NULL WHERE user_id = :uid"
        ), {"uid": _user_id})
        await conn.execute(text(
            "ALTER TABLE logs.log_auditoria ENABLE TRIGGER trg_log_auditoria_immutable"
        ))
        await conn.execute(text(
            "DELETE FROM cadastro.anexos_cliente WHERE cliente_id IN "
            "(SELECT id FROM cadastro.clientes WHERE criado_por_id = :uid)"
        ), {"uid": _user_id})
        await conn.execute(text(
            "DELETE FROM cadastro.clientes WHERE criado_por_id = :uid"
        ), {"uid": _user_id})
        await conn.execute(text("DELETE FROM acesso.usuarios WHERE id = :uid"), {"uid": _user_id})


@pytest.fixture(autouse=True)
async def setup_teardown():
    await _setup_test_user()
    await _setup_customer()
    yield
    await _cleanup()


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {_token}"}


def _contract_payload(**overrides) -> dict:
    base = {
        "cliente_id": _customer_id,
        "numero": f"CTR-RCV-{uuid4().hex[:8].upper()}",
        "data_inicio": "2026-06-01",
        "data_fim": "2027-05-31",
        "valor_total": "12000.00",
        "quantidade_parcelas": 12,
        "periodicidade": "mensal",
        "taxa_juros": "0",
        "metodo": "fixo",
        "observacoes": "Receivable test contract",
    }
    base.update(overrides)
    return base


async def _create_contract_and_activate(client: AsyncClient) -> dict:
    resp = await client.post(
        CONTRACTS_URL,
        json=_contract_payload(),
        headers=_auth_headers(),
    )
    assert resp.status_code == 201
    contract = resp.json()
    cid = contract["id"]
    await client.post(f"{CONTRACTS_URL}/{cid}/activate", headers=_auth_headers())
    return contract


# ── Tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_receivables():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        await _create_contract_and_activate(client)

        resp = await client.get(
            RECEIVABLES_URL,
            params={"page": 1, "size": 20},
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 12
    assert "agregados" in data
    assert "total_em_aberto" in data["agregados"]


@pytest.mark.asyncio
async def test_list_receivables_with_status_filter():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        await _create_contract_and_activate(client)

        resp = await client.get(
            RECEIVABLES_URL,
            params={"status": "em_aberto", "page": 1, "size": 5},
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert item["status"] == "em_aberto"


@pytest.mark.asyncio
async def test_updated_value():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        contract = await _create_contract_and_activate(client)
        inst_id = contract["titulos"][0]["id"]

        resp = await client.get(
            f"{RECEIVABLES_URL}/{inst_id}/updated-value",
            params={"on_date": "2028-01-15"},  # Well after due date
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert Decimal(data["original"]) == Decimal("1000.00")
    assert Decimal(data["juros"]) > 0
    assert Decimal(data["multa"]) > 0
    assert Decimal(data["total"]) > Decimal("1000.00")


@pytest.mark.asyncio
async def test_write_off():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        contract = await _create_contract_and_activate(client)
        inst_id = contract["titulos"][0]["id"]

        resp = await client.post(
            f"{RECEIVABLES_URL}/{inst_id}/write-off",
            json={
                "valor": "1000.00",
                "pago_em": "2026-07-01",
                "forma_pagamento": "pix",
            },
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pago"
    assert Decimal(data["valor_pago"]) == Decimal("1000.00")


@pytest.mark.asyncio
async def test_partial_write_off():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        contract = await _create_contract_and_activate(client)
        inst_id = contract["titulos"][0]["id"]

        resp = await client.post(
            f"{RECEIVABLES_URL}/{inst_id}/partial-write-off",
            json={
                "valor": "300.00",
                "pago_em": "2026-07-01",
                "forma_pagamento": "pix",
            },
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pago_parcial"
    assert Decimal(data["valor_pago"]) == Decimal("300.00")
    assert data["titulo_remanescente_id"] is not None
    assert Decimal(data["valor_remanescente"]) == Decimal("700.00")


@pytest.mark.asyncio
async def test_validation_queue_and_validate():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        contract = await _create_contract_and_activate(client)
        inst_id = contract["titulos"][0]["id"]

        # Manually set installment to pago_aguardando_verificacao via DB
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(text(
                "UPDATE financeiro.titulos_receber SET status = 'pago_aguardando_verificacao', "
                "valor_pago = 1000.00, pago_em = '2026-07-01', "
                "forma_pagamento = 'pix', comprovante_url = 'http://fake/receipt.png' "
                "WHERE id = :iid"
            ), {"iid": inst_id})

        # Check validation queue
        resp = await client.get(
            f"{RECEIVABLES_URL}/validation-queue",
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        queue_data = resp.json()
        assert queue_data["total"] >= 1

        # Validate (approve)
        resp = await client.post(
            f"{RECEIVABLES_URL}/{inst_id}/validate",
            json={"aprovado": True, "observacoes": "Looks good"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "pago"


@pytest.mark.asyncio
async def test_pix_qr():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        contract = await _create_contract_and_activate(client)
        inst_id = contract["titulos"][0]["id"]

        resp = await client.get(
            f"{RECEIVABLES_URL}/{inst_id}/pix-qr",
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["brcode"].startswith("0002")
    assert len(data["brcode"]) > 50


@pytest.mark.asyncio
async def test_renegotiation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        contract = await _create_contract_and_activate(client)
        # Pick first 3 installments
        inst_ids = [i["id"] for i in contract["titulos"][:3]]

        resp = await client.post(
            f"{RECEIVABLES_URL}/renegotiate",
            json={
                "titulos_ids": inst_ids,
                "nova_planilha": {
                    "valor_total": "3000.00",
                    "quantidade_parcelas": 6,
                    "data_inicio": "2026-08-01",
                    "periodicidade": "mensal",
                    "metodo": "fixo",
                },
            },
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["quantidade_original"] == 3
    assert len(data["novos_titulos"]) == 6


@pytest.mark.asyncio
async def test_reversal():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        contract = await _create_contract_and_activate(client)
        inst_id = contract["titulos"][0]["id"]

        # First pay it
        await client.post(
            f"{RECEIVABLES_URL}/{inst_id}/write-off",
            json={
                "valor": "1000.00",
                "pago_em": "2026-07-01",
                "forma_pagamento": "pix",
            },
            headers=_auth_headers(),
        )

        # Now reverse
        resp = await client.post(
            f"{RECEIVABLES_URL}/{inst_id}/reverse",
            json={"motivo": "Customer dispute"},
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["tipo_movimento"] == "full_reversal"
    assert Decimal(data["valor_estornado"]) == Decimal("1000.00")
    assert data["titulo_pagar_id"] is not None


@pytest.mark.asyncio
async def test_bulk_write_off():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        contract = await _create_contract_and_activate(client)
        # Pick first 3 installments (3 x 1000 = 3000)
        inst_ids = [i["id"] for i in contract["titulos"][:3]]

        # Pay 2500 — should fully pay first 2 and partially pay 3rd
        resp = await client.post(
            f"{RECEIVABLES_URL}/bulk-write-off",
            json={
                "titulos_ids": inst_ids,
                "valor_total": "2500.00",
                "pago_em": "2026-07-01",
                "forma_pagamento": "pix",
            },
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["resultados"]) == 3
    assert Decimal(data["total_aplicado"]) == Decimal("2500.00")
    assert Decimal(data["restante"]) == Decimal("0.00")
    # First two should be pago, third pago_parcial
    assert data["resultados"][0]["status"] == "pago"
    assert data["resultados"][1]["status"] == "pago"
    assert data["resultados"][2]["status"] == "pago_parcial"
