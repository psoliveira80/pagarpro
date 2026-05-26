---
epic: 2A
story: 1
title: "Customer Domain Model and CRUD API"
type: "Core"
status: done
---

# Story 2A.1: Customer Domain Model and CRUD API

## User Story
As a Backend developer,
I want a Customer entity with complete REST endpoints,
So that the frontend can manage the customer base.

## Acceptance Criteria

1. `Customer` model with generic fields: full name, CPF/CNPJ (validated), phone (E.164), email, full address, birth date, photo, notes, `score` (default 100), `status` (`ativo`/`inativo`/`bloqueado`), `tags` (JSONB), `metadata_extensions` (JSONB for module-injected fields), `created_by_user_id`.
2. CPF/CNPJ validated and unique; email unique; phone normalized to E.164.
3. Endpoints: `POST /api/v1/customers`, `GET /api/v1/customers?search=&status=&page=&size=`, `GET /api/v1/customers/{id}`, `PATCH /api/v1/customers/{id}`, `DELETE /api/v1/customers/{id}` (soft delete), `POST /api/v1/customers/{id}/attachments`.
4. Attachments stored in MinIO at `customers/{id}/{uuid}-{filename}` with record in `customer_attachments`.
5. Every mutation writes to `audit_log` with HMAC signature.
6. Integration tests covering CRUD + attachment upload.

## Technical Context

### Architecture References
- **Architecture Section 4.2 — Catalog**: Customer entity with `full_name`, `cpf` (VO `Cpf`), `rg`, `cnh` (VO), `phone` (VO `PhoneE164`), `email`, `address` (VO `Address`), `birth_date`, `photo_url`, `status`, `score`, `tags` (JSONB), `notes`, `created_by_user_id`, soft delete.
- **Architecture Section 4.2 — Catalog**: CustomerAttachment entity — `id`, `customer_id`, `kind`, `url`, `mime`, `size`, `uploaded_at`.
- **Architecture Section 5.2 — Customers endpoints**: Full CRUD + attachments + financials + score-history.
- **Architecture Section 4.4 — Value Objects**: `Cpf`, `PhoneE164`, `Money` in `domain/shared/value_objects.py`.
- **Architecture Section 6**: Models in `app/infrastructure/db/models/customer.py`, routes in `app/api/v1/customer_routes.py`, use cases in `app/application/customers/`.
- **Architecture Section 6.1**: Use case pattern with Input/Output dataclasses, repository injection, audit logging.

### Files to Create/Modify
```
backend-api/
├── app/
│   ├── domain/
│   │   ├── catalog/
│   │   │   ├── __init__.py
│   │   │   └── customer.py              # Customer domain entity
│   │   └── shared/
│   │       └── value_objects.py          # add Cpf, PhoneE164, Address VOs (extend from 1.1)
│   ├── infrastructure/
│   │   ├── db/
│   │   │   ├── models/
│   │   │   │   └── customer.py          # Customer + CustomerAttachment SQLAlchemy models
│   │   │   └── repositories/
│   │   │       └── customer_repo.py     # ICustomerRepo implementation
│   │   └── integrations/
│   │       └── storage/
│   │           └── s3_compatible_adapter.py  # MinIO upload (extend or create)
│   ├── domain/
│   │   └── ports/
│   │       └── repositories.py          # ICustomerRepo interface (Protocol)
│   ├── application/
│   │   └── customers/
│   │       ├── __init__.py
│   │       ├── create_customer.py       # CreateCustomer use case
│   │       ├── update_customer.py       # UpdateCustomer use case
│   │       ├── list_customers.py        # ListCustomers use case (search, filter, paginate)
│   │       ├── get_customer.py          # GetCustomer use case
│   │       ├── delete_customer.py       # SoftDeleteCustomer use case
│   │       └── upload_attachment.py     # UploadAttachment use case
│   ├── api/
│   │   └── v1/
│   │       ├── customer_routes.py       # FastAPI router with all customer endpoints
│   │       └── schemas/
│   │           └── customers.py         # Pydantic DTOs: CustomerCreate, CustomerUpdate, CustomerResponse, etc.
│   └── tests/
│       ├── test_customer_crud.py        # integration tests
│       └── test_customer_attachments.py # attachment upload test
├── alembic/
│   └── versions/
│       └── 0004_customers.py            # migration: customers + customer_attachments tables
```

### Dependencies
- **Story 1.1** (FastAPI skeleton, MinIO connection, DB session).
- **Story 1.3** (Alembic, audit_log table, base model mixins).
- **Story 1.4** (Auth — `get_current_user` dependency for `created_by_user_id`).

### Technical Notes
- **CPF/CNPJ validation**: Use the `Cpf` value object from `domain/shared/value_objects.py`. Validate checksum digits algorithmically. Store as 11 digits (CPF) or 14 digits (CNPJ), no formatting. Consider encrypting CPF at rest (AES-256-GCM) per LGPD requirements — store encrypted bytes in a `cpf_enc` column and a partial hash for lookups.
- **Phone normalization**: Accept various formats (e.g., `71999998888`, `(71) 99999-8888`, `+5571999998888`) and normalize to E.164 format (`+5571999998888`). Use the `PhoneE164` value object.
- **Search**: `GET /customers?search=` should search across `full_name`, `email`, `cpf` using `pg_trgm` similarity or `ILIKE` with `unaccent()` for accent-insensitive matching.
- **Pagination**: Use `page` + `size` pattern. Return `{items: [], total: int, page: int, size: int, pages: int}`.
- **Soft delete**: Set `deleted_at = now()`. All queries must filter `WHERE deleted_at IS NULL` by default.
- **Attachment upload**: Accept `multipart/form-data` with file + `kind` field. Upload to MinIO at path `customers/{customer_id}/{uuid}-{original_filename}`. Store metadata in `customer_attachments` table.
- **MinIO/S3 adapter**: Use `boto3` with configurable endpoint URL (MinIO locally, S3 in prod). Implement via `IStorageProvider` port.
- **Audit**: Every create/update/delete must write to `audit_log` via the `AuditLogger` service from Story 1.3. Include `payload_before` (for updates) and `payload_after`.
- **Permission**: Check that the current user has `customers.create`, `customers.read`, `customers.update`, `customers.delete` permissions. Seed these permissions in this migration.
- **`metadata_extensions` JSONB**: This column allows vertical modules to store additional fields on the customer (e.g., Vehicle Module stores CNH data here). The API should accept and return this field transparently.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
