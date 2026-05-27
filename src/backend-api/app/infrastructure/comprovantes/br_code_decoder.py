"""Camada 1 do pipeline de análise (Story 13.19) — BR Code (QR Code do PIX).

BR Code é o padrão EMV-MPM do BACEN. Decodifica o payload do QR estampado
no comprovante e extrai valor, chave PIX, beneficiário e txid sem
nenhum OCR.

**Confiança base: 0.95** quando decodifica com sucesso — é a fonte mais
confiável porque o payload é assinado/estruturado pelo emissor original
(banco do pagador) e independe da qualidade da imagem.

**Fallback gracioso:** se `pyzbar` ou `libzbar0` não estão disponíveis no
ambiente, retorna `None` em vez de falhar — o orquestrador segue pra
camada 2.
"""

from __future__ import annotations

import io
import logging
import re
from decimal import Decimal, InvalidOperation

from PIL import Image

from app.domain.finance.comprovante import EntidadesExtraidas, MetodoAnalise


log = logging.getLogger(__name__)


# Confiança base da camada — só BR Code decodificado vale isso.
CONFIANCA_BASE = 0.95


def _pyzbar_disponivel() -> bool:
    try:
        from pyzbar import pyzbar  # noqa: F401
        return True
    except ImportError:
        return False


def decodificar_br_code(bytes_imagem: bytes) -> tuple[EntidadesExtraidas, float] | None:
    """Tenta decodificar BR Code numa imagem.

    Args:
        bytes_imagem: conteúdo binário da imagem (PNG, JPG, etc.)

    Returns:
        Tuple `(entidades, score)` quando BR Code é encontrado e decodificado.
        `None` quando:
        - pyzbar/libzbar0 não estão disponíveis
        - nenhum QR code na imagem
        - QR code não é BR Code válido
    """
    if not _pyzbar_disponivel():
        log.info("br_code.skip: pyzbar/libzbar0 não disponíveis")
        return None

    from pyzbar import pyzbar

    try:
        img = Image.open(io.BytesIO(bytes_imagem))
    except Exception as exc:
        log.warning(f"br_code.imagem_invalida: {exc}")
        return None

    # Decodifica todos os QR codes da imagem (alguns comprovantes têm 2+)
    try:
        codigos = pyzbar.decode(img)
    except Exception as exc:
        log.warning(f"br_code.decode_falhou: {exc}")
        return None

    for codigo in codigos:
        if codigo.type != "QRCODE":
            continue
        try:
            payload = codigo.data.decode("utf-8", errors="ignore")
        except Exception:
            continue

        entidades = _parse_payload_emv(payload)
        if entidades is not None:
            return entidades, CONFIANCA_BASE

    return None


def _parse_payload_emv(payload: str) -> EntidadesExtraidas | None:
    """Parse mínimo do payload EMV-MPM do BR Code.

    Formato: TLV (Tag-Length-Value), cada campo `IDII LL VVVVV...`:
    - `00`: Payload Format Indicator
    - `01`: Point of Initiation Method
    - `26`/`28`/etc.: Merchant Account (PIX dentro)
    - `52`: Merchant Category Code
    - `53`: Transaction Currency (986 = BRL)
    - `54`: Transaction Amount (valor da transação)
    - `58`: Country Code
    - `59`: Merchant Name (beneficiário)
    - `60`: Merchant City
    - `62`: Additional Data Field Template (txid dentro como subcampo `05`)
    - `63`: CRC16

    Implementação tolerante: se payload não bate com EMV, retorna None.
    """
    if not payload or len(payload) < 20:
        return None

    # Cheap sanity check: payload BR Code começa com "0002" (PFI = 01) ou "000201"
    if not re.match(r"^00\d{2}", payload):
        return None

    campos: dict[str, str] = {}
    i = 0
    try:
        while i < len(payload):
            tag = payload[i : i + 2]
            length = int(payload[i + 2 : i + 4])
            value = payload[i + 4 : i + 4 + length]
            campos[tag] = value
            i += 4 + length
            if len(campos) > 50:  # sanity break — payload mal-formado
                break
    except (ValueError, IndexError):
        return None

    # Valida que tem ao menos os tags obrigatórios do EMV-MPM
    if "00" not in campos or "53" not in campos:
        return None

    # Extrai valor (tag 54). Formato decimal "1234.56".
    valor: Decimal | None = None
    if "54" in campos:
        try:
            valor = Decimal(campos["54"])
        except (InvalidOperation, ValueError):
            valor = None

    # Beneficiário (tag 59 — nome do merchant)
    beneficiario_nome = campos.get("59")

    # Extrai chave PIX do Merchant Account (tag 26 ou 28).
    # Subcampos do 26: 00 = GUI ("BR.GOV.BCB.PIX"), 01 = chave PIX, 02 = info extra.
    chave_pix: str | None = None
    txid: str | None = None
    for tag_merchant in ("26", "27", "28", "29", "30"):
        if tag_merchant not in campos:
            continue
        merchant_payload = campos[tag_merchant]
        subcampos = _parse_subcampos(merchant_payload)
        if "01" in subcampos and "00" in subcampos:
            # PIX se GUI é BR.GOV.BCB.PIX
            if "BR.GOV.BCB.PIX" in subcampos["00"].upper():
                chave_pix = subcampos["01"]

    # txid no Additional Data Field (tag 62, subcampo 05)
    if "62" in campos:
        sub62 = _parse_subcampos(campos["62"])
        txid = sub62.get("05")

    if valor is None and chave_pix is None:
        # BR Code "vazio" — não tem nada útil pra nós
        return None

    return EntidadesExtraidas(
        valor=valor,
        chave_pix=chave_pix,
        pix_txid=txid,
        beneficiario_nome=beneficiario_nome,
        textos_brutos=[payload],
    )


def _parse_subcampos(payload: str) -> dict[str, str]:
    """Parse TLV de subcampos (mesmo formato dos campos top-level)."""
    out: dict[str, str] = {}
    i = 0
    try:
        while i < len(payload):
            tag = payload[i : i + 2]
            length = int(payload[i + 2 : i + 4])
            value = payload[i + 4 : i + 4 + length]
            out[tag] = value
            i += 4 + length
            if len(out) > 30:
                break
    except (ValueError, IndexError):
        pass
    return out
