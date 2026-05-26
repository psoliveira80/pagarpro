---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments:
  - PRD.md
  - ARCHITECTURE.md
  - epics.md
  - ux-design-specification.md
---

# Implementation Readiness Assessment Report

**Date:** 2026-05-07
**Project:** FrotaPay (FrotaUber)

## 1. Document Inventory

| # | Document | Status | Size (approx.) | Notes |
|---|---|---|---|---|
| 1 | `PRD.md` | Found | ~1360 lines | Version 1.0, complete with 8 goals, 63 FRs, 14 NFRs, 9 epics, detailed stories |
| 2 | `ARCHITECTURE.md` | Found | ~2200 lines | Version 1.0, complete DDL, API spec, tech stack, sequence diagrams, full frontend structure |
| 3 | `epics.md` | Found | ~1262 lines | 9 epics, 65 stories with acceptance criteria, FR coverage map |
| 4 | `ux-design-specification.md` | Found | ~1891 lines | 14 steps completed, 5 textual wireframes, component catalog, accessibility checklist |

**Assessment:** All four required documents are present. No duplicates. No missing documents. All are internally version-marked as 1.0 dated 2026-05-07, indicating they were produced in a coordinated sprint.

## 2. PRD Requirements Extraction

### Functional Requirements (FRs)

| ID | Summary |
|---|---|
| FR-AUTH-1 | Login by email/password with Argon2id + optional MFA (TOTP) |
| FR-AUTH-2 | Profiles: Admin, Operador, Validador, Auditor Read-only |
| FR-AUTH-3 | Granular per-module RBAC (CRUD + sensitive actions) |
| FR-AUTH-4 | JWT 15min + rotating refresh token 7d in HttpOnly cookie |
| FR-AUTH-5 | Login audit log, IP, user-agent, 5-attempt lockout |
| FR-CAD-1 | Customer registration with CPF/CNH/attachments/ViaCEP |
| FR-CAD-2 | Vehicle registration with Mercosul plate, FIPE binding, tracker, photos |
| FR-CAD-3 | Auto-fetch FIPE via cascading selectors + monthly refresh job |
| FR-CAD-4 | Vehicle acquisition payment model (cash/financed/consortium/custom) |
| FR-CAD-5 | Real-time vehicle financials: FIPE, depreciation, ROI, payback |
| FR-CAD-6 | Interactive fleet map (Leaflet+OSM, popup actions, block) |
| FR-CAD-7 | Vehicle categories for reporting |
| FR-CTR-1 | Contract creation linking Customer to Vehicle with full terms |
| FR-CTR-2 | Visual installment builder (entry + N regular + extras + grace + custom) |
| FR-CTR-3 | Auto-generate installments on contract save |
| FR-CTR-4 | PDF rendering via Jinja2 + WeasyPrint with SHA-256 hash |
| FR-CTR-5 | Digital signature (PDF upload + future D4Sign/Clicksign extension) |
| FR-CTR-6 | Bulk edit of open installments (atomic + audit) |
| FR-CTR-7 | Paid installment immutability + reverse-write-off (Admin-only) |
| FR-CTR-8 | Contract termination with rescission calculation |
| FR-CTR-9 | Contract versioning with timeline |
| FR-CTR-10 | Contract simulation without persistence |
| FR-CR-1 | Master receivables list with multi-select filters |
| FR-CR-2 | Manual write-off with receipt attachment |
| FR-CR-3 | Bulk write-off across multiple installments |
| FR-CR-4 | Auto-calculate interest + fine + optional discount |
| FR-CR-5 | Receipt validation queue (Validator/Admin) |
| FR-CR-6 | Automatic OCR on Pix receipts (Tesseract + regex) |
| FR-CR-7 | State machine: pago_aguardando_verificacao -> pago |
| FR-CR-8 | Pix QR Code generation (BR Code, no transaction cost) |
| FR-CR-9 | Optional payment gateway adapter (Asaas/Efi/PagBank) |
| FR-CR-10 | Renegotiation flow for overdue titles |
| FR-CP-1 | Hierarchical expense categories |
| FR-CP-2 | Supplier registry |
| FR-CP-3 | One-off payable creation |
| FR-CP-4 | Recurring expenses auto-generation |
| FR-CP-5 | "Lancar e Pagar" quick shortcut |
| FR-CP-6 | Simplified DRE (Income - Expenses) |
| FR-COB-1 | WhatsApp integration via adapter (Evolution API default) |
| FR-COB-2 | AI Collection Agent with pluggable LLM, RAG, function-calling tools |
| FR-COB-3 | No-code agent rule parameterization |
| FR-COB-4 | Customer score (0-100) with configurable formula |
| FR-COB-5 | Auto-send Pix QR via WhatsApp |
| FR-COB-6 | Inbound receipt detection + primary write-off |
| FR-COB-7 | WhatsApp-style 3-pane in-app inbox |
| FR-COB-8 | Human intercept / pause-resume agent |
| FR-COB-9 | Mass dispatch with rate limiting and time window |
| FR-COB-10 | Immutable message history |
| FR-CON-1 | OFX import with FITID deduplication |
| FR-CON-2 | PDF statement import (8+ Brazilian banks + LLM fallback) |
| FR-CON-3 | Open Finance adapter (Pluggy/Belvo/TecnoSpeed) |
| FR-CON-4 | Drag-and-drop reconciliation screen with auto-suggestions |
| FR-CON-5 | Auto-match algorithm with configurable threshold |
| FR-CON-6 | 1:N, N:1, and unmatched-as-new reconciliation patterns |
| FR-CON-7 | Divergence panel (orphans, mismatches, suspects) |
| FR-CON-8 | Final reconciliation transitions to pago (immutable) |
| FR-DSH-1 | Main dashboard with reactive KPI cards |
| FR-DSH-2 | Customer financial dashboard |
| FR-DSH-3 | Vehicle dashboard (ROI, depreciation, payback) |
| FR-DSH-4 | Pre-built exportable reports (7 report types) |
| FR-DSH-5 | Custom report builder with drag-and-drop |
| FR-INT-1 | Port/Protocol interfaces for all external providers (9 ports) |
| FR-INT-2 | Admin integrations screen (enable/disable/test/status) |
| FR-INT-3 | FIPE provider with 30-day cache and fallback |
| FR-INT-4 | GPS tracker adapter (REST/MQTT, block/unblock) |
| FR-INT-5 | Webhook ingestion with signature validation and idempotency |
| FR-PRM-1 | Centralized settings screen (9 sections) |
| FR-PRM-2 | Versioned configuration with change history |
| FR-AUD-1 | Append-only audit log for all relevant operations |
| FR-AUD-2 | Searchable/exportable audit log |
| FR-AUD-3 | HMAC-signed audit entries for tamper detection |

