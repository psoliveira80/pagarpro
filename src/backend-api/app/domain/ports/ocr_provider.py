"""Port for OCR providers."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class IOcrProvider(Protocol):
    """Interface for OCR text extraction from images."""

    async def extract_text(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        """Extract text from an image.

        Args:
            image_bytes: Raw image data.
            mime_type: MIME type of the image.

        Returns:
            Extracted text string.
        """
        ...
