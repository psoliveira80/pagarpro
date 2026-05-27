"""Camada 2 do pipeline (Story 13.19) — PDF textual.

Quando o cliente envia um PDF gerado pelo app do banco (texto extraível),
usamos `pdfplumber` para puxar o texto direto, **sem OCR**. Qualidade
perfeita, velocidade alta.

Detecção automática: se o PDF tem ≥ 50 caracteres extraíveis por página,
consideramos "textual" — caso contrário (PDF escaneado), delegamos para
a camada 3 (OCR).

**Confiança base: 0.85** quando extrai com sucesso. Menor que BR Code
porque depende de qualidade do parsing textual + regex universal.

**Fallback gracioso:** se pdfplumber não disponível, retorna `None`.
"""

from __future__ import annotations

import io
import logging


log = logging.getLogger(__name__)


CONFIANCA_BASE = 0.85
LIMITE_CHARS_PARA_CONSIDERAR_TEXTUAL = 50


def _pdfplumber_disponivel() -> bool:
    try:
        import pdfplumber  # noqa: F401
        return True
    except ImportError:
        return False


def extrair_texto_pdf(bytes_pdf: bytes) -> tuple[str, float] | None:
    """Tenta extrair texto de um PDF.

    Args:
        bytes_pdf: conteúdo binário do PDF.

    Returns:
        Tuple `(texto, confianca_base)` se PDF é textual (extração bem-sucedida).
        `None` se PDF é escaneado (pouco texto extraível — delegar pra OCR) ou
        pdfplumber não disponível.

    Nota: o caller chama `extratores_universais` em cima do `texto`
    para extrair valor/data/CNPJ/etc.
    """
    if not _pdfplumber_disponivel():
        log.info("pdf_texto.skip: pdfplumber não disponível")
        return None

    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(bytes_pdf)) as pdf:
            paginas_texto = []
            total_chars = 0
            for page in pdf.pages:
                texto = page.extract_text() or ""
                paginas_texto.append(texto)
                total_chars += len(texto.strip())

            # Se a média de chars por página é baixa, PDF é escaneado
            avg_chars = total_chars / max(len(pdf.pages), 1)
            if avg_chars < LIMITE_CHARS_PARA_CONSIDERAR_TEXTUAL:
                log.info(
                    f"pdf_texto.parece_escaneado: avg_chars={avg_chars:.0f} "
                    f"em {len(pdf.pages)} páginas → delegando pra OCR"
                )
                return None

            texto_completo = "\n".join(paginas_texto)
            return texto_completo, CONFIANCA_BASE

    except Exception as exc:
        log.warning(f"pdf_texto.extracao_falhou: {exc}")
        return None
