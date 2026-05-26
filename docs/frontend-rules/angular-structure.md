---
trigger: always_on
---

# 📁 ANGULAR_STRUCTURE.md

Este documento define a arquitetura de diretórios para o projeto **BMNS**, utilizando **Angular 21**, o padrão **Standalone** e organização baseada em **Feature Shells**.

---

## 🌳 Raiz do Projeto
- `angular.json`, `package.json`, `tsconfig.json`: Configurações globais de build e ambiente.
- `public/` 🟢 **(Novo Padrão)**: Substitui a antiga `src/assets`.
  - Contém arquivos servidos diretamente: `favicon.ico`, `robots.txt`, `/images` (logos/backgrounds), `/fonts` e `/icons`.
- `src/`
  - `main.ts`: Ponto de entrada (Bootstrap do App).
  - `index.html`: Template principal.
  - `styles.css`: Importações do **TailwindCSS** e variáveis globais.
  - `environments/`: Configurações de variáveis (dev/prod).
  - `app/`: Onde reside toda a lógica do sistema.

---

## 📦 Estrutura Detalhada de `src/app/`

### 1. Inicialização (Root App)
- `app.component.ts|html|css`: Componente mestre (contém o `router-outlet` primário).
- `app.config.ts`: Configurações de providers globais (HttpClient, Sockets, Animations).
- `app.routes.ts`: Roteamento principal com **Lazy Loading** para as Features.

### 2. `/core` (Singletons e Infraestrutura)
*Itens que possuem **instância única** e configuram o estado global ou infraestrutura do sistema.*
- `/guards`: Proteção de rotas (Ex: `auth.guard.ts`).
- `/interceptors`: Manipulação de requisições HTTP (Ex: `jwt.interceptor.ts`).
- `/tokens`: Injection Tokens globais.
- **`/services`**:
  - `auth.service.ts`: Gestão de sessão e tokens.
  - **`theme.service.ts`**: Controle global de Dark/Light mode e persistência.
  - `notification.service.ts`: Orquestração de alertas e AudioContext (P0).

### 3. `/shared` (Reutilização e UI)
*Componentes e utilitários que aparecem em múltiplas partes do sistema, focados em interface pura.*
- `/components`: Botões, inputs, modais genéricos e layouts de cards reutilizáveis (uma pasta para cada componente (ex: /components/button-component/**)).
- `/pipes`: Formatadores de dados (Ex: `currency-br.pipe.ts`).
- `/directives`: Comportamentos visuais (Ex: `pulse-alert.directive.ts`).
- `/models`: Interfaces e tipos compartilhados entre várias features.
- **`/services`**:
  - **`ui-helper.service.ts`**: Serviços utilitários de interface (Ex: manipulação de scroll, helpers de viewport ou cálculos de layout) que não gerenciam estado de negócio.

### 4. `/features` (Módulos de Negócio/Domínio)
*Organização por fluxo de usuário e domínios funcionais isolados.*

- **auth/** (Feature Shell de Autenticação)
  - `/login`, `/register`, `/forgot-password`
- **landing-page/** (Feature Shell Pública)
  - `landing-page.component.ts|html|css`: Layout da landing com seu próprio `router-outlet`.
  - `/components`: Partes exclusivas (Hero, Footer, Pricing).
- **system/** (Feature Shell do Dashboard/War Room)
  - `system.component.ts|html|css`: Layout mestre (Sidebar + Header + Área de Conteúdo).
  - **`/radar`**: Monitoramento em tempo real de mensagens.
  - **`/busca`**: Sistema de filtros e prospecção.
  - **`/config`**: Gestão de sedes, perfil e tokens de portais.

---

## 🛠️ Diretrizes para Localização de Services

Para manter o projeto organizado e evitar o "caos dos serviços", siga estas três regras de ouro:

1.  **Serviços de Estado Global (Core):** Se o serviço gerencia um dado ou comportamento que afeta o sistema inteiro (Autenticação, Tema, Notificações de Alarme), ele deve residir em `app/core/services/`.
2.  **Serviços de Utilidade de UI (Shared):** Se o serviço é um helper para componentes visuais (ajuste de scroll, validação de campos genéricos), ele deve residir em `app/app/shared/services/`.

---

> **Nota de Encapsulamento:** Esta estrutura favorece o **Lazy Loading**. Ao isolar serviços específicos dentro de suas funcionalidades, garantimos que o Angular carregue apenas o código necessário para a tela que o usuário está visualizando, otimizando a performance do sistema de monitoramento.

