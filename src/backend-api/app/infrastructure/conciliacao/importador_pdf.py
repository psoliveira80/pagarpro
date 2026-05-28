"""Importador PDF (Story 13.20).

Extratos em PDF vêm em 2 sabores:

1. **PDF nativo** (gerado eletronicamente pelo banco): tem texto extraível
   via `pdfplumber`. Parse via heurística por linhas/colunas.
2. **PDF escaneado** (foto/scan): precisa OCR — delega para o pipeline
   da Story 13.19 (`ocr.py`).

V1 cobre **PDF nativo** com parser tolerante:
- Detecta linhas que parecem ser transações (data + valor BR no final).
- Tenta inferir descrição (entre data e valor).
- Tenta detectar banco no header.

Bancos com layout complexo (Itaú multi-coluna, BB com agrupamento)
podem deixar transações pra trás — isso é aceitável para V1 porque o
fluxo padrão é OFX. PDF é fallback quando cliente não tem como exportar
OFX.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.infrastructure.conciliacao.dto import (
    FormatoOrigem,
    ResultadoImportacao,
    TransacaoImportada,
)


log = logging.getLogger(__name__)


# Regex de linha de transação genérica: data BR + descrição + valor BR no fim
# Aceita +/- prefixo no valor e parênteses (saída de alguns bancos).
RE_LINHA_TRANSACAO = re.compile(
    r"^(?P<data>\d{2}[/-]\d{2}[/-]\d{4})\s+"
    r"(?P<descricao>.+?)\s+"
    r"(?P<sinal>[-+]?)R?\$?\s*"
    r"(?P<valor>\(?\d{1,3}(?:\.\d{3})*,\d{2}\)?)"
    r"\s*$",
    re.IGNORECASE,
)


def importar_pdf(bytes_arquivo: bytes) -> ResultadoImportacao:
    """Importa extrato PDF nativo (textual)."""
    try:
        import pdfplumber
    except ImportError:
        return ResultadoImportacao(
            formato=FormatoOrigem.PDF,
            transacoes=[],
            erros=["pdfplumber não disponível"],
        )

    transacoes: list[TransacaoImportada] = []
    erros: list[str] = []
    periodo_inicio: date | None = None
    periodo_fim: date | None = None
    nome_banco: str | None = None

    try:
        with pdfplumber.open(io.BytesIO(bytes_arquivo)) as pdf:
            texto_completo = ""
            for page in pdf.pages:
                texto = page.extract_text() or ""
                texto_completo += texto + "\n"

            # Sanity check: PDF escaneado?
            if len(texto_completo.strip()) < 100:
                return ResultadoImportacao(
                    formato=FormatoOrigem.PDF,
                    transacoes=[],
                    erros=[
                        "PDF parece escaneado (pouco texto extraível). "
                        "Suporte a OCR de extrato será adicionado em sub-story."
                    ],
                )

            # Detecta banco no header (top 500 chars)
            from app.infrastructure.comprovantes.detector_banco import detectar_banco
            tpl = detectar_banco(texto_completo[:500])
            if tpl is not None:
                nome_banco = tpl.nome_oficial

            # Itera linha-a-linha procurando padrão de transação
            for linha in texto_completo.splitlines():
                linha = linha.strip()
                if not linha:
                    continue
                m = RE_LINHA_TRANSACAO.match(linha)
                if m is None:
                    continue
                try:
                    tx = _linha_para_transacao(m)
                except Exception as exc:
                    erros.append(f"Linha inválida: {linha[:80]} ({exc})")
                    continue
                transacoes.append(tx)
                periodo_inicio = min(periodo_inicio, tx.data) if periodo_inicio else tx.data
                periodo_fim = max(periodo_fim, tx.data) if periodo_fim else tx.data

    except Exception as exc:
        return ResultadoImportacao(
            formato=FormatoOrigem.PDF,
            transacoes=[],
            erros=[f"Falha ao processar PDF: {exc}"],
        )

    return ResultadoImportacao(
        formato=FormatoOrigem.PDF,
        transacoes=transacoes,
        periodo_inicio=periodo_inicio,
        periodo_fim=periodo_fim,
        nome_banco=nome_banco,
        erros=erros,
    )


def _linha_para_transacao(m: re.Match) -> TransacaoImportada:
    """Mapeia match regex pra DTO."""
    data_str = m.group("data").replace("-", "/")
    data_tx = datetime.strptime(data_str, "%d/%m/%Y").date()

    descricao = m.group("descricao").strip()

    valor_str = m.group("valor")
    # Remove parênteses (notação de saída em alguns extratos)
    eh_negativo_parentes = valor_str.startswith("(") and valor_str.endswith(")")
    valor_str = valor_str.strip("()")
    valor_str = valor_str.replace(".", "").replace(",", ".")
    try:
        valor = Decimal(valor_str)
    except InvalidOperation as exc:
        raise ValueError(f"Valor inválido: {valor_str}") from exc

    sinal = m.group("sinal")
    if sinal == "-" or eh_negativo_parentes:
        valor = -valor

    desc_low = descricao.lower()
    tipo: str | None = None
    if "pix" in desc_low:
        tipo = "pix"
    elif "ted" in desc_low:
        tipo = "ted"
    elif "doc" in desc_low:
        tipo = "doc"

    # FITID sintético: hash da combinação data+valor+descricao
    import hashlib
    fitid = hashlib.sha1(
        f"{data_tx.isoformat()}|{valor}|{descricao[:50]}".encode()
    ).hexdigest()[:32]

    return TransacaoImportada(
        fitid=fitid,
        data=data_tx,
        valor=valor,
        descricao=descricao,
        tipo=tipo,
    )
