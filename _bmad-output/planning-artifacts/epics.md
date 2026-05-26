---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - "_bmad-output/planning-artifacts/PRD.md"
  - "_bmad-output/planning-artifacts/ARCHITECTURE.md"
project_name: "{{product_name}}"
---

# {{product_name}} — Epic & Story Breakdown

## Overview

This document provides the complete epic and story breakdown for **{{product_name}}**, a generic recurring-billing and collections platform with pluggable vertical asset modules. The platform's **Core** handles: clients, contracts with a flexible installment builder, receivables (7-state lifecycle), payables, an AI-powered WhatsApp collection agent, bank reconciliation, dashboards, and auditing. **Vertical modules** plug in via the Asset Abstraction Layer (`IAssetModule` + Domain Events + Module Hooks) to add domain-specific functionality without touching the Core.

The **first vertical module is Vehicles** (fleet management), covering FIPE valuation, GPS tracker integration with remote block/unblock, depreciation, ROI per vehicle, and an interactive fleet map.

The system is a greenfield fullstack web application (Angular 21+ / FastAPI) built on Hexagonal (Ports & Adapters) architecture so that external providers (WhatsApp, Open Finance, payment gateways, LLM, OCR, storage, module-specific APIs) are swappable via configuration. Folder references: `backend-api/` (backend), `frontend/` (frontend).

**Key financial design decisions:**

- **Title lifecycle:** Titles (installments) are generated on contract finalization (`status='vigente'`). Contract changes that affect installments cancel open titles and reissue new ones. Paid titles are immutable.
- **Partial payments:** If paid amount < title amount, the original title receives partial write-off and a NEW title is created for the difference with a new collection cycle.
- **Default payment:** Pix via WhatsApp (zero cost). The system generates Pix QR Code and sends it via WhatsApp; the client pays directly to the bank account and sends a screenshot; OCR + validation + reconciliation confirm the payment. Gateway plugins (Asaas, Stripe, etc.) are optional.

## Requirements Inventory

### Functional Requirements

#### Asset Abstraction Layer (AST) — Core

- **FR-CORE-AST-1.** `IAssetModule` interface that each vertical module implements (Protocol with hooks for domain events, asset details, financials, dashboard widgets, report dimensions, collection tools).
- **FR-CORE-AST-2.** Core NEVER imports module code directly. Communication via Domain Events on an internal event bus (sync in-process for MVP, evolvable to async). Modules register hooks at startup.
- **FR-CORE-AST-3.** Generic `assets` table: `id`, `module_id`, `external_ref`, `display_name`, `status`, `metadata` (JSONB). Contracts reference `asset_id`.
- **FR-CORE-AST-4.** Enable/disable vertical modules in Settings > Modules without restart.
- **FR-CORE-AST-5.** Core lifecycle hooks for domain events: `InstallmentOverdue`, `InstallmentPaid`, `ContractCreated`, `ContractTerminated`, `ReconciliationCompleted`, `CustomerScoreChanged`, `PaymentPartiallyReceived`.

#### Authentication & Access Control (AUTH) — Core

- **FR-CORE-AUTH-1.** Login by email/password with Argon2id hashing and optional MFA (TOTP).
- **FR-CORE-AUTH-2.** Roles: Admin, Operator, Validator, Auditor (read-only), each with scoped capabilities.
- **FR-CORE-AUTH-3.** Granular per-module RBAC (CRUD + sensitive actions). Vertical modules can register additional permissions (e.g., Vehicle Module registers "block vehicle via tracker").
- **FR-CORE-AUTH-4.** Short-lived JWT (15 min) with rotating refresh token (7 days) in `HttpOnly Secure SameSite=Lax` cookie.
- **FR-CORE-AUTH-5.** Audit login/logout, IP, user-agent, failed attempts; lock after 5 failures in 15 min.

#### Generic Registrations (CAD) — Core

- **FR-CORE-CAD-1.** Customer registration with full personal data, validated CPF/CNPJ, ViaCEP address, profile photo, N attachments. Additional fields from vertical modules via schema extension.
- **FR-CORE-CAD-2.** Generic `assets` table (per FR-CORE-AST-3). Each vertical module manages its own detailed asset records and syncs with core `assets`.
- **FR-CORE-CAD-3.** Group assets into generic categories for reporting. Vertical modules can add domain-specific categories.

#### Vehicle Module — Registrations (VH)

- **FR-VH-1.** Vehicle registration with Mercosul plate validation, Renavam, chassis, FIPE binding, tracker code, status, insurance/IPVA/licensing data, photo gallery. Synced with core `assets`.
- **FR-VH-2.** Auto-fetch FIPE via cascading brand/model/year selectors; monthly refresh job (day 5).
- **FR-VH-3.** Vehicle acquisition payment model (cash, financed Price/SAC, consortium, custom).
- **FR-VH-4.** Per-vehicle financials: FIPE value, depreciation, total paid to acquisition, balance, total received, ROI %, payback.
- **FR-VH-5.** Interactive fleet map (Leaflet+OSM, swappable Google Maps) with live positions, popups, block/unblock actions.
- **FR-VH-6.** Schema extension for Customer: CNH (number, category, expiry, photo).
- **FR-VH-7.** Hook `on_installment_overdue`: check parametrized block policy (days overdue >= X AND score < Y), dispatch GPS block via `ITrackerGateway` with mandatory human approval.
- **FR-VH-8.** Additional collection agent tools: `bloquear_veiculo`, `desbloquear_veiculo`, `verificar_localizacao_veiculo` injected via `IAssetModule.get_collection_tools()`.

#### Contracts (CTR) — Core

- **FR-CORE-CTR-1.** Contract linking Customer to Asset (`asset_id`) with full terms (dates, installment model, periodicity, due day, interest, fine, grace, purchase option, guarantees, clauses).
- **FR-CORE-CTR-2.** Visual installment builder: down payment, N regular installments, semestral/annual extras, grace period, custom schedule.
- **FR-CORE-CTR-3.** On finalization (`vigente`): auto-generate titles (`em_aberto`). Contract changes that affect installments cancel open titles and reissue new ones.
- **FR-CORE-CTR-4.** PDF rendering (Jinja2 + WeasyPrint), stored in S3-compatible storage with SHA-256 hash.
- **FR-CORE-CTR-5.** Digital signature (signed-PDF upload; future D4Sign/Clicksign extension point).
- **FR-CORE-CTR-6.** Bulk-edit open installments (postpone, discount, cancel) in atomic transaction with audit event. Paid titles immutable.
- **FR-CORE-CTR-7.** Paid installments (`pago`) are immutable. Corrections require explicit reverse-write-off (Admin-only, audited).
- **FR-CORE-CTR-8.** Contract termination with rescission calculation, final receivable or credit, `ContractTerminated` event for vertical module actions.
- **FR-CORE-CTR-9.** Contract versioning with timeline of revisions.
- **FR-CORE-CTR-10.** Contract simulation without persistence.

#### Receivables (CR) — Core

- **FR-CORE-CR-1.** Master receivables list with multi-select filters (status, customer, asset, contract, date range, value range, competence).
- **FR-CORE-CR-2.** Manual write-off with date, value, method, observation, receipt attachment (mandatory for Pix). Status -> `pago_aguardando_verificacao`.
- **FR-CORE-CR-3.** Partial payments: if paid < title amount, partial write-off + NEW title for the difference with new collection cycle.
- **FR-CORE-CR-4.** Bulk write-off across multiple installments of same customer.
- **FR-CORE-CR-5.** Auto-calculate interest + fine on overdue installments; optional discount with mandatory reason.
- **FR-CORE-CR-6.** Validation queue (Validator/Admin): receipt viewer, expected vs OCR-detected value, Approve/Reject/Request resubmission.
- **FR-CORE-CR-7.** OCR on Pix receipts (Tesseract + regex heuristics) extracting value, date, transaction ID.
- **FR-CORE-CR-8.** State machine: validator approval -> `pago_aguardando_verificacao` -> bank reconciliation -> `pago` (immutable).
- **FR-CORE-CR-9.** Generate Pix QR Code (BR Code) per title, zero cost, via `pix-utils`.
- **FR-CORE-CR-10.** Optional payment gateway integration (Asaas, Efi, PagBank, Stripe) via adapter, disabled by default.
- **FR-CORE-CR-11.** Renegotiation: group overdue titles, recalculate, generate new titles, mark originals `renegociado`.

#### Payables (CP) — Core

- **FR-CORE-CP-1.** Hierarchical expense categories. Core defaults; modules add extras.
- **FR-CORE-CP-2.** Suppliers registry.
- **FR-CORE-CP-3.** One-off Payable with optional asset binding (`asset_id`).
- **FR-CORE-CP-4.** Recurring expenses auto-generating payables.
- **FR-CORE-CP-5.** "Quick Pay" shortcut (create + pay atomically).
- **FR-CORE-CP-6.** Simplified DRE per period, filterable by asset, category, cost center.

#### Smart Collections & WhatsApp Agent (COB) — Core

- **FR-CORE-COB-1.** WhatsApp integration via adapter (default: Evolution API; alternatives: Z-API, UazAPI, WPPConnect, Cloud API).
- **FR-CORE-COB-2.** AI Collection Agent with pluggable LLM, pgvector RAG, core function-calling tools, module-injected tools via `IAssetModule.get_collection_tools()`, persistent memory.
- **FR-CORE-COB-3.** No-code agent parameterization: tone, greetings, cadence, score-based concession, escalation, templates. Modules register additional policies.
- **FR-CORE-COB-4.** Customer score (0-100) from punctuality, overdue days, tenure, paid value. Modules contribute additional factors. Formula configurable.
- **FR-CORE-COB-5.** Auto-send Pix QR via WhatsApp (default payment flow: Pix card -> direct payment -> screenshot -> OCR -> validation -> write-off).
- **FR-CORE-COB-6.** On inbound media: classify, OCR, match to title, partial or full write-off (`pago_aguardando_verificacao`), reply, enqueue for human validation.
- **FR-CORE-COB-7.** WhatsApp-style in-app inbox (3-pane: conversations / chat / customer context).
- **FR-CORE-COB-8.** Manager can intercept ("human takes over"), pause/resume agent.
- **FR-CORE-COB-9.** Mass dispatch with double confirmation, preview, time-window, rate limiting.
- **FR-CORE-COB-10.** Immutable message history with external provider IDs.

#### Bank Reconciliation (CON) — Core

- **FR-CORE-CON-1.** OFX import with FITID deduplication.
- **FR-CORE-CON-2.** PDF statement import (major Brazilian banks) via pdfplumber + optional LLM fallback.
- **FR-CORE-CON-3.** Open Finance adapter (default Pluggy; alternatives Belvo, TecnoSpeed, Klavi), disabled by default.
- **FR-CORE-CON-4.** Reconciliation screen with split panes + drag-and-drop match zone + auto-suggestions.
- **FR-CORE-CON-5.** Auto-match algorithm with configurable confidence threshold.
- **FR-CORE-CON-6.** Support 1:N, N:1, and unmatched-as-payable/revenue.
- **FR-CORE-CON-7.** Divergence panel: orphan transactions, paid titles without bank entry, value mismatches.
- **FR-CORE-CON-8.** Final reconciliation -> title `pago` (immutable), transaction `conciliada` (locked).

#### Dashboards & Reports (DSH) — Core

- **FR-CORE-DSH-1.** Main Dashboard with generic reactive KPI cards (Signals). Modules inject widgets via `IAssetModule.get_dashboard_widgets()`.
- **FR-CORE-DSH-2.** Customer Financial Dashboard.
- **FR-CORE-DSH-3.** Pre-built exportable reports (Excel/PDF). Modules register additional reports via `IAssetModule.get_report_dimensions()`.
- **FR-CORE-DSH-4.** Custom report builder with drag-and-drop dimensions/measures, saved favorites.

#### Vehicle Module — Dashboards & Reports (VH)

- **FR-VH-9.** Vehicle Dashboard widget: investment, ROI %, profit, depreciation, acquisition vs return, KM, productivity, driver history.
- **FR-VH-10.** Additional reports: Top Vehicles by ROI, Block History, Fleet Position snapshot.
- **FR-VH-11.** Main Dashboard injected widgets: Fleet Total (R$ FIPE), Active Vehicles, Parked, In Maintenance.

#### Integrations & Plug-and-Play (INT) — Core

- **FR-CORE-INT-1.** Ports (Protocols) for all external providers: `IWhatsAppGateway`, `IBankReconciliationProvider`, `IPaymentGateway`, `ILLMProvider`, `IStorageProvider`, `IOcrProvider`, `IPdfRenderer`. Modules define additional ports.
- **FR-CORE-INT-2.** Admin Integrations screen: activate/deactivate adapters, encrypted credentials, test connection, status indicator.
- **FR-CORE-INT-3.** Webhook ingestion for all providers with signature validation, idempotency, processing queue.

#### Vehicle Module — Integrations (VH)

- **FR-VH-12.** `IFipeProvider` with default `ApiFipeBrAdapter`, alternative `FipeApiBrAdapter`, fallback. 30-day Redis cache.
- **FR-VH-13.** `ITrackerGateway` with generic REST/MQTT adapters for GPS position, block/unblock. Double approval + audit for block commands.

#### Parameterization (PRM) — Core

- **FR-CORE-PRM-1.** Centralized Settings screen with sections: General, Company, Billing, AI Agent, Integrations, Modules, Users, Permissions, Templates, Audit.
- **FR-CORE-PRM-2.** Versioned configuration with change history.

#### Auditing (AUD) — Core

- **FR-CORE-AUD-1.** Append-only audit log for all relevant operations. Modules register additional actions.
- **FR-CORE-AUD-2.** Searchable audit log with filters and export.
- **FR-CORE-AUD-3.** HMAC-signed entries for tamper detection.

### Non-Functional Requirements

- **NFR-1 (Performance).** P95 read <= 300 ms, write <= 500 ms, dashboard render <= 1.5 s on 4G.
- **NFR-2 (Scalability).** 10k assets / 50k active titles / 100k WhatsApp messages/month without restructuring.
- **NFR-3 (Availability).** SLA 99.5%.
- **NFR-4 (Security).** OWASP ASVS Level 2; Argon2id; JWT RS256; AES-256-GCM at rest; TLS 1.3; security headers; rate limiting.
- **NFR-5 (LGPD).** Data export + deletion; consent; PII access logs.
- **NFR-6 (Financial Auditability).** Every state change on a financial title generates an immutable event; reconciliation is reproducible.
- **NFR-7 (Observability).** JSON structured logs, Prometheus, OpenTelemetry, Grafana.
- **NFR-8 (Accessibility).** WCAG 2.1 AA.
- **NFR-9 (i18n).** pt-BR default; ready for en-US/es-ES.
- **NFR-10 (Plug-and-Play).** Switching a provider = config + new adapter, zero domain change. Adding a module = implement `IAssetModule`, zero core change.
- **NFR-11 (Mobile-First).** Responsive; PWA-ready.
- **NFR-12 (Real-time).** Chat, receipts, title status in UI <= 2 s without refresh.
- **NFR-13 (Backup & DR).** Daily full + continuous WAL; RPO <= 1h, RTO <= 4h.
- **NFR-14 (Cost).** Default stack 100% open-source; no mandatory paid SaaS.
- **NFR-15 (Modular Verticals).** Core works fully without any vertical module active (billing-only mode). Each module independently enable/disable.

### Additional Requirements

- **Greenfield, two-directory structure:** `backend-api/` (FastAPI) and `frontend/` (Angular) under a project root with `docker-compose.yml`. No product name in folder or package names. Product name injected via `PRODUCT_NAME` env var.
- **Hexagonal Architecture non-negotiable:** every external provider behind a Protocol in `app/domain/ports/`; domain never imports `infrastructure/`.
- **Tech stack locked** by Architecture doc; new tech requires approved ADR.
- **PostgreSQL extensions:** `pgcrypto`, `pg_trgm`, `unaccent`, `pgvector` enabled in first migration.
- **DB triggers:** `audit_log` append-only trigger, `installments` `enforce_paid_immutability` trigger in first migrations.
- **Materialized view `mv_asset_roi`:** required for asset ROI dashboards; refreshed by scheduled job. Vehicle Module extends with vehicle-specific columns.
- **Encryption at rest:** AES-256-GCM for CPF, CNH, MFA secrets, integration credentials.
- **Webhook idempotency:** `webhook_events_raw` with `UNIQUE(provider, external_id)` mandatory before any provider integration.
- **Real-time:** SSE default; WebSocket only for chat; polling as degraded fallback.
- **Celery Beat schedule:** monthly FIPE refresh (Vehicle Module), daily score recompute, daily preventive collection, daily recurring-payables generation, daily backup, hourly auto-match reconciliation.
- **Excel one-shot import:** CLI `python -m app.cli import-excel` with idempotent re-runs and `--dry-run`.
- **LGPD endpoints:** customer data export and anonymization.
- **Security headers + Edge controls:** TLS 1.3, HSTS, rate limiting, CSP, etc.
- **Observability stack:** Prometheus, OpenTelemetry, structlog, Grafana dashboards.
- **Testing pyramid:** unit 55% / integration 25% / component+contract 15% / E2E 5%.
- **Branching:** features on `feat/{epic}-{story}-{slug}`; Conventional Commits; `main` protected.
- **Cost guardrails:** LLM spend metric with daily-budget alert and automatic fallback.

### UX Design Requirements

_No standalone UX Design Specification is present. UI/UX guidance is embedded in PRD Section 3 and Architecture Section 10. When a dedicated UX spec is delivered, this section should be backfilled._

### FR Coverage Map

