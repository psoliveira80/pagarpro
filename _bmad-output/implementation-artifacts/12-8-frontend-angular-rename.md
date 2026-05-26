---
epic: 12
story: 8
title: "Frontend Angular — Rename Interfaces, Services & API Paths"
type: "Core Refactor"
status: ready-for-dev
priority: high
depends_on: "12.3"
---

# Story 12.8: Frontend Angular — Rename Interfaces, Services & API Paths

## User Story
As a Developer,
I want all Angular TypeScript interfaces, services, and API path strings updated to match the new Portuguese naming convention and new route paths,
So that the frontend is consistent with the backend after Epic 12 restructuring.

## Context
Story 12.3 renamed all backend routes and response fields. This story updates the Angular frontend to match. **Depends on 12.3. Can run in parallel with 12.4–12.7.**

## Acceptance Criteria

1. All TypeScript interfaces renamed to Portuguese matching new Pydantic schemas.
2. All interface field names updated to Portuguese matching new column names.
3. All `apiUrl` strings in services updated to new route paths.
4. All component property names and template bindings updated.
5. `ng build --configuration=production` passes with zero errors.
6. `npm run lint` passes with zero errors.
7. App runs locally and all screens load without console errors.
8. No hardcoded English entity names remaining in `features/` or `core/services/`.

## Interface Rename Mapping

### core/services/payable.service.ts → core/services/titulos-pagar.service.ts

| Interface antes | Interface depois |
|---|---|
| `Payable` | `TituloPagar` |
| `PayableListResponse` | `TituloPagarListResponse` |
| `PayableCreatePayload` | `TituloPagarCreatePayload` |
| `RecurringPayable` | `DespesaRecorrente` |
| `RecurringPayableCreatePayload` | `DespesaRecorrenteCreatePayload` |
| `QuickPayPayload` | `PagamentoRapidoPayload` |
| `ExpenseCategory` | `CategoriaDespesa` |
| `Supplier` | `Fornecedor` |

### core/services/receivable.service.ts → core/services/titulos-receber.service.ts

| Interface antes | Interface depois |
|---|---|
| `Installment` | `TituloReceber` |
| `InstallmentListResponse` | `TituloReceberListResponse` |
| `WriteOffPayload` | `BaixaTituloPayload` |
| `PartialWriteOffPayload` | `BaixaParcialPayload` |
| `UpdatedValueResponse` | `ValorAtualizadoResponse` |
| `RenegotiationPayload` | `RenegociacaoPayload` |

### core/services/bank.service.ts → core/services/conta-bancaria.service.ts

| Interface antes | Interface depois |
|---|---|
| `BankAccount` | `ContaBancaria` |
| `BankTransaction` | `TransacaoBancaria` |
| `ReconciliationSession` | `SessaoConciliacao` |

### core/services/contract.service.ts → core/services/contratos.service.ts

| Interface antes | Interface depois |
|---|---|
| `Contract` | `Contrato` |
| `InstallmentPreview` | `PreviewTitulo` |
| `ContractEvent` | `EventoContrato` |
| `Generation` | `LoteGeracao` |

## Field Rename in Interfaces

### TituloReceber (era Installment)
```typescript
// Antes
interface Installment {
  id: string;
  contract_id: string;
  due_date: string;
  amount: number;
  paid_amount: number | null;
  payment_method: string | null;
  receipt_url: string | null;
  notes: string | null;
  parent_installment_id: string | null;
}

// Depois
interface TituloReceber {
  id: string;
  empresa_id: string;
  contrato_id: string;
  data_vencimento: string;
  valor: number;
  valor_pago: number | null;
  forma_pagamento: string | null;
  comprovante_url: string | null;
  observacoes: string | null;
  titulo_origem_id: string | null;
}
```

