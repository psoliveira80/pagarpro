---
epic: 6
story: 5
title: "Agent Parameterization UI"
type: "Core + Module Hooks"
status: done
---

# Story 6.5: Agent Parameterization UI

## User Story
As an Admin,
I want to configure the agent's LLM provider, WhatsApp provider, tone, rules, enabled tools, and budget limits,
So that the agent represents my business voice and operates within cost constraints.

## Acceptance Criteria
1. Route `/system/config/agent` with tabbed sections:
   - **Providers**: LLM provider selector (dropdown populated from `integration_credentials` where provider_type='llm'), WhatsApp provider selector (dropdown from provider_type='whatsapp'). Each shows connection status and a "Test Connection" button.
   - **Persona**: name, tone slider with live example (Formal/Friendly/Firm presets), time-of-day greetings.
   - **Service Window**: operating hours, days of week.
   - **Collection Policy**: preventive collection (lead days + template), post-due sequences (D+1/D+3/D+7 templates with toggles), score concession policy (editable table: score_min, score_max, days_tolerance, requires_human_approval).
   - **Tools**: read-only list of enabled tools from `AgentToolRegistry`, grouped by category (Collection, Payment, BI, Module). Each tool shows name, description, required permissions.
   - **Budget & Limits**: monthly LLM spend cap (USD), daily request limit per tenant, rate limit per conversation (messages/hour), alert threshold percentage. Current month spend displayed.
   - **Templates**: Tiptap rich text editor with placeholder insertion (`{{customer_name}}`, `{{amount_due}}`, `{{due_date}}`, `{{pix_qr_link}}`, `{{overdue_days}}`, `{{score}}`), live preview.
2. **Module-specific policies**: each active module can register additional policy sections. E.g., Vehicle Module adds "Remote Block" section (active toggle + conditions: `dias_atraso >= X` AND `score < Y` + requires-human-approval checkbox). Rendered dynamically from backend JSON schema.
3. Every configuration change writes a versioned record with diff to the audit log.
4. "Test Message" button generates a sample reply against a fictional customer using current settings (uses `AGENT_DRY_RUN` mode internally).

## Technical Context

### Architecture References
- Frontend route: `frontend/src/app/features/config/agent/agent-config.component.ts`.
- Sub-components: `provider-selector/`, `persona-editor/`, `policy-editor/`, `tools-viewer/`, `budget-editor/`, `template-editor/`, `agent-tester/`.
- Backend: agent configuration stored as versioned JSON in settings table; API endpoints for CRUD.
- Module policy sections registered via `IAssetModule` at runtime -- frontend renders dynamically based on backend schema.
- LLM and WhatsApp provider dropdowns read from `integration_credentials` table (same table used by Stories 6.1 and 6.4).

### Files to Create/Modify
**Frontend:**
- `frontend/src/app/features/config/agent/agent-config.component.ts` -- main agent configuration page with tabs
- `frontend/src/app/features/config/agent/agent-config.component.html` -- template with tabbed layout
- `frontend/src/app/features/config/agent/agent-config.component.css` -- styles (Tailwind v4)
- `frontend/src/app/features/config/agent/components/provider-selector/provider-selector.component.ts` -- LLM + WhatsApp provider dropdowns with test connection
- `frontend/src/app/features/config/agent/components/persona-editor/persona-editor.component.ts` -- persona name, tone slider, greetings
- `frontend/src/app/features/config/agent/components/policy-editor/policy-editor.component.ts` -- score concession table, collection sequences
- `frontend/src/app/features/config/agent/components/tools-viewer/tools-viewer.component.ts` -- read-only list of registered tools from AgentToolRegistry
- `frontend/src/app/features/config/agent/components/budget-editor/budget-editor.component.ts` -- budget cap, rate limits, current spend display
- `frontend/src/app/features/config/agent/components/template-editor/template-editor.component.ts` -- Tiptap rich text editor with placeholders + preview
- `frontend/src/app/features/config/agent/components/agent-tester/agent-tester.component.ts` -- "Test Message" button with response display
- `frontend/src/app/features/config/agent/agent-config.routes.ts` -- lazy-loaded route

**Backend:**
- `backend-api/app/api/v1/admin_routes.py` -- endpoints: `GET /api/v1/admin/agent-config`, `PUT /api/v1/admin/agent-config`, `POST /api/v1/admin/agent-config/test`, `GET /api/v1/admin/agent-tools` (list registered tools), `GET /api/v1/admin/agent-budget` (current spend)
- `backend-api/app/application/agent/update_agent_config.py` -- use case: validate config, persist versioned record, audit log
- `backend-api/app/application/agent/test_agent_message.py` -- use case: compose prompt with fictional customer, call LLM, return response
- `backend-api/app/domain/agent/agent_config.py` -- `AgentConfig` domain object with persona, policy, budget, template sections

**Tests:**
- `backend-api/tests/unit/application/agent/test_update_agent_config.py`
- `backend-api/tests/unit/application/agent/test_test_agent_message.py`
- `frontend/src/app/features/config/agent/agent-config.component.spec.ts`
- `frontend/src/app/features/config/agent/components/provider-selector/provider-selector.component.spec.ts`

### Dependencies
- Story 6.4 (AI Agent Engine -- LLM provider and AgentToolRegistry needed for provider selector, tools viewer, and "Test Message" feature).
- Story 6.1 (WhatsApp gateway -- for WhatsApp provider selector and test connection).
- Epic 1 (Settings infrastructure, audit log, RBAC -- Admin role required, integration_credentials table).

### Technical Notes
- The tone slider offers presets (Formal, Friendly, Firm) mapping to system prompt snippets, with a live example showing how the agent would greet a customer.
- Tools viewer is read-only in this UI -- tools are registered programmatically in the backend. The UI shows which tools are available and their required permissions.
- Budget/rate limit enforcement happens in `AgentOrchestrator` (Story 6.4) -- this UI only configures the limits.
- Provider selector uses `CustomSelectComponent` with CDK Overlay (project convention: never native `<select>`).
- All forms use the wizard/multi-step pattern per project UX standards.
- Required fields marked with red asterisk: `<span class="text-[var(--danger)]">*</span>`.
- Configuration versioning: each save creates a new version with a diff against the previous version, stored in audit log.
- The "Test Message" endpoint uses `AGENT_DRY_RUN` mode and returns the would-be response without sending.
- Mobile-first responsive layout per project UX standards.

### Session Context
- Docker-only development: backend on port 8100, PostgreSQL on 5433, Redis on 6380.
- Frontend: Angular 21, Standalone components, Signals, Tailwind v4.
- CustomSelectComponent with CDK Overlay is the standard for all dropdowns.
- All CRUD forms use multi-step wizard pattern.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
