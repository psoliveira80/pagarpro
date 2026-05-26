---
epic: 2A
story: 3
title: "Customer Create/Edit Drawer"
type: "Core"
status: done
---

# Story 2A.3: Customer Create/Edit Drawer

## User Story
As a Manager,
I want an ergonomic form to create or edit a customer,
So that registration is fast.

## Acceptance Criteria

1. Form in 3 collapsible sections: Personal Data, Documents, Contact & Address. Vertical modules can inject additional sections (e.g., Vehicle Module injects "CNH" section).
2. Inline validation (Reactive Forms typed).
3. CEP auto-fills via ViaCEP.
4. Photo: drop-zone with circular crop preview.
5. Attachments: multi-file drop-zone with previews.
6. Save closes drawer and refreshes list; error shows toast and preserves form.
7. Accessible: tab order correct, focus to first invalid on submit, `Esc` closes (confirm if dirty).

## Technical Context

### Architecture References
- **Architecture Section 2.5**: Feature components use shared components; forms use Reactive Forms typed.
- **Architecture Section 3.2**: Angular Reactive Forms (nativo), @brazilian-utils/brazilian-utils for CPF/CNPJ validation, ngx-image-cropper for photo crop.
- **Architecture Section 5.2 — Customers endpoints**: `POST /customers`, `PATCH /customers/{id}`, `POST /customers/{id}/attachments`.
- **Architecture Section 4.2 — Asset Registry**: `metadata_extensions` JSONB allows modules to inject additional fields.

### Files to Create/Modify
```
frontend/
├── src/app/
│   ├── features/
│   │   └── system/
│   │       └── customers/
│   │           └── customer-form/
│   │               ├── customer-form.component.ts       # standalone form component
│   │               ├── customer-form.component.html     # template with collapsible sections
│   │               └── customer-form.component.css      # styles
│   ├── shared/
│   │   └── components/
│   │       ├── file-dropzone/
│   │       │   └── file-dropzone.component.ts           # reusable drag-and-drop file upload
│   │       ├── image-cropper/
│   │       │   └── image-cropper.component.ts           # circular crop wrapper (ngx-image-cropper)
│   │       ├── collapsible-section/
│   │       │   └── collapsible-section.component.ts     # expandable form section
│   │       └── address-form/
│   │           └── address-form.component.ts            # reusable address sub-form with CEP lookup
│   ├── core/
│   │   └── services/
│   │       └── viacep.service.ts                        # CEP lookup service
```

### Dependencies
- **Story 1.2** (Angular skeleton, Tailwind, shared components base).
- **Story 2A.1** (Customer API — POST/PATCH endpoints).
- **Story 2A.2** (Customers list screen — drawer container, refresh mechanism).

### Technical Notes
- **Typed Reactive Forms**: Define a strongly typed form group:
  ```typescript
  form = new FormGroup({
    full_name: new FormControl('', { validators: [Validators.required], nonNullable: true }),
    cpf_cnpj: new FormControl('', { validators: [Validators.required, cpfCnpjValidator], nonNullable: true }),
    phone: new FormControl('', { validators: [Validators.required], nonNullable: true }),
    email: new FormControl('', { validators: [Validators.email], nonNullable: true }),
    birth_date: new FormControl<string | null>(null),
    notes: new FormControl(''),
    address: new FormGroup({
      cep: new FormControl(''),
      street: new FormControl(''),
      number: new FormControl(''),
      complement: new FormControl(''),
      neighborhood: new FormControl(''),
      city: new FormControl(''),
      state: new FormControl(''),
    }),
    tags: new FormControl<string[]>([]),
  });
  ```
- **CPF/CNPJ validator**: Use `@brazilian-utils/brazilian-utils` for validation. Create a custom Angular validator:
  ```typescript
  const cpfCnpjValidator: ValidatorFn = (control) => {
    const value = control.value;
    if (!value) return null;
    return isValidCpf(value) || isValidCnpj(value) ? null : { cpfCnpj: true };
  };
  ```
- **ViaCEP integration**: On CEP field blur (when 8 digits entered), call `https://viacep.com.br/ws/{cep}/json/`. Auto-fill street, neighborhood, city, state. Show loading indicator on CEP field.
- **Photo crop**: Use `ngx-image-cropper` with circular crop and 1:1 aspect ratio. On file drop, show cropper dialog. On confirm, upload cropped image as the customer photo.
- **Attachments**: Multi-file dropzone. Show thumbnail previews for images, file icon for others. Each file shows name, size, remove button. On save, upload all pending files via `POST /customers/{id}/attachments`.
- **Collapsible sections**: Each section has a header with chevron icon (toggle open/close). Default: Personal Data open, others closed in create mode; all open in edit mode.
- **Module-injected sections**: Use a registry pattern. When Vehicle Module is active, it registers an additional "CNH" section config. The form component queries active module sections and renders them dynamically. For now, just support the extension point (empty) — Vehicle Module will use it in Epic 2B.
- **Edit mode**: When `customerId` input is provided, load customer data and patch form. Use `PATCH` for updates (only send changed fields).
- **Dirty check on close**: If form is dirty and user presses Esc or clicks backdrop, show confirmation dialog "Descartar alteracoes?".
- **Focus on first invalid**: On submit validation failure, find the first invalid control and focus its native element using `ViewChildren` query.
- **Save flow**: On save, submit to API. On success: close drawer, emit `saved` event (parent refreshes list), show success toast. On error: show error toast, keep drawer open, preserve form state.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
