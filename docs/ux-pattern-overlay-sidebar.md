# UX Pattern: Overlay Sidebar (Sidebar2)

## Padrão

Quando o sistema precisa de uma **seção de configuração ou perfil** com sub-menus, usa-se uma **sidebar secundária (sidebar2)** que desliza sobre a sidebar principal.

## Comportamento

### Abertura
1. Usuário clica no **ícone de gatilho** no header (engrenagem ⚙️ para config, avatar para perfil)
2. A sidebar2 desliza da **esquerda para a direita** com animação CSS (`translateX(-100%) → 0`)
3. Ao abrir, **navega automaticamente para o primeiro item** do menu
4. Se outra sidebar2 estiver aberta, **fecha a anterior** antes de abrir a nova

### Fechamento
1. Usuário clica no **X** no canto superior direito da sidebar2
2. **OU** clica novamente no ícone de gatilho (toggle)
3. Ao fechar, **navega de volta ao dashboard** (`/system/dashboard`)

### Acesso direto via URL
1. Se o usuário acessa diretamente uma rota de configuração no browser (ex: `/system/settings/integrations`)
2. A sidebar2 **abre automaticamente** com o menu correto marcado (highlight no item ativo)
3. Verificação feita no `constructor` do componente shell E no `effect` de `NavigationEnd`

## Especificações CSS

```css
.settings-sidebar-enter {
  animation: slide-in-left 200ms ease-out;
}

@keyframes slide-in-left {
  from { transform: translateX(-100%); }
  to { transform: translateX(0); }
}
```

## Especificações de Layout

| Propriedade | Valor |
|-------------|-------|
| Largura mobile | `w-56` (224px) |
| Largura desktop | `w-64` (256px) |
| z-index | `1200` (acima do header z-1000 e modais z-1100) |
| Posição | `fixed inset-y-0 left-0` |
| Background | `var(--surface-elevated)` |
| Borda | `border-r border-[var(--border)]` |
| Sombra | `shadow-xl` |

## Estrutura do Menu

```html
<aside class="fixed inset-y-0 left-0 z-[1200] w-56 md:w-64 ...">
  <!-- Header com título + X -->
  <div class="flex h-16 items-center justify-between ...">
    <span>Título</span>
    <button (click)="close()"><ui-icon name="heroXMark" /></button>
  </div>

  <!-- Menu agrupado por seção -->
  <nav>
    @for (group of menuItems) {
      <div class="section-label">{{ group.section }}</div>
      @for (item of group.items) {
        <a [routerLink]="item.route" [highlight se ativo]>{{ item.label }}</a>
      }
    }
  </nav>
</aside>
```

## Regras de Exclusividade

- **Apenas uma sidebar2 pode estar aberta por vez** (config OU perfil, nunca ambas)
- Abrir uma fecha a outra: `this.otherSidebar.set(false)`
- O dropdown do perfil (user menu) fecha quando a sidebar de perfil abre

## Aplicações no Sistema

| Sidebar2 | Gatilho | Primeiro item | Seções |
|----------|---------|---------------|--------|
| Configurações | ⚙️ Engrenagem (admin only) | `/settings/users` | Acesso, Parâmetros, Inteligência, Sistema |
| Minha Conta | Avatar do usuário → "Perfil" | `/profile` | Conta (Perfil, Preferências, Segurança) |

## Quando usar este padrão

- Funcionalidades que são **transversais** ao sistema (não são um módulo com rota própria)
- Páginas de **configuração, perfil, preferências**
- Menus com **sub-itens que precisam de navegação lateral**

## Quando NÃO usar

- Para CRUD de entidades (use rotas normais com listagem + wizard)
- Para modais simples (use overlay centralizado)
- Para ações rápidas (use dropdown)
