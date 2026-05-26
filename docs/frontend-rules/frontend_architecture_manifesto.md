---
trigger: always_on
---

# 🏛️ Manifesto de Arquitetura Frontend — LicitaMax (Angular)

Este documento define os mandamentos arquiteturais estritos e o padrão de design para o desenvolvimento frontend. O objetivo é evitar retrabalho, manter o código escalável, limpo e visualmente consistente. Toda nova feature **deve** seguir essas regras.

---

## 1. 📂 Estrutura de Pastas (Domain-Driven e Rasa)

Abandonamos arquiteturas legadas e pastas super-aninhadas. O projeto segue o padrão *Standalone* organizado em 3 grandes pilares dentro de `src/app/`:

### `/core` (Infraestrutura e Singletons)
O cérebro do sistema. Aqui moram apenas itens de instância única global.
*   `/guards` e `/interceptors`.
*   **`/services`**: **REGRA DE OURO:** Todo serviço que faz chamadas à API, gerencia estado de negócio (Auth, Tema, Filtros Globais) MORA AQUI. **Nenhum serviço deve existir dentro da pasta `/features`.**

### `/shared` (Reusabilidade Pura)
Itens genéricos que não possuem regra de negócio específica.
*   `/models` (Interfaces TS compartilhadas).
*   `/pipes` e `/directives`.
*   `/components`: Botões customizados, modais genéricos, inputs estilizados.

### `/features` (Regras de Negócio e Telas)
Dividido por contexto (Ex: `/auth`, `/system`).
*   **Estrutura Rasa (Flat):** Evite redundâncias como `/system/radar/radar/radar.component`. A estrutura correta é `/system/radar/` contendo diretamente os 3 arquivos do componente.
*   A raiz da feature contém o *Layout Shell* da seção (ex: `system.component.ts` com o seu `<router-outlet>`).

---

## 2. 🧩 Anatomia do Componente

*   **Separação Estrita:** É terminantemente proibido o uso de templates ou estilos inline (`template: \`<p>oi</p>\``). Todo componente deve ter seus 3 arquivos dedicados:
    *   `nome.component.ts`
    *   `nome.component.html`
    *   `nome.component.css`

---

## 3. 🗺️ Roteamento (Routing Otimizado)

Para evitar arquivos `app.routes.ts` gigantes e confusos, adotamos a modularização por Feature Shell:
*   Cada grande feature agrupadora deve ter o seu próprio arquivo de rotas (Ex: `auth.routes.ts`).
*   O `app.routes.ts` principal apenas invoca o módulo via **Lazy Loading** usando `loadChildren`:
    ```typescript
    {
      path: 'auth',
      loadChildren: () => import('./features/auth/auth.routes').then(m => m.AUTH_ROUTES)
    }
    ```

---

## 4. 🎨 Design System e Estilização

Nossa stack visual é **Tailwind CSS v4 + Inspiração shadcn/ui + Heroicons**. A era do CSS customizado extenso acabou.

### Regra do Arquivo CSS Vazio
*   Os arquivos `.css` dos componentes devem permanecer **praticamente vazios**.
*   Toda a estilização **deve** ser feita através de classes utilitárias do Tailwind diretamente no `.html`.
*   *Exceção:* Apenas animações `@keyframes` ultracomplexas ou pseudo-elementos impossíveis de tratar via Tailwind devem habitar o `.css`.

### Estética shadcn/ui e Variáveis Globais
*   Buscamos designs "Premium": cores contidas, superfícies elevadas (Glassmorphism sutil), bordas suaves (`rounded-xl` / `rounded-2xl`).
*   Nunca utilize cores fixas diretamente (ex: `bg-gray-900`). **Sempre utilize as variáveis CSS mapeadas globalmente no `styles.css`** através do Tailwind JIT:
    *   `bg-[var(--surface-elevated)]`
    *   `text-[var(--text-primary)]`
    *   `border-[var(--border)]`
    *   `text-[var(--accent)]`
*   Estados de formulários, anéis de foco (`focus:ring`), estados `hover` interativos e `disabled` suaves são obrigatórios.

### Iconografia
*   Uso padronizado e exclusivo dos **Heroicons** (via `@ng-icons/core`). Nenhum outro pacote de ícones ou SVG solto deve ser utilizado para interfaces padrão.

---

> *"Codifique sempre sabendo que a próxima pessoa a manter seu código pode ser você daqui a 6 meses. Mantenha os serviços no lugar certo e o CSS no HTML."*
