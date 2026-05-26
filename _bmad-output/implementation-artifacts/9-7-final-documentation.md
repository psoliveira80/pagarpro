---
epic: 9
story: 7
title: "Final Documentation"
type: "Core"
status: done
---

# Story 9.7: Final Documentation

## User Story
As the Next Developer,
I want complete documentation,
So that I can maintain the product without the original author.

## Acceptance Criteria

1. `README.md` enables local setup in < 10 minutes.
2. `ARCHITECTURE.md` reviewed and versioned.
3. `ADAPTERS.md`: "how to add a new adapter" guide for each Port.
4. `MODULES.md`: "how to create a new vertical module" guide, covering `IAssetModule` implementation, hook registration, schema extensions, UI injection points.
5. OpenAPI at `/docs` with snapshot in `API.md`.
6. `DEPLOYMENT.md` deploy playbook.
7. `RUNBOOK.md` troubleshooting guide.
8. ADRs `0001`-`0010` under `docs/adrs/` (Hexagonal, SSE+WS split, pgvector, Celery, Evolution, Tesseract OCR, No-gateway Pix default, Paid-installment immutability PG trigger, Single-tenant first, Asset Abstraction Layer).

## Technical Context

### Architecture References
- **Architecture Section 2.4**: Hexagonal architecture (ADR-0001).
- **Architecture Section 3.1**: Full tech stack reference.
- **Architecture Section 7.1-7.3**: IAssetModule protocol, module registration, event dispatch — source material for `MODULES.md`.
- **Architecture Section 14 (Deployment)**: Docker Compose, CI/CD — source material for `DEPLOYMENT.md`.
- **Architecture Section 5 (Real-time)**: SSE + WS split rationale (ADR-0002).

### Files to Create/Modify
```
docs/
├── README.md                                           # Project overview, prerequisites, local setup guide
├── ARCHITECTURE.md                                     # Reviewed and versioned architecture document
├── ADAPTERS.md                                         # Guide: how to add a new adapter for each Port
├── MODULES.md                                          # Guide: how to create a new vertical module
├── API.md                                              # OpenAPI snapshot + usage examples
├── DEPLOYMENT.md                                       # Deploy playbook: staging and production
├── RUNBOOK.md                                          # Troubleshooting guide: common issues + resolution
└── adrs/
    ├── 0001-hexagonal-architecture.md                  # ADR: why hexagonal/ports-and-adapters
    ├── 0002-sse-ws-split.md                            # ADR: SSE for notifications, WS for chat
    ├── 0003-pgvector.md                                # ADR: pgvector for semantic search
    ├── 0004-celery.md                                  # ADR: Celery for async task processing
    ├── 0005-evolution-api.md                           # ADR: Evolution API for WhatsApp
    ├── 0006-tesseract-ocr.md                           # ADR: Tesseract for OCR receipt processing
    ├── 0007-no-gateway-pix-default.md                  # ADR: No-gateway Pix as default payment method
    ├── 0008-paid-installment-immutability-trigger.md   # ADR: PG trigger for paid installment immutability
    ├── 0009-single-tenant-first.md                     # ADR: single-tenant architecture first
    └── 0010-asset-abstraction-layer.md                 # ADR: Asset Abstraction Layer with IAssetModule
```

### Dependencies
- All prior epics (1-8) must be feature-complete so documentation reflects the final system
- Story 9.4 (`RUNBOOK_DR.md` — disaster recovery section feeds into `RUNBOOK.md`)

### Technical Notes
- `README.md` must include: project description, prerequisites (Docker, Node 20+, Python 3.12+, uv), one-command local setup (`docker compose up`), seed data instructions, default credentials, and links to other docs.
- `ADAPTERS.md` lists every Port interface (e.g., `IStorageProvider`, `IOcrProvider`, `IPaymentGateway`, `IWhatsAppProvider`, `IOpenFinanceProvider`, `ILlmProvider`) with: interface methods, existing adapters, step-by-step guide to create a new adapter, and testing instructions.
- `MODULES.md` covers: creating a new `IAssetModule` implementation, registering in `ModuleRegistry`, defining module-specific schemas/DTOs, adding domain event hooks, creating module API routes, injecting UI components (tabs, widgets, menu items), and adding module-specific tests.
- Each ADR follows the format: Title, Status (Accepted), Context, Decision, Consequences (positive/negative).
- `API.md` is generated from the OpenAPI schema at `/docs` using a script or manual export. Include key endpoint examples with request/response samples.
- `DEPLOYMENT.md` covers: environment variables reference, Docker image building, staging deployment (auto on push to main), production deployment (manual release tag), database migration procedure, rollback procedure.
- `RUNBOOK.md` includes: health check procedures, common error scenarios and fixes, log analysis guide, performance degradation playbook, integration failure recovery, and escalation contacts.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
