"""Camada 3 do pipeline — OCR (Story 13.19).

**Engine padrão:** Tesseract 5 com idioma `por` (português brasileiro)
+ preprocessing via OpenCV. Leve (~30MB total), instala em segundos,
qualidade boa para imagens limpas de comprovantes de banco.

**Engine premium (upgrade futuro):** PaddleOCR — modelo de deep learning
(~600MB), qualidade superior em imagens muito comprimidas/borradas.
Pode ser ligada por configuração quando volume justificar.

**Fallback se nada disponível:** retorna `None` graciosamente — o
orquestrador segue sem texto OCR e marca o comprovante como "análise
incompleta" pra revisão manual.
"""

from __future__ import annotations

import io
import logging

from app.infrastructure.comprovantes.preprocessamento import preprocessar_para_ocr


log = logging.getLogger(__name__)


CONFIANCA_BASE = 0.65


def _tesseract_disponivel() -> bool:
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _paddleocr_disponivel() -> bool:
    try:
        from paddleocr import PaddleOCR  # noqa: F401
        return True
    except ImportError:
        return False


def extrair_texto_via_ocr(bytes_imagem: bytes) -> tuple[str, float] | None:
    """Tenta extrair texto via OCR. Estratégia em camadas:

    1. PaddleOCR se disponível (qualidade premium, opt-in via instalação).
    2. Tesseract+OpenCV (padrão).
    3. None se nada disponível.

    Returns:
        `(texto_extraído, confianca_base)` ou `None`.
    """
    if _paddleocr_disponivel():
        result = _ocr_paddle(bytes_imagem)
        if result is not None:
            return result, CONFIANCA_BASE + 0.10  # boost por engine premium

    if _tesseract_disponivel():
        result = _ocr_tesseract(bytes_imagem)
        if result is not None:
            return result, CONFIANCA_BASE

    log.warning("ocr.indisponivel: nenhuma engine de OCR funcional")
    return None


def _ocr_tesseract(bytes_imagem: bytes) -> str | None:
    """Tesseract com preprocessing OpenCV + idioma português."""
    import pytesseract
    from PIL import Image

    try:
        # Tenta preprocessing — se não disponível, usa imagem original
        bytes_processados = preprocessar_para_ocr(bytes_imagem) or bytes_imagem
        img = Image.open(io.BytesIO(bytes_processados))

        # Idioma portugês + config para layout misto (texto + dados estruturados)
        # PSM 6 = bloco uniforme de texto (bom para comprovantes)
        texto = pytesseract.image_to_string(
            img,
            lang="por",
            config="--psm 6",
        )
        return texto if texto.strip() else None
    except Exception as exc:
        log.warning(f"ocr_tesseract.falhou: {exc}")
        return None


def _ocr_paddle(bytes_imagem: bytes) -> str | None:
    """PaddleOCR — só roda se a lib estiver instalada (opt-in)."""
    try:
        import numpy as np
        from paddleocr import PaddleOCR
        from PIL import Image

        # PaddleOCR é caro de instanciar (carrega modelos) — cache global
        global _PADDLE_OCR_CACHE
        if "_PADDLE_OCR_CACHE" not in globals():
            _PADDLE_OCR_CACHE = PaddleOCR(use_angle_cls=True, lang="pt")
        ocr = _PADDLE_OCR_CACHE

        img = np.array(Image.open(io.BytesIO(bytes_imagem)))
        result = ocr.ocr(img)
        linhas: list[str] = []
        for box_lista in result:
            for box in box_lista:
                texto = box[1][0]
                if texto:
                    linhas.append(texto)
        return "\n".join(linhas) if linhas else None
    except Exception as exc:
        log.warning(f"ocr_paddle.falhou: {exc}")
        return None
