"""Simple OFX parser — extracts STMTTRN entries from OFX/QFX files.

Does NOT depend on ofxparse. Parses the SGML-like OFX format directly
using regex, which is more reliable for the variety of bank-generated files.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


# Regex to find individual transaction blocks
_STMTTRN_RE = re.compile(
    r"<STMTTRN>(.*?)</STMTTRN>",
    re.DOTALL | re.IGNORECASE,
)

# Regex to extract tag values inside a transaction block
_TAG_RE = re.compile(r"<(\w+)>([^<\r\n]+)")

# Pix description cleanup patterns
_PIX_PATTERNS = [
    re.compile(r"PIX\s*[-/]\s*(.+?)\s*[-/]", re.IGNORECASE),
    re.compile(r"PAGAMENTO PIX\s+(.+)", re.IGNORECASE),
    re.compile(r"RECEBIDO PIX\s+(.+)", re.IGNORECASE),
    re.compile(r"PIX RECEBIDO\s*[-:]?\s*(.+)", re.IGNORECASE),
    re.compile(r"PIX ENVIADO\s*[-:]?\s*(.+)", re.IGNORECASE),
]


def _parse_ofx_date(raw: str) -> date:
    """Parse OFX date format YYYYMMDD or YYYYMMDDHHMMSS[.XXX:TZ]."""
    clean = raw.strip()[:8]
    return datetime.strptime(clean, "%Y%m%d").date()


def _clean_description(raw: str) -> str:
    """Normalize whitespace and try to extract meaningful name from Pix descriptions."""
    text = re.sub(r"\s+", " ", raw.strip())
    for pattern in _PIX_PATTERNS:
        m = pattern.search(text)
        if m:
            return m.group(1).strip()
    return text


def parse_ofx(content: str | bytes) -> list[dict[str, Any]]:
    """Parse OFX content and return list of transaction dicts.

    Each dict has keys: fitid, posted_at, amount, description_raw,
    description_clean, type.
    """
    if isinstance(content, bytes):
        # Try UTF-8 first, fall back to latin-1
        try:
            content = content.decode("utf-8")
        except UnicodeDecodeError:
            content = content.decode("latin-1")

    transactions: list[dict[str, Any]] = []

    for match in _STMTTRN_RE.finditer(content):
        block = match.group(1)
        tags: dict[str, str] = {}
        for tag_match in _TAG_RE.finditer(block):
            tags[tag_match.group(1).upper()] = tag_match.group(2).strip()

        fitid = tags.get("FITID", "")
        if not fitid:
            continue

        try:
            amount = Decimal(tags.get("TRNAMT", "0"))
        except InvalidOperation:
            continue

        try:
            posted_at = _parse_ofx_date(tags.get("DTPOSTED", ""))
        except (ValueError, IndexError):
            continue

        description_raw = tags.get("MEMO", tags.get("NAME", ""))
        description_clean = _clean_description(description_raw)
        trntype = tags.get("TRNTYPE", "other").lower()

        transactions.append({
            "fitid": fitid,
            "posted_at": posted_at,
            "amount": amount,
            "description_raw": description_raw,
            "description_clean": description_clean,
            "type": trntype,
        })

    return transactions


def compute_synthetic_fitid(posted_at: date, amount: Decimal, description: str) -> str:
    """Generate a deterministic FITID for PDF-imported transactions."""
    payload = f"{posted_at.isoformat()}|{amount}|{description}"
    return hashlib.sha256(payload.encode()).hexdigest()[:32]
