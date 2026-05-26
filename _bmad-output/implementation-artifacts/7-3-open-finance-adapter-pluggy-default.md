---
epic: 7
story: 3
title: "Open Finance Adapter — Pluggy Default"
type: "Core"
status: done
---

# Story 7.3: Open Finance Adapter — Pluggy Default

## User Story
As an Admin,
I want to optionally connect Open Finance,
So that statements arrive automatically.

## Acceptance Criteria
1. `IBankReconciliationProvider` Port defined with methods: `connect_account`, `list_accounts`, `fetch_transactions`, `disconnect`.
2. `PluggyAdapter` implemented as default; `BelvoAdapter` and `TecnoSpeedAdapter` as alternatives.
3. Settings > Integrations: "Connect account" flow using the Pluggy Connect widget (embedded iframe/redirect).
4. Celery beat job: incremental transaction sync every 6 hours.
5. Default state: **disabled** (cost concern). Requires explicit Admin activation in Settings > Integrations.
6. Transactions from Open Finance persisted to `bank_transactions` with `imported_from='open_finance'`.

## Technical Context

### Architecture References
- Port: `backend-api/app/domain/ports/bank_reconciliation_provider.py` — `IBankReconciliationProvider` Protocol.
- Adapters in `backend-api/app/infrastructure/integrations/bank/`.
- Webhook endpoint: `POST /api/v1/webhooks/open-finance/{provider}` for Pluggy notifications of new transactions.
- Celery beat schedule: sync every 6 hours via `backend-api/app/workers/beat_schedule.py`.
- Credentials stored encrypted (AES-256-GCM) in `integration_credentials` table.

### Files to Create/Modify
**Backend:**
- `backend-api/app/domain/ports/bank_reconciliation_provider.py` — `IBankReconciliationProvider` Protocol definition
- `backend-api/app/infrastructure/integrations/bank/pluggy_adapter.py` — Pluggy API adapter (connect, list accounts, fetch transactions, disconnect)
- `backend-api/app/infrastructure/integrations/bank/belvo_adapter.py` — Belvo adapter (alternative)
- `backend-api/app/infrastructure/integrations/bank/tecnospeed_adapter.py` — TecnoSpeed adapter (alternative)
- `backend-api/app/application/reconciliation/sync_open_finance.py` — use case: fetch incremental transactions, deduplicate, persist
- `backend-api/app/api/v1/reconciliation_routes.py` — add `POST /api/v1/reconciliation/sync-open-finance` (manual trigger)
- `backend-api/app/api/v1/webhook_routes.py` — add `POST /api/v1/webhooks/open-finance/{provider}` endpoint
- `backend-api/app/workers/tasks/sync_open_finance.py` — Celery task for scheduled sync
- `backend-api/app/workers/beat_schedule.py` — register sync job at 6-hour intervals
- `backend-api/app/infrastructure/settings.py` — add Open Finance config (enabled flag, provider, credentials)
- `backend-api/app/core/di.py` — register bank reconciliation provider in DI container

**Frontend:**
- `frontend/src/app/features/config/integrations/components/open-finance-connect/open-finance-connect.component.ts` — Pluggy Connect widget integration, account list, disconnect button
- `frontend/src/app/features/config/integrations/components/open-finance-connect/open-finance-connect.component.html`
- `frontend/src/app/features/config/integrations/components/open-finance-connect/open-finance-connect.component.css`

**Tests:**
- `backend-api/tests/unit/integrations/bank/test_pluggy_adapter.py`
- `backend-api/tests/unit/application/test_sync_open_finance.py`
- `backend-api/tests/integration/test_open_finance_webhook.py`

### Dependencies
- Story 7.1 (OFX Importer — `bank_transactions` table and repository, shared for all import sources).
- Epic 1 (Webhook framework, integration credentials infrastructure, settings).

### Technical Notes
- Pluggy Connect widget: the frontend embeds the Pluggy Connect SDK which handles bank authentication. On success, it returns an `itemId` that the backend stores for future syncs.
- Incremental sync: the adapter tracks `last_sync_at` per connected account. `fetch_transactions` uses a date range from `last_sync_at` to now.
- Pluggy webhook: Pluggy sends `ITEM_UPDATED` events when new transactions are available. The webhook handler triggers an immediate sync rather than waiting for the next scheduled run.
- Transactions from Open Finance arrive already structured (date, amount, description) — no parsing needed. They go directly into `bank_transactions`.
- Deduplication: Open Finance providers typically include a transaction ID. Use this as `fitid` for the `UNIQUE(account_id, fitid)` constraint.
- Feature disabled by default: the integration card in Settings > Integrations shows as "inactive" with an "Activate" button that opens the connection flow.
- Cost concern: Pluggy charges per connected account/month. The UI should display a cost warning before activation.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
