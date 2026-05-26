"""Testes de isolamento multi-tenant (story 12-7).

Valida que empresas diferentes não conseguem ver/modificar dados uma da outra.
Cobre:

1. **Row Level Security**: queries diretas no banco filtram por `app.empresa_id`
2. **API**: listas só retornam dados da empresa do JWT
3. **API**: GET/PATCH/DELETE de entidade de outra empresa retorna 404 (não 403 —
   404 evita revelar a existência do recurso)
4. **Sem contexto**: query sem `app.empresa_id` setado retorna vazio
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.infrastructure.db.models.contract import Contract
from app.infrastructure.db.models.customer import Customer
from app.infrastructure.db.session import get_engine, get_sessionmaker
from app.infrastructure.security.jwt_service import create_access_token
from app.infrastructure.security.password_hasher import hash_password
from app.main import app

BASE_URL = "http://test"


# ---------------------------------------------------------------------------
# Setup: duas empresas com dados próprios
# ---------------------------------------------------------------------------

async def _seed_duas_empresas() -> dict:
    """Cria duas empresas com 1 user + 2 clientes + 1 contrato cada.

    Cleanup é feito em _cleanup_duas_empresas.
    """
    engine = get_engine()
    suffix = uuid4().hex[:8]

    empresa_a_id = str(uuid4())
    empresa_b_id = str(uuid4())
    user_a_id = str(uuid4())
    user_b_id = str(uuid4())
    cliente_a1_id = str(uuid4())
    cliente_a2_id = str(uuid4())
    cliente_b1_id = str(uuid4())
    cliente_b2_id = str(uuid4())
    contrato_a_id = str(uuid4())
    contrato_b_id = str(uuid4())

    pw = hash_password("SecureP@ss123")

    async with engine.begin() as conn:
        # 2 empresas
        for eid, cnpj, razao in [
            (empresa_a_id, f"{suffix[:8]}11000100"[:14].ljust(14, "0"), f"Alpha-{suffix}"),
            (empresa_b_id, f"{suffix[:8]}22000100"[:14].ljust(14, "0"), f"Beta-{suffix}"),
        ]:
            await conn.execute(text("""
                INSERT INTO comercial.empresas (id, razao_social, cnpj, email)
                VALUES (:id, :razao, :cnpj, :email)
            """), {"id": eid, "razao": razao, "cnpj": cnpj, "email": f"{razao}@test.com"})

        # 1 user por empresa
        for uid, eid, label in [
            (user_a_id, empresa_a_id, "A"),
            (user_b_id, empresa_b_id, "B"),
        ]:
            await conn.execute(text("""
                INSERT INTO acesso.usuarios
                  (id, email, senha_hash, nome_completo, ativo, mfa_ativo, empresa_id)
                VALUES (:id, :email, :pw, :name, true, false, :eid)
            """), {
                "id": uid, "eid": eid, "pw": pw,
                "email": f"user-{label}-{suffix}@test.com",
                "name": f"User {label}",
            })

        # 2 clientes por empresa
        for cid, eid, uid in [
            (cliente_a1_id, empresa_a_id, user_a_id),
            (cliente_a2_id, empresa_a_id, user_a_id),
            (cliente_b1_id, empresa_b_id, user_b_id),
            (cliente_b2_id, empresa_b_id, user_b_id),
        ]:
            await conn.execute(text("""
                INSERT INTO cadastro.clientes
                  (id, empresa_id, nome_completo, cpf_cnpj, criado_por_id, status)
                VALUES (:id, :eid, :nome, :doc, :uid, 'ativo')
            """), {
                "id": cid, "eid": eid, "uid": uid,
                "nome": f"Cliente {cid[:6]}",
                "doc": cid.replace("-", "")[:11],
            })

        # 1 contrato por empresa
        for kid, eid, cid, uid, label in [
            (contrato_a_id, empresa_a_id, cliente_a1_id, user_a_id, "A"),
            (contrato_b_id, empresa_b_id, cliente_b1_id, user_b_id, "B"),
        ]:
            await conn.execute(text("""
                INSERT INTO contrato.contratos
                  (id, empresa_id, cliente_id, numero, valor_total, status,
                   data_inicio, data_fim, criado_por_id, modo_geracao)
                VALUES (:id, :eid, :cid, :num, 12000, 'vigente',
                        '2026-01-01', '2026-12-31', :uid, 'antecipado')
            """), {
                "id": kid, "eid": eid, "cid": cid, "uid": uid,
                "num": f"CT-{label}-{suffix}",
            })

    token_a = create_access_token(
        sub=user_a_id, email=f"user-A-{suffix}@test.com",
        roles=["Admin"], empresa_id=empresa_a_id,
    )
    token_b = create_access_token(
        sub=user_b_id, email=f"user-B-{suffix}@test.com",
        roles=["Admin"], empresa_id=empresa_b_id,
    )

    return {
        "empresa_a_id": empresa_a_id,
        "empresa_b_id": empresa_b_id,
        "user_a_id": user_a_id,
        "user_b_id": user_b_id,
        "cliente_a_ids": [cliente_a1_id, cliente_a2_id],
        "cliente_b_ids": [cliente_b1_id, cliente_b2_id],
        "contrato_a_id": contrato_a_id,
        "contrato_b_id": contrato_b_id,
        "token_a": token_a,
        "token_b": token_b,
        "suffix": suffix,
    }


async def _cleanup_duas_empresas(setup: dict) -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        # Audit log primeiro
        await conn.execute(text("ALTER TABLE logs.log_auditoria DISABLE TRIGGER trg_log_auditoria_immutable"))
        await conn.execute(text(
            "UPDATE logs.log_auditoria SET user_id = NULL WHERE user_id IN (:ua, :ub)"
        ), {"ua": setup["user_a_id"], "ub": setup["user_b_id"]})
        await conn.execute(text("ALTER TABLE logs.log_auditoria ENABLE TRIGGER trg_log_auditoria_immutable"))

        # Cascata: contratos → titulos (titulos têm FK contrato_id)
        await conn.execute(text(
            "DELETE FROM contrato.contratos WHERE id IN (:a, :b)"
        ), {"a": setup["contrato_a_id"], "b": setup["contrato_b_id"]})

        # Clientes
        for cid in (*setup["cliente_a_ids"], *setup["cliente_b_ids"]):
            await conn.execute(text("DELETE FROM cadastro.clientes WHERE id = :id"), {"id": cid})

        # Users
        await conn.execute(text(
            "DELETE FROM acesso.usuarios WHERE id IN (:a, :b)"
        ), {"a": setup["user_a_id"], "b": setup["user_b_id"]})

        # Empresas
        await conn.execute(text(
            "DELETE FROM comercial.empresas WHERE id IN (:a, :b)"
        ), {"a": setup["empresa_a_id"], "b": setup["empresa_b_id"]})


@pytest.fixture
async def duas_empresas():
    setup = await _seed_duas_empresas()
    try:
        yield setup
    finally:
        await _cleanup_duas_empresas(setup)


# ---------------------------------------------------------------------------
# Testes — RLS direto no banco
#
# A role `app` (usada pela aplicação em dev) é SUPERUSER e bypassa RLS por
# padrão. Em produção a aplicação roda com uma role separada sem
# SUPERUSER/BYPASSRLS. Para validar RLS aqui, criamos uma role efêmera
# `app_runtime_test` sem privilégios elevados e fazemos
# `SET SESSION AUTHORIZATION` antes das queries.
# ---------------------------------------------------------------------------

_RUNTIME_ROLE = "app_runtime_test"


async def _ensure_runtime_role() -> None:
    """Cria role sem SUPERUSER/BYPASSRLS para testar RLS de verdade."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text(f"""
            DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{_RUNTIME_ROLE}') THEN
                    CREATE ROLE {_RUNTIME_ROLE} NOSUPERUSER NOBYPASSRLS;
                END IF;
            END $$;
        """))
        # Permite leitura/escrita em todos os schemas tenant-scoped
        for schema in (
            "acesso", "cadastro", "veiculos", "contrato", "financeiro",
            "conta_bancaria", "cobranca", "config", "relatorios",
            "notificacoes", "logs", "comercial",
        ):
            await conn.execute(text(f"GRANT USAGE ON SCHEMA {schema} TO {_RUNTIME_ROLE}"))
            await conn.execute(text(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {schema} TO {_RUNTIME_ROLE}"
            ))


@pytest.mark.asyncio
async def test_rls_query_sem_app_empresa_id_retorna_vazio(duas_empresas):
    """Sem `app.empresa_id` setado, RLS filtra todas as linhas."""
    await _ensure_runtime_role()
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        await session.execute(text(f"SET SESSION AUTHORIZATION {_RUNTIME_ROLE}"))
        try:
            await session.execute(text("SELECT set_config('app.empresa_id', '', true)"))
            result = await session.execute(select(Customer))
            clientes = list(result.scalars().all())
        finally:
            await session.execute(text("RESET SESSION AUTHORIZATION"))

    assert clientes == [], (
        f"Sem app.empresa_id, RLS deveria filtrar tudo — retornou {len(clientes)}"
    )


@pytest.mark.asyncio
async def test_rls_isola_empresa_a_de_empresa_b(duas_empresas):
    """Com `app.empresa_id` = A, RLS NÃO retorna clientes da B."""
    await _ensure_runtime_role()
    session_factory = get_sessionmaker()
    empresa_a_id = duas_empresas["empresa_a_id"]
    cliente_b_ids = set(duas_empresas["cliente_b_ids"])

    async with session_factory() as session:
        await session.execute(text(f"SET SESSION AUTHORIZATION {_RUNTIME_ROLE}"))
        try:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": empresa_a_id},
            )
            result = await session.execute(select(Customer))
            clientes = list(result.scalars().all())
        finally:
            await session.execute(text("RESET SESSION AUTHORIZATION"))

    ids_retornados = {str(c.id) for c in clientes}
    vazamento = ids_retornados & cliente_b_ids
    assert not vazamento, f"RLS vazou clientes da empresa B: {vazamento}"


@pytest.mark.asyncio
async def test_rls_empresa_b_nao_ve_contrato_da_a(duas_empresas):
    """Empresa B com app.empresa_id próprio NÃO vê contrato da A."""
    await _ensure_runtime_role()
    session_factory = get_sessionmaker()
    empresa_b_id = duas_empresas["empresa_b_id"]
    contrato_a_id = duas_empresas["contrato_a_id"]

    async with session_factory() as session:
        await session.execute(text(f"SET SESSION AUTHORIZATION {_RUNTIME_ROLE}"))
        try:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": empresa_b_id},
            )
            result = await session.execute(
                select(Contract).where(Contract.id == contrato_a_id)
            )
            contrato = result.scalar_one_or_none()
        finally:
            await session.execute(text("RESET SESSION AUTHORIZATION"))

    assert contrato is None, (
        "RLS deveria esconder o contrato da empresa A quando context é empresa B"
    )


# ---------------------------------------------------------------------------
# Testes — API: isolamento via JWT
# ---------------------------------------------------------------------------

def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_api_listagem_clientes_isolada(duas_empresas):
    """GET /customers com token A não retorna clientes da B."""
    cliente_b_ids = set(duas_empresas["cliente_b_ids"])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        resp = await client.get(
            "/api/v1/customers?size=100",
            headers=_auth(duas_empresas["token_a"]),
        )

    assert resp.status_code == 200
    ids_retornados = {item["id"] for item in resp.json()["items"]}
    vazamento = ids_retornados & cliente_b_ids
    assert not vazamento, f"Listagem vazou clientes da B: {vazamento}"


@pytest.mark.asyncio
async def test_api_get_cliente_de_outra_empresa_retorna_404(duas_empresas):
    """GET /customers/{id} com ID da B usando token A retorna 404 (não 403)."""
    cliente_b_id = duas_empresas["cliente_b_ids"][0]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        resp = await client.get(
            f"/api/v1/customers/{cliente_b_id}",
            headers=_auth(duas_empresas["token_a"]),
        )

    assert resp.status_code == 404, (
        f"Esperado 404 (recurso 'não existe' do ponto de vista do tenant), "
        f"recebeu {resp.status_code}"
    )


@pytest.mark.asyncio
async def test_api_get_contrato_de_outra_empresa_retorna_404(duas_empresas):
    """GET /contracts/{id} com ID da B usando token A retorna 404."""
    contrato_b_id = duas_empresas["contrato_b_id"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        resp = await client.get(
            f"/api/v1/contracts/{contrato_b_id}",
            headers=_auth(duas_empresas["token_a"]),
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_delete_cliente_de_outra_empresa_retorna_404(duas_empresas):
    """DELETE /customers/{id} com ID da B usando token A retorna 404."""
    cliente_b_id = duas_empresas["cliente_b_ids"][0]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        resp = await client.delete(
            f"/api/v1/customers/{cliente_b_id}",
            headers=_auth(duas_empresas["token_a"]),
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_update_cliente_de_outra_empresa_retorna_404(duas_empresas):
    """PATCH /customers/{id} com ID da B usando token A retorna 404."""
    cliente_b_id = duas_empresas["cliente_b_ids"][0]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        resp = await client.patch(
            f"/api/v1/customers/{cliente_b_id}",
            headers=_auth(duas_empresas["token_a"]),
            json={"nome_completo": "Tentativa de hijack"},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_cliente_da_empresa_propria_acessivel(duas_empresas):
    """Sanity check: token A consegue acessar cliente da própria empresa A."""
    cliente_a_id = duas_empresas["cliente_a_ids"][0]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        resp = await client.get(
            f"/api/v1/customers/{cliente_a_id}",
            headers=_auth(duas_empresas["token_a"]),
        )

    assert resp.status_code == 200
    assert resp.json()["id"] == cliente_a_id
