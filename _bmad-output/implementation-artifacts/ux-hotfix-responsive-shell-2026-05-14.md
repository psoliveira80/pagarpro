---
title: "UX Hotfix: Responsive Shell, Profile Menu, Admin Settings, Spinner Fixes"
type: hotfix
status: done
date: 2026-05-14
---

# UX Hotfix: Responsive Shell, Profile Menu, Admin Settings, Spinner Fixes

## Issues Addressed

### 1. Mobile Responsiveness (Critical)
**Problem:** No mobile breakpoints. UI broke completely on small screens.
**Fix:** Added mobile-first responsive design across all components:
- Sidebar hidden on mobile, opens as overlay with backdrop on hamburger tap
- Header stacks elements vertically on small screens
- Tables use `overflow-x-auto` with horizontal scroll
- Content padding reduced on mobile (`p-4 md:p-6`)
- Less important columns hidden on mobile (`hidden sm:table-cell`)

### 2. User Profile Menu (Header — Top Right)
**Problem:** No user profile icon or logout button visible.
**Fix:** Added to top-right of header:
- User avatar with initials (from `authState().user.full_name`)
- Dropdown menu on click with: name+email, "Meu Perfil", "Preferências", divider, "Sair" (logout)
- Closes on click outside

### 3. Admin Settings Sidebar (sidebar2)
**Problem:** No way for admin to access system settings.
**Fix:** Admin gear icon (heroCog6Tooth) next to profile — only visible for Admin role:
- Opens a settings sidebar that slides in from the left over the main sidebar
- Sections: "Acesso" (Usuários, Roles & Permissões), "Parâmetros" (Financeiro, Contratos, Geral)
- Each item routes to `/system/settings/*`
- Auto-opens when user navigates directly to a settings route
- X button at top-right to close

### 4. Sidebar Collapse Control
**Problem:** X button at the bottom of sidebar was confusing.
**Fix:** Replaced with discrete chevron arrow at the top of sidebar:
- `<` (heroChevronLeft) when expanded
- `>` or hamburger when collapsed
- On mobile: hamburger icon in header opens sidebar overlay

### 5. Broken Spinner / Loading State
**Problem:** Static broken spinner showed "Carregando..." forever when API returned empty or errored.
**Fix across ALL 8 list components:**
- Replaced CSS border-based spinner with SVG spinner (reliable animation)
- Added `error` signal — API failures show error message + "Tentar novamente" button
- Empty state shows icon + message + optional "Criar" CTA (not a spinner)
- Pattern: `isLoading → spinner` | `error → error msg + retry` | `empty → empty state` | `data → table`

### 6. Customer Interface Mismatch
**Problem:** Frontend Customer interface used `document_number`/`document_type` but backend uses `cpf_cnpj`.
**Fix:** Aligned all interfaces and components to use `cpf_cnpj`:
- `CustomerService`: `items` instead of `data`
- `CustomersListComponent`: `formatDocument()` uses `cpf_cnpj` length
- Cascading fixes in customer-drawer, customer-detail, vehicle-wizard, contract-wizard

## Files Changed

### New Files (4)
- `src/app/features/settings/settings-placeholder.component.ts/html/css` — Settings page placeholder
- `_bmad-output/implementation-artifacts/ux-hotfix-responsive-shell-2026-05-14.md` — This doc

### Modified Files (24+)
- `src/app/shared/components/app-shell/app-shell.component.ts` — Profile menu, admin sidebar, mobile
- `src/app/shared/components/app-shell/app-shell.component.html` — Complete rewrite
- `src/app/shared/components/app-shell/app-shell.component.css` — Slide animation
- `src/app/shared/components/icon/icon.component.ts` — +2 icons (heroCog6Tooth, heroUserCircle)
- `src/app/core/services/customer.service.ts` — Interface alignment
- `src/app/features/system/system.routes.ts` — +5 settings routes
- 8x list component .ts files — error signal, catch improvements
- 8x list component .html files — SVG spinner, error/empty states
- 4x other components — cascading Customer interface fixes

## Verification
- Backend: 91/91 tests passing
- Frontend: Build OK, Lint OK
