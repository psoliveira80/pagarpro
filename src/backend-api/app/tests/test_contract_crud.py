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
CUSTOMERS_URL = "/api/v1/customers"
TEST_EMAIL = "contract-test@example.com"
TEST_PASSWORD = "ContractTest@123"

_user_id: str = ""
_token: str = ""
_customer_id: str = ""


async def _setup_test_user() -> tuple[str, str]:
    global _user_id, _token
    user_id = str(uuid4())
    engine = get_engine()
    async with engine.begin() as conn:
        # Nullify stale audit log references before deleting user
        existing = (await conn.execute(text(
            "SELECT id FROM acesso.usuarios WHERE email = :e"
        ), {"e": TEST_EMAIL})).first()
        if existing:
            old_uid = str(existing[0])
            await conn.execute(text(
                "ALTER TABLE logs.log_auditoria DISABLE TRIGGER trg_log_auditoria_immutable"
            ))
            await conn.execute(text(
                "UPDATE logs.log_auditoria SET user_id = NULL WHERE user_id = :uid"
            ), {"uid": old_uid})
            await conn.execute(text(
                "ALTER TABLE logs.log_auditoria ENABLE TRIGGER trg_log_auditoria_immutable"
            ))
            await conn.execute(text(
                "DELETE FROM acesso.refresh_tokens WHERE usuario_id = :uid"
            ), {"uid": old_uid})
            # Clean stale contracts/customers created by old user
            await conn.execute(text(
                "DELETE FROM financeiro.titulos_receber WHERE contrato_id IN "
                "(SELECT id FROM contrato.contratos WHERE criado_por_id = :uid)"
            ), {"uid": old_uid})
            await conn.execute(text(
                "DELETE FROM contrato.eventos_contrato WHERE criado_por_id = :uid"
            ), {"uid": old_uid})
            await conn.execute(text(
                "DELETE FROM contrato.lotes_geracao WHERE criado_por_id = :uid"
            ), {"uid": old_uid})
            await conn.execute(text(
                "DELETE FROM contrato.contratos WHERE criado_por_id = :uid"
            ), {"uid": old_uid})
            await conn.execute(text(
                "DELETE FROM cadastro.anexos_cliente WHERE criado_por_id = :uid"
            ), {"uid": old_uid})
            await conn.execute(text(
                "DELETE FROM cadastro.clientes WHERE criado_por_id = :uid"
            ), {"uid": old_uid})
        await conn.execute(text("DELETE FROM acesso.usuarios WHERE email = :e"), {"e": TEST_EMAIL})
        empresa_row = (await conn.execute(text("SELECT id FROM comercial.empresas LIMIT 1"))).first()
        assert empresa_row is not None, "No empresa found — run seed first"
        empresa_id = str(empresa_row[0])
        await conn.execute(text(
            "INSERT INTO acesso.usuarios (id, email, senha_hash, nome_completo, ativo, mfa_ativo, empresa_id) "
            "VALUES (:id, :email, :pw, :name, true, false, :eid)"
        ), {"id": user_id, "email": TEST_EMAIL, "pw": hash_password(TEST_PASSWORD), "name": "Contract Tester", "eid": empresa_id})

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
            json={"nome_completo": "Contract Test Customer", "cpf_cnpj": f"{uuid4().int % 10**11:011d}"},
            headers=_auth_headers(),
        )
    assert resp.status_code == 201, f"Failed to create customer: {resp.text}"
    _customer_id = resp.json()["id"]
    return _customer_id


async def _cleanup() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        # Clean up contract-related data created by this test user
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
        # Clean audit log references
        await conn.execute(text(
            "ALTER TABLE logs.log_auditoria DISABLE TRIGGER trg_log_auditoria_immutable"
        ))
        await conn.execute(text(
            "UPDATE logs.log_auditoria SET user_id = NULL WHERE user_id = :uid"
        ), {"uid": _user_id})
        await conn.execute(text(
            "ALTER TABLE logs.log_auditoria ENABLE TRIGGER trg_log_auditoria_immutable"
        ))
        # Clean customer attachments and customers
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


