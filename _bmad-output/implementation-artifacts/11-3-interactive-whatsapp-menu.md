---
epic: 11
story: 3
title: "Interactive WhatsApp Menu (List Messages & Reply Buttons)"
type: "Core"
status: ready-for-dev
---

# Story 11.3: Interactive WhatsApp Menu

## User Story
As a Customer,
I want to choose actions from a menu of buttons/options instead of typing,
So that I get faster responses and the company spends less on IA.

## Acceptance Criteria

1. New table `interactive_menus`: `id`, `tenant_id`, `slug` (unique per tenant, e.g., `main_menu`, `payment_menu`), `title`, `body_text`, `footer_text` (nullable), `menu_type` ('list' | 'buttons'), `items` JSONB (array of `{id, label, description, action_type, action_payload}`), `created_at`, `updated_at`. Soft delete.
2. `MenuRenderer` service generates the correct payload for each gateway adapter:
   - Z-API: `{type: 'list', list: {...}}` or `{type: 'buttons', buttons: [...]}`
   - Uazapi: provider-specific shape
   - Evolution API: provider-specific shape
   - Adapter exposes `send_interactive_menu(phone, menu_payload)` extending `IWhatsAppGateway` from Story 6.1.
3. Limites WhatsApp respeitados:
   - List Messages: até 10 items, agrupáveis em até 10 sections
   - Reply Buttons: até 3 buttons (auto-fallback para list se >3)
4. Item `action_type` enum: `send_template` (dispara template existente), `show_submenu` (mostra outro menu), `call_function` (executa função registrada, ex.: `generate_pix_qr`, `get_overdue_summary`), `handover_human` (marca conversa needs-attention + pausa agente).
5. Inbound webhook (Story 6.3) detecta `interactive_response` payload, identifica `selected_id`, executa action correspondente.
6. Seed inicial de menus padrão em português:
   - `main_menu`: "Como posso ajudar?" → [Meus Boletos, Enviar Comprovante, Negociar Dívida, 2ª Via PIX, Falar com Atendente]
   - `payment_menu`: ações de pagamento
   - `overdue_menu`: opções para inadimplente
7. Frontend page **Settings → WhatsApp → Menus Interativos**:
   - Lista de menus com botões "Editar", "Duplicar", "Excluir", "Testar" (envia para número de teste do gestor)
   - Editor drag-drop de items
   - Preview side-by-side mostrando como cliente vai ver no WhatsApp (mockup visual)
   - Validação live de limites WhatsApp (até 10 itens, até 24 chars no label)
8. Endpoint `POST /api/v1/menus/{slug}/preview` — retorna payload gerado para um menu (debug)
9. Endpoint `POST /api/v1/menus/{slug}/test-send` — envia para `tenant.test_phone_number` (do gestor)
10. Em `ia-zero`, qualquer mensagem inbound que não bata em nenhuma intent rule (Story 11.4) responde automaticamente com `main_menu`.
11. Tests:
    - Renderer gera payload válido para cada adapter
    - Limites validados (>10 items rejeita)
    - Inbound `interactive_response` mapeia corretamente para action
    - `show_submenu` mantém histórico de navegação (cliente pode "voltar")

## Technical Context

### Architecture References
- Extensão do `IWhatsAppGateway` (Story 6.1) com novo método
- Inbound webhook pipeline (Story 6.3) ganha branch para `interactive_response`
- Conversation state inclui `last_menu_shown` para handle de "voltar"

### Files to Create/Modify
```
backend-api/
├── app/domain/menus/
│   ├── entities.py                      # InteractiveMenu, MenuItem
│   ├── action_types.py                  # ActionType enum
│   └── renderer.py                      # MenuRenderer
├── app/domain/ports/whatsapp_gateway.py # add send_interactive_menu
├── app/infrastructure/adapters/whatsapp/zapi_adapter.py       # implement
├── app/infrastructure/adapters/whatsapp/uazapi_adapter.py     # implement
├── app/infrastructure/adapters/whatsapp/evolution_api_adapter.py # implement
├── app/application/menus/
│   ├── handle_interactive_response.py
│   └── action_executor.py               # dispatch action_type
├── app/api/v1/menu_routes.py
├── alembic/versions/xxxx_interactive_menus.py
├── alembic/versions/xxxx_seed_default_menus.py
frontend/
├── src/app/features/settings/menus/menus-list.component.ts/.html/.css
├── src/app/features/settings/menus/menu-editor.component.ts/.html/.css
├── src/app/features/settings/menus/menu-preview.component.ts/.html/.css
└── src/app/core/services/menus.service.ts
```

### Dependencies
- Story 6.1 (`IWhatsAppGateway` Protocol)
- Story 6.3 (inbound webhook pipeline)
- Story 10.4 (message templates — alvo de `action_type=send_template`)
- Story 11.2 (operation mode — em `ia-zero` é menu by default)

### Technical Notes
- **WhatsApp 24h window**: menus interativos só funcionam dentro da janela de 24h após última mensagem do cliente. Fora dela, precisa de Template Message aprovado pela Meta. Detectar e fallback para template apropriado.
- **Estado de navegação**: tabela `menu_navigation_state` por conversation com `breadcrumb` (array de menu slugs visitados). TTL 30 min sem atividade → reseta.
- **i18n V2**: hoje só PT-BR; deixar `body_text` etc indexáveis por locale no futuro
- **Limites Uazapi/Evolution**: verificar docs específicas — podem ter limites adicionais. Renderer normaliza ao mínimo comum denominator

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] No regressions
- [ ] Code review (`bmad-code-review`) executed and approved
