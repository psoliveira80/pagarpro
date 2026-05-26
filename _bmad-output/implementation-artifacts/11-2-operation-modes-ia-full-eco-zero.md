---
epic: 11
story: 2
title: "Modos de Operação: ia-full / ia-eco / ia-zero"
type: "Core"
status: ready-for-dev
---

# Story 11.2: Modos de Operação (ia-full / ia-eco / ia-zero)

## História de Usuário
Como Gerente do Tenant,
quero escolher quão agressivamente a IA participa das operações no WhatsApp,
para que eu possa equilibrar a experiência do cliente contra o custo de tokens.

## Critérios de Aceite

1. Três modos de operação definidos como um enum Postgres `operation_mode`: `ia_full`, `ia_eco`, `ia_zero`.
2. Coluna `system_settings.operation_mode` (enum, NOT NULL, default `ia_eco`) e `system_settings.configured_mode` (mesmo enum, default `ia_eco`) — `operation_mode` é o modo ativo (pode ser auto-rebaixado); `configured_mode` é a preferência do gerente (restaurada no reset mensal).
3. **Contrato de comportamento por modo** (aplicado em `OperationModeService.is_allowed(capability)`):
   | Capability | ia-full | ia-eco | ia-zero |
   |---|:---:|:---:|:---:|
   | Resposta livre em texto via LLM | ✅ | ❌ | ❌ |
   | Classificação de intent via LLM | ✅ | ✅ | ❌ |
   | Transcrição de áudio (Whisper/equiv) | ✅ | ✅ | ❌ |
   | OCR Tesseract (default) | ✅ | ✅ | ✅ |
   | OCR com fallback LLM Vision | ✅ | ❌ | ❌ |
   | Negociação (conceder dias de carência) | ✅ | ❌ | ❌ |
   | Enviar template por regra determinística | ✅ | ✅ | ✅ |
   | Renderizar menu interativo | ✅ | ✅ | ✅ |
4. `OperationModeService`:
   - `get_current_mode(tenant_id) -> OperationMode`
   - `is_allowed(tenant_id, capability: str) -> bool`
   - `set_operation_mode(tenant_id, mode, reason: 'manual'|'auto_throttle'|'reset') -> None` — emite `OperationModeChangedEvent`, grava em audit_log
   - `set_configured_mode(tenant_id, mode) -> None` — apenas persiste preferência, não muda o modo ativo
5. Orquestrador do agente (Story 6.4) consulta `OperationModeService.is_allowed()` antes de cada decisão. Se a capability não for permitida → cai para fallback determinístico (intent rules + menu) da Story 11.4.
6. Pipeline de mensagem de entrada em `ia-zero` desvia 100% para o intent rules engine (Story 11.4); LLM nunca é chamado.
7. Endpoints do backend:
   - `GET /api/v1/system/operation-mode` — `{current_mode, configured_mode, reason_for_difference, since}`
   - `PUT /api/v1/system/operation-mode` — gerente troca `configured_mode` (e `current_mode` se não estiver sob throttle)
   - `POST /api/v1/system/operation-mode/restore` — força restauração para `configured_mode` (sai do throttle manualmente)
8. Página de frontend **Configurações → IA & WhatsApp → Modo de Operação**:
   - 3 cards lado a lado (IA Full / IA Eco / IA Zero) com descrição, custo médio por mensagem, e badge "Atual"/"Configurado"
   - Banner se `current_mode != configured_mode`: "Você está em IA Eco automaticamente. Configurado: IA Full." + botão "Restaurar"
   - Modal de confirmação ao trocar para `ia-zero` ("Tem certeza? IA será totalmente desligada")
9. Header global mostra badge do modo atual (cor: verde ia-full, amarelo ia-eco, cinza ia-zero) com tooltip explicativo.
10. Evento SSE `operation_mode_changed` publicado a todos os clients do tenant para atualizar a UI em tempo real.
11. Testes:
    - `is_allowed` retorna corretamente para todas as combinações de modo × capability
    - Mudança de modo persiste no DB E em audit_log
    - SSE disparado na mudança de modo
    - O serviço de modo é tenant-scoped (tenant A em ia-zero não afeta tenant B)

## Contexto Técnico

### Referências de Arquitetura
- O capability gate é um cross-cutting concern — implementar como dependência injetável no DI container
- Entradas no audit_log com `category='security'` (mudança de modo é decisão de segurança operacional)
- Não confundir com `agent_config` (Story 6.4), que controla persona/tom; este aqui é gate de capabilities

### Arquivos a Criar/Modificar
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

### Dependências
- Story 6.4 (orquestrador do agente — vai chamar `is_allowed`)
- Story 11.4 (intent rules engine — fallback em ia-zero)
- Story 11.1 (orçamento de tokens — chama `set_operation_mode` no throttle)

### Notas Técnicas
- **Matriz de decisão** vive em `OperationModeService.CAPABILITY_MATRIX` como constante Python — fácil de testar exaustivamente
- **Migration**: `configured_mode` inicializado com o mesmo valor do default `ia_eco` para tenants existentes
- **Não cachear em memória por mais de 30s** — gerente pode trocar a qualquer momento; cache curto em Redis com key `op_mode:{tenant_id}`, TTL 30s
- **Logging**: cada chamada de `is_allowed` que retorna False com `current_mode=ia-zero` incrementa o contador Prometheus `ia_zero_blocks_total{capability}` — útil para entender o que o usuário está perdendo

## Checklist do Dev
- [ ] Todos os critérios de aceite atendidos
- [ ] Testes escritos e passando
- [ ] Sem regressões
- [ ] Code review (`bmad-code-review`) executado e aprovado