def _contract_payload(**overrides) -> dict:  # type: ignore[no-untyped-def]
    base = {
        "cliente_id": _customer_id,
        "numero": f"CTR-{uuid4().hex[:8].upper()}",
        "data_inicio": "2026-06-01",
        "data_fim": "2027-05-31",
        "valor_total": "12000.00",
        "quantidade_parcelas": 12,
        "periodicidade": "mensal",
        "taxa_juros": "0",
        "metodo": "fixo",
        "observacoes": "Test contract",
    }
    base.update(overrides)
    return base


async def _create_contract(client: AsyncClient, **overrides) -> dict:  # type: ignore[no-untyped-def]
    resp = await client.post(
        CONTRACTS_URL,
        json=_contract_payload(**overrides),
        headers=_auth_headers(),
    )
    assert resp.status_code == 201, f"Failed to create contract: {resp.text}"
    return resp.json()


# ── Tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_draft_contract():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        data = await _create_contract(client)

    assert data["status"] == "rascunho"
    assert data["cliente_id"] == _customer_id
    assert len(data["titulos"]) == 12
    assert Decimal(data["valor_total"]) == Decimal("12000.00")
    # Each titulo should be 1000.00
    assert Decimal(data["titulos"][0]["valor"]) == Decimal("1000.00")


@pytest.mark.asyncio
async def test_preview_schedule():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        resp = await client.post(
            f"{CONTRACTS_URL}/preview-schedule",
            json={
                "valor_total": "6000.00",
                "quantidade_parcelas": 6,
                "data_inicio": "2026-06-01",
                "periodicidade": "mensal",
                "metodo": "fixo",
            },
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["titulos"]) == 6
    assert Decimal(data["total"]) == Decimal("6000.00")
    assert Decimal(data["titulos"][0]["valor"]) == Decimal("1000.00")


