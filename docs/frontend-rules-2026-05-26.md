# Regras Frontend Acumuladas — Sessão 2026-05-26

> **Status:** Rascunho — Pablo vai compilar/refinar depois.
> **Contexto:** Regras passadas durante a Story 12.10 (refactor estrutural PT-BR do frontend Angular).

---

## 1. Estrutura de pastas (Angular `features/`)

### 1.1 Per-component folder
Cada componente fica em **sua própria pasta** com os 3 arquivos dentro (`.ts`, `.html`, `.css`).

**✅ Certo:**
```
features/clientes/
├── clientes-lista/
│   ├── clientes-lista.component.ts
│   ├── clientes-lista.component.html
│   └── clientes-lista.component.css
├── cliente-detalhe/
│   ├── cliente-detalhe.component.ts
│   ├── cliente-detalhe.component.html
│   └── cliente-detalhe.component.css
```

**❌ Errado (arquivos soltos):**
```
features/clientes/
├── clientes-lista.component.ts
├── clientes-lista.component.html
├── cliente-detalhe.component.ts
```

### 1.2 Não criar pasta repetida dentro de outra
Para features com **apenas 1 componente**, o arquivo fica direto na pasta da feature (sem subfolder homônima).

**✅ Certo:**
```
features/sistema/
├── sistema.component.ts
├── sistema.component.html
├── sistema.component.css
└── sistema.routes.ts
```

**❌ Errado (pasta repetida):**
```
features/sistema/
└── sistema/
    ├── sistema.component.ts
    └── ...
```

### 1.3 Routes divididas por feature
Features com **4+ componentes** devem ter o próprio `xxxx.routes.ts` na raiz da feature, incluído no shell via `loadChildren`.

**✅ Certo:**
```
features/
├── clientes/
│   ├── clientes.routes.ts         ← define rotas /clientes/*
│   ├── clientes-lista/
│   └── ...
├── contratos/
│   ├── contratos.routes.ts
│   └── ...
└── sistema/
    └── sistema.routes.ts          ← compõe via loadChildren
```

```typescript
// sistema.routes.ts
export const SYSTEM_ROUTES: Routes = [{
  path: '',
  component: SistemaComponent,
  children: [
    { path: 'clientes', loadChildren: () => import('../clientes/clientes.routes').then(m => m.CLIENTES_ROUTES) },
    { path: 'contratos', loadChildren: () => import('../contratos/contratos.routes').then(m => m.CONTRATOS_ROUTES) },
    // ...
  ],
}];
```

Features com 1-2 componentes (ex: `dashboard/`, `not-found/`) podem ficar inline no shell sem arquivo de routes próprio.

---

## 2. Nomenclatura PT-BR

### 2.1 Tudo em PT-BR — folders, classes, selectors, arquivos, variáveis
Quando renomear código para PT-BR, **estender para tudo**:
- Feature folders
- Classes de componente
- Selectors
- Nomes de arquivo
- Variáveis e métodos

### 2.2 Termos que ficam em inglês
- **Tecnológicos consagrados:** HTTP, REST, JWT, JSON, JSONB, OAuth, RSA, Argon2, CORS, etc.
- **Frameworks/libs:** `FormControl`, `HttpClient`, `FormsModule`, `RouterLink`, etc.
- **Conceitos de UI consagrados:** `wizard`, `modal`, `drawer`, `form`, `dashboard-tab`, `viewer`, `builder`, `placeholder`, `inbox`, `dashboard`.
- **Acrônimos universais:** URL, ID, UUID, PDF, CSV, OCR.
- **Nomes próprios:** FIPE, Pix, OFX, LGPD, WhatsApp, Asaas, etc.

### 2.3 Convenção de nome de componente
**Substantivo primeiro**, qualificador depois — segue o padrão de pasta + arquivo.

| ✅ Certo | ❌ Evitar |
|---|---|
| `clientes-lista` | `lista-clientes` |
| `cliente-detalhe` | `detalhe-cliente` |
| `veiculo-wizard` | `wizard-veiculo` |
| `contratos-lista` | `lista-contratos` |
| `simulacao-modal` | `modal-simulacao` |

### 2.4 Folders mantidos em inglês
Mesmo com renomeação geral, esses ficam:
- `auth/` — termo técnico
- `dashboard/` — consagrado em PT-BR também
- `inbox/` — consagrado UI
- `not-found/` — componente Angular padrão

---

## 3. Quando tiver dúvida
Sempre que tiver dúvida sobre uma nomenclatura, **perguntar ao Pablo**.

---

## 4. Tabela de exemplos de renames aplicados (Story 12.10)

| Antigo | Novo |
|---|---|
| `features/customers/` | `features/clientes/` |
| `features/vehicles/` | `features/veiculos/` |
| `features/contracts/` | `features/contratos/` |
| `features/finance/` | `features/financeiro/` |
| `features/reports/` | `features/relatorios/` |
| `features/settings/` | `features/configuracoes/` |
| `features/system/` | `features/sistema/` |
| `CustomersListComponent` | `ClientesListaComponent` |
| `<app-customers-list>` | `<app-clientes-lista>` |
| `customers-list.component.ts` | `clientes-lista/clientes-lista.component.ts` |
| `/system/customers` | `/sistema/clientes` |

---

## 5. Backend (referência cruzada)
- Domain terms já estavam em PT-BR (Cliente, Veiculo, Contrato, TituloPagar, TituloReceber, ContaBancaria, etc.).
- Documentação (PRD, ARCHITECTURE, stories) deve estar em PT-BR — ver glossário em `docs/glossario-ptbr.md`.
- Nada de inglês em comentário de código ou identificador de domínio — ver memória `feedback-naming-convention-pt`.

---

**Última atualização:** 2026-05-26
**Stories relacionadas:** 12.8 (rename interfaces/services/API paths) + 12.10 (refactor estrutural).
