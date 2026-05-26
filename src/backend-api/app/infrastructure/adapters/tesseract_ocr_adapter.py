"""Tesseract OCR adapter — stub implementation.

Tesseract is configured in Docker but actual OCR processing is deferred.
This adapter satisfies the IOcrProvider interface with a no-op return.
"""

from __future__ import annotations

import structlog

log = structlog.get_logger()


class TesseractOcrAdapter:
    """Stub OCR adapter that returns empty text."""

    async def extract_text(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        """Return empty string — actual OCR integration deferred."""
        log.info(
            "tesseract_ocr_stub_called",
            image_size=len(image_bytes),
            mime_type=mime_type,
        )
        return ""
