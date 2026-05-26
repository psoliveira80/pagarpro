---
epic: 3
story: 7
title: "Contract Versioning and Event Timeline"
type: "Core"
status: done
---

# Story 3.7: Contract Versioning and Event Timeline

## User Story

As a Manager,
I want to see the history of changes to a contract,
So that I can trace any modification.

## Acceptance Criteria

1. Contract detail page "History" tab.
2. Vertical timeline with icon + description + author + date per event.
3. **Given** event click, **Then** payload shown (visual diff when applicable).
4. Each `pdf_generated` event has "View this version's PDF" button.

## Technical Context

### Architecture References

- **FR-CORE-CTR-9**: Contract versioning with timeline of revisions
- **DB Table**: `contract_events` — `id`, `contract_id`, `event_type`, `payload` (JSONB), `pdf_hash`, `created_by_user_id`, `created_at`
- **API Endpoint** (Section 5.2): `GET /api/v1/contracts/{id}/events` — timeline
- **Frontend** (Section 10.1): `frontend/src/app/features/system/contracts/components/contract-events-timeline/`
- **Shared Components**: `shared/components/timeline/`

### Files to Create/Modify

**Create (Frontend):**
- `frontend/src/app/features/system/contracts/components/contract-events-timeline/contract-events-timeline.component.ts`
- `frontend/src/app/features/system/contracts/components/contract-events-timeline/contract-events-timeline.component.html`
- `frontend/src/app/features/system/contracts/components/contract-events-timeline/contract-events-timeline.component.css`

**Create (Backend):**
- `backend-api/app/api/v1/contract_routes.py` — add `GET /{id}/events` endpoint (if not already present)
- `backend-api/tests/integration/test_contract_events_endpoint.py`

**Modify (Frontend):**
- `frontend/src/app/features/system/contracts/contract-detail.component.ts` — add "Historico" tab rendering the timeline component
- `frontend/src/app/features/system/contracts/services/contract.service.ts` — add `getEvents(contractId)` method

### Dependencies

- Story 3.1 (contract_events table)
- Story 3.4 (Contract creation — creates initial events)
- Story 3.5 (PDF generation — pdf_generated events)
- Story 3.6 (Bulk edit — bulk_edit events)

### Technical Notes

- **Timeline component**: vertical timeline (top = most recent). Each node shows:
  - Icon per event type: `created` (document), `signed` (pen), `installments_generated` (list), `installments_reissued` (refresh), `bulk_edit` (edit), `terminated` (x-circle), `pdf_generated` (file-pdf)
  - Description text (generated from event_type + payload summary)
  - Author name (from `created_by_user_id` joined with users)
  - Formatted date/time
- **Event click detail**: modal or expandable section showing the full `payload` JSONB. For events with before/after data (like `bulk_edit`), render a simple diff view (old value -> new value).
- **PDF link**: for `pdf_generated` events, show a "Ver PDF v{version}" button that calls `GET /api/v1/contracts/{id}/pdf?version={version}` and opens the presigned URL in a new tab.
- **Backend endpoint**: `GET /api/v1/contracts/{id}/events` returns paginated list of `contract_events` ordered by `created_at DESC`, with `created_by` user info (name) included via join or sub-select.
- **Contract versioning**: each mutation that changes contract substance increments `contract.version`. The version is recorded in the event payload for reference. The timeline provides a complete audit trail.

## Dev Checklist

- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
