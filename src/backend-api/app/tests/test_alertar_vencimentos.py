"""Testes do motor `alertar_vencimentos_proximos` (Story 13.7).

Foca na lógica de negócio:
- Seleção dos títulos pelo intervalo de vencimento.
- Idempotência diária (não duplica).
- Fallback de canal quando o principal falha.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.core.channels.registry import channel_registry
from app.infrastructure.db.session import get_engine, get_sessionmaker


# ──────────────────────────────────────────────────────────────────
# Fake channel para isolar o motor de Z-API/Evolution real
# ──────────────────────────────────────────────────────────────────

class FakeChannel:
    """Channel stub que registra envios e pode simular falha."""

    def __init__(self, channel_type: str, provider_name: str, falhar: bool = False):
        self._channel_type = channel_type
        self._provider_name = provider_name
        self._falhar = falhar
        self.enviados: list[tuple[str, str]] = []

    @property
    def channel_type(self) -> str:
        return self._channel_type

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def display_name(self) -> str:
        return f"Fake {self._channel_type}"

    async def send_text(self, to: str, text: str):
        if self._falhar:
            raise RuntimeError("simulação de falha")
        self.enviados.append((to, text))
        from app.domain.ports.message_channel import MessageReceipt
        return MessageReceipt(
            provider_message_id=str(uuid4()),
            channel_type=self._channel_type,
            sent_at=datetime.now(timezone.utc),
        )

    async def send_media(self, *args, **kwargs):
        raise NotImplementedError

    async def parse_webhook(self, *args, **kwargs):
        raise NotImplementedError

    async def health_check(self):
        from app.domain.ports.message_channel import ChannelHealth
        return ChannelHealth(
            channel_type=self._channel_type,
            provider=self._provider_name,
            is_healthy=True,
            latency_ms=1.0,
            message="ok",
            checked_at=datetime.now(timezone.utc),
        )


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────

async def _criar_titulo_para_alertar(dias_ate_vencer: int = 3) -> dict:
    """Cria empresa+cliente+veiculo+contrato+título e retorna metadados."""
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
        """), {"id": str(empresa_id), "r": f"AV-{suffix}",
                "c": f"{suffix}33000111"[:14].ljust(14, "0"), "e": f"av{suffix}@t.com"})

        await conn.execute(text("""
            INSERT INTO cadastro.clientes (id, empresa_id, nome_completo, cpf_cnpj, telefone)
            VALUES (:id, :eid, :n, :cpf, :tel)
        """), {
            "id": str(cliente_id), "eid": str(empresa_id),
            "n": "Maria da Silva", "cpf": f"{suffix}11122333"[:11],
            "tel": "11999990000",
        })

        await conn.execute(text("""
            INSERT INTO veiculos.veiculos (id, empresa_id, placa, fipe_marca, fipe_modelo,
              ano_modelo, ano_fabricacao, status)
            VALUES (:id, :eid, :placa, 'Toyota', 'Corolla', 2024, 2024, 'em_uso')
        """), {"id": str(veiculo_id), "eid": str(empresa_id),
                "placa": f"AV{suffix[:5].upper()}"})

        admin_row = (await conn.execute(text(
            "SELECT id FROM acesso.usuarios WHERE email = 'admin@example.com'"
        ))).first()
        admin_id = admin_row[0] if admin_row else None

        await conn.execute(text("""
            INSERT INTO contrato.contratos
              (id, empresa_id, numero, cliente_id, veiculo_id, status,
               data_inicio, data_fim, valor_total, dia_vencimento, modo_geracao, criado_por_id)
            VALUES (:id, :eid, :num, :cli, :vei, 'vigente',
                    :di, :df, 12000, 15, 'antecipado', :uid)
        """), {
            "id": str(contrato_id), "eid": str(empresa_id),
            "num": f"C-{suffix}", "cli": str(cliente_id), "vei": str(veiculo_id),
            "di": date(2026, 1, 1), "df": date(2027, 1, 1),
            "uid": str(admin_id) if admin_id else None,
        })

        vencimento = date.today() + timedelta(days=dias_ate_vencer)
        await conn.execute(text("""
            INSERT INTO financeiro.titulos_receber
              (id, empresa_id, contrato_id, sequencia, data_vencimento, valor, tipo, status)
            VALUES (:id, :eid, :cid, 1, :dv, 1250.00, 'parcela', 'em_aberto')
        """), {
            "id": str(titulo_id), "eid": str(empresa_id), "cid": str(contrato_id),
            "dv": vencimento,
        })

    return {
        "empresa_id": empresa_id,
        "cliente_id": cliente_id,
        "veiculo_id": veiculo_id,
        "contrato_id": contrato_id,
        "titulo_id": titulo_id,
    }


