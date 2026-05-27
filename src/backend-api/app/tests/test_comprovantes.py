"""Testes do pipeline de análise de comprovantes (Story 13.19).

Foca em testes **sintéticos** (sem dependência de comprovantes reais):
- BR Code: gera QR via `qrcode` lib, decodifica, valida entidades.
- PDF textual: gera PDF via reportlab, extrai texto, valida.
- OCR: gera imagem com texto via PIL, OCR via Tesseract.
- Extratores universais: regex contra strings montadas.
- Validação de CPF/CNPJ.
- Detector de banco.
- Matcher com títulos.
- Idempotência por hash.

Testes 'reais' (com comprovante de banco verdadeiro) ficam para quando
Pablo fornecer amostras — story não bloqueia por isso.
"""

from __future__ import annotations

import io
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import qrcode
from PIL import Image, ImageDraw
from sqlalchemy import text

from app.domain.finance.comprovante import EntidadesExtraidas
from app.infrastructure.comprovantes.br_code_decoder import decodificar_br_code
from app.infrastructure.comprovantes.detector_banco import (
    detectar_banco,
    reset_cache_para_testes,
)
from app.infrastructure.comprovantes.extratores_universais import (
    _validar_cnpj,
    _validar_cpf,
    extrair_data,
    extrair_documentos,
    extrair_entidades_de_texto,
    extrair_valor_principal,
)
from app.infrastructure.comprovantes.matcher_titulos import encontrar_titulo_match
from app.infrastructure.comprovantes.ocr import extrair_texto_via_ocr
from app.infrastructure.db.session import get_engine, get_sessionmaker


# ─────────────────────────────────────────────────────────────────
# Validadores CPF/CNPJ
# ─────────────────────────────────────────────────────────────────

def test_valida_cpf_correto():
    # CPF gerado por algoritmo
    assert _validar_cpf("123.456.789-09") is True


def test_rejeita_cpf_com_digitos_errados():
    assert _validar_cpf("123.456.789-10") is False
    assert _validar_cpf("111.111.111-11") is False  # mesmos dígitos


def test_valida_cnpj_correto():
    assert _validar_cnpj("11.222.333/0001-81") is True


def test_rejeita_cnpj_invalido():
    assert _validar_cnpj("11.222.333/0001-99") is False
    assert _validar_cnpj("00.000.000/0000-00") is False


# ─────────────────────────────────────────────────────────────────
# Extratores universais (regex)
# ─────────────────────────────────────────────────────────────────

def test_extrai_valor_principal_pega_o_maior():
    texto = "Valor pago: R$ 1.250,00\nTaxa: R$ 2,50\nSaldo: R$ 350,00"
    assert extrair_valor_principal(texto) == Decimal("1250.00")


def test_extrai_data_brasileira_com_hora():
    texto = "Data da transação: 03/05/2026 às 14:32"
    d = extrair_data(texto)
    assert d == datetime(2026, 5, 3, 14, 32)


def test_extrai_data_sem_hora():
    texto = "Pagamento: 15/06/2026"
    d = extrair_data(texto)
    assert d == datetime(2026, 6, 15, 0, 0)


def test_extrai_documentos_so_validos():
    # CPF válido e CNPJ válido misturados com lixo
    texto = "CPF do pagador: 123.456.789-09\nCPF inválido: 111.111.111-11\nCNPJ: 11.222.333/0001-81"
    cpf, cnpj = extrair_documentos(texto)
    assert cpf == "123.456.789-09"
    assert cnpj == "11.222.333/0001-81"


def test_extrai_entidades_de_comprovante_completo():
    texto = """COMPROVANTE PIX
Nubank S.A.
Data: 03/05/2026 às 14:32
Valor: R$ 1.250,00
Pagador: João da Silva
CPF: 123.456.789-09
Beneficiário: Frota Uber LTDA
CNPJ: 11.222.333/0001-81
Chave PIX: financeiro@frotauber.com
"""
    e = extrair_entidades_de_texto(texto)
    assert e.valor == Decimal("1250.00")
    assert e.data == datetime(2026, 5, 3, 14, 32)
    assert e.pagador_documento == "123.456.789-09"
    assert e.beneficiario_cnpj == "11.222.333/0001-81"
    assert e.chave_pix == "financeiro@frotauber.com"
    assert e.pagador_nome and "João" in e.pagador_nome
    assert e.beneficiario_nome and "Frota Uber" in e.beneficiario_nome