### Non-Functional Requirements (NFRs)

| ID | Area | Summary |
|---|---|---|
| NFR-1 | Performance | P95 read <= 300ms, write <= 500ms, dashboard FCP <= 1.5s on 4G |
| NFR-2 | Scalability | 10k vehicles / 50k titles / 100k WhatsApp msgs/month |
| NFR-3 | Availability | SLA 99.5% (~3.6h downtime/month) |
| NFR-4 | Security | OWASP ASVS L2, Argon2id, JWT RS256, AES-256-GCM at rest, TLS 1.3 |
| NFR-5 | LGPD | "My Data" screen, consent, PII access logging |
| NFR-6 | Financial Audit | Immutable events on title state changes, reproducible reconciliation |
| NFR-7 | Observability | Structured JSON logs, Prometheus, OpenTelemetry, Grafana |
| NFR-8 | Accessibility | WCAG 2.1 AA |
| NFR-9 | Internationalization | pt-BR default, ready for en-US/es-ES |
| NFR-10 | Plug-and-Play | Provider swap = config change + new adapter, zero domain changes |
| NFR-11 | Mobile-First | Responsive for tablet/mobile, PWA-ready |
| NFR-12 | Real-time | Chat/receipt/title updates in <= 2s without refresh |
| NFR-13 | Backup & DR | Daily full + continuous WAL, RPO <= 1h, RTO <= 4h |
| NFR-14 | Cost | 100% open-source default stack, opt-in for paid services |

### Total Counts

- **Functional Requirements:** 63
- **Non-Functional Requirements:** 14
- **Total:** 77

