"""Rasterizador de PDF para imagens — fallback pra PDFs escaneados.

Quando `pdf_text_extractor` devolve `None` (PDF é imagem dentro de PDF,
sem texto extraível), este módulo rasteriza página-a-página pra PNG e
devolve a lista de bytes, que o caller joga no Tesseract da camada 3.

**Filosofia:** complementar, leve, sem trocar o motor.
`pdf2image` é wrapper de `poppler-utils` (já no Debian; ~5MB extra).
Zero modelo baixado, zero GPU. Resolve o gap B4 da auditoria 2026-05-29.

**Fallback gracioso:** se `pdf2image` ou `poppler` não estiverem
instalados, retorna `None` — pipeline segue, comprovante vai pra
homologação manual.
"""

from __future__ import annotations

import io
import logging


log = logging.getLogger(__name__)


DPI_RASTERIZACAO = 200  # boa qualidade pra Tesseract sem inflar imagem demais
MAX_PAGINAS = 5  # comprovante de banco quase sempre tem 1, no máximo 2


def _pdf2image_disponivel() -> bool:
    try:
        import pdf2image  # noqa: F401
        return True
    except ImportError:
        return False


def rasterizar_pdf(bytes_pdf: bytes) -> list[bytes] | None:
    """Converte cada página do PDF em PNG.

    Returns:
        Lista de bytes PNG (uma entrada por página, no máximo `MAX_PAGINAS`).
        `None` se `pdf2image`/`poppler` indisponíveis ou rasterização falha.
    """
    if not _pdf2image_disponivel():
        log.info("pdf_rasterizer.skip: pdf2image não disponível")
        return None

    from pdf2image import convert_from_bytes

    try:
        paginas_pil = convert_from_bytes(
            bytes_pdf,
            dpi=DPI_RASTERIZACAO,
            fmt="png",
            last_page=MAX_PAGINAS,
        )
    except Exception as exc:
        log.warning(f"pdf_rasterizer.falhou: {exc}")
        return None

    paginas_bytes: list[bytes] = []
    for img in paginas_pil:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        paginas_bytes.append(buf.getvalue())
    return paginas_bytes
