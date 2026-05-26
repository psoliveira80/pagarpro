"""Port for audio transcription providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class TranscriptionResult:
    """Result from audio transcription."""

    text: str
    confidence: float = 1.0
    duration_seconds: float = 0.0
    language: str = "pt-BR"


@runtime_checkable
class IAudioTranscriber(Protocol):
    """Interface for audio transcription adapters."""

    async def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/ogg",
        language: str = "pt-BR",
    ) -> TranscriptionResult:
        """Transcribe audio bytes to text."""
        ...