## 3. Epic Coverage Validation

### FR Coverage Matrix

| FR ID | Epic/Story | Status |
|---|---|---|
| FR-AUTH-1 | Epic 1, Story 1.4 | Covered |
| FR-AUTH-2 | Epic 1, Story 1.3 | Covered |
| FR-AUTH-3 | Epic 1, Story 1.3 (progressive per epic) | Covered |
| FR-AUTH-4 | Epic 1, Stories 1.4 + 1.6 | Covered |
| FR-AUTH-5 | Epic 1, Stories 1.3 + 1.4 | Covered |
| FR-CAD-1 | Epic 2, Stories 2.1-2.4 | Covered |
| FR-CAD-2 | Epic 2, Stories 2.6-2.8 | Covered |
| FR-CAD-3 | Epic 2, Stories 2.5 + 2.6 | Covered |
| FR-CAD-4 | Epic 2, Story 2.6 | Covered |
| FR-CAD-5 | Epic 2, Story 2.6 (API) + Epic 8, Story 8.3 (dashboard) | Covered |
| FR-CAD-6 | Epic 2, Story 2.10 | Covered |
| FR-CAD-7 | Epic 2, Story 2.6 (category field) | Covered |
| FR-CTR-1 | Epic 3, Stories 3.1 + 3.4 | Covered |
| FR-CTR-2 | Epic 3, Stories 3.2 + 3.3 | Covered |
| FR-CTR-3 | Epic 3, Story 3.1 + 3.2 | Covered |
| FR-CTR-4 | Epic 3, Story 3.5 | Covered |
| FR-CTR-5 | Epic 3, Story 3.4 (upload area in step 4) | Partial |
| FR-CTR-6 | Epic 3, Story 3.6 | Covered |
| FR-CTR-7 | Epic 3, Story 3.1 (PG trigger) | Covered |
| FR-CTR-8 | Epic 3, Story 3.8 | Covered |
| FR-CTR-9 | Epic 3, Story 3.7 | Covered |
| FR-CTR-10 | Epic 3, Story 3.3 (simulation mode in wizard) | Covered |
| FR-CR-1 | Epic 4, Story 4.1 | Covered |
| FR-CR-2 | Epic 4, Story 4.3 | Covered |
| FR-CR-3 | Epic 4, Story 4.3 (bulk write-off) | Partial |
| FR-CR-4 | Epic 4, Story 4.2 | Covered |
| FR-CR-5 | Epic 4, Story 4.5 | Covered |
| FR-CR-6 | Epic 4, Story 4.4 | Covered |
| FR-CR-7 | Epic 4, Stories 4.3 + 4.5 | Covered |
| FR-CR-8 | Epic 4, Story 4.6 | Covered |
| FR-CR-9 | Epic 4, Story 4.8 | Covered |
| FR-CR-10 | Epic 4, Story 4.7 | Covered |
| FR-CP-1 | Epic 5, Story 5.1 | Covered |
| FR-CP-2 | Epic 5, Story 5.1 | Covered |
| FR-CP-3 | Epic 5, Story 5.2 | Covered |
| FR-CP-4 | Epic 5, Story 5.3 | Covered |
| FR-CP-5 | Epic 5, Story 5.4 | Covered |
| FR-CP-6 | Epic 5, Story 5.5 | Covered |
| FR-COB-1 | Epic 6, Story 6.1 | Covered |
| FR-COB-2 | Epic 6, Story 6.4 | Covered |
| FR-COB-3 | Epic 6, Story 6.5 | Covered |
| FR-COB-4 | Epic 6, Story 6.6 | Covered |
| FR-COB-5 | Epic 6, Story 6.9 (+ reuses FR-CR-8) | Covered |
| FR-COB-6 | Epic 6, Story 6.9 | Covered |
| FR-COB-7 | Epic 6, Story 6.7 | Covered |
| FR-COB-8 | Epic 6, Story 6.7 (toggle in chat header) | Covered |
| FR-COB-9 | Epic 6, Story 6.8 | Covered |
| FR-COB-10 | Epic 6, Story 6.2 | Covered |
| FR-CON-1 | Epic 7, Story 7.1 | Covered |
| FR-CON-2 | Epic 7, Story 7.2 | Covered |
| FR-CON-3 | Epic 7, Story 7.3 | Covered |
| FR-CON-4 | Epic 7, Story 7.4 | Covered |
| FR-CON-5 | Epic 7, Story 7.4 (auto-match section) | Covered |
| FR-CON-6 | Epic 7, Story 7.4 (N:1 and 1:N support) | Covered |
| FR-CON-7 | Epic 7, Story 7.5 | Covered |
| FR-CON-8 | Epic 7, Story 7.4 (confirmation transitions) | Covered |
| FR-DSH-1 | Epic 8, Story 8.1 | Covered |
| FR-DSH-2 | Epic 8, Story 8.2 | Covered |
| FR-DSH-3 | Epic 8, Story 8.3 | Covered |
| FR-DSH-4 | Epic 8, Story 8.4 | Covered |
| FR-DSH-5 | Epic 8, Story 8.5 | Covered |
| FR-INT-1 | Cross-cutting (Epic 2: FIPE/Tracker; Epic 4: OCR/Payment; Epic 6: WhatsApp/LLM; Epic 7: Bank; Epic 9: completeness audit) | Covered |
| FR-INT-2 | Epic 9, Story 9.1 | Covered |
| FR-INT-3 | Epic 2, Story 2.5 | Covered |
| FR-INT-4 | Epic 2, Story 2.9 | Covered |
| FR-INT-5 | Cross-cutting (webhook_events_raw in Epic 1; each provider adds its webhook in its epic) | Covered |
| FR-PRM-1 | Cross-cutting (each epic adds its section; consolidated in Epic 9) | Covered |
| FR-PRM-2 | Epic 9, Story 9.2 (+ config audit in each epic) | Covered |
| FR-AUD-1 | Epic 1 (infra) + all epics emit events | Covered |
| FR-AUD-2 | Epic 9, Story 9.2 | Covered |
| FR-AUD-3 | Epic 1 (HMAC) + Epic 9, Story 9.2 (verification UI) | Covered |