| Requirement | Epic | Notes |
|---|---|---|
| FR-CORE-AST-1 (IAssetModule interface) | Epic 1 | Story 1.8 |
| FR-CORE-AST-2 (event bus, no direct imports) | Epic 1 | Story 1.8 |
| FR-CORE-AST-3 (generic assets table) | Epic 1 | Story 1.8 |
| FR-CORE-AST-4 (enable/disable modules without restart) | Epic 1 | Story 1.8 |
| FR-CORE-AST-5 (lifecycle hooks for domain events) | Epic 1 | Story 1.8 |
| FR-CORE-AUTH-1 (login email/password + Argon2id + MFA) | Epic 1 | — |
| FR-CORE-AUTH-2 (roles Admin/Operator/Validator/Auditor) | Epic 1 | — |
| FR-CORE-AUTH-3 (granular RBAC per module) | Epic 1 | Permissions populated progressively per epic |
| FR-CORE-AUTH-4 (JWT 15min + refresh HttpOnly 7d) | Epic 1 | — |
| FR-CORE-AUTH-5 (audit login + lock after 5 failures) | Epic 1 | — |
| FR-CORE-CAD-1 (Customer with CPF/attachments + module extensions) | Epic 2A | — |
| FR-CORE-CAD-2 (generic assets table sync) | Epic 2A | — |
| FR-CORE-CAD-3 (asset categories) | Epic 2A | — |
| FR-VH-1 (Vehicle registration synced with core assets) | Epic 2B | — |
| FR-VH-2 (auto-fetch FIPE + monthly job) | Epic 2B | Depends on FR-VH-12 |
| FR-VH-3 (vehicle acquisition payment model) | Epic 2B | — |
| FR-VH-4 (per-vehicle financials: ROI, depreciation) | Epic 2B | Materialized view finalized in Epic 8 |
| FR-VH-5 (interactive fleet map) | Epic 2B | Depends on FR-VH-13 |
| FR-VH-6 (CNH schema extension for Customer) | Epic 2B | — |
| FR-VH-7 (hook on_installment_overdue: GPS block) | Epic 2B | — |
| FR-VH-8 (collection agent tools: block/unblock/locate) | Epic 2B | Injected at agent startup in Epic 6 |
| FR-CORE-CTR-1 (Contract linking Customer to Asset) | Epic 3 | — |
| FR-CORE-CTR-2 (visual installment builder) | Epic 3 | — |
| FR-CORE-CTR-3 (auto-generate titles on finalization; reissue on change) | Epic 3 | — |
| FR-CORE-CTR-4 (PDF Jinja2 + WeasyPrint + SHA-256) | Epic 3 | — |
| FR-CORE-CTR-5 (digital signature extension point) | Epic 3 | — |
| FR-CORE-CTR-6 (bulk-edit open installments; paid immutable) | Epic 3 | — |
| FR-CORE-CTR-7 (paid immutability + reverse-write-off) | Epic 3 | PG trigger ships with model |
| FR-CORE-CTR-8 (contract termination with rescission) | Epic 3 | — |
| FR-CORE-CTR-9 (contract versioning timeline) | Epic 3 | — |
| FR-CORE-CTR-10 (contract simulation) | Epic 3 | — |
| FR-CORE-CR-1 (master receivables list) | Epic 4 | — |
| FR-CORE-CR-2 (manual write-off with receipt) | Epic 4 | — |
| FR-CORE-CR-3 (partial payments: write-off + new title for difference) | Epic 4 | — |
| FR-CORE-CR-4 (bulk write-off) | Epic 4 | — |
| FR-CORE-CR-5 (interest/fine + manual discount) | Epic 4 | — |
| FR-CORE-CR-6 (validation queue) | Epic 4 | — |
| FR-CORE-CR-7 (OCR on Pix receipts) | Epic 4 | Depends on FR-CORE-INT-1 (IOcrProvider) |
| FR-CORE-CR-8 (state machine: pago_aguardando_verificacao -> pago) | Epic 4 | Final state `pago` achieved in Epic 7 |
| FR-CORE-CR-9 (Pix QR Code BR Code) | Epic 4 | — |
| FR-CORE-CR-10 (optional payment gateway adapter) | Epic 4 | Disabled by default |
| FR-CORE-CR-11 (renegotiation of overdue titles) | Epic 4 | — |
| FR-CORE-CP-1 (hierarchical expense categories) | Epic 5 | — |
| FR-CORE-CP-2 (suppliers registry) | Epic 5 | — |
| FR-CORE-CP-3 (one-off Payable) | Epic 5 | — |
| FR-CORE-CP-4 (recurring expenses) | Epic 5 | — |
| FR-CORE-CP-5 ("Quick Pay" shortcut) | Epic 5 | — |
| FR-CORE-CP-6 (simplified DRE) | Epic 5 | — |
| FR-CORE-COB-1 (WhatsApp adapter: Evolution/Z-API/etc.) | Epic 6 | — |
| FR-CORE-COB-2 (AI Agent with LLM + RAG + core tools + module tools) | Epic 6 | Module tools injected via IAssetModule |
| FR-CORE-COB-3 (no-code agent parameterization + module policies) | Epic 6 | — |
| FR-CORE-COB-4 (customer score 0-100 with module factors) | Epic 6 | Daily job |
| FR-CORE-COB-5 (auto-send Pix QR via WhatsApp) | Epic 6 | Reuses FR-CORE-CR-9 |
| FR-CORE-COB-6 (inbound receipt: classify, OCR, partial/full write-off) | Epic 6 | — |
| FR-CORE-COB-7 (3-pane WhatsApp inbox) | Epic 6 | WebSocket `/ws/conversations` |
| FR-CORE-COB-8 (human intercept / pause-resume agent) | Epic 6 | — |
| FR-CORE-COB-9 (mass dispatch with controls) | Epic 6 | — |
| FR-CORE-COB-10 (immutable message history) | Epic 6 | — |
| FR-CORE-CON-1 (OFX importer) | Epic 7 | — |
| FR-CORE-CON-2 (PDF statement importer) | Epic 7 | LLM fallback configurable |
| FR-CORE-CON-3 (Open Finance via Pluggy/Belvo/etc.) | Epic 7 | Disabled by default |
| FR-CORE-CON-4 (split-pane drag-and-drop reconciliation) | Epic 7 | — |
| FR-CORE-CON-5 (auto-match algorithm) | Epic 7 | — |
| FR-CORE-CON-6 (1:N, N:1, unmatched-as-payable/revenue) | Epic 7 | — |
| FR-CORE-CON-7 (divergence panel) | Epic 7 | — |
| FR-CORE-CON-8 (final reconciliation -> pago immutable) | Epic 7 | — |
| FR-CORE-DSH-1 (Main Dashboard with generic KPIs + module widgets) | Epic 8 | SSE refresh |
| FR-CORE-DSH-2 (Customer Dashboard) | Epic 8 | — |
| FR-CORE-DSH-3 (pre-built reports + module reports) | Epic 8 | — |
| FR-CORE-DSH-4 (custom report builder) | Epic 8 | — |
| FR-VH-9 (Vehicle Dashboard: ROI/payback/depreciation) | Epic 8 | Refreshes mv_asset_roi |
| FR-VH-10 (Vehicle-specific reports) | Epic 8 | — |
| FR-VH-11 (Main Dashboard injected widgets: fleet KPIs) | Epic 8 | Via get_dashboard_widgets() |
| FR-CORE-INT-1 (Ports/Protocols for all providers) | Cross-cutting | Each Port created in the epic that first needs it; completeness audit in Epic 9 |
| FR-CORE-INT-2 (Admin Integrations screen) | Epic 9 | Centralized panel |
| FR-CORE-INT-3 (webhook ingestion framework) | Cross-cutting | `webhook_events_raw` in Epic 1; each provider adds webhook in its epic |
| FR-VH-12 (FIPE provider with cache + fallback) | Epic 2B | — |
| FR-VH-13 (Tracker gateway REST/MQTT + block commands) | Epic 2B | — |
| FR-CORE-PRM-1 (centralized Settings) | Cross-cutting | Each epic creates its tab; consolidated in Epic 9 |
| FR-CORE-PRM-2 (versioned configuration) | Epic 9 | — |
| FR-CORE-AUD-1 (append-only audit log + module events) | Epic 1 (infra) -> all epics (events) | Table + trigger in Epic 1 |
| FR-CORE-AUD-2 (searchable audit log + export) | Epic 9 | Full UI |
| FR-CORE-AUD-3 (HMAC-signed entries) | Epic 1 (HMAC) -> Epic 9 (verifier UI) | — |

## Epic List

| # | Epic | Type | Outcome in 1 line |
|---|---|---|---|
| 1 | **Foundation & Identity** | Core | Team has foundation running (auth, layout, Asset Abstraction Layer, CI/CD green) — admin logs in and navigates. |
| 2A | **Core Asset Management & Registrations** | Core | Generic client and asset management infrastructure is ready; vertical modules can plug in. |
| 2B | **Vehicle Module: Registrations & Integrations** | Vehicle Module | Vehicle Module registered as IAssetModule; fleet on a real-time map; FIPE valuations auto-refreshed. |
| 3 | **Contracts & Flexible Installments** | Core | Manager generates any contract shape with PDF and linked titles; bulk-edits open titles; paid titles immutable; changes reissue open titles. |
| 4 | **Receivables, Partial Payments & Validation** | Core | Manager runs receivables with partial payment support, receipt validation queue, OCR, free Pix QR — zero-cost default payment flow. |
| 5 | **Payables & Recurring Expenses** | Core | Manager controls outgoing expenses with recurrences, Quick Pay, and visible DRE. |
| 6 | **WhatsApp Inbox & AI Collection Agent** | Core + Module Hooks | Agent runs collections with parametrized policy and module-injected tools; humans intervene at will. |
| 7 | **Sophisticated Bank Reconciliation** | Core | OFX/PDF/Open Finance reconciliation in minutes with drag-and-drop; erroneous write-offs -> zero. |
| 8 | **Dashboards, Reports & Asset Analytics** | Core + Module Hooks | Manager reads operational pulse in seconds; per-asset ROI drives decisions. Module widgets injected. |
| 9 | **Hardening & Plug-and-Play Final** | Core | System enters production with operational confidence; switching a provider is trivial; modules documented. |

---

## Epic 1: Foundation & Identity (Core)

**Goal:** Bring the technical skeleton up in dev and prod with working login, navigable base layout, dark/light theme, Asset Abstraction Layer (`IAssetModule` + event bus + Module Hook registration), and a green CI/CD pipeline — without any domain features yet. By the end, any developer can clone, boot the environment, and reach the authenticated "Hello, X" screen. The core is ready to accept vertical modules.

**Premises:** Directories `backend-api/` and `frontend/` created. Docker Compose with Postgres + Redis + MinIO for local dev. GitHub Actions enabled.

### Story 1.1: Bootstrap the FastAPI Backend (Core)

As a Developer,
I want a FastAPI skeleton wired with Postgres, Alembic, Pydantic v2, and a modular layout,
So that future features have a solid, standardized foundation.

**Acceptance Criteria:**

1. Directory `backend-api/` with Python 3.12+, managed by `uv` (fallback `poetry`).
2. Directory layout: `app/{api,core,domain,infrastructure,modules,workers,tests}` plus `alembic/`. The `modules/` directory will contain vertical modules (initially empty with `__init__.py`).
3. **Given** the API is running, **When** `GET /health` is called, **Then** the response returns `{"status":"ok","db":"ok","redis":"ok","storage":"ok"}` with a real check on each dependency.
4. Alembic configured with first empty migration applied via `alembic upgrade head`.
5. Configuration via Pydantic Settings from `.env` (dev) and environment variables (prod). Secrets never committed. `PRODUCT_NAME` as a configuration variable.
6. Structured JSON logs (`structlog`) emitted to stdout.
7. CORS configured for `http://localhost:4200`.
8. OpenAPI at `/docs` (Swagger) and `/redoc`.
9. Multi-stage Dockerfile (build -> runtime) producing image <= 250 MB.
10. `docker-compose.yml` boots API + Postgres + Redis + MinIO in <= 30 s.
11. `docker-compose.yml` includes `worker` service (Celery worker) and `beat` service (Celery Beat scheduler), both using the same backend-api image with different commands. Worker listens on queues: `default,high,low,events,agent,ocr`.
12. WeasyPrint system dependencies (libpangocairo, libcairo2, libgdk-pixbuf, tesseract-ocr, tesseract-ocr-por) are included in the Dockerfile runtime stage to support future PDF generation and OCR stories.

### Story 1.2: Bootstrap the Angular 21 Frontend (Core)

As a Developer,
I want an Angular 21 standalone skeleton wired with Tailwind v4, Heroicons, and the manifesto-driven folder structure,
So that features are built consistently from day one.

**Acceptance Criteria:**

1. Angular 21+ standalone project in `frontend/`; no NgModules.
2. `src/app/` matches the manifesto: `core`, `shared`, `features`. No `assets/` in `src/` — `public/` at root.
3. Tailwind CSS v4 with `tailwind.config`, typography + forms plugins.
4. `styles.css` with import Tailwind and `@theme` block with **all** CSS variables listed in PRD Section 3.5 (light + dark).
5. `theme.service.ts` in `core/services/` with `theme()` signal and `setTheme('light'|'dark'|'system')`, persisting to localStorage.
6. `@ng-icons/core` + `@ng-icons/heroicons` installed; `<ui-icon name="HeroXMark" />` in `shared/components/icon/`.
7. `AppShellComponent` in `shared/components/app-shell/` with collapsible sidebar, header with theme toggle and product name (via `environment.productName`), `<router-outlet>`.
8. Routes: `/login`, `/dashboard` (placeholder), `/404`.
9. ESLint + Prettier + stylelint; `npm run lint` passes.
10. `index.html` with PWA meta tags and `manifest.webmanifest` placeholder (`name` from build config, never hardcoded).

### Story 1.3: User Identity Tables and Initial Migration (Core)

As a Developer,
I want `users`, `roles`, `permissions`, `user_roles`, `refresh_tokens`, and `audit_log` tables created,
So that the identity system has persistent storage and audit starts from day one.

**Acceptance Criteria:**

1. SQLAlchemy models in `app/infrastructure/db/models/` with UUID PKs via `gen_random_uuid()`, `TIMESTAMPTZ` timestamps, soft-delete via `deleted_at`.
2. Migration enables `pgcrypto`, `pg_trgm`, `unaccent`, `pgvector` extensions.
3. `users` table: `id`, `email` (CITEXT unique), `password_hash`, `full_name`, `is_active`, `is_mfa_enabled`, `mfa_secret_enc` (BYTEA nullable), `last_login_at`, `created_at`, `updated_at`, `deleted_at`.
4. `audit_log` table: `id`, `user_id`, `action`, `entity`, `entity_id`, `payload_before`, `payload_after`, `ip`, `user_agent`, `correlation_id`, `signature_hmac`, `created_at`. Append-only PG trigger blocking UPDATE/DELETE.
5. Indexes: `users.email` unique, `audit_log(user_id, created_at DESC)`, `audit_log(entity, entity_id)`.
6. **Given** a fresh DB, **When** `python -m app.cli seed` runs, **Then** the four roles `Admin`, `Operador`, `Validador`, `Auditor` are inserted, an Admin user `admin@app.local` (password `Admin@123`) is created and linked to the Admin role. Permissions seeded incrementally per epic.
7. `audit_log` table includes columns `module` (TEXT), `category` (TEXT, default 'info' — values: financial/navigation/error/info/security), `severity` (TEXT, default 'info' — values: debug/info/warning/error/critical). Financial and security categories are always persisted; navigation is configurable OFF by default.

### Story 1.4: Login Endpoint with JWT (Core)

As an Admin user,
I want to log in with email and password and receive JWT tokens,
So that I can access protected resources.

**Acceptance Criteria:**

1. **Given** valid credentials, **When** `POST /api/v1/auth/login` is called, **Then** response returns `{access_token, refresh_token, user}` with 200.
2. Passwords verified with Argon2id; failures in <= 200 ms (constant-time); generic `401 Unauthorized`.
3. JWT RS256 with claims `sub`, `email`, `roles`, `iat`, `exp` (15 min), `iss`, `aud`.
4. Refresh token in `HttpOnly Secure SameSite=Lax` cookie, 7 days, rotation on every use.
5. `POST /api/v1/auth/refresh` consumes cookie, invalidates old token, emits new pair.
6. `POST /api/v1/auth/logout` invalidates refresh token (Redis revocation list).
7. **Given** 5 failed attempts in 15 min, **When** 6th arrives, **Then** `429 Too Many Requests` for 15 min.
8. Login events recorded in `audit_log` with HMAC signature.
9. Unit tests: success, wrong password, inactive user, MFA path, rate limit.

### Story 1.5: Login Screen on the Frontend (Core)

As a User,
I want a polished login screen,
So that I can sign in securely with a great first impression.

**Acceptance Criteria:**

1. `LoginComponent` in `features/auth/login/` with three files (TS/HTML/CSS).
2. Reactive Forms (typed) with email (required + email) and password (required, min 8).
3. **Given** the form is invalid, **When** "Entrar" is clicked, **Then** the button stays disabled.
4. Spinner while request is in-flight.
5. **Given** 401, **Then** toast "Credenciais invalidas" and focus returns to email.
6. **Given** 200, **Then** access token stored in `authState()` signal, navigate to `/dashboard`.
7. Visual: centered card with glassmorphism, product name (via `environment.productName`) on top, gradient background, illustration at desktop.
8. `Enter` submits; initial focus on email; visible focus indicators.
9. "Esqueci minha senha" link to `/auth/forgot-password` (placeholder).
10. Playwright E2E: success navigates to `/dashboard`; failure stays with toast.

### Story 1.6: AuthGuard, JWT Interceptor and Silent Refresh (Core)

As the System,
I want protected routes to require authentication and tokens refreshed transparently,
So that the user experience is uninterrupted.

**Acceptance Criteria:**

1. `auth.guard.ts` in `core/guards/` blocks routes when `authState().isAuthenticated()` is false, redirecting to `/login?redirect=...`.
2. `jwt.interceptor.ts` in `core/interceptors/` injects `Authorization: Bearer <token>`.
3. **Given** 401, **Then** attempt `POST /auth/refresh` once, replay on success, clear state and redirect on failure.
4. **Given** multiple concurrent 401s, **Then** only one refresh fires (lock).
5. On logout: clear state and cookie, navigate to `/login`.

### Story 1.7: Initial CI/CD Pipeline (Core)

As the Team,
I want CI checks running lint, type-check, tests, and build on every PR,
So that regressions are caught early.

**Acceptance Criteria:**

1. `.github/workflows/api-ci.yml`: ruff, mypy strict, pytest with coverage, Docker build.
2. `.github/workflows/web-ci.yml`: eslint, `ng build --configuration=production`, vitest.
3. `main` branch protected: PR + 1 review + all green checks.
4. Backend coverage minimum 70%.
5. Total CI duration <= 10 min.

### Story 1.8: Asset Abstraction Layer Bootstrap (Core)

As a Developer,
I want the `IAssetModule` interface defined, the event bus implemented, and Module Hook registration working,
So that vertical modules can plug in without altering the core.

**Acceptance Criteria:**

1. `IAssetModule` Protocol defined in `app/core/assets/module_interface.py` per FR-CORE-AST-1, with complete type hints including `handles_event(event_type) -> bool` for capability declaration, all hook methods returning `list[Action]`, and utility methods (`get_asset_schema`, `get_dashboard_widgets`, `get_report_dimensions`, `get_agent_tools`, `get_score_factors`, `get_custom_routes`).
2. **Asynchronous event bus via Celery** implemented in `app/core/events/event_bus.py`. `publish(event)` enqueues a Celery task `handle_domain_event` on the `events` queue. The Celery worker deserializes the event, checks `active_modules.is_active` + `module_hooks_config.is_active` + module's `handles_event()`, and dispatches to the hook.
3. Domain Events defined in `app/core/events/domain_events.py` as frozen dataclasses inheriting `DomainEvent(event_id, occurred_at, asset_type)`: `ContractCreatedEvent`, `ContractTerminatedEvent`, `InstallmentOverdueEvent`, `InstallmentPaidEvent`, `ReconciliationCompletedEvent`, `CustomerScoreChangedEvent`, `PaymentPartiallyReceivedEvent`.
4. Module Hook registration in `app/core/assets/registry.py`: `register_module()`, `get_module()`, `list_modules()`, `is_module_active()`, `get_tools_for_context(caller_permissions, module_id)`. Modules register at **boot time only**; runtime toggling via `active_modules.is_active` in DB.
5. `assets` table: `id` UUID PK, `module_id`, `external_ref`, `display_name`, `status` (`disponivel`/`em_uso`/`manutencao`/`inativo`), `metadata` (JSONB), timestamps, soft delete.
6. `active_modules` table: `module_id` PK, `is_active`, `config` (JSONB), `registered_at`.
7. `module_hooks_config` table: `id` UUID PK, `module_id` FK, `event_type`, `policy` (JSONB), `is_active`.
8. `event_log` table: `id` BIGSERIAL PK, `event_id` UUID UNIQUE, `event_type`, `asset_type`, `payload` (JSONB), `dispatched_at`, `processed_at`, `processing_status` (`pending`/`processing`/`completed`/`failed`), `error`. Supports replay and debugging.
9. **Every hook handler MUST be idempotent** — check state before acting; `event_log.event_id` UNIQUE prevents double-processing.
10. **Core never JOINs module-specific tables.** Module data is accessed via `get_asset_details(asset_id)`.
11. Unit tests with `task_always_eager=True`: register MockModule, publish event, verify handler called; verify inactive module skipped; verify duplicate `event_id` is ignored.

### Story 1.9: SSE Infrastructure (Core)

As a Developer,
I want SSE endpoints with Redis Pub/Sub dispatch and token-based auth,
So that real-time notifications work across all features.

**Acceptance Criteria:**