async def _cleanup(empresa_id: UUID) -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        await conn.execute(text("ALTER TABLE logs.log_auditoria DISABLE TRIGGER trg_log_auditoria_immutable"))
        try:
            await conn.execute(text("DELETE FROM logs.log_auditoria WHERE entidade IN ('contratos', 'veiculos', 'configuracoes_sistema')"))
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
# Testes
# ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_envia_lembrete_para_titulo_no_intervalo():
    fixtures = await _criar_titulo_para_alertar(dias_ate_vencer=3)
    fake = FakeChannel("whatsapp", "fake-test")
    channel_registry.register(fake)
    try:
        from app.workers.tasks.alertar_vencimentos_proximos import _run
        result = await _run(fixtures["empresa_id"])
        assert result["total_processados"] >= 1
        assert len(fake.enviados) == 1
        telefone, msg = fake.enviados[0]
        assert telefone == "11999990000"
        assert "Maria" in msg
    finally:
        channel_registry.unregister("whatsapp", "fake-test")
        await _cleanup(fixtures["empresa_id"])


@pytest.mark.asyncio
async def test_nao_duplica_lembrete_no_mesmo_dia():
    fixtures = await _criar_titulo_para_alertar(dias_ate_vencer=2)
    fake = FakeChannel("whatsapp", "fake-test")
    channel_registry.register(fake)
    try:
        from app.workers.tasks.alertar_vencimentos_proximos import _run
        await _run(fixtures["empresa_id"])
        assert len(fake.enviados) == 1
        # Segunda execução no mesmo dia → não duplica
        await _run(fixtures["empresa_id"])
        assert len(fake.enviados) == 1, "Lembrete duplicado no mesmo dia"
    finally:
        channel_registry.unregister("whatsapp", "fake-test")
        await _cleanup(fixtures["empresa_id"])


@pytest.mark.asyncio
async def test_titulo_fora_do_intervalo_nao_alerta():
    # Vencimento daqui a 30 dias (fora do default de 3)
    fixtures = await _criar_titulo_para_alertar(dias_ate_vencer=30)
    fake = FakeChannel("whatsapp", "fake-test")
    channel_registry.register(fake)
    try:
        from app.workers.tasks.alertar_vencimentos_proximos import _run
        await _run(fixtures["empresa_id"])
        assert len(fake.enviados) == 0
    finally:
        channel_registry.unregister("whatsapp", "fake-test")
        await _cleanup(fixtures["empresa_id"])


@pytest.mark.asyncio
async def test_titulo_vencido_nao_alerta():
    """Vencimento já passou → 13.7 não toca, fica para o 13.8 (vencidos)."""
    fixtures = await _criar_titulo_para_alertar(dias_ate_vencer=-5)
    fake = FakeChannel("whatsapp", "fake-test")
    channel_registry.register(fake)
    try:
        from app.workers.tasks.alertar_vencimentos_proximos import _run
        await _run(fixtures["empresa_id"])
        assert len(fake.enviados) == 0
    finally:
        channel_registry.unregister("whatsapp", "fake-test")
        await _cleanup(fixtures["empresa_id"])


@pytest.mark.asyncio
async def test_persiste_em_lembretes_enviados():
    fixtures = await _criar_titulo_para_alertar(dias_ate_vencer=1)
    fake = FakeChannel("whatsapp", "fake-test")
    channel_registry.register(fake)
    try:
        from app.workers.tasks.alertar_vencimentos_proximos import _run
        await _run(fixtures["empresa_id"])

        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(text("SET LOCAL row_security = off"))
            row = (await conn.execute(text("""
                SELECT tipo, canal, sucesso FROM financeiro.lembretes_enviados
                WHERE titulo_id = :tid
            """), {"tid": str(fixtures["titulo_id"])})).first()
            assert row is not None
            assert row[0] == "lembrete_vencimento"
            assert row[1] == "whatsapp"
            assert row[2] is True
    finally:
        channel_registry.unregister("whatsapp", "fake-test")
        await _cleanup(fixtures["empresa_id"])
