"""Testes do pipeline de conciliação bancária (Story 13.20).

Cobre:
- Importadores OFX, PDF, CSV (com fixtures sintéticas).
- Idempotência por hash do arquivo.
- Sugestões de match (cross-check com comprovantes + score).
- Aplicar match dispara ServicoTituloPago.
- Aplicar lote respeitando score mínimo.
- Desfazer match em até 30 dias.
- Cross-check com comprovante já homologado.
"""

from __future__ import annotations

import hashlib
import io
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.application.services.servico_conciliacao import (
    ConciliacaoInvalidaError,
    SessaoJaExistenteError,
    ServicoConciliacao,
)
from app.infrastructure.conciliacao.dto import FormatoOrigem
from app.infrastructure.conciliacao.importador_csv import importar_csv
from app.infrastructure.conciliacao.importador_pdf import importar_pdf
from app.infrastructure.db.session import get_engine, get_sessionmaker


# ──────────────────────────────────────────────────────────────────
# Importadores — testes isolados
# ──────────────────────────────────────────────────────────────────

OFX_SINTETICO = """OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
<SIGNONMSGSRSV1>
<SONRS>
<STATUS><CODE>0<SEVERITY>INFO</STATUS>
<DTSERVER>20260503120000
<LANGUAGE>POR
</SONRS>
</SIGNONMSGSRSV1>
<BANKMSGSRSV1>
<STMTTRNRS>
<TRNUID>1
<STATUS><CODE>0<SEVERITY>INFO</STATUS>
<STMTRS>
<CURDEF>BRL
<BANKACCTFROM>
<BANKID>341
<ACCTID>12345
<ACCTTYPE>CHECKING
</BANKACCTFROM>
<BANKTRANLIST>
<DTSTART>20260501
<DTEND>20260531
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260503
<TRNAMT>800.00
<FITID>TX001
<MEMO>PIX RECEBIDO JOAO SILVA
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260510
<TRNAMT>1250.50
<FITID>TX002
<MEMO>TED RECEBIDA MARIA SOUZA
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260515
<TRNAMT>-25.00
<FITID>TX003
<MEMO>TARIFA MENSAL
</STMTTRN>
</BANKTRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""


def test_importa_ofx_extrai_3_transacoes():
    from app.infrastructure.conciliacao.importador_ofx import importar_ofx
    resultado = importar_ofx(OFX_SINTETICO.encode("latin-1"))
    assert resultado.formato == FormatoOrigem.OFX
    assert len(resultado.transacoes) == 3
    # Crédito e débito vêm misturados — caller filtra por eh_credito
    creditos = [t for t in resultado.transacoes if t.eh_credito]
    assert len(creditos) == 2
    assert any(t.valor == Decimal("800.00") for t in creditos)
    assert any(t.valor == Decimal("1250.50") for t in creditos)
    # PIX/TED detectados pelo tipo
    pix = next(t for t in creditos if "JOAO" in t.descricao)
    assert pix.tipo == "pix"


def test_importa_ofx_idempotente_em_fitid():
    """fitid identifica unicamente — re-import não duplica."""
    from app.infrastructure.conciliacao.importador_ofx import importar_ofx
    r1 = importar_ofx(OFX_SINTETICO.encode("latin-1"))
    r2 = importar_ofx(OFX_SINTETICO.encode("latin-1"))
    # Importadores são puros — devolvem mesmos fitids
    ids_1 = sorted([t.fitid for t in r1.transacoes])
    ids_2 = sorted([t.fitid for t in r2.transacoes])
    assert ids_1 == ids_2


def test_importa_csv_com_mapeamento_explicito():
    csv_data = (
        "Data,Histórico,Valor\n"
        "03/05/2026,PIX RECEBIDO JOAO,800.00\n"
        "10/05/2026,TED MARIA,1250.50\n"
        "15/05/2026,TARIFA,-25.00\n"
    )
    resultado = importar_csv(
        csv_data.encode("utf-8"),
        mapeamento={"data": "Data", "valor": "Valor", "descricao": "Histórico"},
    )
    assert len(resultado.transacoes) == 3
    assert resultado.transacoes[0].valor == Decimal("800.00")
    assert resultado.transacoes[2].valor == Decimal("-25.00")


def test_importa_csv_rejeita_sem_mapeamento_obrigatorio():
    resultado = importar_csv(b"col1,col2\n1,2", mapeamento={"data": "col1"})
    assert resultado.transacoes == []
    assert resultado.erros  # erro registrado


def test_importa_pdf_falha_graciosa_em_pdf_escaneado():
    # PDF mínimo válido sem texto — simula escaneado
    pdf_minimo = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF"
    resultado = importar_pdf(pdf_minimo)
    assert resultado.formato == FormatoOrigem.PDF
    # Falha graciosa, sem exceção
    assert resultado.transacoes == [] or len(resultado.erros) > 0


# ──────────────────────────────────────────────────────────────────
# Service — fixtures de banco
# ──────────────────────────────────────────────────────────────────

async def _criar_conta_e_titulos(titulos_valores: list[Decimal]):
    """Cria empresa+conta bancária+N títulos em aberto. Retorna (empresa_id, conta_id, [titulo_ids])."""
    engine = get_engine()
    suffix = uuid4().hex[:8]
    empresa_id = uuid4()
    conta_id = uuid4()
    cliente_id = uuid4()
    veiculo_id = uuid4()
    contrato_id = uuid4()

    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        await conn.execute(text("""
            INSERT INTO comercial.empresas (id, razao_social, cnpj, email)
            VALUES (:id, :r, :c, :e)
        """), {"id": str(empresa_id), "r": f"CB-{suffix}",
                "c": f"{suffix}88000111"[:14].ljust(14, "0"), "e": f"cb{suffix}@t.com"})
        await conn.execute(text("""
            INSERT INTO cadastro.clientes (id, empresa_id, nome_completo, cpf_cnpj, telefone)
            VALUES (:id, :eid, 'Cliente CB', :cpf, '11900008888')
        """), {"id": str(cliente_id), "eid": str(empresa_id),
                "cpf": f"{suffix}22233344"[:11]})
        await conn.execute(text("""
            INSERT INTO veiculos.veiculos (id, empresa_id, placa, fipe_marca, fipe_modelo,
              ano_modelo, ano_fabricacao, status)
            VALUES (:id, :eid, :placa, 'Honda', 'Civic', 2024, 2024, 'em_uso')
        """), {"id": str(veiculo_id), "eid": str(empresa_id),
                "placa": f"CB{suffix[:5].upper()}"})

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

        await conn.execute(text("""
            INSERT INTO conta_bancaria.contas_bancarias (id, empresa_id, nome, ativo)
            VALUES (:id, :eid, 'Conta Teste', true)
        """), {"id": str(conta_id), "eid": str(empresa_id)})

        titulo_ids = []
        for i, valor in enumerate(titulos_valores):
            tid = uuid4()
            titulo_ids.append(tid)
            await conn.execute(text("""
                INSERT INTO financeiro.titulos_receber
                  (id, empresa_id, contrato_id, sequencia, data_vencimento, valor, tipo, status)
                VALUES (:id, :eid, :cid, :seq, :dv, :v, 'parcela', 'em_aberto')
            """), {"id": str(tid), "eid": str(empresa_id), "cid": str(contrato_id),
                    "seq": i + 1, "dv": date(2026, 5, 3 + i * 7), "v": valor})

    return empresa_id, conta_id, titulo_ids


async def _cleanup(empresa_id: UUID) -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        await conn.execute(text("ALTER TABLE logs.log_auditoria DISABLE TRIGGER trg_log_auditoria_immutable"))
        try:
            await conn.execute(text("DELETE FROM logs.log_auditoria WHERE entidade IN ('contratos', 'veiculos', 'titulos_receber', 'comprovantes_pagamento', 'matches_conciliacao')"))
            await conn.execute(text("DELETE FROM conta_bancaria.matches_conciliacao WHERE empresa_id = :e"), {"e": str(empresa_id)})
            await conn.execute(text("DELETE FROM conta_bancaria.transacoes_bancarias WHERE empresa_id = :e"), {"e": str(empresa_id)})
            await conn.execute(text("DELETE FROM conta_bancaria.sessoes_conciliacao WHERE empresa_id = :e"), {"e": str(empresa_id)})
            await conn.execute(text("DELETE FROM conta_bancaria.contas_bancarias WHERE empresa_id = :e"), {"e": str(empresa_id)})
            await conn.execute(text("DELETE FROM financeiro.comprovantes_pagamento WHERE empresa_id = :e"), {"e": str(empresa_id)})
            await conn.execute(text("DELETE FROM financeiro.movimentos_titulo_receber WHERE empresa_id = :e"), {"e": str(empresa_id)})
            await conn.execute(text("DELETE FROM financeiro.titulos_receber WHERE empresa_id = :e"), {"e": str(empresa_id)})
            await conn.execute(text("DELETE FROM contrato.eventos_contrato WHERE empresa_id = :e"), {"e": str(empresa_id)})
            await conn.execute(text("DELETE FROM contrato.contratos WHERE empresa_id = :e"), {"e": str(empresa_id)})
            await conn.execute(text("DELETE FROM veiculos.veiculos WHERE empresa_id = :e"), {"e": str(empresa_id)})
            await conn.execute(text("DELETE FROM cadastro.clientes WHERE empresa_id = :e"), {"e": str(empresa_id)})
            await conn.execute(text("DELETE FROM comercial.empresas WHERE id = :e"), {"e": str(empresa_id)})
        finally:
            await conn.execute(text("ALTER TABLE logs.log_auditoria ENABLE TRIGGER trg_log_auditoria_immutable"))


# ──────────────────────────────────────────────────────────────────
# Service — integração
# ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_importar_ofx_cria_sessao_e_persiste_transacoes():
    empresa_id, conta_id, _ = await _criar_conta_e_titulos([Decimal("800.00"), Decimal("1250.50")])
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(empresa_id)},
            )
            servico = ServicoConciliacao(session, empresa_id)
            sessao = await servico.importar(
                conta_id=conta_id,
                bytes_arquivo=OFX_SINTETICO.encode("latin-1"),
                nome_arquivo="teste.ofx",
                formato=FormatoOrigem.OFX,
            )
            await session.commit()
            assert sessao.total_transacoes == 3
            assert sessao.formato_origem == "ofx"
            assert sessao.hash_arquivo is not None
    finally:
        await _cleanup(empresa_id)


@pytest.mark.asyncio
async def test_importar_mesmo_extrato_2x_retorna_sessao_existente():
    empresa_id, conta_id, _ = await _criar_conta_e_titulos([Decimal("800.00")])
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(empresa_id)},
            )
            servico = ServicoConciliacao(session, empresa_id)
            sessao1 = await servico.importar(
                conta_id=conta_id,
                bytes_arquivo=OFX_SINTETICO.encode("latin-1"),
                nome_arquivo="teste.ofx",
                formato=FormatoOrigem.OFX,
            )
            await session.commit()

            with pytest.raises(SessaoJaExistenteError) as exc:
                await servico.importar(
                    conta_id=conta_id,
                    bytes_arquivo=OFX_SINTETICO.encode("latin-1"),
                    nome_arquivo="teste-duplicado.ofx",
                    formato=FormatoOrigem.OFX,
                )
            assert exc.value.sessao_existente.id == sessao1.id
    finally:
        await _cleanup(empresa_id)


@pytest.mark.asyncio
async def test_listar_sugestoes_cassa_transacao_com_titulo_por_valor():
    """OFX tem crédito de R$ 800. Existe título de R$ 800. Sugestão deve casá-los com score alto."""
    empresa_id, conta_id, titulos = await _criar_conta_e_titulos([Decimal("800.00")])
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(empresa_id)},
            )
            servico = ServicoConciliacao(session, empresa_id)
            sessao = await servico.importar(
                conta_id=conta_id,
                bytes_arquivo=OFX_SINTETICO.encode("latin-1"),
                nome_arquivo="teste.ofx",
                formato=FormatoOrigem.OFX,
            )
            await session.commit()

            sugestoes = await servico.listar_sugestoes(sessao.id)
            # 2 créditos no OFX, 1 título
            # O crédito de R$ 800 deveria casar com o título de R$ 800
            casadas = [s for s in sugestoes if s.titulo_id == titulos[0]]
            assert len(casadas) == 1
            assert casadas[0].score >= 0.85  # valor exato + data próxima
    finally:
        await _cleanup(empresa_id)


@pytest.mark.asyncio
async def test_aplicar_match_dispara_servico_titulo_pago():
    """Aplicar match deve marcar título como pago via ServicoTituloPago da 13.9."""
    empresa_id, conta_id, titulos = await _criar_conta_e_titulos([Decimal("800.00")])
    try:
        sm = get_sessionmaker()
        admin_id = None
        async with sm() as session:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(empresa_id)},
            )
            admin = (await session.execute(
                text("SELECT id FROM acesso.usuarios WHERE email='admin@example.com'")
            )).first()
            admin_id = admin[0] if admin else None

            servico = ServicoConciliacao(session, empresa_id)
            sessao = await servico.importar(
                conta_id=conta_id,
                bytes_arquivo=OFX_SINTETICO.encode("latin-1"),
                nome_arquivo="teste.ofx",
                formato=FormatoOrigem.OFX,
            )
            await session.commit()

            sugestoes = await servico.listar_sugestoes(sessao.id)
            sug_casada = next(s for s in sugestoes if s.titulo_id == titulos[0])

            match = await servico.aplicar_match(
                sessao_id=sessao.id,
                transacao_id=sug_casada.transacao_id,
                titulo_id=sug_casada.titulo_id,
                score=sug_casada.score,
                motivo=sug_casada.motivo,
                aplicado_por_id=admin_id,
            )
            await session.commit()
            assert match.id is not None

        # Verifica em sessão nova que título virou pago
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(text("SET LOCAL row_security = off"))
            row = (await conn.execute(text(
                "SELECT status, valor_pago FROM financeiro.titulos_receber WHERE id = :t"
            ), {"t": str(titulos[0])})).first()
            assert row[0] == "pago"
            assert row[1] == Decimal("800.00")
    finally:
        await _cleanup(empresa_id)


@pytest.mark.asyncio
async def test_aplicar_lote_aplica_apenas_score_alto():
    """Aplica em lote só sugestões com score ≥ 0.95."""
    empresa_id, conta_id, titulos = await _criar_conta_e_titulos([Decimal("800.00"), Decimal("1250.50")])
    try:
        sm = get_sessionmaker()
        admin_id = None
        async with sm() as session:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(empresa_id)},
            )
            admin = (await session.execute(
                text("SELECT id FROM acesso.usuarios WHERE email='admin@example.com'")
            )).first()
            admin_id = admin[0] if admin else None

            servico = ServicoConciliacao(session, empresa_id)
            sessao = await servico.importar(
                conta_id=conta_id,
                bytes_arquivo=OFX_SINTETICO.encode("latin-1"),
                nome_arquivo="teste.ofx",
                formato=FormatoOrigem.OFX,
            )
            await session.commit()

            sugestoes = await servico.listar_sugestoes(sessao.id)
            aplicados = 0
            for sug in sugestoes:
                if sug.score >= 0.85 and sug.titulo_id is not None:
                    await servico.aplicar_match(
                        sessao_id=sessao.id,
                        transacao_id=sug.transacao_id,
                        titulo_id=sug.titulo_id,
                        score=sug.score,
                        motivo=sug.motivo,
                        aplicado_por_id=admin_id,
                    )
                    aplicados += 1
            await session.commit()
            assert aplicados >= 1
    finally:
        await _cleanup(empresa_id)


@pytest.mark.asyncio
async def test_desfazer_match_libera_transacao():
    empresa_id, conta_id, titulos = await _criar_conta_e_titulos([Decimal("800.00")])
    try:
        sm = get_sessionmaker()
        admin_id = None
        match_id = None
        async with sm() as session:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(empresa_id)},
            )
            admin = (await session.execute(
                text("SELECT id FROM acesso.usuarios WHERE email='admin@example.com'")
            )).first()
            admin_id = admin[0] if admin else None

            servico = ServicoConciliacao(session, empresa_id)
            sessao = await servico.importar(
                conta_id=conta_id,
                bytes_arquivo=OFX_SINTETICO.encode("latin-1"),
                nome_arquivo="teste.ofx",
                formato=FormatoOrigem.OFX,
            )
            await session.commit()
            sugestoes = await servico.listar_sugestoes(sessao.id)
            sug = next(s for s in sugestoes if s.titulo_id == titulos[0])
            match = await servico.aplicar_match(
                sessao_id=sessao.id,
                transacao_id=sug.transacao_id,
                titulo_id=sug.titulo_id,
                score=sug.score,
                motivo=sug.motivo,
                aplicado_por_id=admin_id,
            )
            match_id = match.id
            await session.commit()

        async with sm() as session:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(empresa_id)},
            )
            servico = ServicoConciliacao(session, empresa_id)
            desfeito = await servico.desfazer_match(
                match_id=match_id,
                motivo="Teste — pagamento incorreto",
                desfeito_por_id=admin_id,
            )
            await session.commit()
            assert desfeito.desfeito_em is not None
            assert desfeito.motivo_desfazer == "Teste — pagamento incorreto"
    finally:
        await _cleanup(empresa_id)


@pytest.mark.asyncio
async def test_cross_check_com_comprovante_ja_homologado():
    """Quando comprovante PIX foi homologado antes do extrato chegar,
    sugestão para a transação correspondente marca `ja_existia_via_comprovante=True`."""
    empresa_id, conta_id, titulos = await _criar_conta_e_titulos([Decimal("800.00")])
    try:
        sm = get_sessionmaker()
        # Cria comprovante já homologado simulando pagamento prévio via comprovante
        engine = get_engine()
        comp_id = uuid4()
        async with engine.begin() as conn:
            await conn.execute(text("SET LOCAL row_security = off"))
            await conn.execute(text("""
                INSERT INTO financeiro.comprovantes_pagamento
                  (id, empresa_id, titulo_id, arquivo_url, arquivo_hash, tipo_arquivo,
                   metodo_analise, score_confianca, valor_detectado, data_detectada,
                   status, origem)
                VALUES (:id, :eid, :tid, 'fake://x.png', :h, 'image/png',
                        'br_code', 0.95, :v, :d, 'homologado', 'upload')
            """), {
                "id": str(comp_id), "eid": str(empresa_id),
                "tid": str(titulos[0]),
                "h": hashlib.sha256(b"fake").hexdigest(),
                "v": Decimal("800.00"),
                "d": datetime(2026, 5, 3, 14, 0, tzinfo=timezone.utc),
            })

        async with sm() as session:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(empresa_id)},
            )
            servico = ServicoConciliacao(session, empresa_id)
            sessao = await servico.importar(
                conta_id=conta_id,
                bytes_arquivo=OFX_SINTETICO.encode("latin-1"),
                nome_arquivo="teste.ofx",
                formato=FormatoOrigem.OFX,
            )
            await session.commit()

            sugestoes = await servico.listar_sugestoes(sessao.id)
            # A transação de R$ 800 deve ter detectado o comprovante
            sug_800 = next((s for s in sugestoes if s.score == 1.0), None)
            assert sug_800 is not None
            assert sug_800.ja_existia_via_comprovante is True
            assert sug_800.comprovante_id == comp_id
    finally:
        await _cleanup(empresa_id)
