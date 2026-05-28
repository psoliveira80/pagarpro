"""Importador OFX (Story 13.20).

OFX é XML estruturado padrão dos bancos brasileiros. `ofxparse` resolve
o parse — só precisamos mapear os campos.

OFX exporta TODAS as transações (crédito + débito). Para conciliação de
recebimentos, o caller filtra por `t.eh_credito`.
"""

from __future__ import annotations

import io
import logging
from datetime import date
from decimal import Decimal

from app.infrastructure.conciliacao.dto import (
    FormatoOrigem,
    ResultadoImportacao,
    TransacaoImportada,
)


log = logging.getLogger(__name__)


def importar_ofx(bytes_arquivo: bytes) -> ResultadoImportacao:
    """Faz parsing do extrato OFX e retorna transações estruturadas.

    Tolerante: se algumas transações falham parsing individual, registra
    erro e continua com as demais.
    """
    try:
        import ofxparse
    except ImportError:
        return ResultadoImportacao(
            formato=FormatoOrigem.OFX,
            transacoes=[],
            erros=["ofxparse não disponível no ambiente"],
        )

    transacoes: list[TransacaoImportada] = []
    erros: list[str] = []
    periodo_inicio: date | None = None
    periodo_fim: date | None = None
    nome_banco: str | None = None

    try:
        # ofxparse aceita arquivo binário diretamente
        ofx = ofxparse.OfxParser.parse(io.BytesIO(bytes_arquivo))
    except Exception as exc:
        return ResultadoImportacao(
            formato=FormatoOrigem.OFX,
            transacoes=[],
            erros=[f"Falha ao parsear OFX: {exc}"],
        )

    # OFX pode ter múltiplas contas; iteramos todas e juntamos
    contas = ofx.accounts if hasattr(ofx, "accounts") else [ofx.account]
    for conta in contas:
        if conta is None:
            continue
        # Banco emissor
        if hasattr(conta, "institution") and conta.institution:
            nome_banco = nome_banco or getattr(conta.institution, "organization", None)

        statement = conta.statement
        if statement is None:
            continue

        # Período
        if statement.start_date:
            d = statement.start_date.date() if hasattr(statement.start_date, "date") else statement.start_date
            periodo_inicio = min(periodo_inicio, d) if periodo_inicio else d
        if statement.end_date:
            d = statement.end_date.date() if hasattr(statement.end_date, "date") else statement.end_date
            periodo_fim = max(periodo_fim, d) if periodo_fim else d

        for tx in statement.transactions:
            try:
                transacoes.append(_mapear_transacao(tx))
            except Exception as exc:
                erros.append(f"Transação inválida: {exc}")

    return ResultadoImportacao(
        formato=FormatoOrigem.OFX,
        transacoes=transacoes,
        periodo_inicio=periodo_inicio,
        periodo_fim=periodo_fim,
        nome_banco=nome_banco,
        erros=erros,
    )


def _mapear_transacao(tx) -> TransacaoImportada:
    """Converte uma transação `ofxparse` para nosso DTO."""
    data_tx = tx.date.date() if hasattr(tx.date, "date") else tx.date
    valor = Decimal(str(tx.amount)) if tx.amount is not None else Decimal("0")

    # `ofxparse` traz `type` (CREDIT/DEBIT/etc.) e `memo` (descrição).
    descricao = (tx.memo or "").strip() or (tx.payee or "").strip() or "—"

    # Heurística simples de tipo: PIX se descrição contém "pix" (case-insensitive)
    tipo: str | None = None
    desc_low = descricao.lower()
    if "pix" in desc_low:
        tipo = "pix"
    elif "ted" in desc_low:
        tipo = "ted"
    elif "doc" in desc_low:
        tipo = "doc"
    elif "tarifa" in desc_low or "taxa" in desc_low:
        tipo = "tarifa"

    return TransacaoImportada(
        fitid=tx.id,
        data=data_tx,
        valor=valor,
        descricao=descricao,
        tipo=tipo,
    )