1. SSE endpoint `GET /sse/notifications` implemented using `sse-starlette` with Redis Pub/Sub backend.
2. Auth via query param `?token=<jwt>` (EventSource doesn't support headers).
3. `SseService` in `backend-api/app/api/sse.py` subscribes to Redis channel `sse:user:{user_id}`.
4. Reconnection handled natively by EventSource; server sends `retry: 3000` directive.
5. Frontend `SseService` in `frontend/src/app/core/services/sse.service.ts` wraps EventSource with `connected` signal and `lastEvent` signal.
6. Unit test: publish to Redis channel, verify SSE client receives the event.

### Story 1.10: Password Recovery Flow (Core)

As a User,
I want to reset my password via email,
So that I can regain access if I forget my credentials.

**Acceptance Criteria:**

1. `POST /api/v1/auth/password/forgot` accepts `{email}` and sends a reset link via email (configurable SMTP or adapter).
2. `POST /api/v1/auth/password/reset` accepts `{token, new_password}` and resets the password.
3. Reset tokens expire in 1 hour, are single-use, and stored hashed in Redis.
4. `IEmailSender` port defined in `app/domain/ports/email_sender.py` with `SmtpAdapter` default and `ConsoleAdapter` for dev (prints to stdout).
5. Frontend `ForgotPasswordComponent` and `ResetPasswordComponent` in `features/auth/`.
6. Audit log records password reset events.

---

## Epic 2A: Core Asset Management & Registrations (Core)

**Goal:** The manager can register customers and the generic asset infrastructure is ready. The core manages clients and delegates asset details to vertical modules via `IAssetModule`. Module-aware UI shows only relevant content based on active modules.

### Story 2A.1: Customer Domain Model and CRUD API (Core)

As a Backend developer,
I want a Customer entity with complete REST endpoints,
So that the frontend can manage the customer base.

**Acceptance Criteria:**

1. `Customer` model with generic fields: full name, CPF/CNPJ (validated), phone (E.164), email, full address, birth date, photo, notes, `score` (default 100), `status` (`ativo`/`inativo`/`bloqueado`), `tags` (JSONB), `metadata_extensions` (JSONB for module-injected fields), `created_by_user_id`.
2. CPF/CNPJ validated and unique; email unique; phone normalized to E.164.
3. Endpoints: `POST /api/v1/customers`, `GET /api/v1/customers?search=&status=&page=&size=`, `GET /api/v1/customers/{id}`, `PATCH /api/v1/customers/{id}`, `DELETE /api/v1/customers/{id}` (soft delete), `POST /api/v1/customers/{id}/attachments`.
4. Attachments stored in MinIO at `customers/{id}/{uuid}-{filename}` with record in `customer_attachments`.
5. Every mutation writes to `audit_log` with HMAC signature.
6. Integration tests covering CRUD + attachment upload.

### Story 2A.2: Customers List Screen (Core)

As a Manager,
I want to browse all customers in a searchable, filterable table,
So that I find anyone in seconds.

**Acceptance Criteria:**

1. `CustomersListComponent` in `features/system/customers/`.
2. Columns: avatar, name, masked CPF/CNPJ (last 3 visible), phone (WhatsApp shortcut), score (colored badge), status (badge), last update, row actions (view, edit, delete).
3. Text search debounced 300 ms, signal-driven.
4. Filters: status (multi-select), tag (multi-select), score (range slider).
5. URL state: filters in query string.
6. Server-side pagination via signals, preferably using `resource()` API.
7. "Novo Cliente" opens drawer with `CustomerFormComponent`.
8. Skeleton loader during fetch; empty state with illustration and CTA.
9. Keyboard shortcuts: `/` focuses search, `n` opens new, arrows walk rows, `Enter` opens detail.

### Story 2A.3: Customer Create/Edit Drawer (Core)

As a Manager,
I want an ergonomic form to create or edit a customer,
So that registration is fast.

**Acceptance Criteria:**

1. Form in 3 collapsible sections: Personal Data, Documents, Contact & Address. Vertical modules can inject additional sections (e.g., Vehicle Module injects "CNH" section).
2. Inline validation (Reactive Forms typed).
3. CEP auto-fills via ViaCEP.
4. Photo: drop-zone with circular crop preview.
5. Attachments: multi-file drop-zone with previews.
6. Save closes drawer and refreshes list; error shows toast and preserves form.
7. Accessible: tab order correct, focus to first invalid on submit, `Esc` closes (confirm if dirty).

### Story 2A.4: Customer Detail Page with Tabs (Core)

As a Manager,
I want to see the full life of a customer on one page,
So that I have complete context before any decision.

**Acceptance Criteria:**

1. Route `/system/customers/:id` renders `CustomerDetailComponent`.
2. Header: avatar, name, CPF/CNPJ, large score visual, status, primary actions (Edit, WhatsApp Message).
3. Core tabs: **Overview**, **Contracts**, **Receivables**, **Score**, **Documents**, **Conversations**, **Audit**. Vertical modules can inject additional tabs. Each tab lazy-loaded.
4. Overview: metric cards (total contracted, received, open balance, upcoming), event timeline.
5. URL preserves active tab via `?tab=...`.

### Story 2A.5: Generic Assets List (Core)

As a Manager,
I want to see all assets registered in the platform,
So that I have a consolidated view regardless of module.

**Acceptance Criteria:**

1. Route `/system/assets` lists records from the `assets` table with columns: name, module (badge), status, last update, actions.
2. Filters: module type (multi-select), status, text search.
3. Click redirects to the detail page rendered by the corresponding vertical module.
4. If no vertical module is active, empty state: "Activate a vertical module in Settings > Modules to start registering assets."

### Story 2A.6: Excel One-Shot Importer — Customers (Core)

As a Manager going live,
I want to import existing customers from a spreadsheet,
So that I don't re-type dozens of records.

**Acceptance Criteria:**

1. CLI `python -m app.cli import-excel --entity=customers --file=clientes.xlsx --sheet=Clientes` maps columns into `customers` table.
2. **Given** `--dry-run` flag, **Then** validates and prints diff report without persisting.
3. **Given** re-run with same input, **When** existing records found by CPF, **Then** updated (not duplicated).
4. End-of-run report: created, updated, skipped (with reasons).
5. Import writes a summary `audit_log` entry.

---

## Epic 2B: Vehicle Module — Registrations & Integrations (Vehicle Module)

**Goal:** The Vehicle Module is implemented and registered as `IAssetModule`. The manager can register vehicles, see the fleet on a real-time map, and FIPE valuations are auto-refreshed. The module reacts to domain events via hooks. By the end, the vehicle registration spreadsheet is replaceable.

### Story 2B.1: Vehicle Module Structure and IAssetModule Registration (Vehicle Module)

As a Developer,
I want the Vehicle Module structured and registered in the core,
So that it receives domain events and injects domain-specific functionality.

**Acceptance Criteria:**

1. Directory `backend-api/app/modules/vehicles/` with: `__init__.py`, `module.py` (IAssetModule implementation), `models.py`, `routes.py`, `services.py`, `hooks.py`, `ports/`, `adapters/`.
2. Class `VehicleModule(IAssetModule)` implements all interface methods: `on_contract_created`, `on_contract_terminated`, `on_installment_overdue`, `on_installment_paid`, `on_reconciliation_completed`, `get_asset_details`, `get_asset_financials`, `get_dashboard_widgets`, `get_report_dimensions`, `get_collection_tools`.
3. Module registered at startup via `register_module(VehicleModule())`.
4. Entry in `active_modules`: `module_id='vehicles'`, `is_active=True`.
5. Tests: publish `InstallmentOverdueEvent` -> Vehicle Module hook is called.

### Story 2B.2: FIPE Provider Adapter (Vehicle Module)

As the System,
I want an `IFipeProvider` Port with concrete adapters,
So that the FIPE supplier is swappable.

**Acceptance Criteria:**

1. `IFipeProvider` Protocol in `app/modules/vehicles/ports/fipe.py` with `list_brands`, `list_models`, `list_years`, `get_price`.
2. `ApiFipeBrAdapter` (default) in `app/modules/vehicles/adapters/fipe/apifipe_br.py`.
3. `FipeApiBrAdapter` (alternative) in `app/modules/vehicles/adapters/fipe/fipeapi_br.py`.
4. Fallback adapter: primary -> secondary on error.
5. Redis cache with 30-day TTL per key `fipe:{type}:{brand}:{model}:{year}`.
6. Endpoints: `GET /api/v1/modules/vehicles/fipe/{brands|models|years|price}`.
7. Active adapter selected via `FIPE_PROVIDER` env var.

### Story 2B.3: Vehicle Domain Model, FIPE Integration, and Acquisition (Vehicle Module)

As a Backend developer,
I want a Vehicle entity with CRUD, FIPE refresh, and acquisition modeling,
So that the frontend can manage the fleet financially.

**Acceptance Criteria:**

1. `Vehicle` model with all fields from FR-VH-1, plus `asset_id` (FK to `assets`), `current_contract_id` (nullable), `current_customer_id` (nullable, derived).
2. CRUD endpoints under `/api/v1/modules/vehicles/` with permission checks.
3. On create/update, sync record in core `assets` table (create or update `asset_id`).
4. `POST /api/v1/modules/vehicles/{id}/refresh-fipe` updates `valor_fipe_atual` via active adapter.
5. Celery beat job (`0 3 5 * *`) refreshes FIPE for all active vehicles monthly.
6. `VehicleAcquisition` entity (1:1 with Vehicle) with acquisition form (FR-VH-3): type, down_payment, installments (JSONB), interest_rate, amortization_system.
7. `GET /api/v1/modules/vehicles/{id}/financials` returns: FIPE value, depreciation, total paid to acquisition, balance, total received, ROI %, payback.

### Story 2B.4: Vehicle Registration Wizard (Vehicle Module)

As a Manager,
I want a guided wizard to register a vehicle,
So that the many fields don't overwhelm me.

**Acceptance Criteria:**

1. 4 steps: **Identification** (plate, renavam, chassis, color), **FIPE Data** (cascading brand/model/year selectors with auto-filled value), **Acquisition** (date, purchase value, payment form with dynamic sub-form), **Documents & Photos** (insurance, IPVA, photos).
2. FIPE selectors with typeahead and inline loading.
3. **Given** "Financiamento" selected, **Then** sub-form: down payment, installment count, rate, amortization (Price/SAC), preview table.
4. Stepper + Back/Next; form state preserved across steps.
5. Final step: preview before commit; on confirm, create vehicle + acquisition atomically.

### Story 2B.5: Vehicles List and Card Grid (Vehicle Module)

As a Manager,
I want to see the fleet as a table or cards,
So that I can scan its state quickly.

**Acceptance Criteria:**

1. Toggle Table <-> Cards; preference persisted to localStorage.
2. Cards: photo, model, plate, status badge, current driver, ROI %, next due date, mini-map with position.
3. Filters: status, brand, year, current driver, tag.
4. KPI strip: Fleet Total (R$ FIPE sum), Active Vehicles, Parked Vehicles.

### Story 2B.6: GPS Tracker Adapter (Vehicle Module)

As the System,
I want an `ITrackerGateway` Port with a generic implementation,
So that GPS tracking is plug-and-play.

**Acceptance Criteria:**

1. `ITrackerGateway` Protocol with `get_position`, `get_positions`, `block_vehicle`, `unblock_vehicle`, `get_history`.
2. `GenericRestTrackerAdapter` parameterizable by base URL, auth, JSONPath mapping — works for most REST trackers without code changes.
3. `MqttRestTrackerAdapter` for MQTT-command / REST-position trackers.
4. Block/unblock requires Admin profile + password re-confirmation (double approval) and writes signed `audit_log` event with reason.

### Story 2B.7: Interactive Fleet Map (Vehicle Module)

As a Manager,
I want to see all vehicles on an interactive map,
So that I can monitor the operation geographically.

**Acceptance Criteria:**

1. `FleetMapComponent` in `features/modules/vehicles/fleet-map/`.
2. Leaflet with OSM tiles, custom markers (vehicle-type icon + status color).
3. Auto-cluster on zoom-out.
4. **Given** marker click, **Then** popup: photo, model, plate, driver, status, "View Details" + "Block" (with double confirmation).
5. Positions refresh every 30 s via SSE (`/sse/module/vehicles`).
6. Side filters: status, driver, tag.
7. Optional "operating region" polygon highlighting out-of-zone vehicles.

### Story 2B.8: Overdue Hook — GPS Block Policy (Vehicle Module)

As the Vehicle Module,
I want to react to `InstallmentOverdueEvent` by checking the block policy,
So that vehicles are blocked automatically when configured.

**Acceptance Criteria:**

1. Hook `on_installment_overdue` in `VehicleModule` checks parametrized policy: `dias_atraso >= X` AND `score < Y`.
2. If conditions met AND policy requires human approval -> create notification for Admin with "Approve Block" / "Reject".
3. If conditions met AND auto-approval enabled -> dispatch `block_vehicle` via `ITrackerGateway`.
4. `vehicle_blocked` event written to `audit_log` with reason, associated title, customer score.
5. On `InstallmentPaidEvent`, hook checks if vehicle is blocked and all overdue titles are cleared -> auto-dispatch `unblock_vehicle`.

### Story 2B.9: CNH Schema Extension for Customer (Vehicle Module)

As the Vehicle Module,
I want to register CNH fields on the Customer entity,
So that driver documentation is part of the customer profile.

**Acceptance Criteria:**

1. Vehicle Module registers schema extension for Customer via `metadata_extensions`: CNH number, category, expiry date, photo URL.
2. Customer form (Story 2A.3) renders the "CNH" section when Vehicle Module is active.
3. CNH validation: number format, category (A/B/AB/C/D/E), expiry not in the past.
4. CNH photo uploaded to MinIO as a customer attachment with kind `cnh`.

### Story 2B.10: Excel One-Shot Importer — Vehicles (Vehicle Module)

As a Manager going live,
I want to import existing vehicles from a spreadsheet,
So that I don't re-type fleet data.

**Acceptance Criteria:**

1. CLI `python -m app.cli import-excel --entity=vehicles --file=veiculos.xlsx` maps columns into vehicles table and syncs with core `assets`.
2. `--dry-run` validates and prints report without persisting.
3. Re-run with same input: existing records matched by plate are updated (idempotent).
4. End-of-run report: created, updated, skipped (with reasons).
5. Import writes a summary `audit_log` entry.

---

## Epic 3: Contracts & Flexible Installments (Core)

**Goal:** The manager can produce any contract shape imaginable (down payment + N installments + extras + grace + custom), linked to a generic asset (`asset_id`), with PDF and linked titles generated automatically. Supports bulk edits on open installments without touching paid ones. Contract changes reissue open titles. Title lifecycle: titles generated on finalization; contract changes cancel open titles and generate new ones; paid titles immutable.

### Story 3.1: Contract, Installment, ContractEvent Domain Model (Core)

As a Backend developer,
I want the contracts domain modeled in the database,
So that financial rules have a correct foundation.

**Acceptance Criteria:**

1. `contracts` table: id, customer_id, asset_id (FK to `assets`), status (`rascunho`/`vigente`/`encerrado`/`rescindido`), start_date, end_date, total_amount, periodicity, due_day, late_interest_pct_per_day, late_fine_pct, grace_days, has_purchase_option, residual_value, terms_md, pdf_url, version, created_by, signed_at, terminated_at, termination_reason, soft delete.
2. `installments` table: id, contract_id, sequence, due_date, amount, status (`em_aberto`/`vencido`/`pago_aguardando_verificacao`/`pago`/`pago_parcial`/`renegociado`/`cancelado`), kind (`regular`/`down_payment`/`extra_semestral`/`extra_anual`/`custom`), paid_at, paid_amount, payment_method, receipt_url, notes, parent_installment_id (nullable — reference to original title in partial payment), `UNIQUE(contract_id, sequence)`.
3. `contract_events` table (append-only): id, contract_id, event_type, payload (JSONB), pdf_hash, created_by, created_at. Types: `created`, `signed`, `installments_generated`, `installments_reissued`, `bulk_edit`, `cancellation_requested`, `terminated`, `pdf_generated`.
4. `installment_adjustments` table (append-only): id, installment_id, kind (`discount`/`fine`/`interest`/`renegotiation`/`bulk_edit`/`partial_payment`/`reverse_write_off`), amount_delta, snapshot_before, snapshot_after, reason, applied_by, applied_at.
5. PG trigger `enforce_paid_immutability`: **Given** installment status is `pago`, **When** UPDATE attempts to change `amount`, `due_date`, `paid_at`, `paid_amount`, or revert status, **Then** exception raised. Exception: status -> `cancelado` only when session var `app.reverse_write_off=true`.
6. Indexes: `installments(contract_id)`, `installments(due_date, status)`, `installments(status)`.
7. On contract finalization (status -> `vigente`), publish `ContractCreatedEvent` on event bus.
8. `installment_generations` table created with: id, contract_id, batch_label, installment_count, total_amount, has_financial_activity (bool, default false), created_by_user_id, created_at, rolled_back_at, rolled_back_by. Every installment carries a `generation_id` FK linking it to the generation that created it.

### Story 3.2: Installment Builder Backend — Preview + Persist (Core)

As a Backend developer,
I want an endpoint that computes a schedule from an installment definition,
So that the frontend can preview before persisting.

**Acceptance Criteria:**

1. **Given** payload with `start_date`, optional `down_payment`, optional `regular`, optional `extras[]`, optional `grace_days`, optional `custom_overrides[]`, **When** `POST /api/v1/contracts/preview-schedule` is called, **Then** response returns ordered list with `sequence`, `due_date`, `amount`, `kind`.
2. Total of computed installments matches expected total (coherence check).
3. Supports `custom_only` mode for fully hand-edited schedules.
4. `POST /api/v1/contracts/` persists contract + all installments + `contract_events.created` atomically.
5. Schedule calculation in `app/domain/contracts/schedule_calculator.py` with 100% unit test coverage (no I/O).
6. Supports `custom_days` periodicity where `next_due = prev_due + timedelta(days=N)` with N configurable per contract via `custom_days_interval` field.

### Story 3.3: Visual Installment Builder Frontend (Core)

As a Manager,
I want a visual UI to compose installments,
So that I see the schedule before committing.

**Acceptance Criteria:**

1. `ScheduleBuilderComponent` in `features/system/contracts/components/schedule-builder/`.
2. Left pane: configurator (down payment toggle, regular installments, extras, grace days).
3. Right pane: preview table updated reactively via `resource()` calling preview endpoint with debounce.
4. **Given** "Custom Schedule" toggle, **Then** configurator hidden, manual editing only.
5. Preview table supports drag-and-drop (CDK) reorder, inline editing for value and date.
6. "Add installment" and "Remove" buttons.
7. Footer: total parceled, total overall, count, last date, total period.

### Story 3.4: Contract Creation Wizard (Core)

As a Manager,
I want a guided wizard to create a contract,
So that data comes in cleanly and consistently.

**Acceptance Criteria:**

1. 4 steps: **Customer & Asset** (search-typeahead selectors for customer and asset from `assets` table), **Terms** (dates, interest/fine, purchase option), **Schedule** (Story 3.3 component), **Clauses & Review** (Tiptap rich text + PDF preview).
2. Cross-validations: customer is `ativo`, asset is `disponivel`, end_date >= start_date.
3. **Given** any step, **When** "Salvar Rascunho", **Then** persisted as `rascunho`, resumable.
4. **Given** confirm, **Then** contract -> `vigente`, PDF rendering enqueued, installments generated atomically. `ContractCreatedEvent` published.
5. Success toast with "View Contract" deep link.

### Story 3.5: Contract PDF Generation (Core)

As the System,
I want to render a professional PDF from each contract,
So that the manager can print or send it.

**Acceptance Criteria:**

1. Celery task `render_contract_pdf(contract_id)` loads contract + customer + asset details (via `IAssetModule.get_asset_details()`) + installments, renders Jinja2 -> HTML -> WeasyPrint -> PDF.
2. Template in `app/infrastructure/pdf/templates/contract.html.j2` with configurable clauses, data, installment table, signature space.
3. PDFs stored in MinIO at `contracts/{contract_id}/v{version}.pdf`; URL saved in `contract.pdf_url`.
4. SHA-256 hash recorded in `contract_events.pdf_generated`.
5. On contract edit, version increments; prior versions remain accessible.
6. `GET /api/v1/contracts/{id}/pdf?version=` returns presigned MinIO URL (5-min TTL).

### Story 3.6: Bulk Edit on Open Installments (Core)

As a Manager,
I want to update many open installments at once,
So that ad-hoc adjustments are quick.

**Acceptance Criteria:**

1. Contract installment table supports multi-row selection (checkbox + Shift-click range).
2. Floating "Bulk Actions" bar: Postpone X days, Apply discount X% or X R$, Set value, Cancel, Recreate.
3. **Given** bulk action, **Then** applied **only** to installments with status in (`em_aberto`, `vencido`). Paid titles are immutable — skipped with notification.
4. Before/after diff preview in confirmation modal.
5. Backend applies in single transaction with `contract_events.bulk_edit` event.
6. After bulk edit, if installments were changed, old open titles are cancelled and new ones generated (reissue). `contract_events.installments_reissued` event recorded.

### Story 3.7: Contract Versioning and Event Timeline (Core)

As a Manager,
I want to see the history of changes to a contract,
So that I can trace any modification.

**Acceptance Criteria:**

1. Contract detail page "History" tab.
2. Vertical timeline with icon + description + author + date per event.
3. **Given** event click, **Then** payload shown (visual diff when applicable).
4. Each `pdf_generated` event has "View this version's PDF" button.

### Story 3.8: Contract Termination (Core)

As a Manager,
I want to terminate a contract with settlement calculation,
So that asset return is documented.

**Acceptance Criteria:**

1. "Terminate" modal: reason, effective date, rescission fine policy (toggle "Apply X% fine", default from Settings).
2. Backend computes: `sum(open_installments) * pct_fine + manual_adjustment`.
3. **Given** confirm, **Then** final receivable (or credit) created, open installments -> `cancelado`, contract -> `rescindido`, `ContractTerminated` event published (vertical module reacts — e.g., Vehicle Module sets vehicle to `disponivel`).
4. `contract_events.terminated` entry written.

### Story 3.9: Contract Simulation (Core)

As a Manager,
I want to simulate a contract without persisting,
So that I can explore scenarios before committing.

**Acceptance Criteria:**

1. `POST /api/v1/contracts/simulate` accepts full contract + schedule definition, returns computed installments and totals.
2. No database writes; uses the same `schedule_calculator.py` pure function.
3. Frontend preview modal shows all installments with totals.

### Story 3.10: Installment Generation Management & Rollback (Core)

As a Manager,
I want to view all installment generations of a contract and rollback mistake generations instantly,
So that I don't pollute the system with hundreds of canceled titles from a typo.

**Acceptance Criteria:**

1. Contract detail page gains a "Gerações" tab listing all `installment_generations` with batch_label, installment count, total amount, status (active/rolled_back), `has_financial_activity` badge.
2. **Given** a generation with `has_financial_activity = FALSE`, **When** the user clicks "Rollback", **Then** all installments of that generation are **hard deleted** (not canceled), the generation is marked `rolled_back_at = now()`, and an audit_log entry records all deleted installment IDs.
3. **Given** a generation with `has_financial_activity = TRUE`, **When** the user views it, **Then** the "Rollback" button is hidden and a "Cancelar em massa" button is shown instead. Clicking it sets all open installments of that generation to `cancelado`.
4. `has_financial_activity` flips to TRUE when ANY installment in the generation: receives a write-off (full/partial), is sent for collection (Pix card sent via WhatsApp), receives a payment-gateway charge, or has any `installment_adjustment`.
5. The rollback action requires Admin role confirmation.
6. After rollback, the contract's installment list updates immediately.

---

## Epic 4: Receivables, Partial Payments & Validation (Core)

**Goal:** The manager runs the full receivables operation with partial payment support, manual write-off, receipt-validation queue, automatic OCR, and free Pix QR code generation. Default payment flow: Pix via WhatsApp (zero cost).

### Story 4.1: Master Receivables List (Core)

As a Manager,
I want to see every receivable in one powerful table,
So that I can operate financials at scale.

**Acceptance Criteria:**

1. Route `/system/finance/receivables` renders `ReceivablesListComponent`.
2. Filters: status (multi-select), customer, asset, contract, due-date range, value range.
3. Columns: due date, customer (avatar), asset, contract (link), original value, updated value (interest/fine), status (badge), method, row actions.
4. Row actions: Write-off, Partial Write-off, View, Edit (if open), Cancel (if open).
5. Footer totals: "Selected: R$ X | Filter total: R$ Y | Delinquency: R$ Z".
6. Keyboard shortcuts: `b` writes off selected, `Space` selects, `f` focuses filters.

### Story 4.2: Updated Value Calculation — Interest, Fine, Discount (Core)

As the System,
I want a pure function that computes the updated value of an overdue installment,
So that write-offs use the correct amount.

**Acceptance Criteria:**

1. `compute_updated_value(installment, on_date, contract_terms)` is a pure function in `domain/finance/calculations.py`.
2. Formula: `dias_atraso = max(0, on_date - due_date - grace_days)`; `multa = amount * fine_pct if dias_atraso > 0 else 0`; `juros = amount * interest_pct_per_day * dias_atraso`; `total = amount + multa + juros`.
3. `GET /api/v1/receivables/{id}/updated-value?on_date=` returns full breakdown (base, interest, fine, discount, total).
4. Manual discount requires mandatory `reason`, persisted to `installment_adjustments`.
5. Unit tests: on-time, short delay, long delay, within grace, with discount.

### Story 4.3: Manual Write-Off Modal (Core)

As a Manager,
I want to write off an installment by entering payment data,
So that the title leaves "open" status.

**Acceptance Criteria:**

1. Modal: effective date (default today), paid amount (default `updated_value`), method (Pix/cash/transfer/card/other), notes, attachment drop-zone (required for Pix).
2. **Given** Pix and receipt uploaded, **Then** OCR runs in background, auto-populates value and date if confidence >= 70%.
3. **Given** Pix write-off confirmed, **Then** status -> `pago_aguardando_verificacao`.
4. **Given** cash or in-person card, **Then** status -> `pago_aguardando_verificacao`.
5. List refreshes; success toast shown.

### Story 4.4: Partial Payment Support (Core)

As the System,
I want to handle partial payments correctly,
So that the difference is tracked as a new receivable.

**Acceptance Criteria:**

1. `compute_partial_payment(title_amount, paid_amount, original_due_date, grace_days)` pure function in `domain/finance/calculations.py` returns: `original_new_status='pago_parcial'`, `remainder_amount`, `remainder_due_date`, `adjustment_delta`.
2. **Given** paid_amount < title amount, **When** `POST /api/v1/receivables/{id}/partial-write-off` is called with payment data, **Then**:
   - Original title receives `paid_amount` and status `pago_parcial`.
   - `InstallmentAdjustment` with `kind='partial_payment'` created, recording `amount_delta` and reference to new title in `reason` (JSON).
   - A NEW title is generated for the difference (`title.amount - paid_amount`) with `kind='regular'`, `due_date` = next vencimento or same day + `grace_days`, linked to same contract, with `parent_installment_id` pointing to original.
   - Contract sequence incremented.
3. `PaymentPartiallyReceivedEvent` published on event bus (modules can react).
4. Unit tests: various partial amounts, edge cases (paid = 0, paid = full).
5. Concurrent partial payments on the same installment are prevented via pessimistic locking (`SELECT ... FOR UPDATE`). Second concurrent request receives 409 Conflict.

### Story 4.5: OCR Provider Adapter (Core)

As the System,
I want an `IOcrProvider` Port with a default Tesseract implementation,
So that OCR works at zero external cost.

**Acceptance Criteria:**

1. `IOcrProvider` Protocol: `extract_text(file_bytes, mime)`, `extract_pix_receipt(file_bytes, mime)`.
2. `TesseractOcrAdapter` with OpenCV preprocessing (deskew, denoise, threshold), language `por+eng`.
3. `LlmVisionOcrAdapter` (optional fallback) calling GPT-4o Vision or Claude when confidence is low.
4. Pix receipt regexes: value (`R\$\s*[\d.,]+`), date (`\d{2}/\d{2}/\d{4}`), transaction ID, beneficiary, bank.
5. Results cached in Redis by SHA-256 of file bytes (TTL 7 days).

### Story 4.6: Receipt Validation Queue (Core)

As a Validator,
I want a queue of pending receipts,
So that I can validate quickly in batch.

**Acceptance Criteria:**

1. Route `/system/finance/validation-queue` lists installments in `pago_aguardando_verificacao` ordered by date ascending.
2. Split layout: list left, file viewer center (image/PDF with zoom), right pane with title data and Approve/Reject/Request Resubmission.
3. Keyboard: `A` approve, `R` reject, arrow next/previous.
4. **Given** approve, **Then** status -> `pago_aguardando_verificacao`, `audit_log` event with `validated_by_user_id`.
5. **Given** reject, **Then** reason required (predefined + free text).
6. **Given** "Request Resubmission", **Then** WhatsApp message dispatched (uses Epic 6), status unchanged.
7. Top KPIs: pending, validated today, rejected today.

### Story 4.7: Static Pix QR Code Generation (Core)

As the System,
I want to generate a Pix BR Code per installment,
So that collections are immediately payable at zero cost.

**Acceptance Criteria:**

1. Company Pix key configured in Settings > Company (key + beneficiary name).
2. `GET /api/v1/receivables/{id}/pix-qr` returns SVG/PNG QR + "Copy and Paste" BR Code text.
3. Uses `pix-utils` following BCB MN-002 spec.
4. TXID embeds installment ID for reconciliation.
5. Receivable detail: "Generate Pix QR" button opens modal with QR + "Send via WhatsApp" CTA.

### Story 4.8: Renegotiation of Overdue Installments (Core)

As a Manager,
I want to renegotiate overdue receivables,
So that struggling customers can be brought back on track.

**Acceptance Criteria:**

1. **Given** multiple overdue installments of same customer selected, **When** "Renegotiate" triggered, **Then** modal shows sum with updated interest/fine.
2. Modal uses Epic 3 schedule builder for new schedule.
3. **Given** confirmed, **Then** original installments -> `renegociado` (immutable), new installments created.
4. `renegotiated` event with `{old_ids, new_ids, total_old, total_new}` in `audit_log`.

### Story 4.9: Optional Pix Payment Gateway Adapter (Core)

As an Admin,
I want to optionally connect Asaas/Efi,
So that auto-confirmed Pix collections become available when ROI justifies the per-transaction cost.

**Acceptance Criteria:**

1. `IPaymentGateway` Port: `create_charge(installment) -> Charge`, `webhook_handler(payload, signature) -> Event`.
2. `AsaasAdapter`, `EfiAdapter` implemented; `NoOpPaymentGateway` is default (off).
3. Settings > Integrations: Admin can enable, store encrypted credentials, define scope.
4. **Given** webhook at `POST /api/v1/webhooks/payment-gateway/{provider}`, **When** signature validates, **Then** idempotent processing moves installment straight to `pago` (skips manual validation).
5. Default: **disabled**, per zero-cost Pix preference.

### Story 4.10: Installment Reversal — Full & Partial (Core)

As an Admin,
I want to reverse a paid installment fully or partially,
So that overpayments are corrected with full audit trail and the cash flow reflects reality.

**Acceptance Criteria:**

1. **Given** a `pago` or `pago_parcial` installment, **When** Admin clicks "Estornar", **Then** a modal asks: full or partial reversal, amount (if partial), reason, and Admin password re-auth.
2. Full reversal creates `InstallmentAdjustment` with `kind='full_reversal'` and generates a `Payable` with `linked_installment_id` pointing to the original title. The payable amount equals the original `paid_amount`.
3. Partial reversal creates `InstallmentAdjustment` with `kind='partial_reversal'` and generates a `Payable` for the delta amount with `linked_installment_id`.
4. The original installment status does NOT change — it stays `pago` or `pago_parcial` (immutable). The reversal lives entirely in the adjustment + payable.
5. `payables` table includes `linked_installment_id UUID REFERENCES installments(id)` for tracing reversals.
6. DRE and dashboards compute net revenue = gross received - sum of reversal payables.
7. Audit log records the reversal with module='core', category='financial', before/after payload, and Admin user ID.
8. The generated Payable is reconcilable against the bank statement's outgoing transaction in the reconciliation screen.

### Story 4.11: Bulk Write-Off (Core)

As a Manager,
I want to write off multiple installments of the same customer with a single payment,
So that batch payments are fast.

**Acceptance Criteria:**

1. User selects multiple open/overdue installments of the same customer in the receivables list.
2. "Baixa em Lote" action opens a modal showing selected titles, sum total (with interest/fines), and a single payment form.
3. Payment distributes across titles in due-date order (oldest first).
4. Each title gets its own `InstallmentAdjustment` and status change.
5. If paid amount < total selected, the last title gets a partial write-off with remainder title generated.
6. Audit log records the bulk operation with all affected installment IDs.

---

## Epic 5: Payables & Recurring Expenses (Core)

**Goal:** The manager controls every operating expense with one-off entries, auto-generated recurrences, a "Quick Pay" shortcut, and simplified DRE — monthly result visible at a glance.

### Story 5.1: Categories & Suppliers Domain and CRUD API (Core)

As a Backend developer,
I want entities to categorize expenses and suppliers,
So that downstream reports are rich.

**Acceptance Criteria:**

1. `expense_categories` table: id, parent_id (self-referential hierarchy), name, color, icon, is_active, sort_order. Core defaults seeded; modules can register additional categories.
2. `suppliers` table: id, name, document (CPF/CNPJ), contact, bank_data (JSONB), is_active.
3. CRUD endpoints `/api/v1/expense-categories` and `/api/v1/suppliers` with permissions.
4. Default categories seeded: Maintenance, Fuel, Taxes, Insurance, Salaries, Rent, Utilities, Other.

### Story 5.2: Payables Domain and API (Core)

As a Backend developer,
I want a Payable entity with REST endpoints,
So that the frontend can manage expenses.

**Acceptance Criteria:**

1. `payables` table: id, description, supplier_id (nullable), category_id, asset_id (nullable, FK to `assets` for per-asset costing), amount, due_date, status (`em_aberto`/`pago`/`cancelado`), paid_at, paid_amount, payment_method, attachment_url, notes, created_by, recurring_template_id (nullable).
2. CRUD endpoints under `/api/v1/payables`.
3. **Given** payable `em_aberto`, **When** `POST /api/v1/payables/{id}/pay`, **Then** status -> `pago`, audit entry.
4. **Given** "Quick Pay" intent, **When** `POST /api/v1/payables/quick-pay`, **Then** create + pay atomically.

### Story 5.3: Recurring Expenses (Core)

As the System,
I want auto-generated recurring payables,
So that the manager doesn't forget fixed obligations.

**Acceptance Criteria:**

1. `recurring_payable_templates` table: id, description, supplier_id, category_id, asset_id, amount, periodicity (`mensal`/`bimestral`/`anual`), day_of_month, start_date, end_date (nullable), is_active.
2. CRUD endpoints under `/api/v1/recurring-payables`.
3. **Given** daily Celery beat job (`0 4 * * *`), **When** template active and today matches day_of_month and no payable exists for current period, **Then** new payable created.
4. "Recurring Expenses" screen: templates with active toggle, next dates, "Generate now" button.

### Story 5.4: "Quick Pay" Modal (Core)

As a Manager,
I want a fast shortcut to record an expense already paid,
So that instant logging is trivial.

**Acceptance Criteria:**

1. Floating "Lancar e Pagar" button (FAB) available on every screen + command palette.
2. Compact modal: description, supplier (autocomplete + create-inline), category, amount, date (default today), method, attachment, asset (optional).
3. **Given** confirm, **Then** payable created with `status='pago'` in single atomic transaction.

### Story 5.5: Simplified DRE (Core)

As a Manager,
I want to see Income - Expenses by period,
So that I can read the operation's result.

**Acceptance Criteria:**

1. Route `/system/finance/dre` with filters: period (month/quarter/custom), asset, category.
2. Structure: Revenues (by source), Expenses (by category), Gross Margin, Margin %.
3. Bar chart comparing months with drilldown on click.
4. Export to Excel and PDF with formatting preserved.

---

## Epic 6: WhatsApp Inbox & AI Collection Agent (Core + Module Hooks)

**Goal:** The manager stops collecting manually. A polite, parametrizable conversational agent runs collections following pre-defined policies; humans can intervene at any time. Module-injected tools (e.g., Vehicle Module's `bloquear_veiculo`) are available to the agent. Full conversation history in a familiar WhatsApp-style UI. Default payment flow: Pix via WhatsApp (zero cost).

### Story 6.1: WhatsApp Gateway Adapter (Core)

As the System,
I want an `IWhatsAppGateway` Port with Evolution API as default,
So that switching providers does not affect the domain.

**Acceptance Criteria:**

> **MVP scope:** Only EvolutionApiAdapter is required for MVP. ZapiAdapter, UazapiAdapter, WppConnectAdapter, and WhatsAppCloudApiAdapter are V2.

1. `IWhatsAppGateway` Protocol: `send_text`, `send_image`, `send_document`, `send_pix_card`, `mark_as_read`, `webhook_parse`.
2. Adapters: `EvolutionApiAdapter` (default), `ZapiAdapter`, `UazapiAdapter`, `WppConnectAdapter`, `WhatsAppCloudApiAdapter`.
3. Configuration via env + Settings > Integrations: provider, API key, instance ID, webhook secret.

### Story 6.2: Conversations & Messages Domain (Core)

As a Backend developer,
I want persisted conversations and messages,
So that history is always retrievable.

**Acceptance Criteria:**

1. `whatsapp_conversations` table: id, customer_id, phone_e164, last_message_at, unread_count, is_archived, agent_active, agent_paused_until.
2. `whatsapp_messages` table: id, conversation_id, external_id (UNIQUE), direction, kind, content_text, media_url, media_mime, sent_at, delivered_at, read_at, sent_by (`agent` or `human:{user_id}`), status, context (JSONB), embedding (vector(1536) nullable).
3. `GET /api/v1/conversations?search=&unread=&page=` returns paginated list.
4. `GET /api/v1/conversations/{id}/messages?before=&limit=` returns reverse-chronological cursor pagination.
5. WebSocket `/ws/conversations` pushes new messages to subscribers in real time.

### Story 6.3: Webhook Receiver and Inbound Pipeline (Core)

As the System,
I want to receive and process inbound WhatsApp messages with idempotency,
So that no message is ever lost.

**Acceptance Criteria:**

1. `POST /api/v1/webhooks/whatsapp/{provider}` validates signature; raw payload persisted to `webhook_events_raw` (idempotent on `(provider, external_id)`).
2. Handler enqueues Celery task on `whatsapp_inbound` queue.
3. Worker normalizes to `ReceivedMessage`, finds/creates conversation by phone, persists `WhatsAppMessage`, enqueues agent-turn task.
4. Media downloaded to MinIO before OCR/classification.
5. Duplicate external_id -> `{"status":"duplicate"}`, no side effects.

### Story 6.4: AI Agent Engine with RAG (Core + Module Hooks)

As a Backend developer,
I want a conversational agent with rich customer context and module-injected tools,
So that responses are personalized, policy-aware, and domain-capable.

**Acceptance Criteria:**

1. `ILLMProvider` Port: `chat`/`tool_call` semantics. Adapters: `OpenAiAdapter` (default), `AnthropicAdapter`, `GeminiAdapter`, `OllamaAdapter`, `LiteLlmAdapter`.
2. Configuration in Settings > Agent: provider, model, temperature, max tokens.
3. **Given** inbound message, **When** agent turn runs, **Then** prompt composed from: customer record, open/overdue installments with updated values, score, last N messages, active collection policy, manager notes.
4. Old messages vectorized async into pgvector; top-K similar chunks retrieved for prompt enrichment.
5. System prompt parametrized by tone, persona, rules, tool list.
6. **Core function-calling tools**: `consultar_titulos_em_aberto`, `enviar_qr_pix`, `registrar_baixa_primaria`, `solicitar_validacao_humana`, `agendar_cobranca`, `gerar_acordo`, `escalar_para_gestor`.
7. **Module-injected tools**: loaded dynamically via `IAssetModule.get_collection_tools()` at agent startup. E.g., Vehicle Module injects `bloquear_veiculo` (gated: score < threshold AND dias_atraso >= X AND human approval per policy), `desbloquear_veiculo`, `verificar_localizacao_veiculo`.
8. Each turn writes to `agent_runs` (provider, model, tokens, latency, tools_called, final_action, error, cost_usd).
9. Feature flag `AGENT_DRY_RUN`: generates but does not send — queued for human review (calibration mode).

### Story 6.5: Agent Parameterization UI (Core + Module Hooks)

As an Admin,
I want to configure the agent's tone, rules, and templates,
So that it represents my business voice.

**Acceptance Criteria:**

1. Route `/system/config/agent` with sections: **Persona** (name, tone slider with live example, time-of-day greetings), **Service Window** (hours, days), **Preventive Collection** (lead days + template), **Post-Due** (D+1/D+3/D+7 templates with toggles), **Score Concession Policy** (editable table: score_min, score_max, days_tolerance, requires_human_approval), **Interest & Fine** defaults, **Templates** (Tiptap editor with placeholders + preview).
2. **Module-specific policies**: each active module can register additional policy sections. E.g., Vehicle Module adds "Remote Block" (active toggle + conditions: `dias_atraso >= X` AND `score < Y` + requires-human-approval).
3. Every change writes versioned record with diff to audit log.
4. "Test Message" button generates a sample reply against a fictional customer.

### Story 6.6: Customer Score Calculation (Core + Module Hooks)

As a Backend developer,
I want a periodically recomputed score per customer,
So that agent decisions are data-driven.

**Acceptance Criteria:**

1. Daily Celery beat job (`0 2 * * *`) recomputes 0-100 score using: punctuality 12m (60%), avg overdue days (20% inverted), relationship tenure (10% bonus), historical paid amount (10%).
2. **Module contribution**: active modules can add score factors via `IAssetModule`. E.g., Vehicle Module adds "prior blocks count" as penalty factor.
3. Formula configurable in Settings > Score (weights editable).
4. `customer_score_history` records daily snapshot with factor breakdown.
5. Customer "Score" tab plots evolution chart.

### Story 6.7: WhatsApp-style In-App Inbox (Core)

As a Manager,
I want to see and reply to conversations in a familiar interface,
So that human handoff is seamless.

**Acceptance Criteria:**

1. Route `/system/inbox` with 3-pane layout:
   - **Left (320 px)**: conversations with avatar, name, last message, timestamp, unread badge, agent status icon.
   - **Center (flex)**: message thread with bubbles (green-out / white-in), day separators, timestamps, ticks, image lightbox, audio player, PDF preview.
   - **Right (340 px, collapsible)**: customer context (avatar, name, score, status, open titles with updated values, quick actions: Generate Pix, Mark as Paid, Escalate).
2. Chat input: attachments, emojis, audio recording.
3. Header toggle: pause/resume agent on active conversation.
4. WebSocket real-time message delivery.
5. Keyboard: arrows walk conversations, `Ctrl+Enter` sends, `/` focuses search.
6. In-conversation search (text-based).
7. "Agent is typing..." indicator while processing.

### Story 6.8: Controlled Mass Broadcast (Core)

As a Manager,
I want to dispatch preventive collections to all customers due tomorrow,
So that I save time at scale.

**Acceptance Criteria:**

1. Route `/system/inbox/broadcast` with audience filters and live recipient preview.
2. Message editor with placeholders.
3. Double-confirmation modal (with password) + 3 sample renderings.
4. Time window + staggered sends (1 per X seconds) to avoid bans.
5. Post-broadcast report: sent/delivered/read/failed/replied (updated via webhooks).
6. Hard cap 200 recipients per broadcast (anti-spam).

### Story 6.9: Receipt Detection and Primary Write-Off via Agent (Core)

As a Customer,
I want my title considered paid as soon as I send a receipt over WhatsApp,
So that I get instant confirmation.

**Acceptance Criteria:**

1. Inbound media classified via heuristic (image/PDF + OCR detects Pix patterns).
2. **Given** receipt detected, **Then** agent extracts amount + date + transaction ID, finds most likely title (customer + value + date window), calls `registrar_baixa_primaria`.
3. **Given** paid amount < title amount, **Then** agent executes partial write-off (Story 4.4 logic): partial payment recorded, new title for difference generated. Agent informs customer of partial payment and remaining balance.
4. **Given** full write-off succeeds, **Then** agent replies with confirmation template. Installment added to validation queue (Story 4.6).
5. **Given** ambiguous match, **Then** agent asks customer in natural language or escalates to manager.

### Story 6.10: In-App Chat Channel for Agent Orchestrator (Core)

As a Manager,
I want to chat with the Agent Orchestrator directly in the web UI,
So that I can issue commands without opening WhatsApp.

**Acceptance Criteria:**

1. A "Chat com Agente" button in the app header opens a chat drawer/panel.
2. The chat uses the same Agent Orchestrator pipeline — same tools, same RBAC, same LLM.
3. The channel is identified as `in_app` (vs `whatsapp`) in `AgentInput`.
4. Messages are persisted in a separate conversation with `channel='in_app'`.
5. The Manager's JWT provides the RBAC context (no phone number lookup needed).
6. Supports text input; image/file upload for receipt submission.

### Story 6.11: Audio Transcription for Agent Orchestrator (Core)

As a User,
I want to send audio messages that the agent understands,
So that I can interact hands-free.

**Acceptance Criteria:**

1. `IAudioTranscriber` port defined in `app/domain/ports/audio_transcriber.py`.
2. `WhisperApiAdapter` (default) calls OpenAI Whisper API with language='pt-BR'.
3. `ConsoleTranscriberAdapter` for dev (returns placeholder text).
4. Inbound pipeline: when a WhatsApp message has audio, transcribe BEFORE passing to the Agent Orchestrator.
5. In-app chat: audio recording via browser MediaRecorder API, sent as blob, transcribed server-side.
6. Transcription result is stored alongside the message in `whatsapp_messages.transcription` (nullable TEXT field).

---

## Epic 7: Sophisticated Bank Reconciliation (Core)

**Goal:** At month-end (or daily), the manager reconciles the bank statement with system titles in a dual-pane drag-and-drop screen with auto-match, supporting OFX, PDF, and Open Finance.

### Story 7.0: Bank Account Setup (Core)

As a Manager,
I want to register my bank accounts in the system,
So that imported transactions can be linked to the correct account.

**Acceptance Criteria:**

1. `bank_accounts` table: id UUID PK, name TEXT, bank_code VARCHAR(5), agency VARCHAR(10), account_number VARCHAR(20), type TEXT, is_active BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ.
2. CRUD API under `/api/v1/bank-accounts` with Admin permission.
3. Settings > Company > "Contas Bancárias" UI with list + create/edit form.
4. At least one bank account must exist before OFX/PDF import is allowed.

### Story 7.1: OFX Importer (Core)

As a Manager,
I want to upload an OFX file from my bank,
So that transactions enter the system automatically.

**Acceptance Criteria:**

1. Route `/system/finance/reconciliation` exposes "Import OFX" button.
2. Drop-zone accepts `.ofx`; parsing via `ofxparse`.
3. **Given** overlapping FITIDs, **Then** existing transactions skipped (deduplication).
4. `bank_transactions` table: id, account_id, fitid, posted_at, amount (signed), description_raw, description_clean, type, status (`pendente`/`conciliada`/`ignorada`), reconciled_to_kind, reconciled_to_id, imported_from (`ofx`/`pdf`/`open_finance`/`manual`), imported_at; `UNIQUE(account_id, fitid)`.
5. Pre-classification: regex/heuristics extract sender name from Pix descriptions.

### Story 7.2: Smart PDF Importer (Core)

As a Manager,
I want to upload a PDF statement,
So that even banks without OFX support work.

**Acceptance Criteria:**

1. Drop-zone accepts `.pdf`. Backend: `pdfplumber` + per-bank heuristics (BB, Itau, Bradesco, Santander, Caixa, Nubank, Inter, C6).
2. **Given** heuristics < 80% confidence, **When** LLM fallback enabled, **Then** LLM called with structured-JSON prompt; otherwise manual review screen.
3. LLM call gated by feature flag with cost-tracking metric.
4. Review screen: mark/unmark suspicious rows before persisting.
5. Rows persisted to `bank_transactions` with `imported_from='pdf'`.

### Story 7.3: Open Finance Adapter — Pluggy Default (Core)

> **MVP scope:** Only PluggyAdapter is required if enabled. BelvoAdapter and TecnoSpeedAdapter are V2.

As an Admin,
I want to optionally connect Open Finance,
So that statements arrive automatically.

**Acceptance Criteria:**

1. `IBankReconciliationProvider` Port: `connect_account`, `list_accounts`, `fetch_transactions`, `disconnect`.
2. `PluggyAdapter` (default); `BelvoAdapter`, `TecnoSpeedAdapter` alternatives.
3. Settings > Integrations: "Connect account" flow with Pluggy Connect widget.
4. Celery beat: incremental sync every 6 hours.
5. Default: **disabled** (cost concern).

### Story 7.4: Drag-and-Drop Reconciliation Screen (Core)

As a Manager,
I want to reconcile transactions with titles by dragging them,
So that the work is fast and visual.

**Acceptance Criteria:**

1. Route `/system/finance/reconciliation` with 50/50 split:
   - **Left**: bank transactions (status=pendente, filterable by date/value/type).
   - **Right**: system titles (installments + payables in `pago_aguardando_verificacao`).
2. Drag row from one side onto other -> confirmation modal with diff.
3. Auto-match: `score = exact_value(60%) + date_window(30%) + description_match(10%)`; score >= 0.85 highlighted with "match suggested" badge.
4. "Accept all suggestions" button for bulk match.
5. N:1 and 1:N reconciliation supported (multi-select + drop).
6. Unmatched transaction -> convert to payable or free-form revenue.
7. On confirmation: title -> `pago` (immutable), transaction -> `conciliada` (locked).
8. Top indicators: pending transactions, pending titles, conciliated today.

### Story 7.5: Divergence Detection (Core)

As the System,
I want to flag inconsistencies,
So that the manager can investigate.

**Acceptance Criteria:**

1. Top-of-screen "Alerts" panel with three categories:
   - Transactions with no compatible title (orphan revenue or bank error).
   - Titles flagged `pago` without matching transaction (suspect).
   - Value mismatches between transaction and candidate title.
2. Click alert -> contextual investigation pane.

---

## Epic 8: Dashboards, Reports & Asset Analytics (Core + Module Hooks)

**Goal:** The manager has consolidated executive sight and drilldown at any level, with pre-built reports and a custom builder. Vertical modules inject domain-specific widgets and reports via `IAssetModule.get_dashboard_widgets()` and `IAssetModule.get_report_dimensions()`.

### Story 8.0: Materialized Views and Dashboard Data Layer (Core)

As a Developer,
I want materialized views for heavy dashboard queries,
So that dashboards load in under 1.5s.

**Acceptance Criteria:**

1. Alembic migration creates `mv_asset_roi` materialized view (as defined in Architecture Section 9.9).
2. Celery Beat job refreshes `mv_asset_roi` daily at 05:00 via `REFRESH MATERIALIZED VIEW CONCURRENTLY`.
3. Endpoint `POST /api/v1/admin/refresh-views` allows Admin to force-refresh manually.
4. Index on materialized view for fast lookups.

### Story 8.1: Main Dashboard (Core + Module Hooks)

As a Manager,
I want to see business KPIs on a single screen,
So that I can read the operational pulse instantly.

**Acceptance Criteria:**

1. Route `/system/dashboard` with responsive card grid:
   - **Core KPIs**: Monthly Revenue (current vs previous, % delta), Monthly Expenses, Net Profit, Delinquency (R$ + %), Assets in Use, Assets Idle, Total Assets (R$), Next 7 Days Receivables, Pending Receipts, Portfolio Average Score.
   - **Module-injected widgets**: rendered via `IAssetModule.get_dashboard_widgets()`. E.g., Vehicle Module injects: Fleet Total (R$ FIPE consolidated), Active Vehicles, Parked, In Maintenance.
2. Cards reactive via Signals + `resource()`; refresh every 60 s or push via SSE.
3. Card click deep-links to filtered entity list.
4. Timeframe toggle: Today | This Week | This Month | This Quarter | This Year.
5. Charts: 12-month revenue line, expenses-by-category donut, delinquency-by-aging bars.

### Story 8.2: Customer Dashboard (Core)

As a Manager,
I want a financial dashboard per customer,
So that I can negotiate with data.

**Acceptance Criteria:**

1. "Dashboard" tab on customer detail page.
2. Cards: Total Contracted, Total Paid, Total Open, Total Overdue, Current Score (gauge), Punctuality % (12m).
3. Timeline chart: each payment colored by status.
4. Table: active contracts with balances and per-contract ROI.
5. "Export customer history" -> PDF.

### Story 8.3: Vehicle Dashboard (Vehicle Module)

As a Manager,
I want to analyze each vehicle's viability,
So that I can decide on sale/replacement.

**Acceptance Criteria:**

1. "Analysis" tab on vehicle detail page (injected by Vehicle Module).
2. Cards: Investment, Current FIPE, Depreciation, Total Received, ROI %, Accumulated Profit, Payback months.
3. Reads from materialized view `mv_asset_roi`; Celery job refreshes on schedule.
4. Line chart: accumulated investment vs accumulated revenue.
5. **Given** tracker provides KM, **Then** R$/day and R$/km productivity shown.
6. Timeline of drivers who used the vehicle.

### Story 8.4: Pre-built Reports (Core + Module Hooks)

As a Manager,
I want pre-built reports,
So that routine analyses are one click away.

**Acceptance Criteria:**

1. Route `/system/reports` with cards for:
   - **Core reports**: Top Customers by Revenue (12m), Aging of Delinquency, DRE Consolidated and per Asset, Customer ABC Curve.
   - **Module reports** (via `IAssetModule.get_report_dimensions()`): E.g., Vehicle Module adds: Top Vehicles by ROI (12m), Remote Block History, Fleet Position snapshot (date X).
2. Each report opens in viewer with filters, charts, table.
3. Export to Excel (formatted) and PDF (header/footer).
4. Heavy reports: Celery worker generation + SSE notification when ready.

### Story 8.5: Custom Report Builder (Core)

> **V2 — Deferred post-launch.** Pre-built reports (Story 8.4) cover MVP needs.

As an advanced Manager,
I want to compose my own reports,
So that I don't depend on engineering for new analyses.

**Acceptance Criteria:**

1. Route `/system/reports/builder` with three drag-and-drop zones:
   - **Available Dimensions**: customer, asset, contract, category, month, status, etc. + module-registered dimensions.
   - **Rows** and **Columns** targets.
   - **Measures** (count, sum, avg, min, max of numeric fields).
2. Filters: date range, status, customer.
3. Preview table updates live.
4. "Save as" persists to `saved_reports`.

---

## Epic 9: Hardening, Plug-and-Play & Final Documentation (Core)

**Goal:** The last 20% that separates demo from production: full audit with integrity verification, working integrations panel, observability, load tests, UX polish, module documentation, and adapter guide.

### Story 9.1: Centralized Integrations Panel (Core)

As an Admin,
I want a single screen to manage every integration,
So that plug-and-play is operationally real.

**Acceptance Criteria:**

1. Route `/system/config/integrations` with cards per category: WhatsApp Gateway, Open Finance / Banks, Payment Gateway, LLM Provider, OCR Provider, Storage, PDF Renderer. Module-specific integrations: e.g., Vehicle Module adds FIPE, Tracker.
2. Each card: active provider, status (healthy/degraded/error), actions: "Test connection", "Switch provider", "Configure".
3. "Switch provider": dialog lists available adapters with required credentials.
4. Credentials encrypted at rest (AES-256-GCM with master key).
5. Every change writes audit-log diff with secrets masked.
6. `GET /api/v1/integrations/health` returns status of every provider.

### Story 9.2: Audit Log Search and Viewer (Core)

As an Auditor,
I want to query the entire action history,
So that I can trace any event.

**Acceptance Criteria:**

1. Route `/system/audit` with searchable table: user, action, entity, date, IP, payload.
2. Filters: user, entity, action (multi-select), date range.
3. Row expand: payload diff before/after in collapsible JSON pretty-print.
4. Integrity indicator: "OK" if HMAC verifies, "ALERT: tampered" if not.
5. CSV export respects active filter.

### Story 9.3: Module Management UI (Core)

As an Admin,
I want to enable/disable vertical modules and configure their hooks,
So that the platform adapts to my business needs.

**Acceptance Criteria:**

1. Route `/system/config/modules` lists registered modules with: name, status (active/inactive), toggle, "Configure" button.
2. **Given** toggle off, **Then** module stops receiving events, its hooks are deactivated, its UI sections/tabs/widgets disappear, menus hide module-specific items.
3. **Given** toggle on, **Then** module registers, receives events, UI sections appear.
4. "Configure" opens module-specific settings (e.g., Vehicle Module: block policy thresholds, FIPE refresh schedule).
5. Hooks configuration: list of events the module subscribes to, with policy editor per event.

### Story 9.4: Backup, Restore, and DR (Core)

As an Operator,
I want verified automatic backups,
So that disasters are recoverable within SLA.

**Acceptance Criteria:**

1. Daily Celery beat at 03:00: `pg_dump`, compress, ship to off-site (S3/B2/Wasabi, configurable), 30-day retention.
2. Continuous WAL archiving via wal-g or pgBackRest.
3. Weekly restore test in isolated environment with smoke tests; failures alert admins.
4. `RUNBOOK_DR.md` committed with step-by-step restore playbook (RTO < 4h).

### Story 9.5: Full Observability (Core)

As an Operator,
I want Grafana dashboards and alerts,
So that I run the system with confidence.

**Acceptance Criteria:**

1. Prometheus metrics at `/metrics`: per-route request counts, latency histograms, queue depth, errors, DB connections.
2. OpenTelemetry tracing; traces in Jaeger or Tempo.
3. Structured JSON logs with `correlation_id` propagation.
4. Grafana dashboards (API Overview, DB, Workers, Business, Agent IA) in `infra/observability/grafana/`.
5. Alertmanager rules: API 5xx > 1% (5m), P95 > 1s (10m), Celery queue > 1000 (5m), DB conn pool > 90% (5m), disk > 85%, webhook failures > 5% (10m), agent daily LLM spend over threshold.

### Story 9.6: Load Tests and Performance Tuning (Core)

As the Team,
I want to validate the system handles forecast load,
So that launch is safe.

**Acceptance Criteria:**

1. k6 suite in `tests/load/` covering: dashboard, receivables list, write-off, reconciliation.
2. Validated targets: 100 RPS sustained, P95 <= 300 ms (read), 500 ms (write).
3. Optimization changes documented: indexes, query rewrites, caching, cursor pagination.

### Story 9.7: Final Documentation (Core)

As the Next Developer,
I want complete documentation,
So that I can maintain the product without the original author.

**Acceptance Criteria:**

1. `README.md` enables local setup in < 10 minutes.
2. `ARCHITECTURE.md` reviewed and versioned.
3. `ADAPTERS.md`: "how to add a new adapter" guide for each Port.
4. `MODULES.md`: "how to create a new vertical module" guide, covering `IAssetModule` implementation, hook registration, schema extensions, UI injection points.
5. OpenAPI at `/docs` with snapshot in `API.md`.
6. `DEPLOYMENT.md` deploy playbook.
7. `RUNBOOK.md` troubleshooting guide.
8. ADRs `0001`-`0010` under `docs/adrs/` (Hexagonal, SSE+WS split, pgvector, Celery, Evolution, Tesseract OCR, No-gateway Pix default, Paid-installment immutability PG trigger, Single-tenant first, Asset Abstraction Layer).

> **MVP scope:** Only ADRs 0008 (paid installment immutability) and 0010 (two parallel repos) are required pre-launch. Others can be written retroactively.

### Story 9.8: UX Polish and Microinteractions (Core)

> **MVP scope:** axe-core CI, skeleton loaders, and empty states are MVP. FLIP animations, View Transitions, and optimistic UI rollback are V2.

As a User,
I want the app polished,
So that the experience is pleasant under daily use.

**Acceptance Criteria:**

1. Page-transition animations (FLIP / View Transitions API where supported).
2. Skeleton loaders on every list and card.
3. Toasts: unified queue with auto-dismiss.
4. Empty states (illustration + CTA) on every list.
5. Modals respect `prefers-reduced-motion`.
6. Optimistic updates with rollback on error.
7. axe-core in CI with zero critical violations.
8. Mobile review at 375 px and 768 px screen-by-screen.

### Story 9.9: Versioned Configuration and Settings Consolidation (Core)

As an Admin,
I want all configurations versioned with change history,
So that I can audit who changed what and when.

**Acceptance Criteria:**

1. Every configuration section (Company, Billing, Agent, Integrations, Modules, Permissions, Templates) maintains a versioned history with who, when, and prior value.
2. Route `/system/config/history` shows configuration change log with diff viewer.
3. Consolidated Settings screen at `/system/config` with all sections.

### Story 9.10: LGPD "My Data" Self-Service (Core)

As a Customer (external),
I want to export or request deletion of my personal data,
So that the system complies with LGPD.

**Acceptance Criteria:**

1. Endpoint `GET /api/v1/customers/{id}/data-export` generates a ZIP with all personal data (profile, contracts, titles, messages, attachments).
2. Endpoint `POST /api/v1/customers/{id}/anonymize` replaces personal fields with "[redigido]", masks CPF, removes photos — preserving financial history for audit.
3. Anonymization requires Admin role + reason + audit log entry with category='security'.
4. A simple "Meus Dados" page accessible via a unique link sent to the customer (no full app login required — token-based access).
5. The page shows: personal data summary, "Exportar Dados" button, "Solicitar Exclusão" button (sends request to Admin for review).

### Story 9.11: Command Palette (Ctrl+K) (Core)

As a Manager,
I want a global command palette for instant navigation and actions,
So that I never need to hunt for a screen or action.

**Acceptance Criteria:**

1. `Ctrl+K` (or `Cmd+K` on Mac) opens `<ui-command-palette>` overlay anywhere in the app.
2. Search modes: default (fuzzy search across customers, vehicles, contracts, titles by name/CPF/plate/number), `>` prefix for actions ("baixar título 1234"), `#` for titles by number, `@` for customers.
3. Results update live with debounce 200ms; keyboard navigation (↑/↓/Enter/Esc).
4. Recent searches persisted in localStorage (last 10).
5. Component lives in `frontend/src/app/shared/components/command-palette/`.
6. Backend endpoint `GET /api/v1/search?q=&type=` returns unified search results across entities.

---

## Epic 10: Recurrence Engine, Automated Collection & Channel Health (Core)

This epic implements the automated operational backbone: recurring title generation (with monetary correction), payable draft lifecycle, the full collection engine (pre-due reminders → overdue escalation → GPS block), message template management, channel health monitoring, worker scheduler consolidation, user self-registration, and a reusable modal component.

### Story 10.1: Monthly Installment Generation with Correction Index (Core)

As a System,
I want to generate installments monthly applying the current correction index,
So that contracts with monetary correction have accurate values each month.

**Acceptance Criteria:**

1. Contract model extended with `generation_mode` (upfront | monthly), `correction_index` (igpm | ipca | inpc | null), `generation_day` (1-28), `next_generation_date`.
2. `ICorrectionIndexProvider` port with `get_current_rate(index, reference_date) -> Decimal`.
3. `BcbCorrectionAdapter` fetching rates from BCB API (Banco Central do Brasil) — public, no auth. Series: IGPM=189, IPCA=433, INPC=188. Cache in Redis TTL 30 days.
4. Celery Beat task `generate_monthly_installments` runs daily at 06:00.
5. Task is idempotent — checks if installment for that period already exists.
6. Fallback: if BCB unavailable, uses last cached rate + logs warning.

### Story 10.2: Payable Draft Lifecycle (Core)

As a Manager,
I want recurring payables generated as drafts that I can fill in and save,
So that the system reminds me of fixed expenses without requiring exact values upfront.

**Acceptance Criteria:**

1. Payable status lifecycle enforced: `rascunho` → `pendente` → `pago` | `cancelado`.
2. `rascunho`: can edit all fields, can DELETE (hard delete allowed).
3. `pendente`: can edit, pay, or cancel (soft — never hard delete, preserves audit trail).
4. `pago` and `cancelado`: immutable.
5. Recurring template generates payables with `status=rascunho`.
6. SSE notification to manager when draft is generated.

### Story 10.3: Automated Collection Engine (Core)

As a System,
I want to automatically send payment reminders before due date and escalate overdue installments,
So that collection happens without manual intervention.

**Acceptance Criteria:**

1. `collection_policy` in system_settings: `reminder_days_before`, `overdue_escalation` (array of {days, action, template_id}), `agent_can_negotiate`, `agent_max_grace_days`, interest/fine rates.
2. Celery task `check_upcoming_due_dates` (daily 08:00): sends reminder via WhatsApp N days before due date.
3. Celery task `check_overdue_installments` (daily 09:00): updates status to `vencido`, executes escalation per policy (reminder → warn_block → block → notify_manager).
4. Celery task `check_paid_installments` (every 30 min): detects payments, sends confirmation, triggers unblock.
5. All messages sent via `IMessageChannel` (channel registry), not direct adapter.
6. Agent orchestrator handles customer replies with negotiation autonomy (configurable max grace days).
7. Frontend: collection policy config page at `/system/settings/collection`.

### Story 10.4: Message Template Management (Core)

As a Manager,
I want to create and manage message templates for each collection stage,
So that I can customize the tone and content of automated messages.

**Acceptance Criteria:**

1. `message_templates` table: name, channel, trigger (upcoming_due | overdue_d1 | warn_block | payment_confirmed | custom), body, variables.
2. CRUD endpoints for templates.
3. Default templates seeded in Portuguese.
4. Template preview with sample data.
5. Variables: {nome}, {valor}, {valor_atualizado}, {data_vencimento}, {dias_atraso}, {placa}, {contrato}, {link_pagamento}.

### Story 10.5: Channel Health Monitoring (Core)

As a Manager,
I want to see which messaging channels are configured and healthy,
So that I know if my automated collection will work.

**Acceptance Criteria:**

1. Celery task `check_channel_health` runs every 5 minutes — calls `health_check()` on all registered channels via `ChannelRegistry`.
2. Dashboard widget showing channel status with green/yellow/red badges.
3. SSE notification when a channel goes unhealthy.
4. Settings > Integrações shows real-time health per channel with latency.

### Story 10.6: Worker Scheduler Consolidation (Core)

As a System Administrator,
I want all scheduled tasks consolidated with proper crontab timing and a monitoring dashboard,
So that I can verify all automations are running correctly.

**Acceptance Criteria:**

1. All Celery Beat tasks use `crontab()` with exact times (03:00 backup, 04:00 recurring payables, 05:00 scores, 06:00 monthly installments, 08:00 upcoming due, 09:00 overdue, */30 paid check, */5 channel health, */60 views refresh).
2. Admin endpoint lists all scheduled tasks with last run, next run, status.
3. Frontend: "Tarefas Agendadas" page showing each task schedule and execution status.

### Story 10.7: User Registration and Email Verification (Core)

As a new User,
I want to register an account and verify my email,
So that I can access the system securely.

**Acceptance Criteria:**

1. `POST /auth/register` — creates user with `is_active=false`, sends verification email.
2. `POST /auth/verify-email` — activates user account (single-use token, 1h TTL).
3. `POST /auth/resend-verification` — rate limited (3/hour), always returns 200.
4. Login with unverified email returns 403.
5. Frontend: 3-step register wizard (glassmorphism), verify-email page, resend-verification page.

### Story 10.8: Reusable Modal Component (Core)

As a Developer,
I want a single reusable modal component that handles ESC, backdrop click, z-index, and animation,
So that I never repeat modal boilerplate in every component.

**Acceptance Criteria:**

1. `ModalComponent` in `shared/components/modal/` with inputs: `[open]`, `[size]`, `[title]`.
2. Output: `(closed)` on ESC, backdrop click, or X button.
3. Built-in: z-index, backdrop, fade+scale animation, auto-focus for ESC capture.
4. Content projection via `<ng-content>` + `<ng-content select="[modal-footer]">`.
5. ALL existing 13 inline modals replaced with `<app-modal>`.

---

## Epic 11: WhatsApp Token Economy & Operational Modes (Core)

This epic implements the token-economy layer over Epic 6: three operation modes (`ia-full` / `ia-eco` / `ia-zero`) with automatic downgrade on budget exhaustion, deterministic intent routing without LLM, interactive WhatsApp menus, receipt deduplication with manual validation queue, audio handling per mode, manager-driven rule learning, and plan tiers. **Critical operational principle: the system never stops, even when IA is fully exhausted (ia-zero).**

### Story 11.1: Token Budget, Tracking & Throttle Engine (Core)

As a Tenant Manager,
I want a monthly LLM token budget with live tracking, alerts, and automatic mode downgrade,
So that I never get a surprise bill and the WhatsApp operation never stops when IA runs out.

**Acceptance Criteria:**

1. `system_settings.token_budget` JSONB with `monthly_limit_tokens`, `auto_throttle_enabled`, `thresholds`, `reset_day_of_month`.
2. Table `token_usage_monthly` upserted from `agent_runs` (Story 6.4).
3. Celery task `evaluate_token_throttle` (every 5 min) downgrades mode when threshold crossed.
4. Monthly reset restores `configured_mode` on day 1 at 00:05.
5. SSE alerts at 50%/75%/95% of budget.
6. Endpoints: `GET/PUT /api/v1/system/token-usage`, `/token-budget`.
7. Dashboard widget + Settings page + persistent banner when throttled.
8. Anti-flap: manual override blocks auto-throttle for current period.

### Story 11.2: Operation Modes (ia-full / ia-eco / ia-zero) (Core)

As a Tenant Manager,
I want to choose how aggressively the IA participates in WhatsApp operations,
So that I can balance customer experience against token cost.

**Acceptance Criteria:**

1. Postgres enum `operation_mode`: `ia_full`, `ia_eco`, `ia_zero`.
2. Capability matrix gates every LLM/transcription/vision call.
3. `OperationModeService.is_allowed(capability)` consulted by agent orchestrator (Story 6.4).
4. In `ia-zero`, inbound bypasses LLM and goes 100% to intent rules (Story 11.4).
5. UI shows current vs configured mode with auto-restore on monthly reset.
6. Mode change emits SSE + audit_log entry (category=security).
7. Header badge with mode color (green/yellow/grey).

### Story 11.3: Interactive WhatsApp Menu (List Messages & Reply Buttons) (Core)

As a Customer,
I want to choose actions from a menu of buttons/options instead of typing,
So that I get faster responses and the company spends less on IA.

**Acceptance Criteria:**

1. Table `interactive_menus` with items (action_type: send_template | show_submenu | call_function | handover_human).
2. `MenuRenderer` generates per-adapter payload (Z-API / Uazapi / Evolution).
3. WhatsApp limits enforced (List ≤10 items, Buttons ≤3, auto-fallback).
4. Default PT-BR menus seeded (main, payment, overdue).
5. Inbound `interactive_response` mapped to action via dispatcher.
6. Drag-drop editor + side-by-side preview + "Testar" sends to manager's number.
7. In `ia-zero`, unmatched messages auto-respond with main_menu.
8. WhatsApp 24h window detection (templates outside window).

### Story 11.4: Intent Rules Engine (flashtext + rapidfuzz + regex) (Core)

As a System,
I want to classify customer messages deterministically without LLM,
So that we can route to templates/menus/functions in ia-eco and ia-zero modes with zero token cost.

**Acceptance Criteria:**

1. Table `intent_rules` with match_type (keyword/regex/fuzzy), priority, action_type.
2. `IntentMatcher` service: flashtext for keywords, `re` for regex, rapidfuzz for fuzzy.
3. Default PT-BR rules seeded (saudacao, pedido_boletos, comprovante_enviado, etc.).
4. In `ia-zero`: matcher only, no LLM. In `ia-eco`: matcher first, LLM classifier on unknown (~50 tokens).
5. `intent_match_log` for stats and Story 11.7 learning.
6. UI for CRUD + drag-drop priority + "Testar" tester + bulk import.
7. Performance target: p99 < 10ms for 500 rules per tenant.
8. ReDoS prevention on regex validation.

### Story 11.5: Receipt Dedupe + Manual Validation Queue (Core)

As a System,
I want to detect duplicate receipts and gracefully queue low-confidence OCR results for human validation,
So that we never double-credit a payment and the operation continues even when LLM Vision fallback is disabled.

**Acceptance Criteria:**

1. Table `receipt_fingerprints` with pHash + txn_id + confidence + status.
2. Duplicate detection: exact txn_id OR Hamming distance pHash ≤5.
3. Auto write-off only when confidence ≥70 AND single candidate match.
4. In `ia-eco`/`ia-zero`: LLM Vision fallback disabled; low-confidence → manual queue with customer notification template.
5. Page `/system/receipts/pending` with detail modal + candidate ranking.
6. SSE notification on new pending item.
7. Approve / Reject / Reassign endpoints with audit trail.

### Story 11.6: Audio Handling Per Operation Mode (Core)

As a Customer,
I want my voice messages to either be transcribed (when IA is on) or deflected with a friendly menu (when IA is off),
So that I always get a response and the company has predictable cost.

**Acceptance Criteria:**

1. Mode gate: `ia-full`/`ia-eco` transcribe; `ia-zero` deflects.
2. Deflection template + immediate `main_menu` follow-up.
3. 3 consecutive deflected audios → conversation marked `needs-attention`.
4. Inbox shows deflected audios with "Ouvir mesmo assim" manual transcribe option.
5. Toggle `transcribe_in_eco_mode` (default ON).
6. Max audio length config (default 5min) — auto-deflect even in ia-full.

### Story 11.7: Out-of-Scope Detection & Manager Learning (Core)

As a Manager,
I want to see customer messages the system couldn't classify and easily turn my manual reply into a permanent rule,
So that the autopilot keeps getting smarter over time.

**Acceptance Criteria:**

1. Out-of-scope detection across all modes (catch-all hit, LLM unknown, explicit handover).
2. Materialized view + top-50 grouped messages page (Settings → Aprendizado).
3. Inline "Salvar como regra" button on inbox messages flagged out_of_scope.
4. Keyword suggestion via IDF (no LLM) + PT-BR stop word filter.
5. Quick-form (not wizard) to create rule from a message in 2 clicks.
6. Dashboard widget: "X out-of-scope this week — Treinar agora".

### Story 11.8: Plan Tiers UI & Quotas (Core)

As a Tenant Manager,
I want to see which plan I'm on, what each plan includes, and what I'd unlock by upgrading,
So that I can decide whether to increase my budget when I hit limits.

**Acceptance Criteria:**

1. Table `plan_tiers` system-wide (Starter / Pro / Business / Enterprise) with features matrix + token/msg limits.
2. `tenants.plan_tier_id` FK.
3. `PlanService.is_feature_included()` gates feature activation (ex.: Starter can't set `ia-full`).
4. `effective_token_limit` = min(plan limit, manager setting).
5. Settings → Plano: comparador horizontal + upgrade modal (V1 mailto, V2 billing real).
6. Feature gates on token budget edit, mode change, LLM provider selection.
7. Audit log entries on plan change (category=billing).

---

## 🔴 PRIORIDADE ALTA: Tradução PT-BR de Artefatos de Planejamento (decisão 2026-05-24)

> **Decisão de Pablo (2026-05-24):** "Eu não estou entendendo o que está escrito nas stories porque está tudo em inglês e eu não domino o inglês. Coloque no roadmap para, assim que possível, fazermos essa tradução, e a partir de agora deixe configurado para documentar tudo em português."
>
> Config `_bmad/bmm/config.yaml` já foi mudado para `document_output_language: Portuguese`. Documentos NOVOS já saem em PT-BR. Falta traduzir o backlog existente.

### História 12.9: Tradução PT-BR de Artefatos de Planejamento e Stories

**Status:** ready-for-dev (alta prioridade — sem isso, Pablo não consegue revisar nenhuma story)

**Como** product owner que precisa revisar e aprovar cada história antes da implementação,
**quero** que todo o backlog (PRD, épicos, stories) esteja em português,
**para** poder ler, entender e validar o conteúdo sem depender de tradução manual.

**Critérios de aceite:**

1. `_bmad-output/planning-artifacts/PRD.md` traduzido integralmente para PT-BR (terminologia técnica consagrada permanece em inglês: HTTP, JWT, Celery, FastAPI, REST, etc.).
2. `_bmad-output/planning-artifacts/ARCHITECTURE.md` traduzido integralmente para PT-BR.
3. `_bmad-output/planning-artifacts/epics.md`: títulos e descrições de épicos 1 a 11 (que ainda estão em inglês) traduzidos para PT-BR. Épicos 12, 13 e 14 já estão em PT-BR — manter.
4. `_bmad-output/implementation-artifacts/*.md`: todas as stories `ready-for-dev` ou `backlog` traduzidas. Stories `done` podem ficar como estão (não vamos reescrever histórico) — exceção: títulos no sprint-status.yaml ficam como estão (identificadores).
5. `docs/manual-desenvolvedor-tecnico.md` e `docs/manual-desenvolvedor-funcional.md`: já estão em PT-BR — apenas revisar se tem trechos remanescentes em inglês.
6. Glossário em `docs/glossario-ptbr.md` ampliado com termos de produto recém-traduzidos (ex.: "asset" → "ativo", "tracker" → "rastreador", "installment" → "título a receber", "payable" → "título a pagar", "draft" → "rascunho").
7. CHECK: rodar busca por palavras frequentes em inglês (`receivable`, `payable`, `installment`, `customer`, `vehicle`, `tracker`, `attachment`, `recurring`, `template`, `aggregate`) nos artefatos `.md` — não devem aparecer em frases corridas (só em nomes de classe/arquivo/identificador).

**Dev notes:**

- A tradução é mecânica + revisão humana. Pode ser feita em lotes (1 PR por épico).
- Termos técnicos a manter em inglês: HTTP, REST, JWT, OAuth, RSA, Argon2, Celery, FastAPI, Pydantic, SQLAlchemy, Alembic, Redis, PostgreSQL, MinIO, JSONB, UUID, ENUM, TIMESTAMPTZ, ASGI, ORM, DTO, repository, adapter, port, hexagonal, ADR, CRUD, CI/CD, PR, idempotência (já em PT-BR).
- Termos de produto/domínio: traduzir SEMPRE. Ver [[feedback-naming-convention-pt]].
- Após tradução, atualizar `_bmad-output/implementation-artifacts/sprint-status.yaml` apenas se algum slug de identificador mudar (provavelmente não muda — slugs ficam como estão).

**Estimativa:** 1-2 sessões dedicadas. Pode ser feita em paralelo com Epic 12 restante (não bloqueia).

**Onde encaixar na sequência:** **AGORA** — entre fechar Epic 12 (stories 12.4 a 12.8) e iniciar Epic 13. Pablo precisa conseguir revisar as próximas stories antes de aprovar implementação.

---

## ⏸️ PAUSA OBRIGATÓRIA antes de Épico 13: Revisão Automation/Manual + Arquitetura de Workers

> **Decisão de Pablo (2026-05-24):** Antes de implementar qualquer motor do Epic 13, fazer uma sessão dedicada para:
>
> 1. **Definir o que é automático vs manual** para cada operação financeira (geração, juros/multa, bloqueio, cobrança, conciliação, renegociação, encerramento, quitação antecipada). Cada story do Epic 13 deve declarar explicitamente seu trigger.
> 2. **Confirmar arquitetura single-infra multi-tenant**: backend é deployment único, banco único, workers Celery paralelos que varrem TODAS empresas filtrando por estado (não por empresa). NUNCA infra "por cliente". Workers herdam empresa_id do registro processado, não do request. Ver memória `project_single_infra_architecture`.
> 3. **Especificar a "Sala de Health Multi-Tenant"** (story nova, possivelmente Epic 15): UI cross-tenant para devs/operação ver status de workers, filas Celery, motores (último/próximo run, taxa de sucesso), logs estruturados em tempo real, alertas de erro. Funciona FORA do frontend do cliente (subdomain `admin.*` ou rota `/admin/observability/*` com guard role=superadmin). Verificar reuso da infra Grafana/Loki/Prometheus de 9.5 antes de duplicar.
>
> **Sem essa revisão, não iniciar Epic 13.**

---

## Épico 13: Motor Financeiro Central (Core)

> ⚠️ **Nota sobre numeração:** O Epic 12 já está alocado para "Schema Restructure & Multi-Tenancy" (DDL migration, rename PT-BR de tabelas/models, multi-tenancy com empresa_id). As histórias 12.1 a 12.8 do Epic 12 são pré-requisito deste Epic 13 — especialmente 12.6 (workers & tasks rename) que prepara o terreno para os motors deste épico.

**Objetivo:** Tornar o sistema operacional 24h/7 com workers Celery autônomos para geração de títulos, cobrança automatizada, verificação de pagamentos, máquina de estados do contrato e regras de negócio ausentes — incluindo o modelo correto de locação com opção de compra.

**Premissas do modelo de negócio confirmadas:**
- O contrato é **locação com opção de compra** (rent-to-own): N parcelas mensais + 1 parcela única final (opção de compra).
- Saldo devedor = apenas parcelas vencidas e não pagas (`status = 'em_atraso'`). Parcelas futuras **não** são dívida.
- Cancelamento sem atraso → zero saldo devedor. Veículo retorna à frota.
- Opção de compra paga → veículo transferido ao cliente.

**Dependências:** Épicos 1–11 concluídos ou em progresso.

**Convenção de nomenclatura:** TODOS os termos técnicos em PT-BR. Inglês vedado em código de domínio.

---

### História 13.1: Verificação de Consistência PT-BR + Glossário do Domínio

> **Nota:** O rename principal do sistema (tabelas, models SQLAlchemy, schemas Pydantic, routes, workers existentes, frontend) é feito pelas histórias 12.2 a 12.8 do **Epic 12 (Schema Restructure & Multi-Tenancy)**. Esta história 13.1 cobre a **verificação final**, o **glossário** e a **convenção para todo código NOVO** do motor (histórias 13.4 em diante).

**Critérios de Aceite Originais (mantidos):**

Como desenvolvedor do sistema,
quero que todo o código de domínio financeiro use nomenclatura em português,
para que haja consistência entre código, documentação e regras de negócio.

**Critérios de Aceite:**

1. Todos os nomes de funções, classes, variáveis e eventos de domínio financeiro renomeados conforme tabela abaixo — sem quebra de funcionalidade existente.

2. Tabela de mapeamento obrigatória aplicada:

| Nome antigo (EN) | Nome novo (PT-BR) |
|---|---|
| `generate_monthly_installments` | `gerar_titulos_mensais` |
| `check_overdue_installments` | `processar_titulos_vencidos` |
| `check_upcoming_due_dates` | `alertar_vencimentos_proximos` |
| `check_paid_installments` | `conciliar_pagamentos_recebidos` |
| `calculate_customer_scores` | `atualizar_scores_clientes` |
| `generate_recurring_payables` | `gerar_contas_pagar_recorrentes` |
| `check_channel_health` | `monitorar_saude_canais` |
| `refresh_materialized_views` | `atualizar_visoes_materializadas` |
| `on_installment_paid` | `quando_titulo_pago` |
| `on_installment_overdue` | `quando_titulo_vencido` |
| `on_contract_created` | `quando_contrato_ativado` |
| `on_contract_terminated` | `quando_contrato_encerrado` |
| `InstallmentOverdueEvent` | `EventoTituloVencido` |
| `InstallmentPaidEvent` | `EventoTituloPago` |
| `ContractCreatedEvent` | `EventoContratoAtivado` |
| `ContractTerminatedEvent` | `EventoContratoEncerrado` |
| `PaymentPartiallyReceivedEvent` | `EventoPagamentoParcialRecebido` |
| `CustomerScoreChangedEvent` | `EventoScoreClienteAlterado` |
| `collection_policy` | `politica_cobranca` |
| `template_renderer` | `renderizador_template` |
| `IAssetModule` | `IModuloVertical` |
| `IMessageChannel` | `ICanalMensagem` |
| `IPaymentGateway` | `IGatewayPagamento` |
| `ITrackerGateway` | `IGatewayRastreador` |

3. Rotas de API existentes mantêm compatibilidade via aliases com `deprecated=True` até próximo épico — sem breaking change para o frontend.

4. Migrações Alembic geradas para colunas renomeadas em tabelas de auditoria.

5. Suite de testes existente passa sem alteração de lógica — apenas adaptação de imports e nomes renomeados.

6. Arquivo `docs/glossario_dominio.md` criado com a tabela de mapeamento completa.

7. Nenhum termo em inglês de domínio financeiro permanece em: `domain/`, `application/`, `workers/`, `api/routers/`. Infraestrutura técnica (SQLAlchemy, FastAPI, Celery internals) mantém nomenclatura original das bibliotecas.

---

### História 13.2: Máquina de Estados do Contrato com Status `suspenso`

Como operador do sistema,
quero que o contrato possua a máquina de estados completa com o status `suspenso`,
para que contratos inadimplentes sejam pausados automaticamente sem encerramento definitivo.

**Critérios de Aceite:**

1. Enum `SituacaoContrato` com todos os estados e transições válidas (parâmetros de limite lidos de `config.configuracoes_sistema` via `ServicoConfiguracao` — ver História 13.4):

| De | Para | Ator | Gatilho |
|---|---|---|---|
| `rascunho` | `ativo` | Humano | Ativação manual |
| `ativo` | `suspenso` | Automático | Motor ao atingir config `limite_dias_suspensao` (financeiro) |
| `suspenso` | `ativo` | Humano | Pagamento confirmado ou desbloqueio em confiança |
| `ativo` | `encerrado_sem_pendencia` | Automático + Humano | Cancelamento sem atraso |
| `ativo` | `encerrado_com_pendencia` | Automático + Humano | Cancelamento com atraso — passivo gerado |
| `ativo` | `encerrado_compra` | Automático | Opção de compra paga — `OpcaoCompraPaga` |
| `ativo` | `rescindido` | Humano | Rescisão formal |
| `suspenso` | `encerrado_com_pendencia` | Automático + Humano | Inadimplência crônica (> config `limite_dias_encerramento`) |

2. Tabela `contratos` recebe coluna `situacao` com constraint CHECK validando estados acima. Migration Alembic gerada.

3. Colunas adicionais: `suspenso_em` (timestamptz nullable), `motivo_suspensao` (varchar 255 nullable).

4. Serviço `ServicoSituacaoContrato` em `application/services/` com método `transicionar(contrato_id, nova_situacao, motivo)` que valida o grafo, persiste, publica evento de domínio e registra `audit_log` com `categoria='financeiro'`.

5. Contratos `suspenso` são ignorados pelo motor `gerar_titulos_mensais` — nenhuma nova parcela gerada enquanto suspenso.

6. Ao suspender: hook `quando_contrato_suspenso` chama bloqueio do veículo via `IGatewayRastreador`.

7. Ao reativar: hook `quando_contrato_reativado` chama desbloqueio do veículo.

8. Frontend: badge de situação no card do contrato — `ativo` (verde), `suspenso` (âmbar), `encerrado_*` (cinza), `rescindido` (cinza escuro). Badge exibido na listagem de contratos e no detalhe.

9. Testes unitários: todas as transições válidas passam; todas as inválidas lançam `TransicaoInvalidaError`.

---

### História 13.3: Tipo de Título e Opção de Compra

Como sistema financeiro,
quero que a tabela de títulos distingua parcelas regulares de locação da opção de compra,
para que o pagamento da opção de compra dispare automaticamente a transferência de propriedade do veículo.

**Critérios de Aceite:**

1. Enum `TipoTitulo` adicionado:

```sql
CREATE TYPE tipo_titulo AS ENUM (
    'parcela',        -- mensalidade regular de locação
    'opcao_compra',   -- parcela única final — se paga, transfere propriedade
    'multa',          -- multa contratual
    'taxa',           -- taxa avulsa
    'ajuste'          -- ajuste manual
);

ALTER TABLE titulos ADD COLUMN tipo tipo_titulo NOT NULL DEFAULT 'parcela';
ALTER TABLE titulos ADD COLUMN numero_parcela SMALLINT;
ALTER TABLE titulos ADD COLUMN total_parcelas SMALLINT;
```

2. Constraint: apenas 1 título `opcao_compra` por contrato:

```sql
CREATE UNIQUE INDEX uniq_opcao_compra_por_contrato
    ON titulos (contrato_id) WHERE tipo = 'opcao_compra'::tipo_titulo;
```

3. Geração de títulos ao criar contrato: N parcelas `tipo='parcela'` com `numero_parcela` sequencial + 1 parcela `tipo='opcao_compra'` com vencimento após a última parcela regular (apenas se `contrato.valor_opcao_compra IS NOT NULL`).

4. Campo `valor_opcao_compra` adicionado à tabela `contratos` (nullable — contratos de locação pura sem opção de compra têm `NULL`).

5. Hook `quando_titulo_pago` verifica `titulo.tipo`:
   - `parcela` → fluxo normal
   - `opcao_compra` → publica evento `OpcaoCompraPaga(contrato_id, titulo_id, cliente_id, veiculo_id, valor_pago, data_pagamento)`

6. Handler `OpcaoCompraPagaHandler` no módulo de Veículos:
   - `veiculo.status = 'alienado'`
   - `veiculo.proprietario_id = cliente_id`
   - `contrato.situacao = 'encerrado_compra'`
   - Audit log com `categoria='transferencia_propriedade'`

7. Saldo devedor calculado apenas sobre parcelas `tipo='parcela'` com `status='em_atraso'` — opção de compra não entra no cálculo de inadimplência padrão.

8. Frontend: no detalhe do contrato, a opção de compra é exibida em seção separada com destaque visual (`★`), valor, data de vencimento e status (`pendente` / `pago` / `⏸ suspenso — quitar atraso primeiro`).

9. Testes: pagamento da parcela regular → sem transferência; pagamento da `opcao_compra` → veículo alienado, contrato `encerrado_compra`.

---

### História 13.4: Sistema de Configurações Tipadas (`config.configuracoes_sistema`)

Como gestor de empresa,
quero um sistema centralizado e tipado de configurações que sirva a todos os módulos do sistema,
para que qualquer parâmetro (financeiro, frota, comunicação) seja editável sem migration de banco e validado pelo PostgreSQL.

**Critérios de Aceite:**

1. Tabela `config.configuracoes_sistema` criada com validação por tipo via `CHECK constraint`:

```sql
CREATE TABLE config.configuracoes_sistema (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id      UUID REFERENCES comercial.empresas(id) ON DELETE CASCADE,
    modulo          VARCHAR(50) NOT NULL,
    slug            VARCHAR(100) NOT NULL,
    tipo_valor      VARCHAR(20) NOT NULL,
    valor           TEXT NOT NULL,
    descricao       TEXT,
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_por  UUID REFERENCES usuarios(id),

    CONSTRAINT uniq_config_empresa_slug UNIQUE (empresa_id, slug),

    CONSTRAINT ck_tipo_valor_aceito CHECK (
        tipo_valor IN ('string','inteiro','decimal','booleano','json')
    ),

    CONSTRAINT ck_valor_combina_com_tipo CHECK (
        (tipo_valor = 'inteiro'  AND valor ~ '^-?\d+$')                    OR
        (tipo_valor = 'decimal'  AND valor ~ '^-?\d+(\.\d+)?$')            OR
        (tipo_valor = 'booleano' AND valor IN ('true','false'))            OR
        (tipo_valor = 'string')                                            OR
        (tipo_valor = 'json'     AND valor::jsonb IS NOT NULL)
    )
);

CREATE INDEX idx_config_modulo ON config.configuracoes_sistema(modulo);
CREATE INDEX idx_config_empresa_modulo ON config.configuracoes_sistema(empresa_id, modulo);
```

2. **Serviço `ServicoConfiguracao`** em `application/services/` com fallback automático:

```python
class ServicoConfiguracao:
    def obter_inteiro(self, slug: str, modulo: str, padrao: int) -> int: ...
    def obter_decimal(self, slug: str, modulo: str, padrao: Decimal) -> Decimal: ...
    def obter_booleano(self, slug: str, modulo: str, padrao: bool) -> bool: ...
    def obter_string(self, slug: str, modulo: str, padrao: str) -> str: ...
    def obter_json(self, slug: str, modulo: str, padrao: dict) -> dict: ...

    def definir(self, slug: str, modulo: str, valor: Any, tipo_valor: str) -> None: ...
```

3. Seed inicial via `python -m app.cli seed` cria configurações padrão por módulo:

| slug | módulo | tipo_valor | valor padrão | descrição |
|---|---|---|---|---|
| `dias_antecedencia_lembrete` | financeiro | inteiro | 3 | Dias antes do vencimento para enviar lembrete |
| `dias_carencia` | financeiro | inteiro | 0 | Dias de tolerância após vencimento |
| `percentual_multa` | financeiro | decimal | 2.00 | % de multa por atraso |
| `percentual_juros_dia` | financeiro | decimal | 0.0333 | % de juros ao dia |
| `limite_tentativas_cobranca` | financeiro | inteiro | 3 | Máx. mensagens de cobrança por título |
| `intervalo_tentativas_horas` | financeiro | inteiro | 24 | Horas entre tentativas de cobrança |
| `limite_dias_suspensao` | financeiro | inteiro | 15 | Dias de atraso para suspender contrato |
| `limite_dias_encerramento` | financeiro | inteiro | 60 | Dias de atraso para encerrar com pendência |
| `permite_pagamento_parcial` | financeiro | booleano | false | Aceita pagamentos parciais |
| `limite_fusao_parcial_pct` | financeiro | decimal | 20.00 | % do valor da parcela abaixo do qual o resto funde na próxima |
| `desbloqueio_confianca_dias` | frota | inteiro | 3 | Validade em dias do desbloqueio em confiança |
| `desbloqueio_confianca_min_meses_historico` | frota | inteiro | 3 | Mínimo de meses de relacionamento para elegibilidade |
| `desbloqueio_confianca_max_atrasos_historico` | frota | inteiro | 1 | Máx. ocorrências de atraso no histórico |
| `canal_cobranca_principal` | comunicacao | string | whatsapp | Canal padrão de cobrança |
| `canal_cobranca_fallback` | comunicacao | string | (vazio) | Canal de fallback se principal falhar |

4. Endpoint REST `GET /api/v1/configuracoes?modulo={modulo}` (role `admin`) — lista paginada filtrável.
5. Endpoint `PUT /api/v1/configuracoes/{slug}` (role `admin`) — atualiza valor com validação do tipo no backend antes do `INSERT`.
6. Audit log para toda mutação com `categoria='configuracao'` e diff antes/depois.
7. Testes: tentar gravar `tipo_valor='inteiro'` com `valor='abc'` → 422; gravar valor válido → 200.
8. `ServicoConfiguracao` cacheia consultas por `(empresa_id, slug)` por 60s em Redis — invalida no `definir()`.

---

### História 13.5: Infraestrutura Base dos Workers

Como engenheiro de plataforma,
quero a infraestrutura base do worker Celery com filas separadas, observabilidade e idempotência,
para que todos os motors do épico tenham fundação confiável e diagnosticável.

**Critérios de Aceite:**

1. `workers/celeryconfig.py` consolidado com **7 filas** isoladas:

| Fila | Concurrency | Propósito |
|---|---|---|
| `fila_cobranca` | 4 workers × 4 threads | Geração, encargos, cobrança |
| `fila_notificacoes` | 2 workers × 4 threads | WhatsApp/email/SSE com rate-limit |
| `fila_verificacao` | 2 workers × 4 threads | OCR, reconciliação, comprovantes |
| `fila_contratos` | 2 workers × 2 threads | Ciclo de vida de contratos |
| `fila_frota` | 2 workers × 2 threads | GPS, FIPE, documentos |
| `fila_padrao` | 2 workers × 2 threads | Coordinators, manutenção |
| `fila_whatsapp_entrada` | 2 workers × 4 threads | Inbound prioridade máxima |
| `fila_agente` | 2 workers × 1 thread/processo | LLM I/O-bound |

2. `docker-compose.yml` com serviço `beat` (replicas=1 — fixo) + serviços de worker por fila escaláveis.

3. **Padrão fan-out**: coordinator no Beat consulta IDs elegíveis, distribui em lotes de 50 via `group()`/`chord()` do Celery — falha em uma empresa não bloqueia as demais.

4. **3 camadas de idempotência** obrigatórias em toda task de cobrança:
   - `SELECT FOR UPDATE SKIP LOCKED` no PostgreSQL
   - Redis lock `titulo:{id}:{operacao}` com TTL 60s
   - Colunas `proxima_acao_em TIMESTAMPTZ` e `acoes_de_cobranca INTEGER` na tabela `titulos`

5. Tabela `execucoes_motor` para observabilidade:

```sql
CREATE TABLE execucoes_motor (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome_tarefa     VARCHAR(100) NOT NULL,
    empresa_id      UUID REFERENCES empresas(id),
    iniciado_em     TIMESTAMPTZ NOT NULL,
    finalizado_em   TIMESTAMPTZ,
    total_registros INTEGER DEFAULT 0,
    total_erros     INTEGER DEFAULT 0,
    situacao        VARCHAR(20) NOT NULL DEFAULT 'executando',
    detalhes        JSONB,
    CONSTRAINT ck_situacao CHECK (situacao IN ('executando','concluido','erro'))
);
```

6. Tabela `lembretes_enviados` para idempotência de envios:

```sql
CREATE TABLE lembretes_enviados (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    titulo_id   UUID NOT NULL REFERENCES titulos(id),
    tipo        VARCHAR(30) NOT NULL,
    canal       VARCHAR(30) NOT NULL,
    enviado_em  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sucesso     BOOLEAN NOT NULL,
    erro        TEXT,
    UNIQUE(titulo_id, tipo, DATE(enviado_em))
);
```

7. Endpoint `GET /api/v1/motor/execucoes` lista histórico paginado com filtros `nome_tarefa`, `empresa_id`, `situacao`, `data_inicio` (role `admin`).

8. Configuração de retry e dead-letter queue: `acks_late=True`, `reject_on_worker_lost=True`, `max_retries=3` com backoff exponencial.

9. Testes: 2 workers competindo pelo mesmo título → apenas um processa (SKIP LOCKED); worker crasha após processar → não duplica execução (acks_late).

---

### História 13.6: Motor `gerar_titulos_mensais`

Como sistema financeiro,
quero gerar títulos mensais automaticamente com aplicação de índice de correção,
para que o ciclo de cobrança seja autônomo.

**Critérios de Aceite:**

1. Task Celery `gerar_titulos_mensais` com schedule `crontab(hour=3, minute=0, day_of_month=1)`.

2. Lógica: busca contratos com `situacao='ativo'` e `modo_geracao='mensal'` e `proxima_data_geracao <= hoje`. Para cada contrato: verifica idempotência por `(contrato_id, competencia)` → cria título com correção monetária aplicada → avança `proxima_data_geracao`.

3. Tabela `tabela_indices_economicos(indice, competencia, percentual, UNIQUE(indice, competencia))` para armazenamento de IGPM/IPCA/INPC.

4. Contratos com índice configurado mas valor ausente: título gerado com valor base + alerta em `alertas_sistema`.

5. Idempotente: execuções repetidas no mesmo mês não geram duplicatas.

6. Endpoint `POST /api/v1/motor/gerar-titulos` para disparo manual (role `admin`).

---

### História 13.7: Motor `alertar_vencimentos_proximos`

Como cliente,
quero receber lembretes antes do vencimento,
para que eu pague em dia e evite encargos.

**Critérios de Aceite:**

1. Task Celery `alertar_vencimentos_proximos` com schedule `crontab(hour=8, minute=0)`.

2. Busca títulos `tipo='parcela'`, `situacao='pendente'`, `data_vencimento` entre `hoje + 1` e `hoje + ServicoConfiguracao.obter_inteiro('dias_antecedencia_lembrete', 'financeiro', padrao=3)`. Ignora se já enviado hoje (`lembretes_enviados`).

3. Renderiza mensagem via `renderizador_template` com template `lembrete_vencimento`. Envia pelo `ServicoConfiguracao.obter_string('canal_cobranca_principal', 'comunicacao', padrao='whatsapp')`. Fallback para `canal_cobranca_fallback` se falhar.

4. Registra resultado em `lembretes_enviados` e métricas em `execucoes_motor`.

---

### História 13.8: Motor `processar_titulos_vencidos`

Como sistema financeiro,
quero processar automaticamente títulos vencidos com aplicação de encargos e escalonamento até suspensão do contrato,
para que a inadimplência seja tratada sem intervenção manual.

**Critérios de Aceite:**

1. Task Celery `processar_titulos_vencidos` com schedule `crontab(hour=9, minute=0)`.

2. Busca títulos `tipo='parcela'`, `situacao='pendente'`, `data_vencimento < hoje - ServicoConfiguracao.obter_inteiro('dias_carencia', 'financeiro', padrao=0)`.

3. Para cada título: calcula `valor_atualizado = valor_nominal + multa + juros`:
   - `multa = valor × ServicoConfiguracao.obter_decimal('percentual_multa', 'financeiro', padrao=Decimal('2.00')) / 100` no D+1
   - `juros = valor × ServicoConfiguracao.obter_decimal('percentual_juros_dia', 'financeiro', padrao=Decimal('0.0333')) / 100 × dias_atraso`
   
   Atualiza `situacao = 'em_atraso'`, persiste encargos.

4. Envia mensagem de cobrança via `renderizador_template` respeitando `limite_tentativas_cobranca` e `intervalo_tentativas_horas` (lidos via `ServicoConfiguracao`). Registra em `lembretes_enviados`.

5. Ao atingir `limite_dias_suspensao` (config `financeiro`): chama `ServicoSituacaoContrato.transicionar(contrato_id, 'suspenso', motivo=...)`.

6. Ao atingir `limite_dias_encerramento` (config `financeiro`): chama `ServicoSituacaoContrato.transicionar(contrato_id, 'encerrado_com_pendencia', motivo=...)` → hook gera passivo inoperante para cada título `em_atraso`.

7. Publica `EventoTituloVencido` para cada título processado.

8. Idempotente: encargos calculados com base na data atual (sobrescreve, não acumula). Contratos `suspenso` ou terminais ignorados.

9. Testes: D+1 → multa aplicada, mensagem enviada; D+`limite_dias_suspensao+1` → contrato suspenso, veículo bloqueado; D+`limite_dias_encerramento+1` → contrato encerrado, passivo gerado.

---

### História 13.9: Motor `conciliar_pagamentos_recebidos` (com Fusão de Pagamento Parcial)

Como sistema financeiro,
quero verificar automaticamente pagamentos recebidos, reconciliá-los e tratar pagamentos parciais com regra de fusão,
para que o ciclo financeiro seja autônomo e diferenças pequenas sejam fundidas na próxima parcela em vez de gerar título novo desnecessariamente.

**Critérios de Aceite:**

1. Task Celery `conciliar_pagamentos_recebidos` com schedule `crontab(minute='*/15')`.

2. Busca pagamentos com `situacao='pendente_verificacao'`. Para cada um: localiza título por `titulo_id` ou por `(empresa_id, valor, competencia)` como fallback.

3. Hook `quando_titulo_pago(titulo_id, pagamento_id)`: atualiza título (`situacao='pago'`), verifica `titulo.tipo`:
   - `parcela` → fluxo normal: verifica se contrato `suspenso` pode ser reativado
   - `opcao_compra` → publica `OpcaoCompraPaga`

4. Ao reativar contrato suspenso: chama `ServicoDesbloqueioConfianca.verificar()` (História 13.13). Se elegível, `ServicoSituacaoContrato.transicionar(contrato_id, 'ativo', motivo='Pagamento confirmado')`.

5. **Pagamento parcial com fusão automática**: se `valor_pago < valor_titulo`:
   - Calcula `restante = valor_titulo - valor_pago`
   - Lê `limite_fusao_parcial_pct` via `ServicoConfiguracao` (default 20.00%)
   - Se `restante <= valor_titulo × limite_fusao_parcial_pct / 100`:
     - **Funde**: marca título original como `pago_parcial`, adiciona `restante` ao próximo título em aberto do contrato (com nota de auditoria), sem criar título novo
   - Caso contrário:
     - **Separa**: cria título novo `tipo='parcela'`, `valor=restante`, `parent_titulo_id=titulo.id`, vencimento = hoje + `dias_carencia`
   - Publica `EventoPagamentoParcialRecebido` em ambos os casos

6. Pagamentos sem identificação → tabela `pagamentos_nao_identificados` + alerta operacional.

7. Webhook externo `POST /api/v1/webhooks/pagamento` cria pagamento e dispara task com `countdown=5s`.

8. Idempotente: pagamento já `conciliado` ignorado sem erro.

9. Testes:
   - Pagamento integral → título `pago`
   - Pagamento parcial dentro do threshold (ex: paga 95% de R$800, restam R$40 = 5% < 20%) → funde no próximo título
   - Pagamento parcial fora do threshold (ex: paga 50%, restam R$400 = 50% > 20%) → cria título novo com `parent_titulo_id`
   - Opção de compra paga → `OpcaoCompraPaga` publicado, veículo alienado

---

### História 13.10: Renderizador de Templates de Mensagem

Como motor financeiro,
quero um renderizador de templates centralizado,
para que todos os workers enviem mensagens consistentes com variáveis preenchidas.

**Critérios de Aceite:**

1. `renderizador_template.py` em `infrastructure/mensageria/` com função `renderizar(nome_template, contexto: dict) -> str`.

2. Tabela `templates_mensagem(empresa_id, nome, canal, conteudo, ativo)` — personalizáveis por empresa, fallback para templates padrão do sistema.

3. Templates padrão PT-BR seedados: `lembrete_vencimento`, `cobranca_vencida`, `aviso_suspensao`, `pagamento_confirmado`, `opcao_compra_exercida`.

4. Variáveis disponíveis: `{{cliente.nome}}`, `{{titulo.valor}}`, `{{titulo.valor_atualizado}}`, `{{titulo.data_vencimento}}`, `{{titulo.dias_atraso}}`, `{{veiculo.placa}}`, `{{contrato.id}}`, `{{empresa.nome}}`.

5. Endpoint CRUD `GET/POST/PUT /api/v1/templates-mensagem` (role `admin`) com preview com dados de exemplo.

---

### História 13.11: Ledger de Passivo Inoperante

Como gestor financeiro,
quero que títulos em atraso de contratos encerrados sejam registrados como passivo inoperante,
para que a dívida real seja rastreável e possa ser cobrada ou baixada formalmente.

**Critérios de Aceite:**

1. Tabela `passivos_inoperantes` criada:

```sql
CREATE TABLE passivos_inoperantes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id      UUID NOT NULL REFERENCES empresas(id),
    cliente_id      UUID NOT NULL REFERENCES clientes(id),
    contrato_id     UUID NOT NULL REFERENCES contratos(id),
    titulo_id       UUID NOT NULL REFERENCES titulos(id),
    valor_nominal   NUMERIC(12,2) NOT NULL,
    valor_encargos  NUMERIC(12,2) NOT NULL DEFAULT 0,
    situacao        VARCHAR(30) NOT NULL DEFAULT 'pendente',
    origem          VARCHAR(50) NOT NULL,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    baixado_em      TIMESTAMPTZ,
    motivo_baixa    TEXT,
    criado_por      UUID REFERENCES usuarios(id),
    CONSTRAINT ck_passivo_situacao CHECK (situacao IN ('pendente','baixado','recuperado'))
);
```

2. Hook `quando_contrato_encerrado` (quando `situacao='encerrado_com_pendencia'`): itera títulos com `status='em_atraso'` do contrato → cria registro em `passivos_inoperantes` para cada um.

3. Endpoints: `GET /api/v1/passivo-inoperante` (filtros por `empresa_id`, `cliente_id`, `situacao`), `PATCH /{id}/baixar`, `PATCH /{id}/recuperado`.

4. Frontend: aba `Passivos` no detalhe do cliente com badge numérico. Card exibe valor, data origem e botões de ação com `ConfirmService` antes de confirmar.

5. KPI no dashboard: "Passivo Inoperante Total — R$ X / N clientes".

6. Audit log para toda mutação com `categoria='financeiro'`.

---

### História 13.12: Herói Financeiro no Detalhe do Contrato

Como gestor,
quero ver o estado financeiro do contrato de forma clara e imediata ao abrir o detalhe,
para que possa agir sem precisar escanear tabelas.

**Critérios de Aceite:**

1. Componente `ContractHeroComponent` no detalhe do contrato exibe, em estados distintos:

   **Estado EM DIA:**
   - Badge `✓ EM DIA` (verde)
   - Barra de progresso: parcelas pagas / total, com marcador `★` para a opção de compra
   - Totais: "R$X pagos · R$Y restam · Opção de compra: R$Z"
   - Última parcela paga e próximo vencimento (data + countdown em dias)

   **Estado EM ATRASO:**
   - Badge `⚠ EM ATRASO — N parcelas` (âmbar/vermelho)
   - Bloco de atraso acima da barra: lista de parcelas em atraso com valor + encargos + total
   - CTA principal: "Registrar pagamento das parcelas em atraso"
   - Barra de progresso com segmento `em atraso` em cor âmbar
   - Opção de compra com estado `⏸ Suspenso — quitar atraso primeiro`

2. Seção separada para a opção de compra com: valor, data de vencimento, status e texto explicativo ("Se paga, o veículo passa para o nome do cliente").

3. No wizard de novo contrato (Passo 1 — seleção de cliente): se cliente possui passivos inoperantes, exibe banner âmbar obrigatório antes de prosseguir: "Este cliente possui passivo de contratos anteriores — R$X. Deseja criar contrato normalmente ou registrar acordo de passivo?"

4. Botão "Cancelar contrato" no detalhe: abre modal `ConfirmService` com texto diferente conforme situação:
   - Sem atraso: "Carlos não possui parcelas em atraso. O encerramento é limpo — sem saldo devedor."
   - Com atraso: "Carlos possui N parcelas em atraso (R$X). Elas permanecerão como passivo inoperante."

5. Testes E2E: contrato em dia → badge verde, sem bloco de atraso; contrato com atraso → badge âmbar, bloco de atraso visível, CTA correto.

---

### História 13.13: Desbloqueio em Confiança com Expiração

Como operador financeiro,
quero configurar regras de desbloqueio em confiança com prazo de validade,
para que clientes elegíveis sejam reativados ao pagar sem aprovação manual — e re-bloqueados automaticamente se não cumprirem o prazo prometido.

**Critérios de Aceite:**

1. Parâmetros via `ServicoConfiguracao` (módulo `frota`):
   - `desbloqueio_confianca_dias` (inteiro, default 3) — validade do desbloqueio em dias
   - `desbloqueio_confianca_min_meses_historico` (inteiro, default 3) — mínimo de meses de relacionamento
   - `desbloqueio_confianca_max_atrasos_historico` (inteiro, default 1) — máx. ocorrências de atraso no histórico

2. Tabela `veiculos` recebe colunas:
   - `desbloqueio_confianca_ativo_ate TIMESTAMPTZ NULL` — data/hora em que o desbloqueio expira
   - `desbloqueio_confianca_concedido_em TIMESTAMPTZ NULL`
   - `desbloqueio_confianca_concedido_por UUID NULL REFERENCES usuarios(id)`

3. Serviço `ServicoDesbloqueioConfianca`:
   - `verificar_elegibilidade(contrato_id) -> bool` — avalia histórico contra os 3 parâmetros de config
   - `conceder(veiculo_id, usuario_id) -> None` — desbloqueia veículo via `IGatewayRastreador`, preenche `desbloqueio_confianca_ativo_ate = NOW() + dias`
   - `revogar(veiculo_id, motivo) -> None` — re-bloqueia, limpa campos

4. Endpoint `POST /api/v1/contratos/{id}/desbloqueio-confianca` (role `admin` ou agente IA com escopo) com justificativa — registra no `audit_log` categoria `frota`.

5. **Nova task `verificar_desbloqueios_expirados`** com schedule `crontab(minute='*/30')`:
   - Busca veículos com `desbloqueio_confianca_ativo_ate < NOW()` e contrato `suspenso`
   - Para cada: chama `ServicoDesbloqueioConfianca.revogar(veiculo_id, motivo='Prazo de desbloqueio em confiança expirado sem pagamento')`
   - Envia template `aviso_re_bloqueio` ao cliente
   - Registra em `execucoes_motor`

6. Frontend: no detalhe do veículo, se desbloqueio em confiança ativo → badge âmbar `🤝 Desbloqueio em confiança até DD/MM HH:mm` com countdown ao vivo.

7. Testes: cliente elegível pede desbloqueio → veículo desbloqueado por N dias; cliente paga dentro do prazo → desbloqueio convertido em reativação normal; cliente NÃO paga → re-bloqueio automático após `desbloqueio_confianca_dias`.

---

### História 13.14: Override Manual do Valor de Mercado do Veículo

Como gestor de frota,
quero poder sobrescrever manualmente o valor de mercado de um veículo quando o valor FIPE não reflete a realidade,
para que dashboards e cálculos de ROI usem o valor real (carro batido vale menos, carro raro vale mais).

**Critérios de Aceite:**

1. Tabela `veiculos` recebe colunas:
   - `valor_mercado_manual NUMERIC(12,2) NULL`
   - `valor_mercado_manual_atualizado_em TIMESTAMPTZ NULL`
   - `valor_mercado_manual_motivo TEXT NULL`
   - `valor_mercado_manual_atualizado_por UUID NULL REFERENCES usuarios(id)`

2. Função `obter_valor_mercado(veiculo_id) -> Decimal` retorna `valor_mercado_manual` se preenchido, senão `valor_fipe_atual`.

3. Dashboards e cálculos de ROI usam `obter_valor_mercado()` — NUNCA acessam `valor_fipe_atual` diretamente.

4. Endpoint `PUT /api/v1/veiculos/{id}/valor-mercado-manual` com payload `{"valor": decimal, "motivo": string}` (role `admin` ou `gestor_frota`). `motivo` é obrigatório.

5. Endpoint `DELETE /api/v1/veiculos/{id}/valor-mercado-manual` remove o override (volta a usar FIPE).

6. Frontend: no detalhe do veículo, campo "Valor de mercado" com:
   - Valor exibido (manual se sobrescrito, FIPE caso contrário)
   - Badge `📝 Manual` ou `📊 FIPE` ao lado
   - Botão "Sobrescrever" abre modal com input de valor + textarea de motivo
   - Se manual: botão "Remover override" volta a usar FIPE

7. Audit log para toda mutação com `categoria='frota'`.

8. Testes: sem override → ROI usa FIPE; com override → ROI usa manual; remover override → ROI volta a FIPE.

---

### História 13.15: Tela de Configurações do Motor (UI para o gestor)

Como gestor,
quero uma tela visual e organizada para configurar todos os parâmetros do motor financeiro e demais módulos,
para que eu possa ajustar regras de negócio sem precisar de desenvolvedor.

**Atenção UX (Sally):** esta é a tela mais crítica do épico. Se mal feita, o sistema vira planilha cara. Gestor precisa configurar **sem treinamento**, idealmente em menos de 5 minutos por seção.

**Critérios de Aceite:**

1. Rota `/sistema/config/parametros` com layout responsivo mobile-first.

2. Navegação por **tabs verticais** (desktop) ou **accordion** (mobile), uma por módulo:
   - Financeiro (parâmetros de cobrança, multa, juros, suspensão)
   - Frota (desbloqueio em confiança, alertas de documentos)
   - Comunicação (canais, templates default)
   - Motor (status das tasks agendadas, com horários e última execução)

3. Cada parâmetro renderizado conforme `tipo_valor`:
   - `inteiro` → input number com min/max + stepper (`+`/`-`)
   - `decimal` → input number com 2 casas + sufixo `%` ou `R$` quando aplicável (detectado do slug)
   - `booleano` → toggle switch (não checkbox)
   - `string` → select se houver `opcoes_aceitas` no metadata, senão input text
   - `json` → editor JSON com syntax highlighting + validador inline

4. Cada campo mostra:
   - Label legível em PT-BR (não o slug técnico)
   - Tooltip `ℹ️` com descrição e exemplo do efeito da mudança
   - Valor atual + valor padrão (badge "padrão" se = padrão)
   - Botão "Restaurar padrão" ao lado

5. Mudanças são salvas com **debounce de 1s** + indicador visual de salvamento (`✓ Salvo às HH:mm:ss`). Sem botão "Salvar" — autosave.

6. Erro de validação (ex: tentar gravar "abc" em campo inteiro) exibe inline em vermelho sem perder o foco.

7. Cada seção tem **botão de pré-visualização**: "Simular como esses valores impactariam X contratos ativos" (ex: alterar `percentual_multa` mostra "Multa total mensal estimada: R$2.450").

8. Toda mudança gera audit log + opção "Reverter última alteração" disponível por 10 minutos.

9. Permissão: apenas role `admin`. Demais perfis veem em modo somente-leitura com badge `🔒 Apenas admin pode alterar`.

10. Testes E2E: alterar `percentual_multa` de 2.00 para 3.00 → autosave → recarregar página → valor persistido; tentar gravar string em campo inteiro → mensagem inline em vermelho.

---

**Resumo do Épico 13**

| História | Título | Complexidade |
|---|---|---|
| 13.1 | Padronização de Nomenclatura PT-BR | Média |
| 13.2 | Máquina de Estados do Contrato | Média |
| 13.3 | Tipo de Título e Opção de Compra | Alta |
| 13.4 | Sistema de Configurações Tipadas | Média |
| 13.5 | Infraestrutura Base dos Workers | Alta |
| 13.6 | Motor `gerar_titulos_mensais` | Média |
| 13.7 | Motor `alertar_vencimentos_proximos` | Baixa |
| 13.8 | Motor `processar_titulos_vencidos` | Alta |
| 13.9 | Motor `conciliar_pagamentos_recebidos` (com fusão parcial) | Alta |
| 13.10 | Renderizador de Templates | Baixa |
| 13.11 | Ledger de Passivo Inoperante | Média |
| 13.12 | Herói Financeiro no Detalhe do Contrato | Média |
| 13.13 | Desbloqueio em Confiança com Expiração | Média |
| 13.14 | Override Manual do Valor de Mercado do Veículo | Baixa |
| 13.15 | Tela de Configurações do Motor (UI) | Alta |

**Sequência recomendada de implementação:**

`13.1 → 13.4 → 13.2 → 13.3 → 13.5 → 13.10 → 13.6 → 13.7 → 13.8 → 13.9 → 13.11 → 13.13 → 13.12 → 13.14 → 13.15`

**Pré-requisito obrigatório:** Epic 12 (histórias 12.2 a 12.8) deve estar completo antes de iniciar Epic 13. O rename de tabelas/models/schemas/workers existentes do Epic 12 é fundação para os motors deste épico.

**Justificativa da ordem:**
- 13.1 primeiro (verificação PT-BR + glossário): zero risco, valida que Epic 12 deixou tudo consistente
- 13.4 antes de qualquer motor: todos os motors dependem do `ServicoConfiguracao`
- 13.5 (infra) antes dos motors específicos: filas, idempotência, observabilidade
- Motors do mais simples ao mais complexo (13.6 → 13.9)
- 13.13 (desbloqueio) antes de 13.12 (herói): herói usa o estado de desbloqueio na UI
- 13.15 (tela) por último: UI consome tudo que foi construído antes

**Cobertura de teste exigida por história:** mínimo 70%. **Code review obrigatório** via `bmad-code-review` após cada `bmad-dev-story`.

---

## Épico 14: Manual do Desenvolvedor & Documentação Final (Core)

**Objetivo:** Consolidar toda a documentação técnica e funcional do sistema num conjunto de manuais que permita um novo desenvolvedor ser produtivo em < 1 semana e que o sistema seja mantido sem dependência do autor original.

**Pré-requisito:** Todos os épicos anteriores (10, 11, 12, 13) devem estar concluídos. É o último épico do roadmap antes de versão 1.0 estável.

**Por que último:** Documentar sistema em transição é desperdício — toda a documentação fica desatualizada antes de ir a produção. Faz mais sentido escrever depois que o motor de cobrança, multi-tenancy e Epic 13 estiverem fechados e validados.

**Status:** backlog

---

### História 14.1: Manual do Desenvolvedor — Camada Técnica

Como desenvolvedor novo no projeto,
quero um manual técnico que me leve do zero ao primeiro PR mergado em menos de 1 semana,
para que eu seja produtivo sem depender de tribal knowledge.

**Critérios de Aceite:**

1. Documento `docs/manual-desenvolvedor-tecnico.md` com 800-1500 linhas, em PT-BR.
2. Cobre: arquitetura hexagonal, estrutura de pastas, 12 schemas PostgreSQL, padrões obrigatórios (UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, schema= em table_args, ForeignKey qualificado, empresa_id em tudo tenant-scoped), convenções de naming PT-BR + synonyms, workers Celery (7 filas, fan-out, 3 idempotências), Ports & Adapters com exemplos, multi-tenancy Modelo A, testes pytest async, migrations Alembic, env vars, frontend Angular básico, observabilidade.
3. Todo exemplo de código cita path absoluto real do projeto.
4. Decisões arquiteturais consolidadas em uma seção única (ADRs resumidos).
5. Glossário PT-BR↔EN com synonyms vigentes na transição.
6. Mapa "pergunta → arquivo onde encontrar" para navegação rápida.
7. Lista de antipadrões rejeitados em code review.

> ⚠️ **Já entregue em 2026-05-24 como rascunho** — 1123 linhas. Revisar e atualizar após épicos 10/11/12/13 completos.

---

### História 14.2: Manual do Desenvolvedor — Camada Funcional

Como desenvolvedor que precisa entender o NEGÓCIO antes de codar,
quero um manual funcional que explique o sistema do ponto de vista do gestor de frota,
para que minhas decisões técnicas sejam coerentes com o modelo de negócio.

**Critérios de Aceite:**

1. Documento `docs/manual-desenvolvedor-funcional.md` com 600-1200 linhas, em PT-BR.
2. Cobre: visão geral, modelo rent-to-own, atores e perfis, fluxos principais (onboarding, cadastros, contrato, operação diária, motor de cobrança, pagamento parcial, bloqueio/desbloqueio, encerramento, conciliação, configurações tipadas).
3. Regras de negócio explícitas (máquina de estados do contrato, lifecycle do título, definição precisa de saldo devedor, política de cobrança com parâmetros configuráveis, score do cliente).
4. Multi-tenant Modelo A explicado com implicações de negócio.
5. Glossário PT-BR de termos do domínio com significado de negócio (não técnico).
6. Decisões de produto com justificativa (por que rent-to-own, por que Modelo A, por que self-register desabilitado, por que motor Python, por que Pix sem gateway, etc.).
7. Roadmap de épicos com status, entregáveis e valor de negócio de cada um.
8. Apêndice "quer entender X → vá em arquivo Y" para conectar conceito ao código.

> ⚠️ **Já entregue em 2026-05-24 como rascunho** — 662 linhas. Revisar e atualizar após épicos 10/11/12/13 completos.

---

### História 14.3: Documentação de APIs (OpenAPI consolidado)

Como dev frontend ou integrador externo,
quero documentação de API consolidada e navegável,
para consumir os endpoints sem ler código backend.

**Critérios de Aceite:**

1. OpenAPI gerado automaticamente via FastAPI em `/docs` (Swagger) e `/redoc`.
2. Cada endpoint tem `summary`, `description`, `response_model` tipado e exemplos no docstring.
3. Schemas Pydantic com `Field(description=)` em todos os campos.
4. Tags organizadas por módulo (auth, clientes, veículos, contratos, recebíveis, etc.).
5. Documento `docs/api-reference.md` exportado do OpenAPI com curl examples para os 20 endpoints mais usados.
6. Webhooks documentados separadamente (provider, payload, signature validation).

---

### História 14.4: Runbook Operacional

Como operador (DevOps/SRE) do sistema em produção,
quero um runbook com procedimentos de operação e troubleshooting,
para resolver incidentes sem precisar do autor original.

**Critérios de Aceite:**

1. Documento `docs/runbook-operacional.md` em PT-BR.
2. Cobre: deploy (Docker Compose dev + Kubernetes/Coolify prod), backup/restore, rotação de chaves JWT, escala de workers Celery, monitoramento Grafana, alertas Prometheus, troubleshooting comum (queue stuck, DB lento, agente IA falhando).
3. Playbook de incidentes: o que fazer quando o motor de cobrança para, quando WhatsApp gateway cai, quando OCR fica lento, quando o banco trava.
4. Procedimentos LGPD (export/anonimização de dados).
5. Checklist de release (deploy seguro com migration).

---

### História 14.5: Documentação de Adaptadores (ADAPTERS.md)

Como dev integrando um novo provider externo,
quero um guia que explique como criar um novo adapter para qualquer Port,
para integrar provedores sem quebrar a arquitetura hexagonal.

**Critérios de Aceite:**

1. Documento `docs/adapters-guide.md` em PT-BR.
2. Para cada Port (IGatewayPagamento, ICanalMensagem, IGatewayRastreador, IProvedorFipe, IProvedorOcr, IProvedorLLM, IProvedorIndiceCorrecao, IProvedorArmazenamento, IEnviadorEmail): contrato detalhado, exemplo de adapter existente, passo-a-passo para criar um novo.
3. Cobertura de testes obrigatória para novos adapters (≥80%).
4. Convenção de configuração via `config.configuracoes_sistema` (credenciais cifradas).

---

### História 14.6: Documentação de Módulos Verticais (MODULES.md)

Como dev criando uma vertical nova (ex: imóveis, equipamentos),
quero um guia que explique como implementar `IModuloVertical`,
para adicionar verticais sem tocar no Core.

**Critérios de Aceite:**

1. Documento `docs/modules-guide.md` em PT-BR.
2. Explica: interface `IModuloVertical`, hooks (`quando_*`), schema extension, registro de tools no agente IA, dashboard widgets, report dimensions.
3. Usa `ModuloVeiculos` como template ao longo da explicação.
4. Inclui exemplo passo-a-passo de criação de um módulo "Properties" (locação de imóveis) — não precisa ser implementado, só documentado como exercício didático.
5. Checklist do que verificar antes de habilitar um módulo em produção.

---

### História 14.7: Vídeos Curtos de Onboarding (Opcional V2)

> **V2 — Diferido pós-launch.** Manuais escritos cobrem MVP.

Vídeos screencast (5-10 min cada) para acelerar onboarding visual:
- Visão geral em 5min
- Setup local com docker-compose
- Criar primeiro contrato no sistema
- Como debugar uma task Celery
- Como adicionar um adapter novo

---

**Resumo do Épico 14**

| História | Título | Status | Tamanho |
|---|---|---|---|
| 14.1 | Manual do Desenvolvedor — Técnico | rascunho entregue | 1123 linhas |
| 14.2 | Manual do Desenvolvedor — Funcional | rascunho entregue | 662 linhas |
| 14.3 | Documentação de APIs (OpenAPI) | backlog | — |
| 14.4 | Runbook Operacional | backlog | — |
| 14.5 | ADAPTERS.md | backlog | — |
| 14.6 | MODULES.md | backlog | — |
| 14.7 | Vídeos de Onboarding | V2 (diferido) | — |

**Sequência recomendada:** `14.1 → 14.2 → 14.3 → 14.5 → 14.6 → 14.4 → (V2: 14.7)`

**Quando começar:** Apenas após épicos 10, 11, 12 e 13 estarem `done`. Documentar sistema em transição é desperdício.