@pytest.mark.asyncio
async def test_activate_contract():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        contract = await _create_contract(client)
        cid = contract["id"]

        resp = await client.post(
            f"{CONTRACTS_URL}/{cid}/activate",
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "vigente"
    assert data["mensagem"] == "Contrato ativado com sucesso"


@pytest.mark.asyncio
async def test_activate_non_draft_fails():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        contract = await _create_contract(client)
        cid = contract["id"]

        # Activate first time
        await client.post(f"{CONTRACTS_URL}/{cid}/activate", headers=_auth_headers())

        # Try to activate again
        resp = await client.post(f"{CONTRACTS_URL}/{cid}/activate", headers=_auth_headers())

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_contracts():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        await _create_contract(client)
        await _create_contract(client)

        resp = await client.get(
            CONTRACTS_URL,
            params={"page": 1, "size": 10},
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    assert len(data["items"]) >= 2


@pytest.mark.asyncio
async def test_get_contract_detail():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        contract = await _create_contract(client)
        cid = contract["id"]

        resp = await client.get(f"{CONTRACTS_URL}/{cid}", headers=_auth_headers())

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == cid
    assert len(data["titulos"]) == 12


@pytest.mark.asyncio
async def test_update_draft_contract():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        contract = await _create_contract(client)
        cid = contract["id"]

        resp = await client.patch(
            f"{CONTRACTS_URL}/{cid}",
            json={"observacoes": "Updated notes", "clausulas_md": "New clause text"},
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["observacoes"] == "Updated notes"
    assert data["clausulas_md"] == "New clause text"


@pytest.mark.asyncio
async def test_terminate_contract():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        contract = await _create_contract(client)
        cid = contract["id"]

        # Activate first
        await client.post(f"{CONTRACTS_URL}/{cid}/activate", headers=_auth_headers())

        # Terminate
        resp = await client.post(
            f"{CONTRACTS_URL}/{cid}/terminate",
            json={
                "motivo": "Customer request",
                "data_efetiva": "2026-07-01",
                "valor_multa": "500.00",
            },
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "encerrado_sem_pendencia"
    assert data["quantidade_titulos_em_aberto"] == 12
    assert Decimal(data["valor_multa"]) == Decimal("500.00")


@pytest.mark.asyncio
async def test_bulk_edit_dry_run():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        contract = await _create_contract(client)
        cid = contract["id"]
        inst_id = contract["titulos"][0]["id"]

        resp = await client.post(
            f"{CONTRACTS_URL}/{cid}/installments/bulk-edit",
            json={
                "acoes": [
                    {
                        "titulo_id": inst_id,
                        "acao": "discount",
                        "params": {"percentage": 10},
                    }
                ],
                "dry_run": True,
            },
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["aplicado"] is False
    assert len(data["diffs"]) == 1
    assert Decimal(data["diffs"][0]["valor_antigo"]) == Decimal("1000.00")
    assert Decimal(data["diffs"][0]["valor_novo"]) == Decimal("900.00")


@pytest.mark.asyncio
async def test_bulk_edit_apply():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        contract = await _create_contract(client)
        cid = contract["id"]
        inst_id = contract["titulos"][0]["id"]

        resp = await client.post(
            f"{CONTRACTS_URL}/{cid}/installments/bulk-edit",
            json={
                "acoes": [
                    {
                        "titulo_id": inst_id,
                        "acao": "set_value",
                        "params": {"value": "800.00"},
                    }
                ],
                "dry_run": False,
            },
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["aplicado"] is True
    assert Decimal(data["diffs"][0]["valor_novo"]) == Decimal("800.00")


@pytest.mark.asyncio
async def test_simulate_contract():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        resp = await client.post(
            f"{CONTRACTS_URL}/simulate",
            json={
                "valor_total": "10000.00",
                "quantidade_parcelas": 10,
                "data_inicio": "2026-06-01",
                "periodicidade": "mensal",
                "taxa_juros": "0.02",
                "metodo": "price",
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["titulos"]) == 10
    assert Decimal(data["resumo"]["total_juros"]) > 0
    assert Decimal(data["resumo"]["total_pago"]) > Decimal("10000.00")


@pytest.mark.asyncio
async def test_contract_events_timeline():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        contract = await _create_contract(client)
        cid = contract["id"]

        # Activate to generate another event
        await client.post(f"{CONTRACTS_URL}/{cid}/activate", headers=_auth_headers())

        resp = await client.get(
            f"{CONTRACTS_URL}/{cid}/events",
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2  # created + activated
    event_types = [e["tipo"] for e in data["items"]]
    assert "contrato_criado" in event_types
    assert "contrato_ativado" in event_types


@pytest.mark.asyncio
async def test_get_nonexistent_contract():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        resp = await client.get(
            f"{CONTRACTS_URL}/{uuid4()}",
            headers=_auth_headers(),
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_contract_number():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        cn = f"CTR-DUP-{uuid4().hex[:6].upper()}"
        await _create_contract(client, numero=cn)
        resp = await client.post(
            CONTRACTS_URL,
            json=_contract_payload(numero=cn),
            headers=_auth_headers(),
        )

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_generation_list_and_rollback():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        contract = await _create_contract(client)
        cid = contract["id"]

        # List generations
        resp = await client.get(
            f"{CONTRACTS_URL}/{cid}/generations",
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        gens = resp.json()
        assert len(gens) == 1
        gen_id = gens[0]["id"]

        # Rollback (no paid installments -> hard delete)
        resp = await client.post(
            f"{CONTRACTS_URL}/{cid}/generations/{gen_id}/rollback",
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["method"] == "hard_delete"
        assert data["status"] == "rolled_back"

        # Verify installments are gone
        detail = await client.get(f"{CONTRACTS_URL}/{cid}", headers=_auth_headers())
        assert detail.status_code == 200
        assert len(detail.json()["titulos"]) == 0
