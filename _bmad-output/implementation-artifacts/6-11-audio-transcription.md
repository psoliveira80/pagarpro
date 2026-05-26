---
epic: 6
story: 11
title: "Audio Transcription for Agent Orchestrator"
type: "Core"
status: done
---

# Story 6.11: Audio Transcription for Agent Orchestrator

## User Story
As a User,
I want to send audio messages that the agent understands,
So that I can interact hands-free.

## Acceptance Criteria

1. `IAudioTranscriber` port defined in `app/domain/ports/audio_transcriber.py`.
2. `WhisperApiAdapter` (default) calls OpenAI Whisper API with language='pt-BR'.
3. `ConsoleTranscriberAdapter` for dev (returns placeholder text).
4. Inbound pipeline: when a WhatsApp message has audio, transcribe BEFORE passing to the Agent Orchestrator.
5. In-app chat: audio recording via browser MediaRecorder API, sent as blob, transcribed server-side.
6. Transcription result is stored alongside the message in `whatsapp_messages.transcription` (nullable TEXT field).

## Technical Context

### Architecture References
- **Architecture Section 2.4**: Hexagonal — transcription is a port with swappable adapters.
- **PRD FR-CORE-COB-2**: AI Agent with rich context; audio is another input modality.
- **Architecture Section 3.1**: External API adapters pattern.

### Files to Create/Modify
```
backend-api/
├── app/
│   ├── domain/
│   │   └── ports/
│   │       └── audio_transcriber.py            # IAudioTranscriber Protocol
│   ├── infrastructure/
│   │   └── adapters/
│   │       ├── whisper_api_adapter.py          # WhisperApiAdapter (OpenAI)
│   │       └── console_transcriber_adapter.py  # ConsoleTranscriberAdapter (dev)
│   ├── api/
│   │   └── v1/
│   │       └── transcription.py               # POST /api/v1/transcribe (for in-app audio)
│   └── tests/
│       ├── test_audio_transcriber.py
│       └── test_inbound_audio_pipeline.py
├── alembic/
│   └── versions/
│       └── xxxx_add_transcription_to_messages.py  # Add transcription column
frontend/
├── src/app/shared/components/
│   └── audio-recorder/
│       ├── audio-recorder.component.ts         # MediaRecorder wrapper
│       ├── audio-recorder.component.html
│       └── audio-recorder.component.css
```

### Dependencies
- Story 6.3 (inbound pipeline — webhook receiver where audio messages arrive)
- Story 6.10 (in-app chat — audio recording in browser)

### Technical Notes
- `IAudioTranscriber` Protocol methods: `transcribe(audio_bytes: bytes, mime_type: str, language: str = 'pt-BR') -> TranscriptionResult`.
- `TranscriptionResult` dataclass: `text: str`, `confidence: float`, `duration_seconds: float`, `language: str`.
- WhisperApiAdapter: POST to `https://api.openai.com/v1/audio/transcriptions` with model `whisper-1`.
- Supported audio formats: ogg/opus (WhatsApp default), webm (browser MediaRecorder), mp3, wav.
- Pipeline integration point: in the Celery worker for inbound messages, after media download and before agent turn, check if `media_mime` starts with `audio/` and run transcription.
- The transcription text replaces the message content for agent processing (agent sees text, not audio).
- Migration adds `transcription TEXT NULL` column to `whatsapp_messages` table.
- ConsoleTranscriberAdapter returns `"[DEV] Placeholder transcription for audio message"` for local development.
- Cost tracking: log Whisper API calls to `agent_runs` or a dedicated `transcription_runs` table for spend monitoring.
- Audio files are stored in MinIO regardless of transcription success (for retry/audit).

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] No regressions