### Coverage Summary

- **63/63 FRs fully or partially covered**
- **61 fully covered**
- **2 partially covered** (FR-CTR-5, FR-CR-3)
- **0 missing**

### Gap Analysis

**FR-CTR-5 (Digital Signature) - Partial:** The contract wizard Step 4 includes a "digital signature upload area" but there is no dedicated story for the D4Sign/Clicksign integration extension point. The PRD explicitly marks this as "future extension," so the current coverage (upload-based signature) is acceptable for MVP. The adapter pattern (mentioned in FR-INT-1) provides the hook. **Verdict: Acceptable for MVP.**

**FR-CR-3 (Bulk Write-Off) - Partial:** Story 4.3 covers the write-off modal but does not have a separate story for the bulk write-off flow (selecting multiple titles from the same customer and applying a single payment). The receivables list (Story 4.1) supports multi-select and bulk actions, and the API spec in ARCHITECTURE.md defines `POST /receivables/bulk-write-off`. However, the acceptance criteria in Story 4.3 focus on single write-off. **Recommendation:** Add explicit bulk write-off acceptance criteria to Story 4.1 or create a small story 4.3b.

## 4. UX Alignment

### UX Document Status

- **Found:** `ux-design-specification.md` (1891 lines)
- **Steps completed:** 14 of 14 (as noted in frontmatter)
- **Content quality:** Comprehensive. Includes executive summary, emotional design framework, inspiration analysis, design system foundation, core UX definition, textual wireframes for 5 critical screens, user journey flows, component catalog (60+ components), UX consistency patterns, responsive breakpoints, accessibility checklist, and testing strategy.

### PRD <-> UX Alignment

