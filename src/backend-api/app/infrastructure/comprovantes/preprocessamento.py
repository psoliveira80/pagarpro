"""Pré-processamento de imagem antes do OCR (Story 13.19).

Comprovantes PIX vêm geralmente como print de tela do app do banco,
mandado pelo WhatsApp — com perda de qualidade pela compressão. Pré-processar
melhora drasticamente o resultado do Tesseract.

Etapas (em ordem):
1. Detectar e corrigir rotação (deskew) — usuário às vezes envia girado.
2. Converter pra escala de cinza.
3. Upscale 2x quando imagem pequena (melhora reconhecimento de texto pequeno).
4. Denoise (Non-local means).
5. Binarização adaptativa (texto preto em fundo branco).

Tudo via OpenCV — zero custo, zero dependência externa.
"""

from __future__ import annotations

import logging

import numpy as np


log = logging.getLogger(__name__)


def _cv2_disponivel() -> bool:
    try:
        import cv2  # noqa: F401
        return True
    except ImportError:
        return False


# Tamanho mínimo (lado maior) para considerar "imagem pequena" e fazer upscale.
LIMITE_UPSCALE_PX = 1200


def preprocessar_para_ocr(bytes_imagem: bytes) -> bytes | None:
    """Aplica pipeline de preprocessing e retorna PNG processado.

    Retorna `None` se OpenCV não está disponível (o caller pode usar a
    imagem original como fallback).
    """
    if not _cv2_disponivel():
        log.info("preprocess.skip: cv2 não disponível, usando imagem original")
        return None

    import cv2

    try:
        arr = np.frombuffer(bytes_imagem, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            log.warning("preprocess.imagem_invalida")
            return None

        # 1. Cinza
        cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 2. Deskew via momentos de Hu (eficiente em texto)
        cinza = _corrigir_rotacao(cinza)

        # 3. Upscale 2x quando lado maior < LIMITE_UPSCALE_PX
        h, w = cinza.shape
        if max(h, w) < LIMITE_UPSCALE_PX:
            cinza = cv2.resize(cinza, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)

        # 4. Denoise — Non-local means é caro mas dá melhor qualidade
        cinza = cv2.fastNlMeansDenoising(cinza, h=10)

        # 5. Binarização adaptativa — robusta a iluminação irregular
        binarizada = cv2.adaptiveThreshold(
            cinza,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=11,
            C=2,
        )

        # Encode como PNG (sem perda)
        ok, buf = cv2.imencode(".png", binarizada)
        if not ok:
            return None
        return buf.tobytes()

    except Exception as exc:
        log.warning(f"preprocess.erro: {exc}")
        return None


def _corrigir_rotacao(img_cinza):
    """Detecta inclinação do texto e rotaciona pra alinhar horizontal.

    Usa coordenadas dos pixels escuros (texto) para calcular ângulo médio
    via PCA. Funciona bem em texto impresso de comprovantes.
    """
    import cv2

    try:
        # Inverte pra texto virar branco em fundo preto
        thresh = cv2.threshold(
            img_cinza, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU
        )[1]
        coords = np.column_stack(np.where(thresh > 0))
        if coords.size < 10:
            return img_cinza

        angle = cv2.minAreaRect(coords)[-1]
        # Ajuste do ângulo retornado pelo OpenCV
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        # Só rotaciona se ângulo é significativo (> 0.5°)
        if abs(angle) < 0.5:
            return img_cinza

        (h, w) = img_cinza.shape
        M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
        rotacionada = cv2.warpAffine(
            img_cinza, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
        return rotacionada
    except Exception as exc:
        log.warning(f"preprocess.deskew_falhou: {exc}")
        return img_cinza
