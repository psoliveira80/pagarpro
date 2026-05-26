---
epic: 6
story: 4
title: "AI Agent Engine with Tool-Use"
type: "Core"
status: done
---

# Story 6.4: AI Agent Engine with Tool-Use

## User Story
As a Backend developer,
I want a conversational agent engine with pluggable LLM providers and permission-gated tool execution via a ReAct loop,
So that the agent can answer questions, perform actions, and serve both WhatsApp and in-app channels securely.

## Acceptance Criteria
1. `ILlmProvider` Port defined with methods: `chat(messages, tools, temperature, max_tokens) -> LlmResponse`, `stream_chat(messages, tools, ...) -> AsyncIterator[LlmChunk]`. Five adapters: `OpenAiAdapter`, `AnthropicAdapter`, `GroqAdapter`, `GeminiAdapter`, `OllamaAdapter`.
2. LLM provider configurable per tenant via `integration_credentials` table (provider_type='llm'). Factory reads active LLM credential and returns the correct adapter.
3. `AgentOrchestrator` implements a ReAct loop: Reason -> Act -> Observe, max 10 iterations per turn. If max iterations reached, returns a graceful "I could not complete this request" message.
4. `AgentToolRegistry` service: `register_tool(name, fn, schema, required_permissions)`, `list_tools(user_permissions) -> list[ToolDef]`, `execute_tool(name, args, context) -> ToolResult`. Only tools the current user/channel has permissions for are included in the LLM prompt.
5. Pre-defined core tools registered at startup:
   - `get_overdue_installments(customer_id) -> list[Installment]`
   - `get_collection_summary(tenant_id) -> CollectionSummary`
   - `get_customer_payment_history(customer_id) -> list[Payment]`
   - `generate_pix_qr(installment_id) -> PixQrData`
6. Security invariants enforced:
   - `tenant_id` is always injected by the backend from JWT/session context, never accepted from LLM output.
   - LLM never generates raw SQL. All data access goes through pre-defined tool functions.
   - Every tool input is validated with Pydantic models before execution.
   - Query results are capped at 200 rows. Database queries have a 10-second timeout.
   - All tool executions are audit-logged.
7. System prompt templates stored in DB (agent_config table): `collection_agent` (for WhatsApp channel), `internal_assistant` (for in-app channel). Templates support placeholders: `{{tenant_name}}`, `{{persona_name}}`, `{{tone}}`, `{{tool_list}}`, `{{current_date}}`.
8. `agent_runs` table for observability: `id`, `tenant_id`, `conversation_id`, `triggered_by_message_id`, `provider`, `model`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `latency_ms`, `iterations` (int), `tools_called` (JSONB array), `final_action`, `error`, `cost_usd`, `created_at`. Index on `(tenant_id, created_at DESC)`.
9. Each agent turn writes to `agent_runs` with full token usage and tool call trace.
10. Feature flag `AGENT_DRY_RUN`: generates response but does not send -- queued for human review (calibration mode).
11. NO RAG/pgvector -- deferred to a future story. NO LangChain/LangGraph dependencies.

## Technical Context

### Architecture References
- LLM Port: `app/domain/ports/llm_provider.py` with adapters in `app/infrastructure/adapters/llm/`.
- Agent orchestrator: `app/application/agent/orchestrator.py` -- the ReAct loop lives here.
- Tool registry: `app/application/agent/tool_registry.py` -- central registry for all agent tools.
- Agent tools: `app/application/agent/tools/` -- each tool is a Python async function with Pydantic input schema.
- Celery task: `app/workers/tasks/run_agent_turn.py` -- async task wrapper for agent turns (used by WhatsApp pipeline).
- For in-app channel, the orchestrator is called directly (not via Celery) to enable SSE streaming.
- Follows same port/adapter pattern as `IFipeProvider`, `ITrackerGateway`, `IEmailSender`.