| PRD UI Design Goal (Section 3) | UX Spec Coverage | Status |
|---|---|---|
| "Premium operational tool" (Linear/Notion/Stripe grade) | Executive Summary + Inspiration Analysis explicitly references these products | Aligned |
| Reactive by default (Signals + WS/SSE) | Real-Time Update Patterns (Section 12.8) + honest-state indicators | Aligned |
| Progressive disclosure (drawers/modals/popovers) | Drawer, Modal, Popover components defined; confirmation tiers documented | Aligned |
| Zero learning curve for Excel users | Keyboard shortcuts fully specified (Section 12.9); J/K/Enter/Esc; Ctrl+K palette | Aligned |
| Drag-and-drop (conciliation, schedule builder, reports) | Three distinct D&D semantics documented (Section 12.10) with CDK | Aligned |
| Command palette (Ctrl+K) | `<ui-command-palette>` component defined with search semantics | Aligned |
| Inline editing | Specified in schedule builder and parameter tables | Aligned |
| Dark/light theme | Design system tokens for both themes; `theme.service.ts` specified | Aligned |
| Glassmorphism-light surfaces | Mentioned in design system section, login screen, and surface token variables | Aligned |
| Tabular-nums (JetBrains Mono) | Explicitly called out in typography, money input, and data table patterns | Aligned |
| WCAG 2.1 AA | Full compliance checklist (Section 13.4) with testing strategy | Aligned |
| PWA-ready | Section 13.3 covers manifest, service worker, offline strategy | Aligned |

**Assessment:** Full alignment. The UX spec operationalizes every UI goal from PRD Section 3 into specific patterns, components, and acceptance-testable criteria.

### Architecture <-> UX Alignment

| Architecture Frontend Decision | UX Spec Alignment | Status |
|---|---|---|
| Angular 21 standalone + Signals | Component catalog uses `signal<T>` inputs throughout | Aligned |
| `resource()` API for data fetching | Referenced in schedule builder, customer list, dashboard cards | Aligned |
| Tailwind v4 + shadcn-like tokens | Design System Section 1.1 fully specifies token structure and `@theme` block | Aligned |
| Heroicons via @ng-icons | `<ui-icon>` component wrapping @ng-icons/heroicons exclusively | Aligned |
| SSE for notifications/dashboard/tracker | Real-time patterns specify SSE channels; honest-state indicator shows channel type | Aligned |
| WebSocket for chat only | Chat components use WS; all other real-time uses SSE | Aligned |
| CDK Drag-Drop | Three D&D contexts specified with CDK-specific patterns | Aligned |
| Leaflet + OSM | `<fleet-map>` component specified with cluster markers and SSE updates | Aligned |
| Folder structure (core/shared/features) | Component catalog locations match Architecture Section 10.1 exactly | Aligned |
| No NgModules, standalone only | All components specified as standalone | Aligned |

**Assessment:** Full alignment. Architecture and UX spec share the same component model, routing strategy, and technology choices.

### Gaps or Contradictions

1. **Minor: Command Palette Introduction Story.** The UX spec assigns `<ui-command-palette>` to Story 9.4 (originally "Full Observability"). The PRD lists it as a core interaction paradigm. The epics.md does not have a dedicated story for the command palette. **Recommendation:** The command palette should be introduced earlier (Story 1.2 or a small story in Epic 2) since the PRD defines it as essential for Excel-user parity. The current plan defers it to Epic 9, which is too late for user testing.

2. **Minor: LGPD "My Data" screen.** NFR-5 requires a "My Data" screen for drivers (export + deletion). The Architecture mentions LGPD endpoints (`GET /api/v1/customers/{id}/data-export`). However, no story in epics.md explicitly covers this screen or the anonymization flow. It is implicitly part of Epic 9 hardening but should be called out. **Recommendation:** Add a story to Epic 9 for LGPD compliance endpoints and the driver self-service screen.

3. **Minor: Inconsistent component introduction story references.** The UX spec's component catalog lists several components as "Introduced In: Story 5.1" (e.g., `<chat-bubble>`, `<chat-input>`, `<agent-status-chip>`). These are WhatsApp inbox components that belong to Epic 6, not Epic 5. This appears to be a numbering error in the UX spec. **Impact:** Low -- the mapping intent is clear (WhatsApp components belong to Epic 6).

## 5. Epic Quality Review

### User Value Focus

All 9 epics are organized around user-facing value outcomes:

