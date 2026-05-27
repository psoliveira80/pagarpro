---
epic: 13
story: 12
title: "Herói Financeiro no Detalhe do Contrato"
type: "UX + Frontend"
status: ready-for-dev
priority: medium
depends_on: "13.3, 13.8, 13.11, 13.13"
authored_by: "Amelia (dev) via bmad-create-story"
created_at: "2026-05-27"
---

# Story 13.12: Herói Financeiro no Detalhe do Contrato

## História de Usuário

**Como** gestor,
**eu quero** ver o estado financeiro do contrato de forma clara e imediata ao abrir o detalhe,
**para que** possa agir sem precisar escanear tabelas.

## Contexto

Hoje o detalhe do contrato mostra dados em tabela. Esta story cria um **componente herói** no topo da tela com badges, barra de progresso e CTA contextual — gestor entende em 2 segundos se contrato está em dia ou em atraso.

**Pré-requisitos:** 13.3 (opção de compra na barra), 13.8 (encargos pra mostrar), 13.11 (passivos pra alertar no wizard), 13.13 (desbloqueio em confiança no estado).

## Critérios de Aceite

1. Componente `ContractHeroComponent` no detalhe do contrato exibe, em estados distintos:

   **Estado EM DIA:**
   - Badge `✓ EM DIA` (verde)
   - Barra de progresso: parcelas pagas / total, com marcador `★` para a opção de compra
   - Totais: "R$X pagos · R$Y restam · Opção de compra: R$Z"
   - Última parcela paga e próximo vencimento (data + countdown em dias)

   **Estado EM ATRASO:**
   - Badge `⚠ EM ATRASO — N parcelas` (âmbar/vermelho)
   - Bloco de atraso acima da barra: lista de parcelas em atraso com valor + encargos + total
   - CTA principal: "Registrar pagamento das parcelas em atraso"
   - Barra de progresso com segmento `em atraso` em cor âmbar
   - Opção de compra com estado `⏸ Suspenso — quitar atraso primeiro`

2. Seção separada para a opção de compra com: valor, data de vencimento, status e texto explicativo ("Se paga, o veículo passa para o nome do cliente").

3. No wizard de novo contrato (Passo 1 — seleção de cliente): se cliente possui passivos inoperantes, exibe banner âmbar obrigatório antes de prosseguir: "Este cliente possui passivo de contratos anteriores — R$X. Deseja criar contrato normalmente ou registrar acordo de passivo?"

4. Botão "Cancelar contrato" no detalhe: abre modal `ConfirmService` com texto diferente conforme situação:
   - Sem atraso: "Carlos não possui parcelas em atraso. O encerramento é limpo — sem saldo devedor."
   - Com atraso: "Carlos possui N parcelas em atraso (R$X). Elas permanecerão como passivo inoperante."

5. Testes E2E: contrato em dia → badge verde, sem bloco de atraso; contrato com atraso → badge âmbar, bloco de atraso visível, CTA correto.

## Contexto Técnico

### Componente Angular

Criar em `src/frontend/src/app/features/contratos/contrato-detalhe/heroi-financeiro/` (per-component folder pattern).

### Endpoint backend

`GET /api/v1/contratos/{id}/resumo-financeiro` retornando:
```json
{
  "situacao_geral": "em_dia" | "em_atraso",
  "parcelas_pagas": 12,
  "parcelas_totais": 24,
  "valor_pago": 9600.00,
  "valor_restante": 9600.00,
  "opcao_compra": {"valor": 5000.00, "situacao": "pendente"},
  "atrasadas": [{"numero": 13, "valor": 800.00, "encargos": 60.00, "total": 860.00}],
  "proximo_vencimento": "2026-06-15"
}
```

## Arquivos a Criar/Modificar

```
src/frontend/src/app/features/contratos/contrato-detalhe/
├── contrato-detalhe.component.html                      # MODIFICAR — embarcar heroi
└── heroi-financeiro/                                    # CRIAR — per-component folder
    ├── heroi-financeiro.component.ts
    ├── heroi-financeiro.component.html
    └── heroi-financeiro.component.css

src/backend-api/app/api/v1/
└── contratos_routes.py                                  # MODIFICAR — endpoint resumo-financeiro
```

## Checklist do Dev

- [ ] 13.3, 13.8, 13.11, 13.13 concluídas.
- [ ] Endpoint resumo-financeiro retorna dados corretos.
- [ ] Componente herói renderiza ambos estados.
- [ ] CTA "Registrar pagamento" abre modal correto.
- [ ] Banner de passivo aparece no wizard quando aplicável.
- [ ] Modal de cancelamento ajusta texto por situação.
- [ ] Testes E2E passam (Cypress ou Playwright se houver).

## Notas

- Story foca em UX — backend já existe parcialmente (resumo financeiro pode reaproveitar agregações).
- Barra de progresso deve ser visualmente acessível (contraste AA, indicação não-cor para colordaltônicos).
