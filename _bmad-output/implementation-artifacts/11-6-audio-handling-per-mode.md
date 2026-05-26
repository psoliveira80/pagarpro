---
epic: 11
story: 6
title: "Audio Handling Per Operation Mode"
type: "Core"
status: ready-for-dev
---

# Story 11.6: Audio Handling Per Operation Mode

## User Story
As a Customer,
I want my voice messages to either be transcribed (when IA is on) or deflected with a friendly menu (when IA is off),
So that I always get a response and the company has predictable cost.

## Acceptance Criteria

1. Inbound audio pipeline (extends Story 6.11 — Audio Transcription) checks `OperationModeService.is_allowed('audio_transcription', tenant_id)` antes de chamar Whisper/equivalente.
2. **ia-full**: transcreve com Whisper → texto cai em pipeline normal de inbound (LLM conversacional pode responder livremente)
3. **ia-eco**: transcreve com Whisper → texto cai em pipeline ia-eco normal (`IntentMatcher` primeiro, LLM classifier se unknown)
4. **ia-zero**: NÃO transcreve. Envia template configurável `audio_deflection_template`:
   - Default body: "Olá! No momento estamos atendendo apenas mensagens escritas. Por favor, digite sua mensagem ou escolha uma das opções abaixo:"
   - Imediatamente após, envia `interactive_menu` `main_menu` (Story 11.3)
5. Conversa em `ia-zero` que recebe áudio fica com flag `last_audio_deflected_at`. Se cliente mandar 3 áudios em sequência sem responder, marca conversation com `status='needs-attention'` (gestor vê no inbox).
6. Estatística por modo: contador Prometheus `audio_messages_received_total{mode}` e `audio_messages_transcribed_total{mode}`. Diferença em ia-zero = áudios defletidos.
7. Backend changes:
   - `handle_inbound_audio.py` — wrapper que decide transcrever vs defletir
   - `send_audio_deflection.py` — envia template + menu
8. Template padrão `audio_deflection_template` seedado em `message_templates` (Story 10.4) — gestor pode editar texto/tone.
9. Frontend impact:
   - No inbox (Story 6.7), áudios defletidos aparecem como balão de áudio do cliente + balão de bot com texto "🤖 Áudio defletido (modo IA Zero)" + link "Ouvir mesmo assim" (gestor pode ouvir/transcrever manualmente clicando)
   - "Ouvir mesmo assim" dispara endpoint `POST /api/v1/messages/{id}/transcribe-manual` (cobra do budget de tokens mesmo em ia-zero, mas é ação consciente do gestor)
10. Settings → IA & WhatsApp → Áudio: toggle `transcribe_in_eco_mode` (default ON, gestor pode desligar para economizar mais), preview do template de deflexão.
11. Tests:
    - Cada modo dispara o branch correto (mocks de Whisper, gateway)
    - 3 áudios consecutivos em ia-zero promove conversation para needs-attention
    - "Ouvir mesmo assim" funciona e debita tokens corretamente

## Technical Context

### Architecture References
- Builds on Story 6.11 (Audio Transcription — pipeline original)
- Usa `OperationModeService` (Story 11.2)
- Usa `MenuRenderer` para dispara `main_menu` (Story 11.3)
- Usa `message_templates` (Story 10.4)

### Files to Create/Modify
```
backend-api/
├── app/application/audio/
│   ├── handle_inbound_audio.py          # decide transcribe vs deflect
│   └── send_audio_deflection.py
├── app/api/v1/message_routes.py         # add /messages/{id}/transcribe-manual
├── alembic/versions/xxxx_seed_audio_deflection_template.py
frontend/
├── src/app/features/inbox/components/chat-message/audio-deflected-bubble.component.ts/.html/.css
└── src/app/features/settings/ai-whatsapp/audio-settings.component.ts/.html/.css
```

### Dependencies
- Story 6.11 (Audio Transcription pipeline)
- Story 11.2 (OperationModeService)
- Story 11.3 (Interactive Menu — main_menu reuso)
- Story 10.4 (Message Templates)

### Technical Notes
- **Custo Whisper**: ~$0.006/min de áudio com OpenAI; provider configurável. Tracking em `agent_runs.cost_usd` com category='audio_transcription'.
- **Limite audio length**: mensagens >5min defletidas mesmo em ia-full (custo desproporcional). Configurável `system_settings.max_audio_seconds`.
- **Manual transcribe é audit-loggado**: gestor que escolhe transcrever gera log com motivo (opcional input no modal).
- **Não bloquear inbound**: deflexão é fire-and-forget Celery, não bloqueia webhook response

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] No regressions
- [ ] Code review (`bmad-code-review`) executed and approved