| Epic | Value Statement | Technical-Only? |
|---|---|---|
| 1. Foundation & Identity | "Admin logs in and navigates" | Partially -- bootstrap stories (1.1, 1.7) are infra, but justified as mandatory foundation |
| 2. Catalog | "Registration spreadsheet is replaceable" | No -- direct user value |
| 3. Contracts | "Any contract shape, professional PDF, bulk edits" | No |
| 4. Receivables | "3-layer anti-fraud (OCR + validator + reconciliation)" | No |
| 5. Payables | "Monthly result (DRE) visible" | No |
| 6. WhatsApp Agent | "Agent conducts collections; human intervenes when wanted" | No |
| 7. Reconciliation | "Reconciliation in minutes; erroneous write-offs -> zero" | No |
| 8. Dashboards | "Pulse of the operation in seconds; ROI decides sale/trade" | No |
| 9. Hardening | "Production-ready with confidence; provider swap is trivial" | Partially -- ops/hardening, but necessary for go-live |

**Assessment:** Good. Epics 1 and 9 have technical-leaning stories, but this is standard for greenfield projects. The technical stories are correctly placed as bookends (foundation first, hardening last).

### Epic Independence

Each epic delivers end-to-end value after completion:

- **Epic 1:** Runnable app with auth -- usable standalone.
- **Epic 2:** Customer and vehicle catalog -- usable without contracts.
- **Epic 3:** Contracts with installments -- depends on Epic 2 (catalog exists), but this is a natural dependency.
- **Epic 4:** Receivables -- depends on Epic 3 (installments exist).
- **Epic 5:** Payables -- depends only on Epic 1 (basic infra). Could theoretically run in parallel with Epic 3.
- **Epic 6:** WhatsApp + Agent -- depends on Epic 4 (receivables exist for write-off).
- **Epic 7:** Reconciliation -- depends on Epic 4 (titles to reconcile).
- **Epic 8:** Dashboards -- depends on Epics 2-5 (data to display). Could be partially parallelized.
- **Epic 9:** Hardening -- depends on all previous epics.

**Assessment:** Dependencies are strictly sequential and respect the 12-week phased rollout specified in the Architecture. No circular dependencies. Each epic produces a deployable increment. Epic 5 (Payables) is notably independent of Epic 3/4 and could be parallelized if a second dev-agent is available.

### Story Dependencies

Within each epic, stories generally flow from backend model -> backend API -> frontend UI, which is a natural build order. No forward dependencies detected (no story requires a feature from a later epic to function).

**One observation:** Story 4.5 (Validation Queue) has an AC that says "Request Resubmission dispatches WhatsApp message via Epic 6 collection module." This creates a forward reference to Epic 6. However, the AC correctly scopes it: the WhatsApp integration is optional at this stage -- the button can be implemented as a no-op or use a simple notification. The epics.md addresses this by noting the dependency is deferred. **Impact:** Low, but the story should clearly mark this as a "stub until Epic 6" in its AC.

### Story Sizing

Stories are generally well-sized for single dev-agent completion (target: <= 1 day per story).

**Potential over-sized stories:**

| Story | Concern | Recommendation |
|---|---|---|
| 6.1 (WhatsApp Gateway) | 5 adapter implementations in one story | Consider splitting: core port + Evolution adapter as 6.1a, remaining 4 adapters as 6.1b |
| 6.4 (AI Agent Engine with RAG) | LLM adapter + RAG pipeline + 10 tools + function calling + dry-run mode | This is the most complex story in the project. Split into: 6.4a (ILLMProvider + basic agent loop), 6.4b (RAG with pgvector), 6.4c (tools implementation) |
| 8.5 (Custom Report Builder) | Full drag-and-drop pivot-table builder from scratch | Complex UI; acceptable as one story but will likely take > 1 day |

### Acceptance Criteria Quality

ACs are generally excellent: specific, testable, and often written in Given/When/Then format. They reference exact field names, API paths, status transitions, and UI behaviors.

**Strengths:**
- PG trigger behavior is specified with exact exception cases (Story 3.1)
- Pure function testing requirements are explicit (Stories 3.2, 4.2)
- Keyboard shortcuts are pinned to specific keys
- Security requirements (double-confirmation, Admin-only) are in the ACs, not assumed

**Weaknesses:**
- Some ACs reference "as defined in FR-CAD-1" rather than repeating the fields, creating an indirect dependency. This is acceptable but means the dev-agent must cross-reference the PRD.
- Story 9.7 (UX Polish) has vague ACs ("every list", "every action") that would benefit from an explicit screen-by-screen checklist.

