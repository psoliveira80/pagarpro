---
epic: 11
story: 2
title: "Operation Modes: ia-full / ia-eco / ia-zero"
type: "Core"
status: ready-for-dev
---

# Story 11.2: Operation Modes (ia-full / ia-eco / ia-zero)

## User Story
As a Tenant Manager,
I want to choose how aggressively the IA participates in WhatsApp operations,
So that I can balance customer experience against token cost.

## Acceptance Criteria

1. Three operation modes defined as a Postgres enum `operation_mode`: `ia_full`, `ia_eco`, `ia_zero`.
2. `system_settings.operation_mode` column (enum, NOT NULL, default `ia_eco`) and `system_settings.configured_mode` (same enum, default `ia_eco`) — `operation_mode` is the live mode (may be auto-downgraded); `configured_mode` is the manager's preference (restored on monthly reset).
3. **Mode behavior contract** (enforced in `OperationModeService.is_allowed(capability)`):
   | Capability | ia-full | ia-eco | ia-zero |
   |---|:---:|:---:|:---:|
   | Free-form text reply via LLM | ✅ | ❌ | ❌ |
   | Intent classification via LLM | ✅ | ✅ | ❌ |
   | Audio transcription (Whisper/equiv) | ✅ | ✅ | ❌ |
   | OCR Tesseract (default) | ✅ | ✅ | ✅ |
   | OCR LLM Vision fallback | ✅ | ❌ | ❌ |
   | Negotiation (grant grace days) | ✅ | ❌ | ❌ |
   | Send template by deterministic rule | ✅ | ✅ | ✅ |
   | Render interactive menu | ✅ | ✅ | ✅ |
4. `OperationModeService`:
   - `get_current_mode(tenant_id) -> OperationMode`
   - `is_allowed(tenant_id, capability: str) -> bool`
   - `set_operation_mode(tenant_id, mode, reason: 'manual'|'auto_throttle'|'reset') -> None` — emite `OperationModeChangedEvent`, grava em audit_log
   - `set_configured_mode(tenant_id, mode) -> None` — só persiste preferência, não muda live mode
5. Agent orchestrator (Story 6.4) consulta `OperationModeService.is_allowed()` antes de cada decisão. Se capability não permitida → cai pra fallback determinístico (intent rules + menu) da Story 11.4.
6. Inbound message pipeline em `ia-zero` desvia 100% para intent rules engine (Story 11.4); LLM nunca é chamado.
7. Backend endpoints:
   - `GET /api/v1/system/operation-mode` — `{current_mode, configured_mode, reason_for_difference, since}`
   - `PUT /api/v1/system/operation-mode` — manager troca configured_mode (e current_mode se não estiver throttled)
   - `POST /api/v1/system/operation-mode/restore` — força restore para configured_mode (sai do throttle manualmente)
8. Frontend page **Settings → IA & WhatsApp → Modo de Operação**:
   - 3 cards lado a lado (IA Full / IA Eco / IA Zero) com descrição, custo médio/msg, e badge "Atual"/"Configurado"
   - Banner se `current_mode != configured_mode`: "Você está em IA Eco automaticamente. Configurado: IA Full." + botão "Restaurar"
   - Modal de confirmação ao trocar para `ia-zero` ("Tem certeza? IA será totalmente desligada")
9. Header global mostra badge do modo atual (cor: verde ia-full, amarelo ia-eco, cinza ia-zero) com tooltip explicativo.
10. SSE event `operation_mode_changed` publicado a todos os clients do tenant para atualizar UI em tempo real.
11. Tests:
    - `is_allowed` retorna corretamente para todas as combinações de modo × capability
    - Mudança de modo persiste em DB E em audit_log
    - SSE fired on mode change
    - Mode service é tenant-scoped (tenant A em ia-zero não afeta tenant B)

## Technical Context

### Architecture References
- Capability gate é um cross-cutting concern — implementar como dependency injectable no DI container
- Audit_log entries com `category='security'` (mudança de modo é decisão de segurança operacional)
- Não confundir com `agent_config` (Story 6.4) que controla persona/tom; este é gate de capabilities

### Files to Create/Modify
```
backend-api/
├── app/domain/operation_mode/
│   ├── enums.py                         # OperationMode enum
│   ├── service.py                       # OperationModeService
│   └── events.py                        # OperationModeChangedEvent
├── app/application/agent/orchestrator.py # gate todas as decisões via is_allowed()
├── app/application/collections/handle_inbound_message.py # ia-zero bypass
├── app/api/v1/system_routes.py
├── alembic/versions/xxxx_operation_mode_enum_and_columns.py
frontend/
├── src/app/features/settings/operation-mode/operation-mode.component.ts/.html/.css
├── src/app/features/settings/operation-mode/mode-card.component.ts/.html/.css
├── src/app/core/services/operation-mode.service.ts
└── src/app/shared/components/mode-badge/mode-badge.component.ts/.html/.css
```

### Dependencies
- Story 6.4 (Agent orchestrator — vai chamar is_allowed)
- Story 11.4 (Intent rules engine — fallback em ia-zero)
- Story 11.1 (Token budget — chama set_operation_mode no throttle)

### Technical Notes
- **Decision matrix** vive em `OperationModeService.CAPABILITY_MATRIX` como constante Python — fácil de testar exaustivamente
- **Migration**: `configured_mode` inicializado com mesmo valor do default `ia_eco` para tenants existentes
- **Não cachear em memória por mais de 30s** — manager pode trocar a qualquer momento; cache curto em Redis com key `op_mode:{tenant_id}`, TTL 30s
- **Logging**: cada chamada de `is_allowed` que retorna False com `current_mode=ia-zero` incrementa contador Prometheus `ia_zero_blocks_total{capability}` — útil pra entender o que o usuário está perdendo

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] No regressions
- [ ] Code review (`bmad-code-review`) executed and approved
