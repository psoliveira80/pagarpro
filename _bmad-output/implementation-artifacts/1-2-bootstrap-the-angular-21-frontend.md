---
epic: 1
story: 2
title: "Bootstrap the Angular 21 Frontend"
type: "Core"
status: done
---

# Story 1.2: Bootstrap the Angular 21 Frontend

## User Story
As a Developer,
I want an Angular 21 standalone skeleton wired with Tailwind v4, Heroicons, and the manifesto-driven folder structure,
So that features are built consistently from day one.

## Acceptance Criteria

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

## Technical Context

### Architecture References
- **Architecture Section 2.5**: Frontend layered pattern — Features -> Shared -> Core -> API Client.
- **Architecture Section 3.2**: Frontend tech stack — Angular 21+ standalone, Signals + resource(), Tailwind v4, @ng-icons/heroicons, Reactive Forms, date-fns, Vitest + @ngneat/spectator.
- **Architecture Section 2.5**: State via signals local to components; signal services in `core/` for global state (auth, theme, notifications).
- **Architecture Section 2.5**: Lazy loading by feature shell.

### Files to Create/Modify
```
frontend/
├── angular.json
├── package.json
├── tsconfig.json
├── tailwind.config.ts                       # Tailwind v4 config with typography + forms plugins
├── .eslintrc.json
├── .prettierrc
├── .stylelintrc.json
├── public/
│   ├── manifest.webmanifest                 # PWA manifest placeholder
│   └── favicon.ico
├── src/
│   ├── index.html                           # PWA meta tags
│   ├── styles.css                           # Tailwind imports + @theme block with CSS vars
│   ├── main.ts                              # bootstrapApplication
│   ├── app/
│   │   ├── app.component.ts
│   │   ├── app.routes.ts                    # top-level routes: /login, /dashboard, /404
│   │   ├── core/
│   │   │   ├── services/
│   │   │   │   └── theme.service.ts         # theme() signal, setTheme(), localStorage
│   │   │   ├── guards/                      # placeholder for auth guard
│   │   │   └── interceptors/                # placeholder for JWT interceptor
│   │   ├── shared/
│   │   │   └── components/
│   │   │       ├── icon/
│   │   │       │   └── icon.component.ts    # <ui-icon name="..."> wrapper
│   │   │       └── app-shell/
│   │   │           ├── app-shell.component.ts
│   │   │           ├── app-shell.component.html
│   │   │           └── app-shell.component.css
│   │   ├── features/
│   │   │   ├── auth/
│   │   │   │   └── login/                   # placeholder LoginComponent
│   │   │   └── dashboard/                   # placeholder DashboardComponent
│   │   └── environments/
│   │       ├── environment.ts               # productName from env or build config
│   │       └── environment.prod.ts
│   └── not-found/
│       └── not-found.component.ts           # 404 page
```

### Dependencies
- None — this story can be developed in parallel with Story 1.1.

### Technical Notes
- Use `ng new` with `--standalone --style=css --routing` flags, then restructure into the manifesto layout.
- **No NgModules**: all components are standalone with `imports` array.
- Tailwind v4: install `tailwindcss`, `@tailwindcss/typography`, `@tailwindcss/forms`. In `styles.css` use `@import "tailwindcss"` and define the `@theme` block with CSS custom properties for colors, spacing, radius, shadows — both light and dark mode variants using `@media (prefers-color-scheme: dark)` or a `.dark` class approach.
- `ThemeService`: inject in root, use a `signal<'light'|'dark'|'system'>()`, read localStorage on init, write to localStorage on change, toggle `.dark` class on `document.documentElement`.
- `AppShellComponent`: sidebar with `nav` links (Dashboard placeholder), collapsible via signal, header with product name from `environment.productName`, theme toggle button using Heroicons (sun/moon).
- Routes should use lazy loading: `loadComponent` for login/dashboard.
- Icons: `@ng-icons/core` provides `NgIconComponent`; wrap it in a `UiIconComponent` for consistent sizing/styling.
- `manifest.webmanifest`: use a generic `name` field populated from build config, not hardcoded product name.
- Vitest config: ensure `vitest.config.ts` is set up for Angular with `@analogjs/vitest-angular` or equivalent.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
