"""PDF bank statement parser — stub implementation.

In production this would use pdfplumber with per-bank heuristics.
For now it extracts text and applies basic regex patterns to find transactions.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

# Basic transaction line pattern: DD/MM/YYYY  description  value
_TX_LINE_RE = re.compile(
    r"(\d{2}/\d{2}/\d{4})\s+(.+?)\s+([-]?\d[\d.,]*)\s*$",
    re.MULTILINE,
)


def parse_pdf_text(text_content: str) -> tuple[list[dict[str, Any]], float]:
    """Parse raw text extracted from PDF.

    Returns (transactions, confidence).
    confidence = ratio of lines that matched transaction pattern.
    """
    lines = [l.strip() for l in text_content.split("\n") if l.strip()]
    total_data_lines = max(len(lines) - 5, 1)  # subtract header lines estimate

    transactions: list[dict[str, Any]] = []
    for m in _TX_LINE_RE.finditer(text_content):
        try:
            posted_at = datetime.strptime(m.group(1), "%d/%m/%Y").date()
        except ValueError:
            continue

        raw_amount = m.group(3).replace(".", "").replace(",", ".")
        try:
            amount = Decimal(raw_amount)
        except InvalidOperation:
            continue

        description_raw = m.group(2).strip()
        payload = f"{posted_at.isoformat()}|{amount}|{description_raw}"
        fitid = hashlib.sha256(payload.encode()).hexdigest()[:32]

        transactions.append({
            "fitid": fitid,
            "posted_at": posted_at,
            "amount": amount,
            "description_raw": description_raw,
            "description_clean": re.sub(r"\s+", " ", description_raw),
            "type": "credit" if amount > 0 else "debit",
        })

    confidence = len(transactions) / total_data_lines if total_data_lines > 0 else 0.0
    confidence = min(confidence, 1.0)

    return transactions, confidence


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF file. Uses pdfplumber if available, otherwise returns empty."""
    try:
        import pdfplumber
        import io
        text_parts: list[str] = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts)
    except ImportError:
        # pdfplumber not installed — return empty so caller can handle
        return ""
    except Exception:
        return ""
