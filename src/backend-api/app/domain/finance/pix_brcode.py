"""Pix BR Code (EMV) generator.

Generates a static Pix BR Code string following the EMV QR Code specification
for Pix payments in Brazil.
"""

from __future__ import annotations

from decimal import Decimal


def _crc16_ccitt(data: str) -> str:
    """Compute CRC-16/CCITT-FALSE for EMV QR Code."""
    crc = 0xFFFF
    for byte in data.encode("ascii"):
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return f"{crc:04X}"


def _tlv(tag: str, value: str) -> str:
    """Build a TLV (Tag-Length-Value) field."""
    return f"{tag}{len(value):02d}{value}"


def generate_pix_brcode(
    chave: str,
    nome: str,
    cidade: str,
    valor: Decimal | None = None,
    txid: str = "***",
) -> str:
    """Generate a static Pix BR Code string (EMV format).

    Args:
        chave: Pix key (CPF, CNPJ, email, phone, or random key).
        nome: Merchant name (max 25 chars).
        cidade: Merchant city (max 15 chars).
        valor: Transaction amount (optional for static codes).
        txid: Transaction ID (max 25 chars).

    Returns:
        Complete EMV BR Code string with CRC-16.
    """
    # Payload Format Indicator
    payload = _tlv("00", "01")

    # Merchant Account Information (GUI + key)
    gui = _tlv("00", "br.gov.bcb.pix")
    key = _tlv("01", chave)
    mai = _tlv("26", gui + key)
    payload += mai

    # Merchant Category Code
    payload += _tlv("52", "0000")

    # Transaction Currency (986 = BRL)
    payload += _tlv("53", "986")

    # Transaction Amount
    if valor is not None and valor > 0:
        payload += _tlv("54", f"{valor:.2f}")

    # Country Code
    payload += _tlv("58", "BR")

    # Merchant Name (truncate to 25)
    payload += _tlv("59", nome[:25])

    # Merchant City (truncate to 15)
    payload += _tlv("60", cidade[:15])

    # Additional Data Field Template (txid)
    additional = _tlv("05", txid[:25])
    payload += _tlv("62", additional)

    # CRC placeholder — tag 63, length 04, value computed over entire string
    payload += "6304"
    crc = _crc16_ccitt(payload)
    payload += crc

    return payload