### Violations Found

1. **Story 6.4 is over-sized.** It combines LLM integration, RAG pipeline, 10 function-calling tools, guardrails, cost tracking, and dry-run mode. This exceeds the "AI agent-sized" constraint. **Severity: Medium.**

2. **Story 6.1 bundles 5 adapter implementations.** While the port interface is shared, implementing and testing 5 WhatsApp adapters against different APIs is substantial. **Severity: Low** (only the default Evolution adapter needs to work for MVP; others can be stubs).

3. **Forward reference in Story 4.5** to Epic 6 WhatsApp module for "Request Resubmission." **Severity: Low** (can be stubbed).

4. **Missing explicit story for bulk write-off** (FR-CR-3). The receivables list supports multi-select and the API is defined, but no story AC covers the specific bulk payment flow. **Severity: Low.**

5. **Missing story for LGPD "My Data" screen** and customer anonymization flow. **Severity: Medium** -- this is a regulatory requirement.

6. **Command Palette deferred to Epic 9** despite being a core UX paradigm in the PRD. **Severity: Low** -- functional but not ideal for user feedback during earlier testing.

## 6. Architecture Alignment

### PRD <-> Architecture Consistency

The Architecture document is a faithful translation of the PRD into technical decisions:

- **Hexagonal Architecture** directly implements FR-INT-1 (plug-and-play ports) and NFR-10.
- **Tech stack** (Python 3.12 + FastAPI + PostgreSQL 16 + Redis 7 + Angular 21) is locked and documented.
- **Data model** covers every entity mentioned in the PRD with correct relationships, constraints, and indexes.
- **API endpoints** cover every FR with appropriate REST paths, methods, and permission gates.
- **Real-time decisions** (SSE for notifications/dashboard/tracker, WebSocket for chat, polling as fallback) are explicit and well-justified.
- **Worker jobs** (FIPE refresh, score recompute, preventive collection, recurring payables, backup, auto-match) are all defined in Celery Beat schedule.
- **Security** (Argon2id, JWT RS256, AES-256-GCM, HMAC audit, rate limiting, TLS 1.3) aligns with NFR-4.
- **Observability** (Prometheus, OpenTelemetry, structlog, Grafana) aligns with NFR-7.

**No contradictions detected** between PRD and Architecture.

### Tech Stack Validation

| Requirement Area | Tech Stack Coverage | Complete? |
|---|---|---|
| Authentication | Argon2id (argon2-cffi), JWT RS256 (python-jose), TOTP | Yes |
| Data persistence | PostgreSQL 16 + SQLAlchemy 2 async + Alembic | Yes |
| Caching/queuing | Redis 7 + Celery 5.4 | Yes |
| Object storage | MinIO (boto3) | Yes |
| OCR | pytesseract + opencv-python + LLM fallback | Yes |
| PDF generation | WeasyPrint + Jinja2 | Yes |
| PDF parsing | pdfplumber | Yes |
| OFX parsing | ofxparse | Yes |
| Pix QR | pix-utils | Yes |
| Maps | Leaflet + @asymmetrik/ngx-leaflet | Yes |
| Charts | ngx-echarts | Yes |
| Rich text | Tiptap | Yes |
| Drag-and-drop | @angular/cdk/drag-drop | Yes |
| PDF in-app viewer | ngx-extended-pdf-viewer | Yes |
| Image cropping | ngx-image-cropper | Yes |
| Brazilian validators | @brazilian-utils/brazilian-utils | Yes |
| E2E testing | Playwright | Yes |
| Component testing | Vitest + @ngneat/spectator | Yes |
| Visual regression | Storybook + Chromatic | Yes |
| Contract testing | schemathesis | Yes |

**Assessment:** The tech stack is complete and well-matched to requirements. No gaps identified.

### Missing Technical Considerations

1. **Email notifications.** The PRD does not explicitly require email, but password recovery (FR-AUTH-1 implies "forgot password") needs an email delivery mechanism. The Architecture defines `/auth/password/forgot` and `/auth/password/reset` endpoints but does not specify an email provider adapter. **Recommendation:** Add an `IEmailProvider` port (or note that password reset tokens are delivered via the existing WhatsApp channel).

