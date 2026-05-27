"""Testes do motor `processar_titulos_vencidos` (Story 13.8).

Cobre:
- `calcular_encargos`: função pura, casos D-0, D+1, D+30.
- Worker: aplica encargos a títulos em atraso.
- Worker: suspende contrato quando atinge `limite_dias_suspensao`.
- Worker: encerra contrato quando atinge `limite_dias_encerramento`.
- Worker: respeita régua (não envia se já cobrou hoje).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.core.channels.registry import channel_registry
from app.domain.finance.calculos_encargos import calcular_encargos
from app.infrastructure.db.session import get_engine


# ──────────────────────────────────────────────────────────────────
# Função pura `calcular_encargos`
# ──────────────────────────────────────────────────────────────────

def test_encargos_dentro_da_carencia_sem_juros():
    e = calcular_encargos(
        Decimal("1000"),
        date(2026, 6, 1),
        date(2026, 6, 2),  # D+1 mas carência=3
        dias_carencia=3,
        percentual_multa=Decimal("2.00"),
        percentual_juros_dia=Decimal("0.0333"),
    )
    assert e.dentro_da_carencia is True
    assert e.valor_atualizado == Decimal("1000")
    assert e.multa == Decimal("0.00")


def test_encargos_d1_apos_carencia_zero():
    e = calcular_encargos(
        Decimal("1000"),
        date(2026, 6, 1),
        date(2026, 6, 2),
        dias_carencia=0,
        percentual_multa=Decimal("2.00"),
        percentual_juros_dia=Decimal("0.0333"),
    )
    assert e.dentro_da_carencia is False
    assert e.dias_atraso == 1
    assert e.multa == Decimal("20.00")  # 2% de 1000
    assert e.juros == Decimal("0.33")  # 0.0333% * 1 dia
    assert e.valor_atualizado == Decimal("1020.33")


def test_encargos_30_dias():
    e = calcular_encargos(
        Decimal("1000"),
        date(2026, 6, 1),
        date(2026, 7, 1),  # 30 dias
        dias_carencia=0,
        percentual_multa=Decimal("2.00"),
        percentual_juros_dia=Decimal("0.0333"),
    )
    assert e.dias_atraso == 30
    assert e.multa == Decimal("20.00")
    assert e.juros == Decimal("9.99")  # 0.0333% * 30 ≈ 1% (juros simples)
    assert e.valor_atualizado == Decimal("1029.99")


# ──────────────────────────────────────────────────────────────────
# Worker — fixtures
# ──────────────────────────────────────────────────────────────────

class FakeChannel:
    def __init__(self):
        self.enviados: list[tuple[str, str]] = []

    @property
    def channel_type(self):
        return "whatsapp"

    @property
    def provider_name(self):
        return "fake-pv"

    @property
    def display_name(self):
        return "Fake WhatsApp"

    async def send_text(self, to: str, body: str):
        self.enviados.append((to, body))
        from app.domain.ports.message_channel import MessageReceipt
        return MessageReceipt(
            provider_message_id=str(uuid4()),
            channel_type="whatsapp",
            sent_at=datetime.now(timezone.utc),
        )

    async def send_media(self, *a, **k): raise NotImplementedError
    async def parse_webhook(self, *a, **k): raise NotImplementedError
    async def health_check(self):
        from app.domain.ports.message_channel import ChannelHealth
        return ChannelHealth(
            channel_type="whatsapp", provider="fake-pv",
            is_healthy=True, latency_ms=1.0, message="ok",
            checked_at=datetime.now(timezone.utc),
        )


async def _criar_fixture(dias_atraso: int) -> dict:
    """Cria empresa+cliente+veiculo+contrato vigente + 1 título vencido há N dias."""
    engine = get_engine()
    suffix = uuid4().hex[:8]
    empresa_id = uuid4()
    cliente_id = uuid4()
    veiculo_id = uuid4()
    contrato_id = uuid4()
    titulo_id = uuid4()

    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        await conn.execute(text("""
            INSERT INTO comercial.empresas (id, razao_social, cnpj, email)
            VALUES (:id, :r, :c, :e)
        """), {"id": str(empresa_id), "r": f"PV-{suffix}",
                "c": f"{suffix}44000111"[:14].ljust(14, "0"), "e": f"pv{suffix}@t.com"})
        await conn.execute(text("""
            INSERT INTO cadastro.clientes (id, empresa_id, nome_completo, cpf_cnpj, telefone)
            VALUES (:id, :eid, :n, :cpf, '11900000000')
        """), {"id": str(cliente_id), "eid": str(empresa_id),
                "n": "Pedro Inadimplente", "cpf": f"{suffix}55566677"[:11]})
        await conn.execute(text("""
            INSERT INTO veiculos.veiculos (id, empresa_id, placa, fipe_marca, fipe_modelo,
              ano_modelo, ano_fabricacao, status)
            VALUES (:id, :eid, :placa, 'Toyota', 'Corolla', 2024, 2024, 'em_uso')
        """), {"id": str(veiculo_id), "eid": str(empresa_id),
                "placa": f"PV{suffix[:5].upper()}"})
        admin = (await conn.execute(text(
            "SELECT id FROM acesso.usuarios WHERE email='admin@example.com'"
        ))).first()
        await conn.execute(text("""
            INSERT INTO contrato.contratos
              (id, empresa_id, numero, cliente_id, veiculo_id, status,
               data_inicio, data_fim, valor_total, dia_vencimento, modo_geracao, criado_por_id)
            VALUES (:id, :eid, :num, :cli, :vei, 'vigente',
                    :di, :df, 12000, 15, 'antecipado', :uid)
        """), {"id": str(contrato_id), "eid": str(empresa_id),
                "num": f"C-{suffix}", "cli": str(cliente_id), "vei": str(veiculo_id),
                "di": date(2026, 1, 1), "df": date(2027, 1, 1),
                "uid": str(admin[0]) if admin else None})

        vencimento = date.today() - timedelta(days=dias_atraso)
        await conn.execute(text("""
            INSERT INTO financeiro.titulos_receber
              (id, empresa_id, contrato_id, sequencia, data_vencimento, valor, tipo, status,
               acoes_de_cobranca)
            VALUES (:id, :eid, :cid, 1, :dv, 1000.00, 'parcela', 'em_atraso', 0)
        """), {"id": str(titulo_id), "eid": str(empresa_id),
                "cid": str(contrato_id), "dv": vencimento})

    return {
        "empresa_id": empresa_id,
        "contrato_id": contrato_id,
        "titulo_id": titulo_id,
    }


async def _cleanup(empresa_id: UUID) -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        await conn.execute(text("ALTER TABLE logs.log_auditoria DISABLE TRIGGER trg_log_auditoria_immutable"))
        try:
            await conn.execute(text("DELETE FROM logs.log_auditoria WHERE entidade IN ('contratos', 'veiculos')"))
            await conn.execute(text("DELETE FROM financeiro.lembretes_enviados WHERE empresa_id = :e"), {"e": str(empresa_id)})
            await conn.execute(text("DELETE FROM motor.execucoes_motor WHERE empresa_id = :e"), {"e": str(empresa_id)})
            await conn.execute(text("DELETE FROM contrato.eventos_contrato WHERE empresa_id = :e"), {"e": str(empresa_id)})
            await conn.execute(text("DELETE FROM financeiro.titulos_receber WHERE empresa_id = :e"), {"e": str(empresa_id)})
            await conn.execute(text("DELETE FROM contrato.contratos WHERE empresa_id = :e"), {"e": str(empresa_id)})
            await conn.execute(text("DELETE FROM veiculos.veiculos WHERE empresa_id = :e"), {"e": str(empresa_id)})
            await conn.execute(text("DELETE FROM cadastro.clientes WHERE empresa_id = :e"), {"e": str(empresa_id)})
            await conn.execute(text("DELETE FROM comercial.empresas WHERE id = :e"), {"e": str(empresa_id)})
        finally:
            await conn.execute(text("ALTER TABLE logs.log_auditoria ENABLE TRIGGER trg_log_auditoria_immutable"))


# ──────────────────────────────────────────────────────────────────
# Worker — integração
# ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_envia_cobranca_para_titulo_recem_vencido():
    fx = await _criar_fixture(dias_atraso=3)
    fake = FakeChannel()
    channel_registry.register(fake)
    try:
        from app.workers.tasks.processar_titulos_vencidos import _run
        result = await _run(fx["empresa_id"])
        assert result["total_processados"] >= 1
        assert len(fake.enviados) == 1
        # Mensagem deve conter o nome do cliente e valor atualizado
        msg = fake.enviados[0][1]
        assert "Pedro" in msg
        # 3 dias de juros + multa 2% = 1021.00 (1000 + 20 + 1.00)
        # Só checo que valor atualizado aparece e é > base
        assert "R$ 1000,00" in msg  # valor base
        assert "R$ 1021,00" in msg  # valor atualizado (multa 20 + juros 1)
    finally:
        channel_registry.unregister("whatsapp", "fake-pv")
        await _cleanup(fx["empresa_id"])


@pytest.mark.asyncio
async def test_suspende_contrato_quando_atinge_limite_dias():
    """Default limite_dias_suspensao=15. 20 dias de atraso → contrato suspenso."""
    fx = await _criar_fixture(dias_atraso=20)
    fake = FakeChannel()
    channel_registry.register(fake)
    try:
        from app.workers.tasks.processar_titulos_vencidos import _run
        await _run(fx["empresa_id"])

        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(text("SET LOCAL row_security = off"))
            row = (await conn.execute(text(
                "SELECT status, motivo_suspensao FROM contrato.contratos WHERE id = :c"
            ), {"c": str(fx["contrato_id"])})).first()
            assert row[0] == "suspenso"
            assert "20" in (row[1] or "")
        # Quando suspende, NÃO envia mensagem (decisão de design — Story 13.8 spec)
        assert len(fake.enviados) == 0
    finally:
        channel_registry.unregister("whatsapp", "fake-pv")
        await _cleanup(fx["empresa_id"])


@pytest.mark.asyncio
async def test_encerra_contrato_com_pendencia_apos_limite_encerramento():
    """Default limite_dias_encerramento=60. 70 dias de atraso → encerrado_com_pendencia."""
    fx = await _criar_fixture(dias_atraso=70)
    fake = FakeChannel()
    channel_registry.register(fake)
    try:
        from app.workers.tasks.processar_titulos_vencidos import _run
        await _run(fx["empresa_id"])
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(text("SET LOCAL row_security = off"))
            row = (await conn.execute(text(
                "SELECT status FROM contrato.contratos WHERE id = :c"
            ), {"c": str(fx["contrato_id"])})).first()
            assert row[0] == "encerrado_com_pendencia"
    finally:
        channel_registry.unregister("whatsapp", "fake-pv")
        await _cleanup(fx["empresa_id"])


@pytest.mark.asyncio
async def test_aplica_status_em_atraso():
    """Título 'em_aberto' → 'em_atraso' após processamento."""
    fx = await _criar_fixture(dias_atraso=5)
    # Reverte status pra em_aberto (fixture grava em_atraso por default)
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        await conn.execute(text(
            "UPDATE financeiro.titulos_receber SET status = 'em_aberto' WHERE id = :t"
        ), {"t": str(fx["titulo_id"])})

    fake = FakeChannel()
    channel_registry.register(fake)
    try:
        from app.workers.tasks.processar_titulos_vencidos import _run
        await _run(fx["empresa_id"])
        async with engine.begin() as conn:
            await conn.execute(text("SET LOCAL row_security = off"))
            row = (await conn.execute(text(
                "SELECT status FROM financeiro.titulos_receber WHERE id = :t"
            ), {"t": str(fx["titulo_id"])})).first()
            assert row[0] == "em_atraso"
    finally:
        channel_registry.unregister("whatsapp", "fake-pv")
        await _cleanup(fx["empresa_id"])


@pytest.mark.asyncio
async def test_nao_duplica_cobranca_no_mesmo_dia():
    fx = await _criar_fixture(dias_atraso=5)
    fake = FakeChannel()
    channel_registry.register(fake)
    try:
        from app.workers.tasks.processar_titulos_vencidos import _run
        await _run(fx["empresa_id"])
        assert len(fake.enviados) == 1
        # Segunda execução no mesmo dia: respeita intervalo_horas (default 24h)
        # → não envia segunda mensagem
        await _run(fx["empresa_id"])
        assert len(fake.enviados) == 1
    finally:
        channel_registry.unregister("whatsapp", "fake-pv")
        await _cleanup(fx["empresa_id"])
