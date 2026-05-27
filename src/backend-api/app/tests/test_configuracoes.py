"""Testes da Story 13.4 — Sistema de Configurações Tipadas.

Cobre:
1. `ServicoConfiguracao.obter_*` retorna padrão quando slug não existe
2. `definir()` valida tipo antes de gravar (rejeita 'inteiro' com valor='abc')
3. CHECK constraint do banco também rejeita lixo (defesa em profundidade)
4. Override de tenant prevalece sobre config global
5. Cache Redis hit/miss/invalidação
6. Audit log gerado em mutação via endpoint
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.application.services.servico_configuracao import (
    ServicoConfiguracao,
    TipoConfiguracaoInvalidoError,
)
from app.infrastructure.db.session import get_engine, get_sessionmaker


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

async def _get_empresa_id() -> UUID:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        row = (await conn.execute(text("SELECT id FROM comercial.empresas LIMIT 1"))).first()
        if row is None:
            raise RuntimeError("Nenhuma empresa no banco — rode migrations + seed primeiro.")
        return row[0]


async def _cleanup_slug(slug: str) -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        await conn.execute(
            text("DELETE FROM config.configuracoes_sistema WHERE slug = :slug AND empresa_id IS NOT NULL"),
            {"slug": slug},
        )


# ──────────────────────────────────────────────────────────────────
# Leitura tipada + fallback
# ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_obter_inteiro_retorna_padrao_quando_slug_nao_existe():
    empresa_id = await _get_empresa_id()
    sm = get_sessionmaker()
    async with sm() as session:
        await session.execute(
            text("SELECT set_config('app.empresa_id', :eid, true)"),
            {"eid": str(empresa_id)},
        )
        servico = ServicoConfiguracao(session, empresa_id, redis=None)
        valor = await servico.obter_inteiro("slug_inexistente_xyz", "financeiro", padrao=42)
        assert valor == 42


@pytest.mark.asyncio
async def test_obter_decimal_le_config_global_seedada():
    """O seed criou `percentual_multa = 2.00` (global, decimal). Qualquer tenant lê isso."""
    empresa_id = await _get_empresa_id()
    sm = get_sessionmaker()
    async with sm() as session:
        await session.execute(
            text("SELECT set_config('app.empresa_id', :eid, true)"),
            {"eid": str(empresa_id)},
        )
        servico = ServicoConfiguracao(session, empresa_id, redis=None)
        valor = await servico.obter_decimal("percentual_multa", "financeiro", padrao=Decimal("0"))
        assert valor == Decimal("2.00")


@pytest.mark.asyncio
async def test_obter_booleano_funciona_com_seed():
    """Seed `permite_pagamento_parcial = false` (global, booleano)."""
    empresa_id = await _get_empresa_id()
    sm = get_sessionmaker()
    async with sm() as session:
        await session.execute(
            text("SELECT set_config('app.empresa_id', :eid, true)"),
            {"eid": str(empresa_id)},
        )
        servico = ServicoConfiguracao(session, empresa_id, redis=None)
        valor = await servico.obter_booleano("permite_pagamento_parcial", "financeiro", padrao=True)
        assert valor is False


# ──────────────────────────────────────────────────────────────────
# Validação de tipo (Python + CHECK constraint)
# ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_definir_rejeita_inteiro_com_valor_nao_numerico():
    """A validação Python pega antes de chegar no banco."""
    empresa_id = await _get_empresa_id()
    sm = get_sessionmaker()
    async with sm() as session:
        await session.execute(
            text("SELECT set_config('app.empresa_id', :eid, true)"),
            {"eid": str(empresa_id)},
        )
        servico = ServicoConfiguracao(session, empresa_id, redis=None)
        with pytest.raises(TipoConfiguracaoInvalidoError):
            await servico.definir("teste_invalido", "financeiro", "abc", "inteiro")


@pytest.mark.asyncio
async def test_definir_rejeita_tipo_valor_desconhecido():
    empresa_id = await _get_empresa_id()
    sm = get_sessionmaker()
    async with sm() as session:
        await session.execute(
            text("SELECT set_config('app.empresa_id', :eid, true)"),
            {"eid": str(empresa_id)},
        )
        servico = ServicoConfiguracao(session, empresa_id, redis=None)
        with pytest.raises(TipoConfiguracaoInvalidoError):
            await servico.definir("teste", "financeiro", 1, "tipo_inexistente")


@pytest.mark.asyncio
async def test_check_constraint_db_rejeita_lixo_via_sql_direto():
    """Defesa em profundidade: mesmo INSERT direto sem validação Python falha."""
    empresa_id = await _get_empresa_id()
    engine = get_engine()
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        async with engine.begin() as conn:
            await conn.execute(text("SET LOCAL row_security = off"))
            await conn.execute(
                text(
                    "INSERT INTO config.configuracoes_sistema "
                    "(empresa_id, modulo, slug, tipo_valor, valor) "
                    "VALUES (:eid, 'teste', 'check_test', 'inteiro', 'nao_eh_int')"
                ),
                {"eid": str(empresa_id)},
            )


# ──────────────────────────────────────────────────────────────────
# Override tenant prevalece sobre global
# ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_override_tenant_prevalece_sobre_global():
    """Seed define `percentual_multa=2.00` global. Tenant pode subir pra 5.00 sem afetar
    outros tenants."""
    slug = f"percentual_multa_test_{uuid4().hex[:8]}"
    # Cria config global como fixture
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        await conn.execute(
            text(
                "INSERT INTO config.configuracoes_sistema "
                "(empresa_id, modulo, slug, tipo_valor, valor) "
                "VALUES (NULL, 'financeiro', :slug, 'decimal', '2.00')"
            ),
            {"slug": slug},
        )

    try:
        empresa_id = await _get_empresa_id()
        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(empresa_id)},
            )
            servico = ServicoConfiguracao(session, empresa_id, redis=None)

            # Antes do override → lê global
            v0 = await servico.obter_decimal(slug, "financeiro", padrao=Decimal("0"))
            assert v0 == Decimal("2.00")

            # Cria override de tenant
            await servico.definir(slug, "financeiro", Decimal("5.00"), "decimal")
            await session.commit()

            # Agora lê override (cache pode estar invalidado, força nova consulta)
            servico2 = ServicoConfiguracao(session, empresa_id, redis=None)
            v1 = await servico2.obter_decimal(slug, "financeiro", padrao=Decimal("0"))
            assert v1 == Decimal("5.00")
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("SET LOCAL row_security = off"))
            await conn.execute(
                text("DELETE FROM config.configuracoes_sistema WHERE slug = :slug"),
                {"slug": slug},
            )


# ──────────────────────────────────────────────────────────────────
# Cache Redis
# ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cache_redis_hit_e_invalidacao():
    from redis.asyncio import Redis

    from app.infrastructure.settings import get_settings

    settings = get_settings()
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        # limpa toda chave config:* antes de testar
        keys = await redis.keys("config:*test_cache*")
        if keys:
            await redis.delete(*keys)

        slug = f"cache_test_{uuid4().hex[:8]}"
        empresa_id = await _get_empresa_id()
        sm = get_sessionmaker()
        try:
            async with sm() as session:
                await session.execute(
                    text("SELECT set_config('app.empresa_id', :eid, true)"),
                    {"eid": str(empresa_id)},
                )
                servico = ServicoConfiguracao(session, empresa_id, redis=redis)

                # 1ª leitura: miss → padrão. Cache __none__ é setado.
                v0 = await servico.obter_inteiro(slug, "financeiro", padrao=99)
                assert v0 == 99
                cached = await redis.get(f"config:{empresa_id}:{slug}")
                assert cached == "__none__"

                # Cria valor → invalida
                await servico.definir(slug, "financeiro", 7, "inteiro")
                await session.commit()
                cached_after_set = await redis.get(f"config:{empresa_id}:{slug}")
                assert cached_after_set is None  # invalidado

                # 3ª leitura: hit no banco, popula cache
                v1 = await servico.obter_inteiro(slug, "financeiro", padrao=99)
                assert v1 == 7
                cached_now = await redis.get(f"config:{empresa_id}:{slug}")
                assert cached_now == "7"
        finally:
            await _cleanup_slug(slug)
    finally:
        await redis.aclose()


# ──────────────────────────────────────────────────────────────────
# Endpoint REST
# ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_endpoint_put_atualiza_e_gera_audit_log():
    """PUT /api/v1/configuracoes/{slug} grava + gera audit log com categoria=configuracao."""
    from httpx import ASGITransport, AsyncClient

    from app.infrastructure.security.jwt_service import create_access_token
    from app.main import app

    # Pega um admin existente
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        row = (await conn.execute(text("""
            SELECT u.id, u.empresa_id
            FROM acesso.usuarios u
            JOIN acesso.usuario_perfis up ON up.usuario_id = u.id
            JOIN acesso.perfis p ON p.id = up.perfil_id
            WHERE LOWER(p.nome) = 'admin' AND u.ativo = true
            LIMIT 1
        """))).first()
    if row is None:
        pytest.skip("Sem admin seed disponível")

    user_id, empresa_id = row
    token = create_access_token(
        sub=str(user_id),
        email="admin@test",
        roles=["Admin"],
        empresa_id=str(empresa_id),
    )

    slug = f"endpoint_test_{uuid4().hex[:8]}"
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.put(
                f"/api/v1/configuracoes/{slug}",
                json={"valor": "10", "tipo_valor": "inteiro", "modulo": "financeiro"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["valor"] == "10"
            assert body["tipo_valor"] == "inteiro"
            assert body["modulo"] == "financeiro"
            assert body["escopo"] == "tenant"

        # Verifica audit log
        async with engine.begin() as conn:
            await conn.execute(text("SET LOCAL row_security = off"))
            audit_row = (await conn.execute(text("""
                SELECT action, category, entidade_id
                FROM logs.log_auditoria
                WHERE action = 'configuracao.atualizada' AND entidade_id = :slug
                ORDER BY criado_em DESC LIMIT 1
            """), {"slug": slug})).first()
            assert audit_row is not None
            assert audit_row[1] == "configuracao"
    finally:
        await _cleanup_slug(slug)


@pytest.mark.asyncio
async def test_endpoint_put_422_quando_tipo_invalido():
    from httpx import ASGITransport, AsyncClient

    from app.infrastructure.security.jwt_service import create_access_token
    from app.main import app

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        row = (await conn.execute(text("""
            SELECT u.id, u.empresa_id
            FROM acesso.usuarios u
            JOIN acesso.usuario_perfis up ON up.usuario_id = u.id
            JOIN acesso.perfis p ON p.id = up.perfil_id
            WHERE LOWER(p.nome) = 'admin' AND u.ativo = true
            LIMIT 1
        """))).first()
    if row is None:
        pytest.skip("Sem admin seed disponível")

    user_id, empresa_id = row
    token = create_access_token(
        sub=str(user_id),
        email="admin@test",
        roles=["Admin"],
        empresa_id=str(empresa_id),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.put(
            "/api/v1/configuracoes/teste_invalido_endpoint",
            json={"valor": "abc", "tipo_valor": "inteiro", "modulo": "financeiro"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_endpoint_get_403_para_usuario_sem_role_admin():
    """Usuário comum (sem role admin) recebe 403."""
    from httpx import ASGITransport, AsyncClient

    from app.infrastructure.security.jwt_service import create_access_token
    from app.main import app

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        # Pega user SEM role admin
        row = (await conn.execute(text("""
            SELECT u.id, u.empresa_id
            FROM acesso.usuarios u
            WHERE u.ativo = true
              AND NOT EXISTS (
                  SELECT 1 FROM acesso.usuario_perfis up
                  JOIN acesso.perfis p ON p.id = up.perfil_id
                  WHERE up.usuario_id = u.id AND LOWER(p.nome) = 'admin'
              )
            LIMIT 1
        """))).first()
    if row is None:
        pytest.skip("Sem usuário não-admin disponível")

    user_id, empresa_id = row
    token = create_access_token(
        sub=str(user_id),
        email="user@test",
        roles=[],
        empresa_id=str(empresa_id),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(
            "/api/v1/configuracoes",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403
