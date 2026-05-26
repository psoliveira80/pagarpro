---
epic: 10
story: 8
title: "Reusable Modal Component with ESC, Backdrop, Animation"
type: "Core"
status: ready-for-dev
---

# Story 10.8: Reusable Modal Component

## User Story
As a Developer,
I want a single reusable modal component that handles ESC, backdrop click, z-index, and animation,
So that I never repeat modal boilerplate in every component.

## Acceptance Criteria

1. `ModalComponent` in `shared/components/modal/` (3 files) with inputs: `[open]` (boolean), `[size]` ('sm' | 'md' | 'lg' | 'xl' | 'full'), `[title]` (string optional).
2. Outputs: `(closed)` emitted on ESC key, backdrop click, or X button.
3. Built-in: `z-[1100]`, backdrop `bg-black/50`, fade+scale animation, `tabindex="-1"` auto-focus for ESC capture.
4. Content projection via `<ng-content>` for body and optional `<ng-content select="[modal-footer]">` for footer buttons.
5. Responsive: full-width on mobile, max-width by size on desktop.
6. Replace ALL 13 existing inline modals with `<app-modal>`.
7. Remove ALL per-component `@HostListener('document:keydown.escape')` — the modal handles it.
8. Document pattern in `~/.claude/CLAUDE.md`.

## Technical Context

### Usage Pattern
```html
<app-modal [open]="showModal()" (closed)="showModal.set(false)" size="md" title="Novo Aviso">
  <!-- body content -->
  <div modal-footer>
    <button (click)="showModal.set(false)">Cancelar</button>
    <button (click)="save()">Salvar</button>
  </div>
</app-modal>
```

### Files to Create/Modify
```
frontend/
├── src/app/shared/components/modal/
│   ├── modal.component.ts
│   ├── modal.component.html
│   └── modal.component.css
├── 13 component files that currently have inline modals — replace with <app-modal>
```

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] All 13 inline modals replaced
- [ ] ESC works on all modals
- [ ] Build + lint passing