2. **Rate limiting implementation.** NFR-4 requires "per-IP and per-user rate limiting." The Architecture mentions rate limiting at the edge (Caddy/Traefik: 100 req/IP/min) and in the login endpoint (5 attempts / 15 min). However, there is no explicit middleware for per-user rate limiting on sensitive API endpoints beyond login. **Recommendation:** The Architecture's edge config covers the IP dimension; per-user limiting should be noted as a FastAPI middleware pattern.

3. **Database connection pooling.** The Architecture mentions async SQLAlchemy but does not specify connection pool sizing or PgBouncer. Given the NFR-2 scalability target (10k vehicles), this should be explicit. **Impact:** Low for MVP; relevant at scale.

4. **Excel one-shot import.** The epics.md includes Story 2.11 for Excel catalog import (CLI), which is noted in the Architecture's Additional Requirements. However, the PRD does not have a dedicated FR for this. The Architecture adds it as a go-live requirement. **Assessment:** Correctly handled as an architecture-driven requirement.

## 7. Summary and Recommendations

### Overall Readiness Status

**READY** -- with minor action items below.

The four planning artifacts form a cohesive, internally consistent set. The PRD is thorough (63 FRs + 14 NFRs), the Architecture translates every requirement into executable technical decisions, the epics cover 100% of FRs with well-structured stories, and the UX spec operationalizes the visual/interaction design with pixel-level precision. The project can proceed to implementation.

### Critical Issues Requiring Immediate Action

None. There are no blocking issues preventing implementation from starting with Epic 1, Story 1.1.

### Warnings (Non-Blocking)

1. **Story 6.4 (AI Agent Engine) is too large.** Split into 3 sub-stories before sprint planning: (a) LLM port + basic conversational loop, (b) pgvector RAG integration, (c) function-calling tools with guardrails. This story as-is will exceed the 1-day target.

2. **Missing LGPD story.** Add a story to Epic 9 (or a new story 9.8) covering the "My Data" self-service screen, CSV export endpoint, and customer anonymization flow. This is a regulatory requirement (NFR-5) without explicit epic coverage.

3. **Bulk write-off (FR-CR-3) under-specified.** Add acceptance criteria for the multi-installment payment flow to Story 4.1 or create Story 4.3b. The API endpoint exists in the Architecture (`POST /receivables/bulk-write-off`) but no story tests it end-to-end.

4. **Command Palette timing.** Consider introducing `<ui-command-palette>` in Epic 2 or 3 rather than Epic 9. It is listed as a core interaction paradigm in the PRD and would improve developer/tester productivity during the build itself.

5. **Story 6.1 bundles 5 adapters.** For MVP, only the Evolution API adapter needs to be fully tested. Mark Z-API, UazAPI, WppConnect, and Cloud API adapters as "skeleton implementations" to reduce scope and test burden.

6. **Email delivery mechanism.** Add an `IEmailProvider` port or document that password recovery uses WhatsApp as the delivery channel.

7. **UX spec component story references.** Three components (`<chat-bubble>`, `<chat-input>`, `<agent-status-chip>`) are incorrectly tagged as "Introduced In: Story 5.1" when they belong to Epic 6. Correct the references to avoid confusion during implementation.

### Recommended Next Steps

1. **Start implementation with Story 1.1** (Bootstrap FastAPI Backend). All prerequisites are documented. No blockers.

2. **Before Sprint 2**, split Story 6.4 into sub-stories and add the LGPD story to Epic 9.

3. **Before Sprint 3**, add bulk write-off AC to Epic 4 stories.

4. **Before Sprint 5** (Epic 6 window), secure a test instance of Evolution API and confirm the WhatsApp number for development.

5. **Consider parallelizing** Epic 5 (Payables) with Epic 3 (Contracts) if two dev-agents are available, since Epic 5 has no dependency on Epic 3.

6. The **12-week phased rollout** defined in the Architecture (Foundation weeks 1-2, Contracts 3-4, CR/CP 5-6, Reconciliation 7-8, WhatsApp+Agent 9-11, Dashboards+Hardening 12) is realistic given the story sizing.
