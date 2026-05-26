---
epic: 10
story: 8
title: "Componente de Modal Reutilizável com ESC, Backdrop e Animação"
type: "Core"
status: ready-for-dev
---

# Story 10.8: Componente de Modal Reutilizável

## História de Usuário
Como Desenvolvedor,
quero um único componente de modal reutilizável que trate ESC, clique no backdrop, z-index e animação,
para que eu nunca precise repetir boilerplate de modal em cada componente.

## Critérios de Aceite

1. `ModalComponent` em `shared/components/modal/` (3 arquivos) com inputs: `[open]` (boolean), `[size]` ('sm' | 'md' | 'lg' | 'xl' | 'full'), `[title]` (string opcional).
2. Outputs: `(closed)` emitido ao apertar ESC, clicar no backdrop ou no botão X.
3. Built-in: `z-[1100]`, backdrop `bg-black/50`, animação de fade+scale, `tabindex="-1"` com auto-focus para captura de ESC.
4. Content projection via `<ng-content>` para o corpo e opcionalmente `<ng-content select="[modal-footer]">` para os botões do rodapé.
5. Responsivo: largura total no mobile, largura máxima por tamanho no desktop.
6. Substituir TODOS os 13 modais inline existentes por `<app-modal>`.
7. Remover TODOS os `@HostListener('document:keydown.escape')` por componente — o modal cuida disso.
8. Documentar o padrão em `~/.claude/CLAUDE.md`.

## Contexto Técnico

### Padrão de Uso
```html
<app-modal [open]="showModal()" (closed)="showModal.set(false)" size="md" title="Novo Aviso">
  <!-- body content -->
  <div modal-footer>
    <button (click)="showModal.set(false)">Cancelar</button>
    <button (click)="save()">Salvar</button>
  </div>
</app-modal>
```

### Arquivos a Criar/Modificar
```
frontend/
├── src/app/shared/components/modal/
│   ├── modal.component.ts
│   ├── modal.component.html
│   └── modal.component.css
├── 13 arquivos de componentes que atualmente têm modais inline — substituir por <app-modal>
```

## Checklist do Dev
- [ ] Todos os critérios de aceite atendidos
- [ ] Todos os 13 modais inline substituídos
- [ ] ESC funciona em todos os modais
- [ ] Build + lint passando
