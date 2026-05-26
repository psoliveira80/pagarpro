"""Regex parser for Pix receipt text.

Extracts common fields from OCR'd Pix receipt text.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation


def parse_pix_receipt(text: str) -> dict:
    """Parse OCR'd Pix receipt text and extract structured data.

    Returns a dict with: valor, data, pagador, beneficiario, txid.
    Missing fields are None.
    """
    result: dict = {
        "valor": None,
        "data": None,
        "pagador": None,
        "beneficiario": None,
        "txid": None,
    }

    # Valor: R$ 1.234,56 or R$1234.56
    valor_match = re.search(
        r"(?:valor|value|total)[:\s]*R?\$?\s*([\d.,]+)",
        text,
        re.IGNORECASE,
    )
    if valor_match:
        raw = valor_match.group(1).strip()
        # Brazilian format: 1.234,56 -> 1234.56
        if "," in raw:
            raw = raw.replace(".", "").replace(",", ".")
        try:
            result["valor"] = Decimal(raw)
        except InvalidOperation:
            pass

    # Data: DD/MM/YYYY or YYYY-MM-DD
    data_match = re.search(
        r"(?:data|date)[:\s]*(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})",
        text,
        re.IGNORECASE,
    )
    if data_match:
        result["data"] = data_match.group(1)

    # Pagador
    pagador_match = re.search(
        r"(?:pagador|payer|de|origin)[:\s]*([^\n]+)",
        text,
        re.IGNORECASE,
    )
    if pagador_match:
        result["pagador"] = pagador_match.group(1).strip()

    # Beneficiario
    beneficiario_match = re.search(
        r"(?:benefici[aá]rio|recebedor|receiver|para|destination)[:\s]*([^\n]+)",
        text,
        re.IGNORECASE,
    )
    if beneficiario_match:
        result["beneficiario"] = beneficiario_match.group(1).strip()

    # TxID / E2E ID
    txid_match = re.search(
        r"(?:txid|id\s*(?:da\s*)?transa[cç][aã]o|e2e|end.to.end)[:\s]*([A-Za-z0-9]+)",
        text,
        re.IGNORECASE,
    )
    if txid_match:
        result["txid"] = txid_match.group(1).strip()

    return result
