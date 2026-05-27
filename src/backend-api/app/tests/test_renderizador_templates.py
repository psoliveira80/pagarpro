"""Testes da Story 13.10 — Renderizador de Templates de Mensagem."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.infrastructure.db.session import get_engine, get_sessionmaker
from app.infrastructure.mensageria.renderizador_template import (
    CONTEXTO_EXEMPLO,
    RenderizadorTemplate,
    TemplateNaoEncontradoError,
    TemplateRenderError,
)


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

async def _get_empresa_id():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        row = (await conn.execute(text("SELECT id FROM comercial.empresas LIMIT 1"))).first()
        return row[0]


async def _set_tenant(session, empresa_id):
    await session.execute(
        text("SELECT set_config('app.empresa_id', :eid, true)"),
        {"eid": str(empresa_id)},
    )


async def _cleanup_template(nome: str):
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        await conn.execute(
            text("DELETE FROM comunicacao.templates_mensagem WHERE nome = :nome AND empresa_id IS NOT NULL"),
            {"nome": nome},
        )


# ──────────────────────────────────────────────────────────────────
# Renderização básica
# ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_renderiza_template_global_seedado():
    """Template `lembrete_vencimento` foi seedado; tenant qualquer renderiza."""
    empresa_id = await _get_empresa_id()
    sm = get_sessionmaker()
    async with sm() as session:
        await _set_tenant(session, empresa_id)
        renderizador = RenderizadorTemplate(session, empresa_id)
        rendered = await renderizador.renderizar("lembrete_vencimento", CONTEXTO_EXEMPLO)
        assert "João" in rendered
        assert "R$ 1.250,00" in rendered
        assert "ABC1D23" in rendered


@pytest.mark.asyncio
async def test_levanta_quando_template_nao_existe():
    empresa_id = await _get_empresa_id()
    sm = get_sessionmaker()
    async with sm() as session:
        await _set_tenant(session, empresa_id)
        renderizador = RenderizadorTemplate(session, empresa_id)
        with pytest.raises(TemplateNaoEncontradoError):
            await renderizador.renderizar("template_inexistente_xyz", {})


@pytest.mark.asyncio
async def test_levanta_quando_variavel_ausente_no_contexto():
    """StrictUndefined faz Jinja2 falhar em vez de renderizar string vazia."""
    empresa_id = await _get_empresa_id()
    sm = get_sessionmaker()
    async with sm() as session:
        await _set_tenant(session, empresa_id)
        renderizador = RenderizadorTemplate(session, empresa_id)
        with pytest.raises(TemplateRenderError):
            # contexto faltando `cliente` que o template referencia
            await renderizador.renderizar("lembrete_vencimento", {})


# ──────────────────────────────────────────────────────────────────
# Override por tenant
# ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_override_tenant_prevalece_sobre_global():
    nome = f"teste_override_{uuid4().hex[:8]}"
    # Cria template global como fixture
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        await conn.execute(
            text(
                "INSERT INTO comunicacao.templates_mensagem "
                "(empresa_id, nome, canal, conteudo, ativo) "
                "VALUES (NULL, :nome, 'whatsapp', 'GLOBAL: olá', true)"
            ),
            {"nome": nome},
        )

    try:
        empresa_id = await _get_empresa_id()
        sm = get_sessionmaker()
        async with sm() as session:
            await _set_tenant(session, empresa_id)
            renderizador = RenderizadorTemplate(session, empresa_id)

            # Antes do override → lê global
            v0 = await renderizador.renderizar(nome, {})
            assert v0 == "GLOBAL: olá"

            # Cria override do tenant
            await session.execute(
                text(
                    "INSERT INTO comunicacao.templates_mensagem "
                    "(empresa_id, nome, canal, conteudo, ativo) "
                    "VALUES (:eid, :nome, 'whatsapp', 'TENANT: oi', true)"
                ),
                {"eid": str(empresa_id), "nome": nome},
            )
            await session.commit()

            # Agora lê override
            v1 = await renderizador.renderizar(nome, {})
            assert v1 == "TENANT: oi"
    finally:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(text("SET LOCAL row_security = off"))
            await conn.execute(
                text("DELETE FROM comunicacao.templates_mensagem WHERE nome = :nome"),
                {"nome": nome},
            )


# ──────────────────────────────────────────────────────────────────
# Sandbox de segurança
# ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sandbox_bloqueia_acesso_a_atributos_privados():
    """SandboxedEnvironment proíbe `__class__`, `__bases__` etc.
    Mitigação contra exfiltração de objetos via template malicioso."""
    empresa_id = await _get_empresa_id()
    sm = get_sessionmaker()
    async with sm() as session:
        await _set_tenant(session, empresa_id)
        renderizador = RenderizadorTemplate(session, empresa_id)
        # Tenta escapar do sandbox via __class__ (clássico Python sandbox escape)
        malicioso = "{{ cliente.__class__.__mro__ }}"
        with pytest.raises(TemplateRenderError):
            await renderizador.preview(malicioso, {"cliente": {"nome": "x"}})


@pytest.mark.asyncio
async def test_sandbox_bloqueia_acesso_a_builtins():
    empresa_id = await _get_empresa_id()
    sm = get_sessionmaker()
    async with sm() as session:
        await _set_tenant(session, empresa_id)
        renderizador = RenderizadorTemplate(session, empresa_id)
        # SandboxedEnvironment não expõe `open`/`__import__` no contexto
        with pytest.raises(TemplateRenderError):
            await renderizador.preview("{{ open('etc/passwd').read() }}", {})


# ──────────────────────────────────────────────────────────────────
# Preview ad-hoc
# ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_preview_renderiza_sem_persistir():
    empresa_id = await _get_empresa_id()
    sm = get_sessionmaker()
    async with sm() as session:
        await _set_tenant(session, empresa_id)
        renderizador = RenderizadorTemplate(session, empresa_id)
        rendered = await renderizador.preview(
            "Olá {{cliente.nome}}, valor: {{titulo.valor}}",
            CONTEXTO_EXEMPLO,
        )
        assert "João da Silva" in rendered
        assert "R$ 1.250,00" in rendered


# ──────────────────────────────────────────────────────────────────
# Endpoints REST
# ──────────────────────────────────────────────────────────────────

async def _admin_token():
    from app.infrastructure.security.jwt_service import create_access_token

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
        return None, None
    user_id, empresa_id = row
    token = create_access_token(
        sub=str(user_id),
        email="admin@test",
        roles=["Admin"],
        empresa_id=str(empresa_id),
    )
    return token, empresa_id


@pytest.mark.asyncio
async def test_endpoint_listar_inclui_templates_globais():
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    token, _ = await _admin_token()
    if token is None:
        pytest.skip("Sem admin seed")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(
            "/api/v1/templates-mensagem",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        nomes = [t["nome"] for t in body]
        assert "lembrete_vencimento" in nomes
        assert "cobranca_vencida" in nomes
        # Templates seedados são globais
        global_t = next(t for t in body if t["nome"] == "lembrete_vencimento")
        assert global_t["escopo"] == "global"


@pytest.mark.asyncio
async def test_endpoint_post_cria_override_e_get_reflete():
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    token, _ = await _admin_token()
    if token is None:
        pytest.skip("Sem admin seed")

    nome = f"teste_endpoint_{uuid4().hex[:8]}"
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/api/v1/templates-mensagem",
                json={
                    "nome": nome,
                    "canal": "whatsapp",
                    "conteudo": "Olá {{cliente.nome}}",
                    "descricao": "Teste",
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["escopo"] == "tenant"
            assert body["nome"] == nome
    finally:
        await _cleanup_template(nome)


@pytest.mark.asyncio
async def test_endpoint_preview_422_quando_sintaxe_invalida():
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    token, _ = await _admin_token()
    if token is None:
        pytest.skip("Sem admin seed")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/templates-mensagem/preview",
            json={
                "conteudo": "{{ cliente.__class__ }}",  # sandbox bloqueia
                "contexto": {"cliente": {"nome": "x"}},
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_endpoint_preview_renderiza_com_contexto_exemplo():
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    token, _ = await _admin_token()
    if token is None:
        pytest.skip("Sem admin seed")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/templates-mensagem/preview",
            json={"conteudo": "{{cliente.nome}} - {{titulo.valor}}"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert "João da Silva" in r.json()["rendered"]
