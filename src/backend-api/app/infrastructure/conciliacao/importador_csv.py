"""Importador CSV (Story 13.20).

Extrato em CSV/XLSX exportado pelo banco. Mapeamento de colunas explícito
pelo caller (frontend pede ao gestor qual coluna é Data, qual é Valor, etc.).

V1 sem mapeamento persistente — o frontend envia o mapeamento na request.
Story futura: persistir mapeamento por banco para reutilização.
"""

from __future__ import annotations

import csv
import hashlib
import io
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.infrastructure.conciliacao.dto import (
    FormatoOrigem,
    ResultadoImportacao,
    TransacaoImportada,
)


log = logging.getLogger(__name__)


def importar_csv(
    bytes_arquivo: bytes,
    mapeamento: dict[str, str],
    formato_data: str = "%d/%m/%Y",
    encoding: str = "utf-8",
    delimitador: str = ",",
) -> ResultadoImportacao:
    """Importa CSV com mapeamento explícito de colunas.

    Args:
        bytes_arquivo: conteúdo do CSV.
        mapeamento: dict com chaves obrigatórias `data`, `valor`, `descricao`
            e opcional `fitid`. Valor é o nome da coluna no CSV.
        formato_data: strftime format. Default brasileiro.
        encoding: usar `latin-1` para CSV exportado por bancos legados.
        delimitador: `,` `;` ou `\\t`.

    Exemplo:
        mapeamento = {"data": "Data", "valor": "Valor", "descricao": "Histórico"}
    """
    if not all(k in mapeamento for k in ("data", "valor", "descricao")):
        return ResultadoImportacao(
            formato=FormatoOrigem.CSV,
            transacoes=[],
            erros=["Mapeamento obrigatório: data, valor, descricao"],
        )

    try:
        texto = bytes_arquivo.decode(encoding, errors="replace")
    except Exception as exc:
        return ResultadoImportacao(
            formato=FormatoOrigem.CSV,
            transacoes=[],
            erros=[f"Encoding inválido: {exc}"],
        )

    reader = csv.DictReader(io.StringIO(texto), delimiter=delimitador)
    transacoes: list[TransacaoImportada] = []
    erros: list[str] = []
    periodo_inicio = None
    periodo_fim = None

    for linha_num, linha in enumerate(reader, start=2):  # 1 é header
        try:
            data_str = (linha.get(mapeamento["data"]) or "").strip()
            data_tx = datetime.strptime(data_str, formato_data).date()

            valor_str = (linha.get(mapeamento["valor"]) or "").strip()
            valor_str = valor_str.replace("R$", "").strip()
            eh_negativo_parentes = valor_str.startswith("(") and valor_str.endswith(")")
            valor_str = valor_str.strip("()")
            # Detecta formato: BR ("1.250,00" ou "800,00") vs US ("1250.00" ou "800.00").
            # Critério: presença de vírgula → BR. Sem vírgula → US (ponto é decimal).
            if "," in valor_str:
                valor_str = valor_str.replace(".", "").replace(",", ".")
            valor = Decimal(valor_str)
            if eh_negativo_parentes:
                valor = -valor

            descricao = (linha.get(mapeamento["descricao"]) or "").strip() or "—"

            fitid = None
            if "fitid" in mapeamento:
                fitid = (linha.get(mapeamento["fitid"]) or "").strip() or None
            if not fitid:
                fitid = hashlib.sha1(
                    f"{data_tx.isoformat()}|{valor}|{descricao[:50]}".encode()
                ).hexdigest()[:32]

            desc_low = descricao.lower()
            tipo: str | None = None
            if "pix" in desc_low:
                tipo = "pix"
            elif "ted" in desc_low:
                tipo = "ted"
            elif "doc" in desc_low:
                tipo = "doc"

            transacoes.append(TransacaoImportada(
                fitid=fitid,
                data=data_tx,
                valor=valor,
                descricao=descricao,
                tipo=tipo,
            ))

            periodo_inicio = min(periodo_inicio, data_tx) if periodo_inicio else data_tx
            periodo_fim = max(periodo_fim, data_tx) if periodo_fim else data_tx

        except (InvalidOperation, ValueError) as exc:
            erros.append(f"Linha {linha_num} inválida: {exc}")
        except Exception as exc:
            erros.append(f"Linha {linha_num} erro inesperado: {exc}")

    return ResultadoImportacao(
        formato=FormatoOrigem.CSV,
        transacoes=transacoes,
        periodo_inicio=periodo_inicio,
        periodo_fim=periodo_fim,
        erros=erros,
    )
