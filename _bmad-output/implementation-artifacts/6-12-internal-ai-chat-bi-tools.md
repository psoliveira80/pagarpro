---
epic: 6
story: 12
title: "Internal AI Chat BI Tools"
type: "Core"
status: done
---

# Story 6.12: Internal AI Chat BI Tools

## User Story
As a Manager using the in-app chat,
I want the AI agent to have access to business intelligence tools that query real operational data,
So that I can get instant answers about overdue installments, collection performance, revenue, customer history, vehicle positions, and contract status without navigating to separate screens.

## Acceptance Criteria
1. The following BI tools are implemented as Python async functions and registered in `AgentToolRegistry`:
   - `get_overdue_installments(tenant_id, filters: {customer_id?, days_overdue_min?, days_overdue_max?, limit?}) -> list[OverdueInstallment]` -- returns overdue installments with current interest/fine values.
   - `get_collection_summary(tenant_id, period: {start_date, end_date}) -> CollectionSummary` -- total receivable, collected, overdue, collection rate %, top defaulters.
   - `get_revenue_by_period(tenant_id, period: {start_date, end_date, group_by: 'day'|'week'|'month'}) -> list[RevenueBucket]` -- revenue breakdown with totals.
   - `get_customer_payment_history(tenant_id, customer_id, limit?) -> list[PaymentRecord]` -- chronological payment history with status, amount, method.
   - `get_vehicle_position(tenant_id, vehicle_id) -> VehiclePosition` -- latest GPS position with timestamp, address, speed (delegates to `ITrackerGateway`).
   - `list_defaulters(tenant_id, min_days_overdue?, limit?) -> list[DefaulterRecord]` -- customers with overdue installments, sorted by total debt.
   - `get_contract_status(tenant_id, contract_id) -> ContractDetail` -- contract summary with installment schedule, paid/pending/overdue counts, total values.
2. Every tool input is validated with a Pydantic model before execution. Invalid inputs return a structured error message (not an exception).
3. All database queries use SQLAlchemy parametrized queries (never raw SQL, never string interpolation).
4. `tenant_id` is always injected by the backend from the authenticated session context -- never accepted as an LLM-provided argument. The tool function signature includes `tenant_id` but the `AgentToolRegistry` injects it automatically.
5. Query results are capped at **200 rows** maximum. If more results exist, the response includes a `truncated: true` flag and a `total_count` field.
6. All database queries execute with a **10-second timeout**. Timeouts return a structured error message.
7. Database access uses a **read-only connection** (separate SQLAlchemy session with read-only transaction isolation) to prevent accidental writes.
8. Each tool response includes a **confidence indicator**: `high` (direct data, no ambiguity), `medium` (partial match or estimated values), `low` (fallback or no data found). The in-app chat UI renders this as a colored dot on the response card.
9. Unit tests for each tool function covering: happy path, empty results, max row cap, timeout handling, invalid input validation, tenant isolation.

## Technical Context

### Architecture References
- Tools are registered in `AgentToolRegistry` (Story 6.4) at application startup.
- Each tool is a standalone async function in `app/application/agent/tools/`.
- Tools follow the same pattern as the core tools defined in Story 6.4 (`get_overdue_installments`, `get_collection_summary`, `get_customer_payment_history`, `generate_pix_qr`), but this story covers the full BI set including new tools.
- The `AgentOrchestrator` ReAct loop (Story 6.4) calls these tools when the LLM issues a `tool_call`.
- Responses are rendered as structured response cards in the in-app chat (Story 6.10).

### Files to Create/Modify
**Backend:**
- `backend-api/app/application/agent/tools/bi_tools.py` -- all BI tool functions:
  - `get_overdue_installments`
  - `get_collection_summary`
  - `get_revenue_by_period`
  - `get_customer_payment_history`
  - `list_defaulters`
  - `get_contract_status`
- `backend-api/app/application/agent/tools/vehicle_tools.py` -- vehicle-specific tools:
  - `get_vehicle_position` (delegates to `ITrackerGateway` port)
- `backend-api/app/application/agent/tools/schemas.py` -- Pydantic input/output schemas for all BI tools:
  - `OverdueInstallmentsInput`, `OverdueInstallment`
  - `CollectionSummaryInput`, `CollectionSummary`
  - `RevenueByPeriodInput`, `RevenueBucket`
  - `CustomerPaymentHistoryInput`, `PaymentRecord`
  - `VehiclePositionInput`, `VehiclePosition`
  - `ListDefaultersInput`, `DefaulterRecord`
  - `ContractStatusInput`, `ContractDetail`
  - `ToolResponse[T]` generic wrapper with `data`, `truncated`, `total_count`, `confidence`
