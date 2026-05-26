---
epic: 11
story: 3
title: "Menu Interativo do WhatsApp (List Messages e Reply Buttons)"
type: "Core"
status: ready-for-dev
---

# Story 11.3: Menu Interativo do WhatsApp

## História de Usuário
Como Cliente,
quero escolher ações em um menu de botões/opções em vez de digitar,
para que eu receba respostas mais rápidas e a empresa gaste menos com IA.

## Critérios de Aceite

1. Nova tabela `interactive_menus`: `id`, `tenant_id`, `slug` (único por tenant, ex.: `main_menu`, `payment_menu`), `title`, `body_text`, `footer_text` (nullable), `menu_type` ('list' | 'buttons'), `items` JSONB (array de `{id, label, description, action_type, action_payload}`), `created_at`, `updated_at`. Soft delete.
2. Serviço `MenuRenderer` gera o payload correto para cada adapter de gateway:
   - Z-API: `{type: 'list', list: {...}}` ou `{type: 'buttons', buttons: [...]}`
   - Uazapi: formato específico do provider
   - Evolution API: formato específico do provider
   - O adapter expõe `send_interactive_menu(phone, menu_payload)` estendendo `IWhatsAppGateway` da Story 6.1.
3. Limites do WhatsApp respeitados:
   - List Messages: até 10 items, agrupáveis em até 10 sections
   - Reply Buttons: até 3 buttons (fallback automático para list se >3)
4. Enum `action_type` do item: `send_template` (dispara template existente), `show_submenu` (mostra outro menu), `call_function` (executa função registrada, ex.: `generate_pix_qr`, `get_overdue_summary`), `handover_human` (marca conversa como needs-attention + pausa agente).
5. Webhook de entrada (Story 6.3) detecta payload `interactive_response`, identifica `selected_id`, executa action correspondente.
6. Seed inicial de menus padrão em português:
   - `main_menu`: "Como posso ajudar?" → [Meus Boletos, Enviar Comprovante, Negociar Dívida, 2ª Via PIX, Falar com Atendente]
   - `payment_menu`: ações de pagamento
   - `overdue_menu`: opções para inadimplente
7. Página de frontend **Configurações → WhatsApp → Menus Interativos**:
   - Lista de menus com botões "Editar", "Duplicar", "Excluir", "Testar" (envia para número de teste do gestor)
   - Editor drag-drop de items
   - Preview side-by-side mostrando como o cliente vai ver no WhatsApp (mockup visual)
   - Validação ao vivo dos limites do WhatsApp (até 10 itens, até 24 chars no label)
8. Endpoint `POST /api/v1/menus/{slug}/preview` — retorna payload gerado para um menu (debug)
9. Endpoint `POST /api/v1/menus/{slug}/test-send` — envia para `tenant.test_phone_number` (do gestor)
10. Em `ia-zero`, qualquer mensagem de entrada que não bata em nenhuma intent rule (Story 11.4) responde automaticamente com `main_menu`.
11. Testes:
    - Renderer gera payload válido para cada adapter
    - Limites validados (>10 items é rejeitado)
    - `interactive_response` de entrada mapeia corretamente para action
    - `show_submenu` mantém histórico de navegação (cliente pode "voltar")

## Contexto Técnico

### Referências de Arquitetura
- Extensão do `IWhatsAppGateway` (Story 6.1) com novo método
- Pipeline de webhook de entrada (Story 6.3) ganha branch para `interactive_response`
- Estado da conversa inclui `last_menu_shown` para tratar o "voltar"

### Arquivos a Criar/Modificar
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

### Dependências
- Story 6.1 (Protocol `IWhatsAppGateway`)
- Story 6.3 (pipeline de webhook de entrada)
- Story 10.4 (message templates — alvo de `action_type=send_template`)
- Story 11.2 (modo de operação — em `ia-zero` é menu por padrão)

### Notas Técnicas
- **Janela de 24h do WhatsApp**: menus interativos só funcionam dentro da janela de 24h após a última mensagem do cliente. Fora dela, precisa de Template Message aprovado pela Meta. Detectar e fazer fallback para o template apropriado.
- **Estado de navegação**: tabela `menu_navigation_state` por conversation com `breadcrumb` (array de slugs de menu visitados). TTL 30 min sem atividade → reseta.
- **i18n V2**: hoje só PT-BR; deixar `body_text` etc. indexáveis por locale no futuro
- **Limites Uazapi/Evolution**: verificar docs específicas — podem ter limites adicionais. O renderer normaliza para o mínimo denominador comum

## Checklist do Dev
- [ ] Todos os critérios de aceite atendidos
- [ ] Testes escritos e passando
- [ ] Sem regressões
- [ ] Code review (`bmad-code-review`) executado e aprovado
