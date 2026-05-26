---
epic: 9
story: 10
title: "LGPD My Data Self-Service"
type: "Core"
status: done
---
# Story 9.10: LGPD "My Data" Self-Service

## User Story
As a Customer (external),
I want to export or request deletion of my personal data,
So that the system complies with LGPD.

## Acceptance Criteria

1. Endpoint `GET /api/v1/customers/{id}/data-export` generates a ZIP with all personal data (profile, contracts, titles, messages, attachments).
2. Endpoint `POST /api/v1/customers/{id}/anonymize` replaces personal fields with "[redigido]", masks CPF, removes photos — preserving financial history for audit.
3. Anonymization requires Admin role + reason + audit log entry with category='security'.
4. A simple "Meus Dados" page accessible via a unique link sent to the customer (no full app login required — token-based access).
5. The page shows: personal data summary, "Exportar Dados" button, "Solicitar Exclusão" button (sends request to Admin for review).

## Technical Context

### Architecture References
- **NFR-5 (LGPD)**: Data export + deletion; consent; PII access logs.
- **Architecture Section 4 (Domain)**: Customer entity with personal data fields.
- **Architecture Section 5 (API Endpoints)**: Customer-facing endpoints with token-based auth.

### Files to Create/Modify
```
backend-api/
├── app/api/v1/customer_data_routes.py             # data-export and anonymize endpoints
├── app/application/customers/data_export.py       # ZIP generation use case
├── app/application/customers/anonymize.py         # Anonymization use case
├── app/domain/customers/anonymization.py          # Anonymization rules (pure)
├── app/api/v1/public/my_data_routes.py            # Token-based public endpoint
├── app/domain/customers/data_access_token.py      # Token generation/validation
├── app/infrastructure/db/models/data_access_token.py  # Token persistence
├── app/tests/unit/domain/customers/
│   └── test_anonymization.py                      # Unit tests
├── app/tests/integration/api/
│   └── test_customer_data_routes.py               # Integration tests

frontend/
├── src/app/features/public/my-data/
│   ├── my-data-page.component.ts
│   ├── my-data-page.component.html
│   └── my-data-page.component.css
```

### Dependencies
- Story 2A.1 (customer domain)

### Technical Notes
- The data export ZIP should include: customer profile JSON, contracts list, installments history, WhatsApp messages (text only, no media), and uploaded attachments.
- Anonymization must preserve referential integrity — `customer_id` FKs remain valid but personal fields are redacted.
- CPF masking: show only first 3 digits (e.g., "123.***.***-**").
- The token for "Meus Dados" page should be a signed JWT with short expiry (24h) and single-use for deletion requests.
- Photos should be replaced with a generic placeholder, not just URL nullified — MinIO objects must be deleted.
- Financial records (amounts, dates, statuses) are preserved for audit compliance.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] No regressions
