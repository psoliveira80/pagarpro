---
epic: 11
story: 6
title: "Tratamento de Áudio por Modo de Operação"
type: "Core"
status: ready-for-dev
---

# Story 11.6: Tratamento de Áudio por Modo de Operação

## História de Usuário
Como Cliente,
quero que minhas mensagens de voz sejam ou transcritas (quando a IA está ligada) ou defletidas com um menu amigável (quando a IA está desligada),
para que eu sempre receba uma resposta e a empresa tenha custo previsível.

## Critérios de Aceite

1. Pipeline de áudio de entrada (estende a Story 6.11 — Transcrição de Áudio) verifica `OperationModeService.is_allowed('audio_transcription', tenant_id)` antes de chamar Whisper/equivalente.
2. **ia-full**: transcreve com Whisper → texto cai no pipeline normal de entrada (LLM conversacional pode responder livremente)
3. **ia-eco**: transcreve com Whisper → texto cai no pipeline ia-eco normal (`IntentMatcher` primeiro, classifier LLM se 'unknown')
4. **ia-zero**: NÃO transcreve. Envia template configurável `audio_deflection_template`:
   - Body default: "Olá! No momento estamos atendendo apenas mensagens escritas. Por favor, digite sua mensagem ou escolha uma das opções abaixo:"
   - Imediatamente em seguida, envia `interactive_menu` `main_menu` (Story 11.3)
5. Conversa em `ia-zero` que recebe áudio fica com flag `last_audio_deflected_at`. Se o cliente mandar 3 áudios em sequência sem responder, marca a conversation com `status='needs-attention'` (gestor vê no inbox).
6. Estatística por modo: contador Prometheus `audio_messages_received_total{mode}` e `audio_messages_transcribed_total{mode}`. Diferença em ia-zero = áudios defletidos.
7. Mudanças no backend:
   - `handle_inbound_audio.py` — wrapper que decide entre transcrever ou defletir
   - `send_audio_deflection.py` — envia template + menu
8. Template padrão `audio_deflection_template` seedado em `message_templates` (Story 10.4) — gestor pode editar texto/tom.
9. Impacto no frontend:
   - No inbox (Story 6.7), áudios defletidos aparecem como balão de áudio do cliente + balão de bot com texto "🤖 Áudio defletido (modo IA Zero)" + link "Ouvir mesmo assim" (gestor pode ouvir/transcrever manualmente clicando)
   - "Ouvir mesmo assim" dispara o endpoint `POST /api/v1/messages/{id}/transcribe-manual` (consome do orçamento de tokens mesmo em ia-zero, mas é ação consciente do gestor)
10. Configurações → IA & WhatsApp → Áudio: toggle `transcribe_in_eco_mode` (default ON, gestor pode desligar para economizar mais), preview do template de deflexão.
11. Testes:
    - Cada modo dispara o branch correto (mocks de Whisper, gateway)
    - 3 áudios consecutivos em ia-zero promove a conversation para needs-attention
    - "Ouvir mesmo assim" funciona e debita tokens corretamente

## Contexto Técnico

### Referências de Arquitetura
- Construído em cima da Story 6.11 (Transcrição de Áudio — pipeline original)
- Usa `OperationModeService` (Story 11.2)
- Usa `MenuRenderer` para disparar `main_menu` (Story 11.3)
- Usa `message_templates` (Story 10.4)

### Arquivos a Criar/Modificar
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

### Dependências
- Story 6.11 (pipeline de Transcrição de Áudio)
- Story 11.2 (OperationModeService)
- Story 11.3 (Menu Interativo — reuso do `main_menu`)
- Story 10.4 (Message Templates)

### Notas Técnicas
- **Custo do Whisper**: ~$0.006/min de áudio com OpenAI; provider configurável. Rastreamento em `agent_runs.cost_usd` com `category='audio_transcription'`.
- **Limite de duração de áudio**: mensagens >5min são defletidas mesmo em ia-full (custo desproporcional). Configurável em `system_settings.max_audio_seconds`.
- **Transcrição manual é audit-loggada**: gestor que escolhe transcrever gera log com motivo (input opcional no modal).
- **Não bloquear o inbound**: a deflexão é fire-and-forget Celery, não bloqueia a resposta do webhook

## Checklist do Dev
- [ ] Todos os critérios de aceite atendidos
- [ ] Testes escritos e passando
- [ ] Sem regressões
- [ ] Code review (`bmad-code-review`) executado e aprovado