# ─────────────────────────────────────────────────────────────────
# Detector de banco
# ─────────────────────────────────────────────────────────────────

def test_detector_reconhece_nubank():
    reset_cache_para_testes()
    tpl = detectar_banco("Comprovante Nubank S.A.")
    assert tpl is not None
    assert tpl.slug == "nubank"


def test_detector_reconhece_caixa():
    reset_cache_para_testes()
    tpl = detectar_banco("Caixa Econômica Federal pagamento PIX")
    assert tpl is not None
    assert tpl.slug == "caixa"


def test_detector_devolve_none_para_banco_desconhecido():
    reset_cache_para_testes()
    assert detectar_banco("Banco Marciano XYZ S.A.") is None


# ─────────────────────────────────────────────────────────────────
# BR Code decoder
# ─────────────────────────────────────────────────────────────────

def test_br_code_decodifica_payload_emv_valido():
    payload = (
        "00020126410014BR.GOV.BCB.PIX0119teste@frotauber.com"
        "5204000053039865406012.345802BR"
        "5913Frota Uber LTDA6009Sao Paulo62070503xyz6304ABCD"
    )
    img = qrcode.make(payload)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    result = decodificar_br_code(buf.getvalue())
    assert result is not None
    entidades, score = result
    assert score >= 0.90
    assert entidades.valor == Decimal("12.34")
    assert entidades.chave_pix == "teste@frotauber.com"


