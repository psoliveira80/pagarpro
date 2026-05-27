"""Testes da Story 13.9 — Motor de Conciliação de Pagamentos.

Foca na lógica testável sem integração bancária externa:
- `decidir_conciliacao`: função pura (4 decisões)
- `ServicoTituloPago`:
  - Pagamento integral → status='pago'
  - Pagamento parcial dentro do threshold → fundido na próxima parcela
  - Pagamento parcial fora do threshold → cria título novo
  - Opção de compra paga → aliena veículo (delega para ServicoOpcaoCompra)
  - Idempotência: chamar 2x não duplica
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.application.services.servico_titulo_pago import (
    ServicoTituloPago,
    TituloPagoInvalidoError,
)
from app.domain.finance.conciliacao import (
    DecisaoConciliacao,
    decidir_conciliacao,
)
from app.infrastructure.db.session import get_engine, get_sessionmaker


# ──────────────────────────────────────────────────────────────────
# Função pura
# ──────────────────────────────────────────────────────────────────

def test_conciliacao_integral_quando_valores_batem():
    r = decidir_conciliacao(Decimal("800"), Decimal("800"), Decimal("20.00"))
    assert r.decisao == DecisaoConciliacao.INTEGRAL
    assert r.restante == Decimal("0.00")


def test_conciliacao_integral_com_tolerancia_de_1_centavo():
    """800.00 vs 800.01 = diferença 0.01 → tratado como integral."""
    r = decidir_conciliacao(Decimal("800.00"), Decimal("800.01"), Decimal("20.00"))
    assert r.decisao == DecisaoConciliacao.INTEGRAL


def test_conciliacao_excedente_quando_paga_a_mais():
    r = decidir_conciliacao(Decimal("850"), Decimal("800"), Decimal("20.00"))
    assert r.decisao == DecisaoConciliacao.EXCEDENTE
    assert r.restante == Decimal("-50.00")


def test_conciliacao_fundido_dentro_do_threshold():
    """800 valor titulo, paga 760 (resta 40 = 5% < 20%) → fundido."""
    r = decidir_conciliacao(Decimal("760"), Decimal("800"), Decimal("20.00"))
    assert r.decisao == DecisaoConciliacao.FUNDIDO
    assert r.restante == Decimal("40.00")


def test_conciliacao_separado_fora_do_threshold():
    """800 valor titulo, paga 400 (resta 400 = 50% > 20%) → separado."""
    r = decidir_conciliacao(Decimal("400"), Decimal("800"), Decimal("20.00"))
    assert r.decisao == DecisaoConciliacao.SEPARADO
    assert r.restante == Decimal("400.00")


def test_conciliacao_no_limite_exato_funde():
    """800 valor titulo, paga 640 (resta 160 = 20% exatos) → fundido (`<=`)."""
    r = decidir_conciliacao(Decimal("640"), Decimal("800"), Decimal("20.00"))
    assert r.decisao == DecisaoConciliacao.FUNDIDO


# ──────────────────────────────────────────────────────────────────
# ServicoTituloPago — integração
# ──────────────────────────────────────────────────────────────────

async def _criar_contrato_com_titulos(quantos_titulos: int = 2, com_opcao_compra: bool = False) -> dict:
    """Cria contrato vigente com N parcelas em aberto + opcionalmente opcao_compra."""
    engine = get_engine()
    suffix = uuid4().hex[:8]
    empresa_id = uuid4()
    cliente_id = uuid4()
    veiculo_id = uuid4()
    contrato_id = uuid4()
    titulos_ids = [uuid4() for _ in range(quantos_titulos)]
    opcao_id = uuid4() if com_opcao_compra else None

    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        await conn.execute(text("""
            INSERT INTO comercial.empresas (id, razao_social, cnpj, email)
            VALUES (:id, :r, :c, :e)
        """), {"id": str(empresa_id), "r": f"CP-{suffix}",
                "c": f"{suffix}66000111"[:14].ljust(14, "0"), "e": f"cp{suffix}@t.com"})
        await conn.execute(text("""
            INSERT INTO cadastro.clientes (id, empresa_id, nome_completo, cpf_cnpj, telefone)
            VALUES (:id, :eid, :n, :cpf, '11900001111')
        """), {"id": str(cliente_id), "eid": str(empresa_id),
                "n": "Ana Pagadora", "cpf": f"{suffix}11199988"[:11]})
        await conn.execute(text("""
            INSERT INTO veiculos.veiculos (id, empresa_id, placa, fipe_marca, fipe_modelo,
              ano_modelo, ano_fabricacao, status)
            VALUES (:id, :eid, :placa, 'Honda', 'Civic', 2024, 2024, 'em_uso')
        """), {"id": str(veiculo_id), "eid": str(empresa_id),
                "placa": f"CP{suffix[:5].upper()}"})

        admin = (await conn.execute(text(
            "SELECT id FROM acesso.usuarios WHERE email='admin@example.com'"
        ))).first()
        await conn.execute(text("""
            INSERT INTO contrato.contratos
              (id, empresa_id, numero, cliente_id, veiculo_id, status,
               data_inicio, data_fim, valor_total, dia_vencimento, modo_geracao, criado_por_id,
               valor_opcao_compra)
            VALUES (:id, :eid, :num, :cli, :vei, 'vigente',
                    :di, :df, :tot, 15, 'antecipado', :uid, :voc)
        """), {"id": str(contrato_id), "eid": str(empresa_id),
                "num": f"C-{suffix}", "cli": str(cliente_id), "vei": str(veiculo_id),
                "di": date(2026, 1, 1), "df": date(2027, 1, 1),
                "tot": Decimal("9600"),
                "uid": str(admin[0]) if admin else None,
                "voc": Decimal("5000") if com_opcao_compra else None})

        for i, tid in enumerate(titulos_ids):
            vencimento = date(2026, 7 + i, 15)
            await conn.execute(text("""
                INSERT INTO financeiro.titulos_receber
                  (id, empresa_id, contrato_id, sequencia, data_vencimento, valor, tipo, status)
                VALUES (:id, :eid, :cid, :seq, :dv, 800.00, 'parcela', 'em_aberto')
            """), {"id": str(tid), "eid": str(empresa_id), "cid": str(contrato_id),
                    "seq": i + 1, "dv": vencimento})

        if com_opcao_compra:
            await conn.execute(text("""
                INSERT INTO financeiro.titulos_receber
                  (id, empresa_id, contrato_id, sequencia, data_vencimento, valor, tipo, status)
                VALUES (:id, :eid, :cid, :seq, :dv, 5000.00, 'opcao_compra', 'em_aberto')
            """), {"id": str(opcao_id), "eid": str(empresa_id), "cid": str(contrato_id),
                    "seq": quantos_titulos + 1, "dv": date(2027, 1, 15)})

    return {
        "empresa_id": empresa_id,
        "contrato_id": contrato_id,
        "veiculo_id": veiculo_id,
        "cliente_id": cliente_id,
        "titulos_ids": titulos_ids,
        "opcao_id": opcao_id,
    }


async def _cleanup(empresa_id: UUID) -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        await conn.execute(text("ALTER TABLE logs.log_auditoria DISABLE TRIGGER trg_log_auditoria_immutable"))
        try:
            await conn.execute(text("DELETE FROM logs.log_auditoria WHERE entidade IN ('contratos', 'veiculos', 'titulos_receber')"))
            await conn.execute(text("DELETE FROM motor.execucoes_motor WHERE empresa_id = :e"), {"e": str(empresa_id)})
            await conn.execute(text("DELETE FROM contrato.eventos_contrato WHERE empresa_id = :e"), {"e": str(empresa_id)})
            await conn.execute(text("DELETE FROM financeiro.movimentos_titulo_receber WHERE empresa_id = :e"), {"e": str(empresa_id)})
            await conn.execute(text("DELETE FROM financeiro.titulos_receber WHERE empresa_id = :e"), {"e": str(empresa_id)})
            await conn.execute(text("DELETE FROM contrato.contratos WHERE empresa_id = :e"), {"e": str(empresa_id)})
            await conn.execute(text("DELETE FROM veiculos.veiculos WHERE empresa_id = :e"), {"e": str(empresa_id)})
            await conn.execute(text("DELETE FROM cadastro.clientes WHERE empresa_id = :e"), {"e": str(empresa_id)})
            await conn.execute(text("DELETE FROM comercial.empresas WHERE id = :e"), {"e": str(empresa_id)})
        finally:
            await conn.execute(text("ALTER TABLE logs.log_auditoria ENABLE TRIGGER trg_log_auditoria_immutable"))


@pytest.mark.asyncio
async def test_pagamento_integral_marca_titulo_pago():
    fx = await _criar_contrato_com_titulos()
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(fx["empresa_id"])},
            )
            servico = ServicoTituloPago(session, fx["empresa_id"])
            result = await servico.registrar_pagamento(
                fx["titulos_ids"][0], Decimal("800.00")
            )
            await session.commit()
            assert result["decisao"] == "integral"

        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(text("SET LOCAL row_security = off"))
            row = (await conn.execute(text(
                "SELECT status, valor_pago FROM financeiro.titulos_receber WHERE id = :t"
            ), {"t": str(fx["titulos_ids"][0])})).first()
            assert row[0] == "pago"
            assert row[1] == Decimal("800.00")
    finally:
        await _cleanup(fx["empresa_id"])


@pytest.mark.asyncio
async def test_pagamento_parcial_dentro_threshold_funde_proximo():
    """800 valor, paga 760 (resta 40 = 5% < 20%) → funde 40 no próximo título."""
    fx = await _criar_contrato_com_titulos(quantos_titulos=2)
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(fx["empresa_id"])},
            )
            servico = ServicoTituloPago(session, fx["empresa_id"])
            result = await servico.registrar_pagamento(
                fx["titulos_ids"][0], Decimal("760.00")
            )
            await session.commit()
            assert result["decisao"] == "fundido"
            assert result["fundido_em"] == str(fx["titulos_ids"][1])

        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(text("SET LOCAL row_security = off"))
            # Primeiro título → pago_parcial
            r1 = (await conn.execute(text(
                "SELECT status, valor_pago FROM financeiro.titulos_receber WHERE id = :t"
            ), {"t": str(fx["titulos_ids"][0])})).first()
            assert r1[0] == "pago_parcial"
            assert r1[1] == Decimal("760.00")
            # Segundo título → valor incrementado em 40 (800 + 40 = 840)
            r2 = (await conn.execute(text(
                "SELECT valor, status FROM financeiro.titulos_receber WHERE id = :t"
            ), {"t": str(fx["titulos_ids"][1])})).first()
            assert r2[0] == Decimal("840.00")
            assert r2[1] == "em_aberto"
    finally:
        await _cleanup(fx["empresa_id"])


@pytest.mark.asyncio
async def test_pagamento_parcial_fora_threshold_separa():
    """800 valor, paga 400 (resta 400 = 50% > 20%) → cria título novo."""
    fx = await _criar_contrato_com_titulos(quantos_titulos=2)
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(fx["empresa_id"])},
            )
            servico = ServicoTituloPago(session, fx["empresa_id"])
            result = await servico.registrar_pagamento(
                fx["titulos_ids"][0], Decimal("400.00")
            )
            await session.commit()
            assert result["decisao"] == "separado"
            titulo_novo_id = result["titulo_novo"]

        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(text("SET LOCAL row_security = off"))
            # Original → pago_parcial
            r1 = (await conn.execute(text(
                "SELECT status, valor_pago FROM financeiro.titulos_receber WHERE id = :t"
            ), {"t": str(fx["titulos_ids"][0])})).first()
            assert r1[0] == "pago_parcial"
            # Novo → valor 400, parent_id = original
            r2 = (await conn.execute(text(
                "SELECT valor, status, titulo_origem_id FROM financeiro.titulos_receber WHERE id = :t"
            ), {"t": titulo_novo_id})).first()
            assert r2[0] == Decimal("400.00")
            assert r2[1] == "em_aberto"
            assert str(r2[2]) == str(fx["titulos_ids"][0])
    finally:
        await _cleanup(fx["empresa_id"])


@pytest.mark.asyncio
async def test_opcao_compra_paga_aliena_veiculo():
    fx = await _criar_contrato_com_titulos(quantos_titulos=1, com_opcao_compra=True)
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(fx["empresa_id"])},
            )
            servico = ServicoTituloPago(session, fx["empresa_id"])
            result = await servico.registrar_pagamento(
                fx["opcao_id"], Decimal("5000.00")
            )
            await session.commit()
            assert result["decisao"] == "integral"
            assert result["opcao_compra"] is not None

        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(text("SET LOCAL row_security = off"))
            r = (await conn.execute(text(
                "SELECT status, proprietario_id FROM veiculos.veiculos WHERE id = :v"
            ), {"v": str(fx["veiculo_id"])})).first()
            assert r[0] == "alienado"
            assert str(r[1]) == str(fx["cliente_id"])
            c = (await conn.execute(text(
                "SELECT status FROM contrato.contratos WHERE id = :c"
            ), {"c": str(fx["contrato_id"])})).first()
            assert c[0] == "encerrado_compra"
    finally:
        await _cleanup(fx["empresa_id"])


@pytest.mark.asyncio
async def test_idempotencia_chamar_2x_nao_duplica():
    fx = await _criar_contrato_com_titulos()
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(fx["empresa_id"])},
            )
            servico = ServicoTituloPago(session, fx["empresa_id"])
            await servico.registrar_pagamento(fx["titulos_ids"][0], Decimal("800.00"))
            r2 = await servico.registrar_pagamento(fx["titulos_ids"][0], Decimal("800.00"))
            await session.commit()
            assert r2["decisao"] == "ja_pago"
    finally:
        await _cleanup(fx["empresa_id"])
