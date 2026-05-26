---
epic: 9
story: 8
title: "UX Polish and Microinteractions"
type: "Core"
status: done
---

# Story 9.8: UX Polish and Microinteractions

## User Story
As a User,
I want the app polished,
So that the experience is pleasant under daily use.

## Acceptance Criteria

1. Page-transition animations (FLIP / View Transitions API where supported).
2. Skeleton loaders on every list and card.
3. Toasts: unified queue with auto-dismiss.
4. Empty states (illustration + CTA) on every list.
5. Modals respect `prefers-reduced-motion`.
6. Optimistic updates with rollback on error.
7. axe-core in CI with zero critical violations.
8. Mobile review at 375 px and 768 px screen-by-screen.

## Technical Context

### Architecture References
- **Architecture Section 10.1**: Frontend component structure; shared components at `frontend/src/app/shared/components/`.
- **Architecture Section 18.2 (Frontend Coding Standards)**: Standalone components, Tailwind with CSS tokens, Signals for state.
- **Architecture Section 16 (Performance)**: Frontend FCP <= 1.2s, TTI <= 2.5s targets.
- **Architecture Section 17.3 (Frontend Testing)**: Component tests with `@ngneat/spectator`, E2E with Playwright.

### Files to Create/Modify
```
frontend/
├── src/app/shared/components/
│   ├── skeleton-loader/
│   │   ├── skeleton-loader.component.ts                # Reusable skeleton loader (card, table row, text)
│   │   ├── skeleton-loader.component.html
│   │   └── skeleton-loader.component.css
│   ├── empty-state/
│   │   ├── empty-state.component.ts                    # Illustration + title + CTA button
│   │   ├── empty-state.component.html
│   │   └── empty-state.component.css
│   ├── toast/
│   │   ├── toast.component.ts                          # Toast notification with auto-dismiss queue
│   │   ├── toast.component.html
│   │   └── toast.component.css
│   └── toast/
│       └── toast.service.ts                            # Singleton service: queue, auto-dismiss, severity levels
├── src/app/shared/directives/
│   └── reduced-motion.directive.ts                     # Directive: detect prefers-reduced-motion, disable animations
├── src/app/shared/animations/
│   └── page-transitions.ts                             # FLIP / View Transitions API animation definitions
├── src/app/features/system/
│   ├── customers/customers-list.component.ts           # Modify: add skeleton, empty state, optimistic updates
│   ├── customers/customers-list.component.html
│   ├── contracts/contracts-list.component.ts           # Modify: add skeleton, empty state
│   ├── contracts/contracts-list.component.html
│   ├── finance/receivables/receivables-list.component.ts   # Modify: add skeleton, empty state, optimistic updates
│   ├── finance/receivables/receivables-list.component.html
│   ├── finance/payables/payables-list.component.ts     # Modify: add skeleton, empty state
│   ├── finance/payables/payables-list.component.html
│   ├── vehicles/vehicles-list.component.ts             # Modify: add skeleton, empty state
│   ├── vehicles/vehicles-list.component.html
│   ├── reports/reports-list.component.ts               # Modify: add skeleton, empty state
│   ├── reports/reports-list.component.html
│   ├── inbox/inbox.component.ts                        # Modify: add skeleton, empty state for conversation list
│   └── dashboard/dashboard.component.ts                # Modify: add skeleton loaders for KPI cards

frontend/
├── .axe-linter.yml                                     # axe-core CI configuration
├── src/app/app.component.ts                            # Modify: add View Transitions API support
└── playwright/
    └── accessibility.spec.ts                           # E2E: axe-core accessibility checks on key pages
```

### Dependencies
- All prior frontend stories (Epics 1-8) — components must exist before polish is applied
- Shared component library established in Epic 1

### Technical Notes
- **Skeleton loaders**: Create a generic `SkeletonLoaderComponent` with inputs for variant (`card`, `table-row`, `text`, `chart`). Each list/card page wraps its content in `@if (data.isLoading()) { <skeleton-loader /> } @else { ... }`.
- **Empty states**: `EmptyStateComponent` accepts `illustration` (SVG name), `title`, `description`, and `ctaLabel`/`ctaRoute`. Apply to every list view when the data array is empty.
- **Toast service**: Singleton `ToastService` manages a queue of toast messages with severity (success, error, warning, info), auto-dismiss after 5s (configurable), and manual dismiss. Maximum 3 visible toasts stacked.
- **Page transitions**: Use the View Transitions API (`document.startViewTransition()`) for page navigations where supported. Fallback to simple fade for unsupported browsers. Animations disabled when `prefers-reduced-motion: reduce` is active.
- **Optimistic updates**: For write operations (e.g., write-off, status change), update the local signal state immediately, then revert if the API call fails. Show error toast on rollback.
- **axe-core**: Add `axe-core` as a dev dependency. Create a Playwright test that runs `axe.run()` on key pages (dashboard, customer list, contract detail, inbox) and asserts zero critical/serious violations. Add to CI pipeline.
- **Mobile review**: Manually test all screens at 375px (mobile) and 768px (tablet) breakpoints. Fix layout issues, ensure touch targets >= 44px, and verify responsive behavior of tables (horizontal scroll or card layout).
- **`prefers-reduced-motion`**: All CSS animations and transitions must be wrapped in `@media (prefers-reduced-motion: no-preference) { ... }`. The `reduced-motion.directive.ts` provides a signal `prefersReducedMotion` for use in component logic.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