### Files to Create/Modify
**Backend:**
- `backend-api/app/domain/ports/llm_provider.py` -- `ILlmProvider` Protocol + `LlmResponse`, `LlmChunk`, `ToolCall` dataclasses
- `backend-api/app/infrastructure/adapters/llm/__init__.py` -- package init
- `backend-api/app/infrastructure/adapters/llm/openai_adapter.py` -- OpenAI adapter (GPT-4o, etc.)
- `backend-api/app/infrastructure/adapters/llm/anthropic_adapter.py` -- Anthropic adapter (Claude)
- `backend-api/app/infrastructure/adapters/llm/groq_adapter.py` -- Groq adapter (fast inference)
- `backend-api/app/infrastructure/adapters/llm/gemini_adapter.py` -- Google Gemini adapter
- `backend-api/app/infrastructure/adapters/llm/ollama_adapter.py` -- Ollama adapter (local/self-hosted)
- `backend-api/app/infrastructure/adapters/llm/llm_factory.py` -- factory reads `integration_credentials` and returns active LLM adapter
- `backend-api/app/application/agent/orchestrator.py` -- `AgentOrchestrator` with ReAct loop
- `backend-api/app/application/agent/tool_registry.py` -- `AgentToolRegistry` service
- `backend-api/app/application/agent/tools/__init__.py` -- tools package
- `backend-api/app/application/agent/tools/collection_tools.py` -- `get_overdue_installments`, `get_collection_summary`, `get_customer_payment_history`
- `backend-api/app/application/agent/tools/payment_tools.py` -- `generate_pix_qr`
- `backend-api/app/application/agent/prompt_builder.py` -- system prompt template composition
- `backend-api/app/infrastructure/db/models/agent_run.py` -- `AgentRun` ORM model
- `backend-api/app/workers/tasks/run_agent_turn.py` -- Celery task wrapper for WhatsApp-triggered turns
- `backend-api/alembic/versions/xxxx_create_agent_runs.py` -- migration for `agent_runs` table
- `backend-api/app/core/di.py` -- register LLM factory, AgentOrchestrator, AgentToolRegistry in DI

**Tests:**
- `backend-api/tests/unit/application/agent/test_orchestrator.py` -- ReAct loop tests (0 tools, 1 tool, multi-tool, max iterations)
- `backend-api/tests/unit/application/agent/test_tool_registry.py` -- registration, permission gating, execution
- `backend-api/tests/unit/application/agent/tools/test_collection_tools.py`
- `backend-api/tests/unit/application/agent/tools/test_payment_tools.py`
- `backend-api/tests/unit/adapters/llm/test_openai_adapter.py`
- `backend-api/tests/unit/adapters/llm/test_anthropic_adapter.py`
- `backend-api/tests/integration/test_agent_turn_e2e.py`

### Dependencies
- Story 6.1 (WhatsApp gateway -- for sending agent responses on WhatsApp channel).
- Story 6.2 (Conversations & Messages -- ConversationStore for message history and persistence).
- Story 6.3 (Webhook inbound pipeline -- triggers agent turn for WhatsApp).
- Epic 1 (DI container, settings, auth, SSE infrastructure, integration_credentials table).
- Epic 4 (Receivables domain -- for tool implementations querying installments, payments, Pix QR).

### Technical Notes
- The ReAct loop: (1) Send messages + tool definitions to LLM, (2) If LLM returns tool_calls, execute each via AgentToolRegistry, (3) Append tool results as `role='tool'` messages, (4) Loop back to step 1. Exit when LLM returns a text response with no tool_calls, or max 10 iterations.
- Tool definitions follow OpenAI function-calling JSON schema format for cross-provider compatibility. Each adapter translates to its provider's native format.
- `AgentToolRegistry` filters tools by the current user's permissions before including them in the LLM prompt. WhatsApp customers get a restricted tool set; internal managers get an expanded set.
- For streaming (in-app channel), `stream_chat` yields `LlmChunk` objects that include partial text and/or tool_call deltas. The orchestrator buffers tool calls until complete, executes them, then resumes streaming.
- Cost tracking: each `agent_runs` entry records `cost_usd` computed from token counts and model pricing table. A Prometheus metric `llm_cost_usd_total` is incremented per run.
- The agent turn for WhatsApp is an async Celery task to avoid blocking the webhook response path. For in-app, it runs inline with SSE streaming.
- `AGENT_DRY_RUN` feature flag: when enabled, agent response is saved to `agent_runs` with `final_action='dry_run'` and not dispatched.
- Module-injected tools (e.g., `bloquear_veiculo` from Vehicle Module) are registered via `IAssetModule.get_agent_tools()` at startup -- but that registration mechanism is handled in the respective module stories, not here.

### Session Context
- Docker-only development: backend on port 8100, PostgreSQL on 5433, Redis on 6380.
- Adapters folder convention: `app/infrastructure/adapters/`.
- Existing port examples: `app/domain/ports/fipe_provider.py`, `app/domain/ports/tracker_gateway.py`.
- No LangChain, no LangGraph, no heavy frameworks. Pure Python async with httpx for LLM API calls.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