### TituloPagar (era Payable)
```typescript
// Antes
interface Payable {
  due_date: string;
  amount: number;
  supplier_id: string | null;
  linked_installment_id: string | null;
}

// Depois
interface TituloPagar {
  data_vencimento: string;
  valor: number;
  fornecedor_id: string | null;
  titulo_receber_origem_id: string | null;
}
```

## API Path Mapping

| Path antes | Path depois |
|---|---|
| `/api/v1/receivables` | `/api/v1/titulos-receber` |
| `/api/v1/receivables/{id}/write-off` | `/api/v1/titulos-receber/{id}/baixar` |
| `/api/v1/receivables/{id}/partial-write-off` | `/api/v1/titulos-receber/{id}/baixar-parcial` |
| `/api/v1/receivables/{id}/pix-qr` | `/api/v1/titulos-receber/{id}/pix-qr` |
| `/api/v1/receivables/renegotiate` | `/api/v1/titulos-receber/renegociar` |
| `/api/v1/payables` | `/api/v1/titulos-pagar` |
| `/api/v1/payables/quick-pay` | `/api/v1/titulos-pagar/pagamento-rapido` |
| `/api/v1/recurring-payables` | `/api/v1/despesas-recorrentes` |
| `/api/v1/suppliers` | `/api/v1/fornecedores` |
| `/api/v1/expense-categories` | `/api/v1/categorias-despesa` |
| `/api/v1/bank-accounts` | `/api/v1/contas-bancarias` |
| `/api/v1/reconciliation/bank-transactions` | `/api/v1/conciliacao/transacoes-bancarias` |
| `/api/v1/reconciliation/match` | `/api/v1/conciliacao/conciliar` |

## Component Property Rename (key examples)

```typescript
// Antes (payables-list.component.ts)
payables: Signal<Payable[]> = signal([]);
selectedPayable: Signal<Payable | null> = signal(null);

// Depois (titulos-pagar-list.component.ts)
titulos: Signal<TituloPagar[]> = signal([]);
tituloSelecionado: Signal<TituloPagar | null> = signal(null);
```

```html
<!-- Antes -->
<td>{{ payable.due_date | date }}</td>
<td>{{ payable.amount | currency:'BRL' }}</td>

<!-- Depois -->
<td>{{ titulo.data_vencimento | date }}</td>
<td>{{ titulo.valor | currency:'BRL' }}</td>
```

## Technical Context

### Files to Create/Modify
```
frontend/src/app/
├── core/services/
│   ├── titulos-receber.service.ts    # CRIAR (era receivable.service.ts)
│   ├── titulos-pagar.service.ts      # CRIAR (era payable.service.ts)
│   ├── contratos.service.ts          # CRIAR (era contract.service.ts)
│   └── conta-bancaria.service.ts     # CRIAR (era bank.service.ts)
└── features/
    ├── finance/
    │   ├── titulos-receber/           # RENOMEAR pasta + arquivos
    │   ├── titulos-pagar/             # RENOMEAR pasta + arquivos
    │   └── conciliacao/               # RENOMEAR pasta + arquivos
    └── contracts/
        └── (renomear bindings de template)
```

### Convenção de nomes em Angular
- Arquivos: `titulos-receber-list.component.ts` (kebab-case)
- Classes: `TitulosReceberListComponent` (PascalCase)
- Signals: `titulos`, `tituloSelecionado`, `carregando` (camelCase PT-BR)
- Templates: propriedades em português (`data_vencimento`, `valor`)

## Dev Checklist
- [ ] 12.3 concluída antes de começar
- [ ] Todos os serviços com novos nomes de interface e paths de API
- [ ] Todos os componentes com properties em português
- [ ] Todos os templates HTML com bindings atualizados
- [ ] `ng build --configuration=production` passa
- [ ] `npm run lint` passa
- [ ] App abre no browser sem erros no console
- [ ] Telas de títulos a receber, pagar, contratos e reconciliação funcionando
- [ ] Nenhuma referência a `Installment`, `Payable`, `Supplier`, `BankAccount` (inglês) restante
