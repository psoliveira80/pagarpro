"""Whisper API adapter for audio transcription."""

from __future__ import annotations

import httpx
import structlog

from app.domain.ports.audio_transcriber import IAudioTranscriber, TranscriptionResult
from app.infrastructure.settings import get_settings

log = structlog.get_logger()


class WhisperApiAdapter:
    """Audio transcription via OpenAI Whisper API."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or getattr(get_settings(), "LLM_API_KEY", "")

    async def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/ogg",
        language: str = "pt-BR",
    ) -> TranscriptionResult:
        ext_map = {
            "audio/ogg": "ogg",
            "audio/mpeg": "mp3",
            "audio/mp3": "mp3",
            "audio/wav": "wav",
            "audio/webm": "webm",
            "audio/mp4": "m4a",
        }
        ext = ext_map.get(mime_type, "ogg")

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"file": (f"audio.{ext}", audio_bytes, mime_type)},
                data={
                    "model": "whisper-1",
                    "language": language.split("-")[0],  # pt-BR -> pt
                    "response_format": "verbose_json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        return TranscriptionResult(
            text=data.get("text", ""),
            confidence=1.0,
            duration_seconds=data.get("duration", 0.0),
            language=data.get("language", language),
        )


class ConsoleTranscriberAdapter:
    """Dev-mode audio transcription that returns placeholder text."""

    async def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/ogg",
        language: str = "pt-BR",
    ) -> TranscriptionResult:
        return TranscriptionResult(
            text="[DEV] Placeholder transcription for audio message",
            confidence=0.5,
            duration_seconds=0.0,
            language=language,
        )