- `backend-api/app/application/agent/tools/tool_registration.py` -- startup function that registers all BI tools in `AgentToolRegistry` with their schemas, descriptions, and required permissions
- `backend-api/app/infrastructure/db/read_only_session.py` -- read-only SQLAlchemy session factory with timeout configuration
- `backend-api/app/core/di.py` -- register read-only session and call tool registration at startup

**Tests:**
- `backend-api/tests/unit/application/agent/tools/test_bi_tools.py` -- tests for each BI tool:
  - Happy path with mock data
  - Empty result set
  - Row cap enforcement (> 200 rows)
  - Query timeout handling
  - Invalid input rejection (Pydantic validation)
  - Tenant isolation (tool only returns data for injected tenant_id)
- `backend-api/tests/unit/application/agent/tools/test_vehicle_tools.py` -- `get_vehicle_position` tests with mocked `ITrackerGateway`
- `backend-api/tests/unit/application/agent/tools/test_schemas.py` -- Pydantic schema validation tests
- `backend-api/tests/unit/application/agent/tools/test_tool_registration.py` -- verify all tools are registered with correct metadata

### Dependencies
- Story 6.4 (AI Agent Engine -- `AgentToolRegistry` for registration and `AgentOrchestrator` for execution).
- Story 6.10 (In-App Chat Channel -- the primary consumer of these tools via structured response cards).
- Epic 4 (Receivables domain -- installments, payments, write-offs data models and repositories).
- Epic 3 (Contracts domain -- contract and installment schedule data).
- Epic 2A (Customer domain -- customer data for payment history and defaulter lists).
- Epic 2B (Vehicle Module -- `ITrackerGateway` for vehicle position, vehicle data models).

### Technical Notes
- **Tenant isolation**: The `AgentToolRegistry.execute_tool()` method injects `tenant_id` from the authenticated context before calling the tool function. The LLM sees `tenant_id` in the tool schema description as "automatically provided" and should not attempt to set it.
- **Read-only session**: Create a separate SQLAlchemy session factory configured with `execution_options={"isolation_level": "REPEATABLE READ"}` and wrapped to reject any `INSERT/UPDATE/DELETE` operations. This prevents a bug in any tool from accidentally mutating data.
- **Row limit enforcement**: Each tool applies `LIMIT 201` to its query. If 201 rows are returned, the response is truncated to 200 with `truncated=True` and a `total_count` from a separate `COUNT(*)` query.
- **Query timeout**: Use `asyncio.wait_for(query_coroutine, timeout=10.0)`. On timeout, return `ToolResponse(data=[], error="Query timed out. Try narrowing your filters.", confidence="low")`.
- **Confidence logic**:
  - `high`: query returned data, no ambiguity, filters were specific (e.g., specific customer_id or contract_id).
  - `medium`: query returned data but filters were broad (e.g., all overdue) or results were truncated.
  - `low`: query returned no data, or a timeout/error occurred.
- **Tool descriptions** (used in LLM prompt) should be clear, concise, and in Portuguese to match the agent's language context. Example: `"Busca parcelas vencidas de um cliente ou de toda a carteira. Retorna valor atualizado com juros e multa."`
- Interest and fine calculations for overdue installments should reuse `calculations.py` from the finance domain (Epic 4) to ensure consistency with the receivables list.
- `get_vehicle_position` delegates to `ITrackerGateway.get_last_position(vehicle_id)` -- it does not query the database directly for GPS data. If no tracker is configured, it returns a structured "tracker not configured" response.
- All tool results are logged in `agent_runs.tools_called` JSONB array for observability and debugging.

### Session Context
- Docker-only development: backend on port 8100, PostgreSQL on 5433, Redis on 6380.
- Existing domain models: `Installment` (Epic 4), `Contract` (Epic 3), `Customer` (Epic 2A), `Vehicle` (Epic 2B).
- Existing ports: `ITrackerGateway` (Epic 2B), repositories for all entities.
- Finance calculations: `backend-api/app/domain/finance/calculations.py` (interest/fine computation).

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
