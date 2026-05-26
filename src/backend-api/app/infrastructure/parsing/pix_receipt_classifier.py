"""Heuristic classifier and extractor for Pix receipt images/PDFs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass
class PixReceiptData:
    """Extracted data from a Pix receipt."""

    is_receipt: bool = False
    confidence: float = 0.0
    amount: Decimal | None = None
    transaction_id: str | None = None
    date_str: str | None = None
    bank_name: str | None = None


# Patterns indicating a Pix receipt
PIX_PATTERNS = [
    r"comprovante\s+de\s+pag",
    r"comprovante\s+pix",
    r"transfer[eê]ncia\s+pix",
    r"pix\s+enviado",
    r"pix\s+recebido",
    r"chave\s+pix",
    r"e2e\s*id",
    r"end\s*to\s*end",
    r"identificador\s+da\s+transa",
    r"comprovante\s+de\s+transfer",
]

# Amount patterns (R$ 1.234,56 or R$ 1234.56)
AMOUNT_PATTERNS = [
    r"R\$\s*([\d.]+,\d{2})",
    r"valor[:\s]+R?\$?\s*([\d.]+,\d{2})",
    r"valor\s+da\s+transfer[eê]ncia[:\s]+R?\$?\s*([\d.]+,\d{2})",
]

# Transaction ID patterns
TXN_ID_PATTERNS = [
    r"E2E\s*(?:ID)?[:\s]+([A-Za-z0-9]+)",
    r"end\s*to\s*end[:\s]+([A-Za-z0-9]+)",
    r"identificador[:\s]+([A-Za-z0-9]+)",
    r"NSU[:\s]+(\d+)",
    r"c[oó]digo\s+da\s+transa[cç][aã]o[:\s]+([A-Za-z0-9]+)",
]

# Date patterns
DATE_PATTERNS = [
    r"(\d{2}/\d{2}/\d{4})",
    r"(\d{2}\.\d{2}\.\d{4})",
    r"(\d{4}-\d{2}-\d{2})",
]

# Bank names
BANK_NAMES = [
    "banco do brasil", "bb", "itau", "itaú", "bradesco", "santander",
    "caixa", "nubank", "inter", "c6 bank", "mercado pago", "picpay",
    "pagbank", "pagseguro", "sicoob", "sicredi", "banrisul", "original",
    "neon", "next", "will bank",
]


def classify_receipt(ocr_text: str) -> PixReceiptData:
    """Classify OCR text as a Pix receipt and extract structured data.

    Args:
        ocr_text: Text extracted from an image or PDF via OCR.

    Returns:
        PixReceiptData with classification result and extracted fields.
    """
    text_lower = ocr_text.lower()

    # Count Pix pattern matches
    matches = sum(
        1 for pattern in PIX_PATTERNS if re.search(pattern, text_lower)
    )

    is_receipt = matches >= 2
    confidence = min(1.0, matches / 3.0)

    if not is_receipt:
        return PixReceiptData(is_receipt=False, confidence=confidence)

    # Extract amount (search original text since R$ is case-sensitive)
    amount = None
    for pattern in AMOUNT_PATTERNS:
        match = re.search(pattern, ocr_text, re.IGNORECASE)
        if match:
            raw = match.group(1).replace(".", "").replace(",", ".")
            try:
                amount = Decimal(raw)
            except InvalidOperation:
                pass
            break

    # Extract transaction ID
    transaction_id = None
    for pattern in TXN_ID_PATTERNS:
        match = re.search(pattern, ocr_text, re.IGNORECASE)
        if match:
            transaction_id = match.group(1).strip()
            break

    # Extract date
    date_str = None
    for pattern in DATE_PATTERNS:
        match = re.search(pattern, ocr_text)
        if match:
            date_str = match.group(1)
            break

    # Detect bank name
    bank_name = None
    for bank in BANK_NAMES:
        if bank in text_lower:
            bank_name = bank.title()
            break

    return PixReceiptData(
        is_receipt=True,
        confidence=confidence,
        amount=amount,
        transaction_id=transaction_id,
        date_str=date_str,
        bank_name=bank_name,
    )
