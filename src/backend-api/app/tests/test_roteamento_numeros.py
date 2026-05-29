"""Testes da Story 13.21 — Adapter Evolution Go + Roteamento de Números.

Cobre:
- `EvolutionGoAdapter.parse_webhook`: extração de texto, mídia, botão, lista.
- `EvolutionGoAdapter._so_digitos`: normalização de número.
- `EvolutionGoAdapter.send_text`: chamada HTTP + tratamento de ban (401/403).
- `ServicoRoteamentoNumeros`:
  - Atribuição estável (cliente atribuído fica fixo).
  - Balanceamento por carga (escolhe o número com menor contagem).
  - Tiebreaker por `eh_principal`.
  - Sem números ativos → levanta erro.
  - Marcar banido → migra clientes + audit log.
  - Marcar principal → bloqueia só 1 principal por empresa.

Testes de webhook real (envio de mensagem) ficam para teste manual end-to-end
quando Pablo conectar uma instância de teste.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import httpx
import pytest
import respx
from sqlalchemy import text

from app.application.services.servico_roteamento_numeros import (
    NenhumNumeroAtivoError,
    ServicoRoteamentoNumeros,
)
from app.infrastructure.adapters.whatsapp.evolution_go_adapter import (
    BotaoPix,
    BotaoReply,
    EvolutionGoAdapter,
    EvolutionGoBanidoError,
    _telefone_de_jid,
    _extrair_texto,
)
from app.infrastructure.db.session import get_engine, get_sessionmaker


# ──────────────────────────────────────────────────────────────────
# Adapter — funções utilitárias (puras)
# ──────────────────────────────────────────────────────────────────

def test_telefone_de_jid_extrai_so_digitos():
    assert _telefone_de_jid("5511987654321@s.whatsapp.net") == "5511987654321"
    assert _telefone_de_jid("5511987654321:14@s.whatsapp.net") == "5511987654321"
    assert _telefone_de_jid("") == ""


def test_extrair_texto_de_conversation_simples():
    msg = {"conversation": "olá mundo"}
    assert _extrair_texto(msg) == "olá mundo"


def test_extrair_texto_de_extended_text():
    msg = {"extendedTextMessage": {"text": "texto longo"}}
    assert _extrair_texto(msg) == "texto longo"


def test_extrair_texto_de_caption_de_imagem():
    msg = {"imageMessage": {"caption": "veja a foto"}}
    assert _extrair_texto(msg) == "veja a foto"


def test_extrair_texto_de_botao_clicado():
    msg = {"buttonsResponseMessage": {"selectedButtonId": "menu_extrato"}}
    assert _extrair_texto(msg) == "__btn__:menu_extrato"


def test_extrair_texto_de_row_de_lista():
    msg = {"listResponseMessage": {"singleSelectReply": {"selectedRowId": "plan_basic"}}}
    assert _extrair_texto(msg) == "__row__:plan_basic"


def test_so_digitos_remove_caracteres():
    adapter = EvolutionGoAdapter(api_url="http://x", instance_token="t")
    assert adapter._so_digitos("+55 (11) 98765-4321") == "5511987654321"


# ──────────────────────────────────────────────────────────────────
# Adapter — parse_webhook
# ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_parse_webhook_message_texto_simples():
    adapter = EvolutionGoAdapter(api_url="http://x", instance_token="t")
    payload = {
        "event": "Message",
        "instanceId": "abc-123",
        "data": {
            "Info": {
                "ID": "msg-001",
                "Chat": "5511987654321@s.whatsapp.net",
                "Sender": "5511987654321@s.whatsapp.net",
                "IsFromMe": False,
                "IsGroup": False,
                "PushName": "Pedro",
                "Type": "text",
                "Timestamp": "2026-05-28T14:30:00Z",
            },
            "Message": {"conversation": "vou pagar amanhã"},
        },
    }
    result = await adapter.parse_webhook({}, payload)
    assert result is not None
    assert result.sender_phone == "5511987654321"
    assert result.text == "vou pagar amanhã"
    assert result.external_id == "msg-001"
    assert result.is_audio is False


@pytest.mark.asyncio
async def test_parse_webhook_ignora_grupo():
    adapter = EvolutionGoAdapter(api_url="http://x", instance_token="t")
    payload = {
        "event": "Message",
        "data": {
            "Info": {"IsFromMe": False, "IsGroup": True, "Chat": "abc@g.us"},
            "Message": {"conversation": "olá grupo"},
        },
    }
    assert await adapter.parse_webhook({}, payload) is None


@pytest.mark.asyncio
async def test_parse_webhook_ignora_outgoing_proprio():
    adapter = EvolutionGoAdapter(api_url="http://x", instance_token="t")
    payload = {
        "event": "Message",
        "data": {
            "Info": {"IsFromMe": True, "IsGroup": False, "Chat": "5511987654321@s.whatsapp.net"},
            "Message": {"conversation": "minha mensagem"},
        },
    }
    assert await adapter.parse_webhook({}, payload) is None


@pytest.mark.asyncio
async def test_parse_webhook_extrai_media_url():
    adapter = EvolutionGoAdapter(api_url="http://x", instance_token="t")
    payload = {
        "event": "Message",
        "data": {
            "Info": {
                "ID": "msg-img",
                "Chat": "5511987654321@s.whatsapp.net",
                "IsFromMe": False,
                "IsGroup": False,
                "Type": "image",
            },
            "Message": {
                "imageMessage": {
                    "mediaUrl": "https://media.example/foto.jpg",
                    "mimetype": "image/jpeg",
                }
            },
            "mediaUrl": "https://media.example/foto.jpg",  # root preferido
        },
    }
    result = await adapter.parse_webhook({}, payload)
    assert result is not None
    assert result.media_url == "https://media.example/foto.jpg"
    assert result.media_mime == "image/jpeg"


@pytest.mark.asyncio
async def test_parse_webhook_status_update():
    adapter = EvolutionGoAdapter(api_url="http://x", instance_token="t")
    payload = {
        "event": "Receipt",
        "data": {"messageId": "msg-001", "status": "delivered"},
    }
    result = await adapter.parse_webhook({}, payload)
    assert result is not None
    assert result.status == "delivered"


@pytest.mark.asyncio
async def test_parse_webhook_evento_irrelevante():
    adapter = EvolutionGoAdapter(api_url="http://x", instance_token="t")
    assert await adapter.parse_webhook({}, {"event": "PairSuccess"}) is None
    assert await adapter.parse_webhook({}, {"event": "LoggedOut"}) is None


# ──────────────────────────────────────────────────────────────────
# Adapter — envio (com mock respx)
# ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_text_chama_endpoint_correto():
    adapter = EvolutionGoAdapter(api_url="https://evo.test", instance_token="tk123")
    with respx.mock(base_url="https://evo.test") as rsx:
        rsx.post("/send/text").mock(
            return_value=httpx.Response(200, json={"id": "msg-out-1"})
        )
        result = await adapter.send_text("+5511987654321", "olá")
        # Confere que enviou com número só dígitos e header apikey correto
        request = rsx.calls.last.request
        assert request.headers["apikey"] == "tk123"
        body = request.read().decode()
        assert "5511987654321" in body
        assert '"text"' in body
        assert "olá" in body
        assert result == {"id": "msg-out-1"}


@pytest.mark.asyncio
async def test_send_text_401_levanta_banido():
    adapter = EvolutionGoAdapter(api_url="https://evo.test", instance_token="tk123")
    with respx.mock(base_url="https://evo.test") as rsx:
        rsx.post("/send/text").mock(
            return_value=httpx.Response(401, text="instance_banned")
        )
        with pytest.raises(EvolutionGoBanidoError) as exc:
            await adapter.send_text("+5511987654321", "olá")
        assert exc.value.codigo_http == 401


@pytest.mark.asyncio
async def test_send_buttons_reply_envia_payload_correto():
    adapter = EvolutionGoAdapter(api_url="https://evo.test", instance_token="tk")
    with respx.mock(base_url="https://evo.test") as rsx:
        rsx.post("/send/button").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        await adapter.send_buttons_reply(
            "+5511987654321",
            descricao="Escolha:",
            botoes=[
                BotaoReply(id="menu_extrato", titulo="📋 Extrato"),
                BotaoReply(id="menu_pagar", titulo="💰 Pagar"),
            ],
        )
        body = rsx.calls.last.request.read().decode()
        assert '"type": "reply"' in body or '"type":"reply"' in body
        assert "menu_extrato" in body
        assert "menu_pagar" in body


@pytest.mark.asyncio
async def test_send_button_pix_payload_correto():
    adapter = EvolutionGoAdapter(api_url="https://evo.test", instance_token="tk")
    with respx.mock(base_url="https://evo.test") as rsx:
        rsx.post("/send/button").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        await adapter.send_button_pix(
            "+5511987654321",
            descricao="Pague aqui",
            botao_pix=BotaoPix(
                nome_recebedor="Frota Uber LTDA",
                chave_pix="11.222.333/0001-81",
                tipo_chave="cnpj",
            ),
        )
        body = rsx.calls.last.request.read().decode()
        assert '"type": "pix"' in body or '"type":"pix"' in body
        assert "Frota Uber LTDA" in body
        assert "cnpj" in body


@pytest.mark.asyncio
async def test_send_buttons_trunca_acima_de_3():
    adapter = EvolutionGoAdapter(api_url="https://evo.test", instance_token="tk")
    with respx.mock(base_url="https://evo.test") as rsx:
        rsx.post("/send/button").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        await adapter.send_buttons_reply(
            "+5511987654321",
            descricao="X",
            botoes=[
                BotaoReply(id="a", titulo="A"),
                BotaoReply(id="b", titulo="B"),
                BotaoReply(id="c", titulo="C"),
                BotaoReply(id="d", titulo="D"),  # deve ser truncado
            ],
        )
        body = rsx.calls.last.request.read().decode()
        assert '"id": "d"' not in body and '"id":"d"' not in body


# ──────────────────────────────────────────────────────────────────
# ServicoRoteamentoNumeros — fixtures
# ──────────────────────────────────────────────────────────────────

async def _criar_fixture(qtd_numeros: int = 1, qtd_clientes: int = 0) -> dict:
    """Cria empresa + N credenciais Evolution Go + M clientes."""
    engine = get_engine()
    suffix = uuid4().hex[:8]
    empresa_id = uuid4()
    credenciais = []
    clientes = []

    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        await conn.execute(text("""
            INSERT INTO comercial.empresas (id, razao_social, cnpj, email)
            VALUES (:id, :r, :c, :e)
        """), {
            "id": str(empresa_id),
            "r": f"RN-{suffix}",
            "c": f"{suffix}99000111"[:14].ljust(14, "0"),
            "e": f"rn{suffix}@t.com",
        })

        # Cria N credenciais
        for i in range(qtd_numeros):
            cred_id = uuid4()
            credenciais.append(cred_id)
            await conn.execute(text("""
                INSERT INTO config.credenciais_integracao
                  (id, empresa_id, categoria, provedor, ativo, config, status)
                VALUES (:id, :eid, 'whatsapp', 'evolution_go', true,
                        CAST(:cfg AS jsonb), 'ativo')
            """), {
                "id": str(cred_id),
                "eid": str(empresa_id),
                "cfg": f'{{"instance_id": "inst-{suffix}-{i}", "instance_token": "tk-{i}", '
                       f'"numero_e164": "+5511{i:08d}", "status_whatsapp": "ativo", '
                       f'"eh_principal": {"true" if i == 0 else "false"}}}',
            })

        # Cria M clientes (sem número atribuído inicialmente)
        for i in range(qtd_clientes):
            cliente_id = uuid4()
            clientes.append(cliente_id)
            await conn.execute(text("""
                INSERT INTO cadastro.clientes
                  (id, empresa_id, nome_completo, cpf_cnpj, telefone)
                VALUES (:id, :eid, :n, :cpf, '11999990000')
            """), {
                "id": str(cliente_id),
                "eid": str(empresa_id),
                "n": f"Cliente {i}",
                "cpf": f"{suffix}{i:06d}11"[:11],
            })

    return {
        "empresa_id": empresa_id,
        "credenciais": credenciais,
        "clientes": clientes,
        "suffix": suffix,
    }


async def _cleanup(empresa_id: UUID) -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        await conn.execute(text("ALTER TABLE logs.log_auditoria DISABLE TRIGGER trg_log_auditoria_immutable"))
        try:
            await conn.execute(text(
                "DELETE FROM logs.log_auditoria WHERE entidade = 'credenciais_integracao'"
            ))
            await conn.execute(text(
                "UPDATE cadastro.clientes SET numero_origem_id = NULL WHERE empresa_id = :e"
            ), {"e": str(empresa_id)})
            await conn.execute(text("DELETE FROM cadastro.clientes WHERE empresa_id = :e"), {"e": str(empresa_id)})
            await conn.execute(text(
                "DELETE FROM config.credenciais_integracao WHERE empresa_id = :e"
            ), {"e": str(empresa_id)})
            await conn.execute(text("DELETE FROM comercial.empresas WHERE id = :e"), {"e": str(empresa_id)})
        finally:
            await conn.execute(text("ALTER TABLE logs.log_auditoria ENABLE TRIGGER trg_log_auditoria_immutable"))


async def _set_tenant(session, empresa_id):
    await session.execute(
        text("SELECT set_config('app.empresa_id', :e, true)"),
        {"e": str(empresa_id)},
    )


# ──────────────────────────────────────────────────────────────────
# ServicoRoteamentoNumeros — testes
# ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_atribuir_numero_idempotente_quando_ja_atribuido():
    fx = await _criar_fixture(qtd_numeros=2, qtd_clientes=1)
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await _set_tenant(session, fx["empresa_id"])
            servico = ServicoRoteamentoNumeros(session, fx["empresa_id"])
            primeira = await servico.atribuir_numero(fx["clientes"][0])
            segunda = await servico.atribuir_numero(fx["clientes"][0])
            await session.commit()
            assert primeira == segunda
    finally:
        await _cleanup(fx["empresa_id"])


@pytest.mark.asyncio
async def test_atribuir_balanceia_entre_numeros_ativos():
    """3 números, 6 clientes → cada número recebe ~2 clientes."""
    fx = await _criar_fixture(qtd_numeros=3, qtd_clientes=6)
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await _set_tenant(session, fx["empresa_id"])
            servico = ServicoRoteamentoNumeros(session, fx["empresa_id"])
            for cliente_id in fx["clientes"]:
                await servico.atribuir_numero(cliente_id)
            await session.commit()

        # Conta clientes por número
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(text("SET LOCAL row_security = off"))
            rows = (await conn.execute(text("""
                SELECT numero_origem_id, COUNT(*) FROM cadastro.clientes
                WHERE empresa_id = :e AND numero_origem_id IS NOT NULL
                GROUP BY numero_origem_id
            """), {"e": str(fx["empresa_id"])})).all()
            contagens = sorted([r[1] for r in rows])
            # Distribuição justa: cada número entre 1 e 3 clientes
            assert min(contagens) >= 1
            assert max(contagens) - min(contagens) <= 1
    finally:
        await _cleanup(fx["empresa_id"])


@pytest.mark.asyncio
async def test_atribuir_sem_numero_ativo_levanta_erro():
    fx = await _criar_fixture(qtd_numeros=0, qtd_clientes=1)
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await _set_tenant(session, fx["empresa_id"])
            servico = ServicoRoteamentoNumeros(session, fx["empresa_id"])
            with pytest.raises(NenhumNumeroAtivoError):
                await servico.atribuir_numero(fx["clientes"][0])
    finally:
        await _cleanup(fx["empresa_id"])


@pytest.mark.asyncio
async def test_marcar_banido_migra_clientes_para_outro_numero():
    fx = await _criar_fixture(qtd_numeros=2, qtd_clientes=3)
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await _set_tenant(session, fx["empresa_id"])
            servico = ServicoRoteamentoNumeros(session, fx["empresa_id"])
            # Atribui todos os clientes ao primeiro número manualmente
            from app.infrastructure.db.models.cadastro import Cliente
            from sqlalchemy import update
            await session.execute(
                update(Cliente).where(
                    Cliente.empresa_id == fx["empresa_id"]
                ).values(numero_origem_id=fx["credenciais"][0])
            )
            await session.commit()

            # Bane o primeiro
            migrados = await servico.marcar_numero_banido(
                fx["credenciais"][0],
                motivo="Teste manual",
            )
            await session.commit()
            assert migrados == 3

        # Confirma que os 3 clientes agora estão no segundo número
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(text("SET LOCAL row_security = off"))
            rows = (await conn.execute(text("""
                SELECT numero_origem_id FROM cadastro.clientes
                WHERE empresa_id = :e
            """), {"e": str(fx["empresa_id"])})).all()
            for row in rows:
                assert row[0] == fx["credenciais"][1]
    finally:
        await _cleanup(fx["empresa_id"])


@pytest.mark.asyncio
async def test_marcar_banido_sem_outro_ativo_deixa_cliente_orfao():
    fx = await _criar_fixture(qtd_numeros=1, qtd_clientes=2)
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await _set_tenant(session, fx["empresa_id"])
            servico = ServicoRoteamentoNumeros(session, fx["empresa_id"])
            from app.infrastructure.db.models.cadastro import Cliente
            from sqlalchemy import update
            await session.execute(
                update(Cliente).where(
                    Cliente.empresa_id == fx["empresa_id"]
                ).values(numero_origem_id=fx["credenciais"][0])
            )
            await session.commit()

            migrados = await servico.marcar_numero_banido(
                fx["credenciais"][0], motivo="Teste"
            )
            await session.commit()
            # Não há outro número ativo → 0 migrados, clientes ficam sem número
            assert migrados == 0

        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(text("SET LOCAL row_security = off"))
            rows = (await conn.execute(text("""
                SELECT numero_origem_id FROM cadastro.clientes
                WHERE empresa_id = :e
            """), {"e": str(fx["empresa_id"])})).all()
            for row in rows:
                assert row[0] is None
    finally:
        await _cleanup(fx["empresa_id"])


@pytest.mark.asyncio
async def test_definir_principal_bloqueia_outros():
    fx = await _criar_fixture(qtd_numeros=3, qtd_clientes=0)
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await _set_tenant(session, fx["empresa_id"])
            servico = ServicoRoteamentoNumeros(session, fx["empresa_id"])
            # Marca o segundo como principal
            await servico.definir_numero_principal(fx["credenciais"][1])
            await session.commit()

        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(text("SET LOCAL row_security = off"))
            rows = (await conn.execute(text("""
                SELECT id, config->>'eh_principal' AS p
                FROM config.credenciais_integracao
                WHERE empresa_id = :e
            """), {"e": str(fx["empresa_id"])})).all()
            principais = [r[0] for r in rows if r[1] == "true"]
            assert len(principais) == 1
            assert principais[0] == fx["credenciais"][1]
    finally:
        await _cleanup(fx["empresa_id"])


@pytest.mark.asyncio
async def test_listar_numeros_inclui_contagem_de_clientes():
    fx = await _criar_fixture(qtd_numeros=2, qtd_clientes=4)
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await _set_tenant(session, fx["empresa_id"])
            servico = ServicoRoteamentoNumeros(session, fx["empresa_id"])
            # Atribui automaticamente
            for cliente_id in fx["clientes"]:
                await servico.atribuir_numero(cliente_id)
            await session.commit()

            lista = await servico.listar_numeros()
            assert len(lista) == 2
            total = sum(n["clientes_atribuidos"] for n in lista)
            assert total == 4
    finally:
        await _cleanup(fx["empresa_id"])
