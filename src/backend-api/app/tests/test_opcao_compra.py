"""Testes da Story 13.3 — Tipo de Título e Opção de Compra."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.application.services.servico_opcao_compra import (
    OpcaoCompraInvalidaError,
    ServicoOpcaoCompra,
)
from app.domain.finance.tipo_titulo import TIPOS_DEVEDORES, TipoTitulo
from app.infrastructure.db.session import get_engine, get_sessionmaker


# ──────────────────────────────────────────────────────────────────
# Testes unitários do enum
# ──────────────────────────────────────────────────────────────────

def test_tipos_devedores_inclui_parcela_e_multa():
    assert TipoTitulo.PARCELA in TIPOS_DEVEDORES
    assert TipoTitulo.MULTA in TIPOS_DEVEDORES
    assert TipoTitulo.TAXA in TIPOS_DEVEDORES


def test_opcao_compra_nao_eh_devedor():
    """Saldo devedor / inadimplência NÃO inclui opção de compra."""
    assert TipoTitulo.OPCAO_COMPRA not in TIPOS_DEVEDORES


def test_ajuste_nao_eh_devedor():
    assert TipoTitulo.AJUSTE not in TIPOS_DEVEDORES


# ──────────────────────────────────────────────────────────────────
# Constraint de banco
# ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_check_constraint_rejeita_tipo_invalido():
    """O CHECK constraint rejeita tipos fora dos 5 oficiais."""
    contrato_id, empresa_id, cliente_id, veiculo_id, admin_id = await _criar_fixtures()
    try:
        engine = get_engine()
        # Insere um título regular primeiro pra ter onde testar
        titulo_id = uuid4()
        async with engine.begin() as conn:
            await conn.execute(text("SET LOCAL row_security = off"))
            await conn.execute(text("""
                INSERT INTO financeiro.titulos_receber
                  (id, empresa_id, contrato_id, sequencia, data_vencimento, valor, tipo)
                VALUES (:id, :eid, :cid, 1, :dv, 100, 'parcela')
            """), {"id": str(titulo_id), "eid": str(empresa_id),
                    "cid": str(contrato_id), "dv": date(2026, 6, 1)})

        with pytest.raises(IntegrityError):
            async with engine.begin() as conn:
                await conn.execute(text("SET LOCAL row_security = off"))
                await conn.execute(
                    text("UPDATE financeiro.titulos_receber SET tipo = 'tipo_invento' WHERE id = :tid"),
                    {"tid": str(titulo_id)},
                )
    finally:
        await _cleanup_fixtures(empresa_id)


@pytest.mark.asyncio
async def test_unique_index_aceita_apenas_uma_opcao_compra_por_contrato():
    """O índice único parcial impede 2 títulos opcao_compra no mesmo contrato."""
    contrato_id, empresa_id, *_ = await _criar_fixtures()
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(text("SET LOCAL row_security = off"))
            await conn.execute(text("""
                INSERT INTO financeiro.titulos_receber
                  (empresa_id, contrato_id, sequencia, data_vencimento, valor, tipo)
                VALUES (:eid, :cid, 13, :dv, 5000, 'opcao_compra')
            """), {"eid": str(empresa_id), "cid": str(contrato_id), "dv": date(2027, 1, 1)})

        with pytest.raises(IntegrityError):
            async with engine.begin() as conn:
                await conn.execute(text("SET LOCAL row_security = off"))
                await conn.execute(text("""
                    INSERT INTO financeiro.titulos_receber
                      (empresa_id, contrato_id, sequencia, data_vencimento, valor, tipo)
                    VALUES (:eid, :cid, 14, :dv, 5000, 'opcao_compra')
                """), {"eid": str(empresa_id), "cid": str(contrato_id), "dv": date(2027, 2, 1)})
    finally:
        await _cleanup_fixtures(empresa_id)


# ──────────────────────────────────────────────────────────────────
# Serviço
# ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_servico_processar_pagamento_aliena_veiculo():
    contrato_id, empresa_id, cliente_id, veiculo_id, admin_id = await _criar_fixtures()
    try:
        engine = get_engine()
        titulo_id = uuid4()
        # Cria opção de compra paga
        async with engine.begin() as conn:
            await conn.execute(text("SET LOCAL row_security = off"))
            await conn.execute(text("""
                INSERT INTO financeiro.titulos_receber
                  (id, empresa_id, contrato_id, sequencia, data_vencimento, valor,
                   tipo, status, pago_em, valor_pago)
                VALUES (:id, :eid, :cid, 13, :dv, 5000, 'opcao_compra',
                        'pago', :pe, 5000)
            """), {
                "id": str(titulo_id),
                "eid": str(empresa_id),
                "cid": str(contrato_id),
                "dv": date(2027, 1, 1),
                "pe": date(2027, 1, 5),
            })

        # Executa serviço
        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(empresa_id)},
            )
            servico = ServicoOpcaoCompra(session, empresa_id)
            result = await servico.processar_pagamento(titulo_id)
            await session.commit()
            assert result["veiculo_id"] == str(veiculo_id)
            assert result["cliente_id"] == str(cliente_id)

        # Verifica veículo alienado
        async with engine.begin() as conn:
            await conn.execute(text("SET LOCAL row_security = off"))
            row = (await conn.execute(text("""
                SELECT status, proprietario_id FROM veiculos.veiculos WHERE id = :vid
            """), {"vid": str(veiculo_id)})).first()
            assert row[0] == "alienado"
            assert str(row[1]) == str(cliente_id)

            # Contrato deve ter ido para encerrado_compra
            crow = (await conn.execute(text("""
                SELECT status FROM contrato.contratos WHERE id = :cid
            """), {"cid": str(contrato_id)})).first()
            assert crow[0] == "encerrado_compra"
    finally:
        await _cleanup_fixtures(empresa_id)


@pytest.mark.asyncio
async def test_servico_rejeita_titulo_que_nao_eh_opcao_compra():
    contrato_id, empresa_id, *_ = await _criar_fixtures()
    try:
        engine = get_engine()
        titulo_id = uuid4()
        async with engine.begin() as conn:
            await conn.execute(text("SET LOCAL row_security = off"))
            await conn.execute(text("""
                INSERT INTO financeiro.titulos_receber
                  (id, empresa_id, contrato_id, sequencia, data_vencimento, valor,
                   tipo, status, pago_em, valor_pago)
                VALUES (:id, :eid, :cid, 1, :dv, 800, 'parcela', 'pago', :pe, 800)
            """), {
                "id": str(titulo_id),
                "eid": str(empresa_id),
                "cid": str(contrato_id),
                "dv": date(2026, 6, 1),
                "pe": date(2026, 6, 5),
            })

        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(empresa_id)},
            )
            servico = ServicoOpcaoCompra(session, empresa_id)
            with pytest.raises(OpcaoCompraInvalidaError, match="não 'opcao_compra'"):
                await servico.processar_pagamento(titulo_id)
    finally:
        await _cleanup_fixtures(empresa_id)


@pytest.mark.asyncio
async def test_servico_rejeita_titulo_nao_pago():
    contrato_id, empresa_id, *_ = await _criar_fixtures()
    try:
        engine = get_engine()
        titulo_id = uuid4()
        async with engine.begin() as conn:
            await conn.execute(text("SET LOCAL row_security = off"))
            await conn.execute(text("""
                INSERT INTO financeiro.titulos_receber
                  (id, empresa_id, contrato_id, sequencia, data_vencimento, valor,
                   tipo, status)
                VALUES (:id, :eid, :cid, 13, :dv, 5000, 'opcao_compra', 'em_aberto')
            """), {
                "id": str(titulo_id),
                "eid": str(empresa_id),
                "cid": str(contrato_id),
                "dv": date(2027, 1, 1),
            })

        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(empresa_id)},
            )
            servico = ServicoOpcaoCompra(session, empresa_id)
            with pytest.raises(OpcaoCompraInvalidaError, match="só processa quando pago"):
                await servico.processar_pagamento(titulo_id)
    finally:
        await _cleanup_fixtures(empresa_id)


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────

async def _criar_fixtures() -> tuple[UUID, UUID, UUID, UUID, UUID | None]:
    """Cria empresa+cliente+veiculo+contrato (vigente) e retorna ids.
    Retorna (contrato_id, empresa_id, cliente_id, veiculo_id, admin_id)."""
    engine = get_engine()
    suffix = uuid4().hex[:8]
    empresa_id = uuid4()
    cliente_id = uuid4()
    veiculo_id = uuid4()
    contrato_id = uuid4()

    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        await conn.execute(text("""
            INSERT INTO comercial.empresas (id, razao_social, cnpj, email)
            VALUES (:id, :razao, :cnpj, :email)
        """), {
            "id": str(empresa_id),
            "razao": f"OC-{suffix}",
            "cnpj": f"{suffix}22000111"[:14].ljust(14, "0"),
            "email": f"oc{suffix}@test.com",
        })

        await conn.execute(text("""
            INSERT INTO cadastro.clientes (id, empresa_id, nome_completo, cpf_cnpj)
            VALUES (:id, :eid, :nome, :cpf)
        """), {
            "id": str(cliente_id),
            "eid": str(empresa_id),
            "nome": f"Cliente {suffix}",
            "cpf": f"{suffix}22233344"[:11],
        })

        await conn.execute(text("""
            INSERT INTO veiculos.veiculos
              (id, empresa_id, placa, fipe_marca, fipe_modelo, ano_modelo,
               ano_fabricacao, status)
            VALUES (:id, :eid, :placa, 'Toyota', 'Corolla', 2024, 2024, 'indisponivel')
        """), {
            "id": str(veiculo_id),
            "eid": str(empresa_id),
            "placa": f"OC{suffix[:5].upper()}",
        })

        admin_row = (await conn.execute(text(
            "SELECT id FROM acesso.usuarios LIMIT 1"
        ))).first()
        admin_id = admin_row[0] if admin_row else None

        await conn.execute(text("""
            INSERT INTO contrato.contratos
              (id, empresa_id, numero, cliente_id, veiculo_id, status,
               data_inicio, data_fim, valor_total, dia_vencimento, modo_geracao,
               valor_opcao_compra, criado_por_id)
            VALUES (:id, :eid, :num, :cli, :vei, 'vigente',
                    :di, :df, 12000, 15, 'antecipado', 5000, :uid)
        """), {
            "id": str(contrato_id),
            "eid": str(empresa_id),
            "num": f"C-{suffix}",
            "cli": str(cliente_id),
            "vei": str(veiculo_id),
            "di": date(2026, 1, 1),
            "df": date(2027, 1, 1),
            "uid": str(admin_id) if admin_id else None,
        })
    return contrato_id, empresa_id, cliente_id, veiculo_id, admin_id


async def _cleanup_fixtures(empresa_id: UUID) -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        await conn.execute(text("ALTER TABLE logs.log_auditoria DISABLE TRIGGER trg_log_auditoria_immutable"))
        try:
            await conn.execute(text(
                "DELETE FROM logs.log_auditoria WHERE entidade IN ('veiculos', 'contratos') "
                "AND payload_after::text LIKE '%' || :eid || '%'"
            ), {"eid": str(empresa_id)})
            await conn.execute(text("DELETE FROM contrato.eventos_contrato WHERE empresa_id = :eid"), {"eid": str(empresa_id)})
            await conn.execute(text("DELETE FROM financeiro.titulos_receber WHERE empresa_id = :eid"), {"eid": str(empresa_id)})
            await conn.execute(text("DELETE FROM contrato.contratos WHERE empresa_id = :eid"), {"eid": str(empresa_id)})
            await conn.execute(text("DELETE FROM veiculos.veiculos WHERE empresa_id = :eid"), {"eid": str(empresa_id)})
            await conn.execute(text("DELETE FROM cadastro.clientes WHERE empresa_id = :eid"), {"eid": str(empresa_id)})
            await conn.execute(text("DELETE FROM comercial.empresas WHERE id = :eid"), {"eid": str(empresa_id)})
        finally:
            await conn.execute(text("ALTER TABLE logs.log_auditoria ENABLE TRIGGER trg_log_auditoria_immutable"))
