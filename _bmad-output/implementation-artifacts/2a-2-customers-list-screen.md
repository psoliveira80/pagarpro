---
epic: 2A
story: 2
title: "Customers List Screen"
type: "Core"
status: done
---

# Story 2A.2: Customers List Screen

## User Story
As a Manager,
I want to browse all customers in a searchable, filterable table,
So that I find anyone in seconds.

## Acceptance Criteria

1. `CustomersListComponent` in `features/system/customers/`.
2. Columns: avatar, name, masked CPF/CNPJ (last 3 visible), phone (WhatsApp shortcut), score (colored badge), status (badge), last update, row actions (view, edit, delete).
3. Text search debounced 300 ms, signal-driven.
4. Filters: status (multi-select), tag (multi-select), score (range slider).
5. URL state: filters in query string.
6. Server-side pagination via signals, preferably using `resource()` API.
7. "Novo Cliente" opens drawer with `CustomerFormComponent`.
8. Skeleton loader during fetch; empty state with illustration and CTA.
9. Keyboard shortcuts: `/` focuses search, `n` opens new, arrows walk rows, `Enter` opens detail.

## Technical Context

### Architecture References
- **Architecture Section 2.5**: Feature components in `features/system/...`; data fetching via `resource()` API.
- **Architecture Section 3.2**: Angular 21 Signals + resource(), Tailwind v4, @ng-icons/heroicons.
- **Architecture Section 5.2 — Customers endpoints**: `GET /customers?search=&status=&page=&size=` with pagination response.

### Files to Create/Modify
```
frontend/
├── src/app/
│   ├── features/
│   │   └── system/
│   │       └── customers/
│   │           ├── customers.routes.ts                   # lazy route config
│   │           ├── customers-list/
│   │           │   ├── customers-list.component.ts       # standalone component
│   │           │   ├── customers-list.component.html     # template
│   │           │   └── customers-list.component.css      # styles
│   │           └── customer-form/
│   │               └── (placeholder — implemented in 2A.3)
│   ├── core/
│   │   └── services/
│   │       └── customers.service.ts                      # API calls: list, search, delete
│   ├── shared/
│   │   └── components/
│   │       ├── data-table/
│   │       │   ├── data-table.component.ts               # reusable table with pagination
│   │       │   └── data-table.component.html
│   │       ├── badge/
│   │       │   └── badge.component.ts                    # colored badge component
│   │       ├── skeleton-loader/
│   │       │   └── skeleton-loader.component.ts          # skeleton animation
│   │       ├── empty-state/
│   │       │   └── empty-state.component.ts              # empty state with illustration + CTA
│   │       └── drawer/
│   │           └── drawer.component.ts                   # slide-out drawer container
│   └── app.routes.ts                                     # add /system/customers route
```

### Dependencies
- **Story 1.2** (Angular skeleton, Tailwind, AppShell).
- **Story 1.5** (Auth service — must be authenticated to access).
- **Story 1.6** (AuthGuard protecting routes).
- **Story 2A.1** (Customer API endpoints on backend).

### Technical Notes
- **`resource()` API for data fetching** (Angular 21):
  ```typescript
  customers = resource({
    request: () => ({ search: this.search(), status: this.statusFilter(), page: this.page(), size: this.size() }),
    loader: ({ request }) => this.customersService.list(request),
  });
  ```
  This automatically re-fetches when signals change.
- **Debounced search**: Use a `signal<string>` for raw input, then a `computed` or `effect` with `setTimeout`/`clearTimeout` pattern (300ms) to produce the debounced search value.
- **URL state sync**: On filter change, update `Router` query params. On component init, read query params to initialize filter signals. Use `ActivatedRoute.queryParams` observable -> signal.
- **CPF masking**: Show only last 3 digits: `***.***.**X-XX`. This is a display-only concern in the template.
- **Score badge colors**: 0-30 red, 31-60 yellow, 61-85 blue, 86-100 green. Use Tailwind color classes.
- **Status badge**: `ativo` = green, `inativo` = gray, `bloqueado` = red.
- **WhatsApp shortcut**: Phone column shows a small WhatsApp icon that opens `https://wa.me/{phone}` in new tab.
- **Keyboard shortcuts**: Use `@HostListener('document:keydown')` in the component to handle `/`, `n`, arrows, Enter. Only activate when no input is focused (except `/` which focuses search).
- **Skeleton loader**: Show 5-8 rows of pulsing gray bars matching column widths while `customers.isLoading()` is true.
- **Empty state**: Show when `customers.value()?.items.length === 0` and not loading. Include illustration SVG and "Cadastrar primeiro cliente" button.
- **Delete**: Soft delete with confirmation dialog. On confirm, call `DELETE /customers/{id}`, then refresh list.
- **Drawer**: Reusable `DrawerComponent` in `shared/components/drawer/` — slides in from right, backdrop, close on Esc or backdrop click. Content projected via `<ng-content>`.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
