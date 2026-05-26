"""Tests for bank reconciliation endpoints (Epic 7)."""

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
BANK_ACCOUNTS_URL = "/api/v1/bank-accounts"
RECONCILIATION_URL = "/api/v1/reconciliation"
TEST_EMAIL = "bank-test@example.com"
TEST_PASSWORD = "BankTest@123"

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
        ), {"id": user_id, "email": TEST_EMAIL, "pw": hash_password(TEST_PASSWORD), "name": "Bank Tester", "eid": empresa_id})
    token = create_access_token(sub=user_id, email=TEST_EMAIL, roles=["Admin"], empresa_id=empresa_id)
    _user_id = user_id
    _token = token
    return user_id, token


async def _cleanup() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM conta_bancaria.transacoes_bancarias"))
        await conn.execute(text("DELETE FROM conta_bancaria.sessoes_conciliacao"))
        await conn.execute(text("DELETE FROM conta_bancaria.contas_bancarias"))
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


# ── Bank Account Tests ──────────────────────────────────────


@pytest.mark.asyncio
async def test_create_bank_account():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        resp = await client.post(
            BANK_ACCOUNTS_URL,
            json={
                "nome": "Conta Principal",
                "codigo_banco": "001",
                "nome_banco": "Banco do Brasil",
                "agencia": "1234",
                "numero_conta": "56789-0",
                "tipo": "corrente",
            },
            headers=_auth_headers(),
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["nome"] == "Conta Principal"
    assert data["nome_banco"] is None  # bank_name dropped in migration 0015
    assert data["ativo"] is True


@pytest.mark.asyncio
async def test_list_bank_accounts():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        await client.post(
            BANK_ACCOUNTS_URL,
            json={"nome": "Conta A", "nome_banco": "Itau"},
            headers=_auth_headers(),
        )
        resp = await client.get(BANK_ACCOUNTS_URL, headers=_auth_headers())

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    names = [a["nome"] for a in data]
    assert "Conta A" in names


@pytest.mark.asyncio
async def test_update_bank_account():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        resp = await client.post(
            BANK_ACCOUNTS_URL,
            json={"nome": "Old Name"},
            headers=_auth_headers(),
        )
        aid = resp.json()["id"]

        resp = await client.patch(
            f"{BANK_ACCOUNTS_URL}/{aid}",
            json={"nome": "New Name"},
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    assert resp.json()["nome"] == "New Name"


@pytest.mark.asyncio
async def test_delete_bank_account():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        resp = await client.post(
            BANK_ACCOUNTS_URL,
            json={"nome": "To Delete"},
            headers=_auth_headers(),
        )
        aid = resp.json()["id"]

        resp = await client.delete(f"{BANK_ACCOUNTS_URL}/{aid}", headers=_auth_headers())
    assert resp.status_code == 204


# ── OFX Import Tests ────────────────────────────────────────


SAMPLE_OFX = """
OFXHEADER:100
DATA:OFXSGML
<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<STMTRS>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260510
<TRNAMT>1500.00
<FITID>2026051001
<MEMO>PIX - JOAO SILVA - Pagamento
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260511
<TRNAMT>-250.50
<FITID>2026051102
<MEMO>TED para fornecedor
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260512
<TRNAMT>800.00
<FITID>2026051203
<MEMO>PIX RECEBIDO Maria Santos
</STMTTRN>
</BANKTRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""


@pytest.mark.asyncio
async def test_import_ofx():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        # Create account first
        resp = await client.post(
            BANK_ACCOUNTS_URL,
            json={"nome": "OFX Account"},
            headers=_auth_headers(),
        )
        aid = resp.json()["id"]

        # Upload OFX
        resp = await client.post(
            f"{RECONCILIATION_URL}/import-ofx/{aid}",
            files={"file": ("statement.ofx", SAMPLE_OFX.encode(), "application/octet-stream")},
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_parseado"] == 3
    assert data["novos_inseridos"] == 3
    assert data["duplicatas_puladas"] == 0


@pytest.mark.asyncio
async def test_import_ofx_dedup():
    """Second import of same OFX should skip all as duplicates."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        resp = await client.post(
            BANK_ACCOUNTS_URL,
            json={"nome": "Dedup Account"},
            headers=_auth_headers(),
        )
        aid = resp.json()["id"]

        # First import
        await client.post(
            f"{RECONCILIATION_URL}/import-ofx/{aid}",
            files={"file": ("s.ofx", SAMPLE_OFX.encode(), "application/octet-stream")},
            headers=_auth_headers(),
        )

        # Second import — duplicates
        resp = await client.post(
            f"{RECONCILIATION_URL}/import-ofx/{aid}",
            files={"file": ("s.ofx", SAMPLE_OFX.encode(), "application/octet-stream")},
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["novos_inseridos"] == 0
    assert data["duplicatas_puladas"] == 3


# ── Transactions listing ────────────────────────────────────


@pytest.mark.asyncio
async def test_list_transactions():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        resp = await client.post(
            BANK_ACCOUNTS_URL,
            json={"nome": "List Account"},
            headers=_auth_headers(),
        )
        aid = resp.json()["id"]

        await client.post(
            f"{RECONCILIATION_URL}/import-ofx/{aid}",
            files={"file": ("s.ofx", SAMPLE_OFX.encode(), "application/octet-stream")},
            headers=_auth_headers(),
        )

        resp = await client.get(
            f"{RECONCILIATION_URL}/transactions",
            params={"account_id": aid},
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3


# ── Match / Reconcile ──────────────────────────────────────


@pytest.mark.asyncio
async def test_match_and_ignore():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        # Create account + import
        resp = await client.post(
            BANK_ACCOUNTS_URL,
            json={"nome": "Match Account"},
            headers=_auth_headers(),
        )
        aid = resp.json()["id"]

        await client.post(
            f"{RECONCILIATION_URL}/import-ofx/{aid}",
            files={"file": ("s.ofx", SAMPLE_OFX.encode(), "application/octet-stream")},
            headers=_auth_headers(),
        )

        # Get transactions
        resp = await client.get(
            f"{RECONCILIATION_URL}/transactions",
            params={"account_id": aid},
            headers=_auth_headers(),
        )
        txns = resp.json()["items"]
        tx_id = txns[0]["id"]

        # Ignore a transaction
        resp = await client.post(
            f"{RECONCILIATION_URL}/transactions/{tx_id}/ignore",
            headers=_auth_headers(),
        )
        assert resp.status_code == 200

        # Match another transaction to a fake target
        fake_target = str(uuid4())
        resp = await client.post(
            f"{RECONCILIATION_URL}/match",
            json={
                "transacao_ids": [txns[1]["id"]],
                "tipo_destino": "titulo_receber",
                "destino_id": fake_target,
            },
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["quantidade_conciliada"] == 1


# ── Divergences ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_divergences_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        resp = await client.get(
            f"{RECONCILIATION_URL}/divergences",
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "transacoes_orfas" in data
    assert "titulos_suspeitos_pagos" in data
    assert "divergencias_valor" in data
    assert "total_orfas" in data


# ── OFX Parser Unit Tests ──────────────────────────────────


def test_ofx_parser_basic():
    from app.infrastructure.parsing.ofx_parser import parse_ofx
    result = parse_ofx(SAMPLE_OFX)
    assert len(result) == 3
    assert result[0]["fitid"] == "2026051001"
    assert result[0]["amount"] == Decimal("1500.00")
    assert result[0]["description_clean"] == "JOAO SILVA"  # extracted from Pix pattern


def test_ofx_parser_pix_cleanup():
    from app.infrastructure.parsing.ofx_parser import parse_ofx
    result = parse_ofx(SAMPLE_OFX)
    # Third transaction: "PIX RECEBIDO Maria Santos"
    assert result[2]["description_clean"] == "Maria Santos"
