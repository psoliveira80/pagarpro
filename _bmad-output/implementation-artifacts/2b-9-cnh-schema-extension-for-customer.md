---
epic: 2B
story: 9
title: "CNH Schema Extension for Customer"
type: "Vehicle Module"
status: done
---

# Story 2B.9: CNH Schema Extension for Customer

## User Story

As the Vehicle Module,
I want to register CNH fields on the Customer entity,
So that driver documentation is part of the customer profile.

## Acceptance Criteria

1. Vehicle Module registers schema extension for Customer via `metadata_extensions`: CNH number, category, expiry date, photo URL.
2. Customer form (Story 2A.3) renders the "CNH" section when Vehicle Module is active.
3. CNH validation: number format, category (A/B/AB/C/D/E), expiry not in the past.
4. CNH photo uploaded to MinIO as a customer attachment with kind `cnh`.

## Technical Context

### Architecture References

- **FR-VH-6**: Schema extension for Customer: CNH (number, category, expiry, photo)
- **Customer DB Table** (Section 9.4): `customers` already has `cnh_number TEXT`, `cnh_category VARCHAR(5)`, `cnh_expires_at DATE` columns baked into the schema
- **Customer Attachments**: `customer_attachments` table with `kind` field — use `kind='cnh'` for CNH photo
- **Value Object**: `Cnh` VO with `number`, `category`, `expiry` — defined in `backend-api/app/domain/shared/value_objects.py` (Section 4.2)
- **Storage**: MinIO via `IStorageProvider` — `backend-api/app/infrastructure/integrations/storage/s3_compatible_adapter.py`
- **Module Service**: `core/services/module.service.ts` on frontend — checks if Vehicle Module is active

### Files to Create/Modify

**Modify (Backend):**
- `backend-api/app/domain/shared/value_objects.py` — add `Cnh` value object with validation (number format, category enum, expiry check)
- `backend-api/app/modules/vehicles/module.py` — register `metadata_extensions` for Customer entity: `{entity: 'customer', fields: [{name: 'cnh_number', ...}, {name: 'cnh_category', ...}, {name: 'cnh_expires_at', ...}]}`
- `backend-api/app/api/v1/customer_routes.py` — ensure CNH fields are accepted in create/update when Vehicle Module is active
- `backend-api/app/modules/vehicles/schemas.py` — add `CnhExtensionDTO` with validation

**Modify (Frontend):**
- `frontend/src/app/features/system/customers/customer-form.component.ts` — conditionally render CNH section when Vehicle Module is active (check via `module.service.ts`)
- `frontend/src/app/features/system/customers/customer-form.component.html` — add CNH fields section with conditional `@if`

**Create:**
- `frontend/src/app/features/system/customers/components/cnh-section/cnh-section.component.ts` — CNH form section: number input, category select (A/B/AB/C/D/E), expiry date picker, photo upload
- `frontend/src/app/features/system/customers/components/cnh-section/cnh-section.component.html`
- `frontend/src/app/features/system/customers/components/cnh-section/cnh-section.component.css`
- `backend-api/tests/unit/modules/vehicles/test_cnh_extension.py`

### Dependencies

- Story 2B.1 (Vehicle Module registered)
- Story 2A.3 (Customer form component)
- Epic 1 (MinIO storage adapter, customer_attachments table)

### Technical Notes

- The `customers` table already has CNH columns (`cnh_number`, `cnh_category`, `cnh_expires_at`) in the DDL. The Vehicle Module's schema extension mechanism is about telling the frontend to render these fields when the module is active.
- **Validation**: CNH number is 11 digits. Category must be one of: `A`, `B`, `AB`, `C`, `D`, `E`, `AC`, `AD`, `AE`. Expiry date must not be in the past (warning if within 30 days of expiry).
- **Photo upload**: CNH photo is uploaded via `POST /api/v1/customers/{id}/attachments` with `kind='cnh'`. The `cnh-section` component includes a `file-dropzone` for the photo.
- **Frontend conditional rendering**: `cnh-section` component is only shown when `moduleService.isActive('vehicle')` returns true. Use `@if` in template.
- **Module metadata_extensions pattern**: `VehicleModule` exposes a method (e.g., `get_customer_extensions()`) that returns the list of additional fields. The customer form queries active modules for extensions and renders them dynamically.

## Dev Checklist

- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
