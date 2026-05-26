---
epic: 9
story: 11
title: "Command Palette (Ctrl+K)"
type: "Core"
status: done
---
# Story 9.11: Command Palette (Ctrl+K)

## User Story
As a Manager,
I want a global command palette for instant navigation and actions,
So that I never need to hunt for a screen or action.

## Acceptance Criteria

1. `Ctrl+K` (or `Cmd+K` on Mac) opens `<ui-command-palette>` overlay anywhere in the app.
2. Search modes: default (fuzzy search across customers, vehicles, contracts, titles by name/CPF/plate/number), `>` prefix for actions ("baixar título 1234"), `#` for titles by number, `@` for customers.
3. Results update live with debounce 200ms; keyboard navigation (↑/↓/Enter/Esc).
4. Recent searches persisted in localStorage (last 10).
5. Component lives in `frontend/src/app/shared/components/command-palette/`.
6. Backend endpoint `GET /api/v1/search?q=&type=` returns unified search results across entities.

## Technical Context

### Architecture References
- **Architecture Section 10 (Frontend Architecture)**: Shared components in `shared/components/`.
- **Architecture Section 5 (API Endpoints)**: Unified search endpoint pattern.
- **NFR-1 (Performance)**: P95 read <= 300ms — search must be fast.

### Files to Create/Modify
```
backend-api/
├── app/api/v1/search_routes.py                    # GET /api/v1/search unified endpoint
├── app/application/search/unified_search.py       # Search orchestrator across entities
├── app/tests/integration/api/
│   └── test_search_routes.py                      # Integration tests

frontend/
├── src/app/shared/components/command-palette/
│   ├── command-palette.component.ts
│   ├── command-palette.component.html
│   ├── command-palette.component.css
│   └── command-palette.service.ts                 # Manages open/close state, recent searches
├── src/app/core/services/
│   └── search.service.ts                          # API client for unified search
```

### Dependencies
- Story 1.2 (frontend shell)
- Story 2A.1 (customers API)

### Technical Notes
- The unified search endpoint should use `pg_trgm` + `unaccent` for fuzzy matching across multiple tables.
- Consider using a UNION query with `ts_rank` for relevance scoring.
- The frontend component should use a CDK overlay or a custom portal for positioning.
- Keyboard shortcut registration should be in the AppShellComponent to ensure global capture.
- The `>` prefix mode should map to known actions (e.g., "baixar título" -> navigate to write-off modal for that title).
- Recent searches stored in localStorage key `command-palette-recent`.
- Results should be grouped by entity type with section headers.
- Mac detection via `navigator.platform` for showing Cmd vs Ctrl in the UI hint.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] No regressions