def test_br_code_retorna_none_em_imagem_sem_qr():
    img = Image.new("RGB", (200, 200), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    assert decodificar_br_code(buf.getvalue()) is None


# ─────────────────────────────────────────────────────────────────
# OCR (Tesseract)
# ─────────────────────────────────────────────────────────────────

def test_ocr_extrai_texto_de_imagem_sintetica():
    """Gera imagem com texto e valida que OCR pega ao menos os valores principais."""
    img = Image.new("RGB", (1000, 400), color="white")
    d = ImageDraw.Draw(img)
    d.text((30, 30), "COMPROVANTE PIX", fill="black")
    d.text((30, 80), "Valor: R$ 1.250,00", fill="black")
    d.text((30, 130), "Data: 03/05/2026", fill="black")
    d.text((30, 180), "CPF: 123.456.789-09", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    result = extrair_texto_via_ocr(buf.getvalue())
    assert result is not None
    texto, score = result
    assert score > 0
    # OCR tem erros mas valor e data padrão devem estar presentes
    assert "1.250" in texto or "1250" in texto


# ─────────────────────────────────────────────────────────────────
# Matcher com títulos (integração com DB)
# ─────────────────────────────────────────────────────────────────

async def _criar_fixture_com_titulo(valor_titulo: Decimal, dias_ate_vencer: int = 0):
    """Cria empresa+cliente+veiculo+contrato+título e retorna ids."""
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
        """), {"id": str(empresa_id), "r": f"CMP-{suffix}",
                "c": f"{suffix}77000111"[:14].ljust(14, "0"), "e": f"cmp{suffix}@t.com"})
        await conn.execute(text("""
            INSERT INTO cadastro.clientes (id, empresa_id, nome_completo, cpf_cnpj, telefone)
            VALUES (:id, :eid, 'Cliente Teste', :cpf, '11999990000')
        """), {"id": str(cliente_id), "eid": str(empresa_id),
                "cpf": f"{suffix}11122333"[:11]})
        await conn.execute(text("""
            INSERT INTO veiculos.veiculos (id, empresa_id, placa, fipe_marca, fipe_modelo,
              ano_modelo, ano_fabricacao, status)
            VALUES (:id, :eid, :placa, 'Toyota', 'Corolla', 2024, 2024, 'em_uso')
        """), {"id": str(veiculo_id), "eid": str(empresa_id),
                "placa": f"CP{suffix[:5].upper()}"})

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

        vencimento = date.today() + timedelta(days=dias_ate_vencer)
        await conn.execute(text("""
            INSERT INTO financeiro.titulos_receber
              (id, empresa_id, contrato_id, sequencia, data_vencimento, valor, tipo, status)
            VALUES (:id, :eid, :cid, 1, :dv, :v, 'parcela', 'em_aberto')
        """), {"id": str(titulo_id), "eid": str(empresa_id), "cid": str(contrato_id),
                "dv": vencimento, "v": valor_titulo})

    return empresa_id, titulo_id, vencimento


async def _cleanup(empresa_id: UUID):
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        await conn.execute(text("ALTER TABLE logs.log_auditoria DISABLE TRIGGER trg_log_auditoria_immutable"))
        try:
            await conn.execute(text("DELETE FROM logs.log_auditoria WHERE entidade IN ('contratos', 'veiculos', 'titulos_receber', 'comprovantes_pagamento')"))
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


@pytest.mark.asyncio
async def test_matcher_encontra_titulo_por_valor_exato_e_data():
    empresa_id, titulo_id, vencimento = await _criar_fixture_com_titulo(Decimal("800.00"), dias_ate_vencer=0)
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(empresa_id)},
            )
            ent = EntidadesExtraidas(
                valor=Decimal("800.00"),
                data=datetime(vencimento.year, vencimento.month, vencimento.day, 14, 0),
            )
            match = await encontrar_titulo_match(session, empresa_id, ent)
            assert match is not None
            assert match.titulo_id == titulo_id
            assert match.score_match >= 0.85  # valor exato + data exata
    finally:
        await _cleanup(empresa_id)


@pytest.mark.asyncio
async def test_matcher_retorna_none_quando_valor_nao_bate():
    empresa_id, _, _ = await _criar_fixture_com_titulo(Decimal("800.00"))
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(empresa_id)},
            )
            ent = EntidadesExtraidas(valor=Decimal("999.99"))
            match = await encontrar_titulo_match(session, empresa_id, ent)
            assert match is None
    finally:
        await _cleanup(empresa_id)


# ─────────────────────────────────────────────────────────────────
# Service orquestrador (integração)
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_servico_analisa_br_code_e_vincula_titulo():
    """Pipeline ponta-a-ponta com BR Code sintético casando título."""
    from app.application.services.servico_analise_comprovante import (
        ServicoAnaliseComprovante,
    )

    empresa_id, titulo_id, vencimento = await _criar_fixture_com_titulo(Decimal("12.34"))
    try:
        payload = (
            "00020126410014BR.GOV.BCB.PIX0119teste@frotauber.com"
            "5204000053039865406012.345802BR"
            "5913Frota Uber LTDA6009Sao Paulo62070503xyz6304ABCD"
        )
        img = qrcode.make(payload)
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(empresa_id)},
            )
            servico = ServicoAnaliseComprovante(session, empresa_id)
            comp = await servico.analisar(
                bytes_arquivo=buf.getvalue(),
                tipo_mime="image/png",
                arquivo_url="s3://fake/teste.png",
            )
            await session.commit()
            assert comp.metodo_analise == "br_code"
            assert float(comp.score_confianca) >= 0.9
            assert comp.valor_detectado == Decimal("12.34")
            assert comp.titulo_id == titulo_id  # casou!
    finally:
        await _cleanup(empresa_id)


@pytest.mark.asyncio
async def test_servico_idempotente_por_hash_de_arquivo():
    """Enviar o mesmo arquivo 2x retorna o registro existente."""
    from app.application.services.servico_analise_comprovante import (
        ComprovanteJaAnalisadoError,
        ServicoAnaliseComprovante,
    )

    empresa_id, _, _ = await _criar_fixture_com_titulo(Decimal("100.00"))
    try:
        img = Image.new("RGB", (200, 200), color="white")
        d = ImageDraw.Draw(img)
        d.text((20, 20), "Comprovante teste R$ 100,00", fill="black")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        bytes_arquivo = buf.getvalue()

        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(empresa_id)},
            )
            servico = ServicoAnaliseComprovante(session, empresa_id)
            comp1 = await servico.analisar(
                bytes_arquivo=bytes_arquivo,
                tipo_mime="image/png",
                arquivo_url="s3://fake/1.png",
            )
            await session.commit()

            # Segunda chamada com mesmos bytes
            with pytest.raises(ComprovanteJaAnalisadoError) as exc:
                await servico.analisar(
                    bytes_arquivo=bytes_arquivo,
                    tipo_mime="image/png",
                    arquivo_url="s3://fake/2.png",
                )
            assert exc.value.comprovante_existente.id == comp1.id
    finally:
        await _cleanup(empresa_id)
