---
epic: 13
story: 14
title: "Override Manual do Valor de Mercado do Veículo"
type: "Domínio Frota"
status: ready-for-dev
priority: low
depends_on: "13.1"
authored_by: "Amelia (dev) via bmad-create-story"
created_at: "2026-05-27"
---

# Story 13.14: Override Manual do Valor de Mercado do Veículo

## História de Usuário

**Como** gestor de frota,
**eu quero** poder sobrescrever manualmente o valor de mercado de um veículo quando o valor FIPE não reflete a realidade,
**para que** dashboards e cálculos de ROI usem o valor real (carro batido vale menos, carro raro vale mais).

## Contexto

Hoje dashboards usam `valor_fipe_atual` direto. Em casos atípicos (veículo batido, veículo raro, FIPE desatualizado), o número está errado. Esta story permite override manual com justificativa obrigatória + audit.

## Critérios de Aceite

1. Tabela `veiculos` recebe colunas:
   - `valor_mercado_manual NUMERIC(12,2) NULL`
   - `valor_mercado_manual_atualizado_em TIMESTAMPTZ NULL`
   - `valor_mercado_manual_motivo TEXT NULL`
   - `valor_mercado_manual_atualizado_por UUID NULL REFERENCES acesso.usuarios(id)`

2. Função `obter_valor_mercado(veiculo_id) -> Decimal` retorna `valor_mercado_manual` se preenchido, senão `valor_fipe_atual`.

3. Dashboards e cálculos de ROI usam `obter_valor_mercado()` — NUNCA acessam `valor_fipe_atual` diretamente.

4. Endpoint `PUT /api/v1/veiculos/{id}/valor-mercado-manual` com payload `{"valor": decimal, "motivo": string}` (role `admin` ou `gestor_frota`). `motivo` é obrigatório.

5. Endpoint `DELETE /api/v1/veiculos/{id}/valor-mercado-manual` remove o override (volta a usar FIPE).

6. Frontend: no detalhe do veículo, campo "Valor de mercado" com:
   - Valor exibido (manual se sobrescrito, FIPE caso contrário)
   - Badge `📝 Manual` ou `📊 FIPE` ao lado
   - Botão "Sobrescrever" abre modal com input de valor + textarea de motivo
   - Se manual: botão "Remover override" volta a usar FIPE

7. Audit log para toda mutação com `categoria='frota'`.

8. Testes: sem override → ROI usa FIPE; com override → ROI usa manual; remover override → ROI volta a FIPE.

## Contexto Técnico

### Refator obrigatório

Buscar `valor_fipe_atual` em todo o código (`grep -rn "valor_fipe_atual"` ou `fipe_value`) e substituir por chamada a `obter_valor_mercado()`. Dashboards (Story 8.3) usam — esta é a área principal a refatorar.

### Imutabilidade do FIPE

`valor_fipe_atual` **continua sendo atualizado** pela integração FIPE mensal — não muda. O override é uma camada por cima.

## Arquivos a Criar/Modificar

```
src/backend-api/
├── alembic/versions/0029_valor_mercado_manual.py
├── app/application/veiculos/
│   └── valor_mercado.py                                 # CRIAR — obter_valor_mercado()
├── app/api/v1/
│   └── veiculos_routes.py                               # MODIFICAR — endpoints
├── app/infrastructure/db/models/veiculos.py             # MODIFICAR — 4 colunas
├── app/api/v1/dashboard_routes.py                       # MODIFICAR — usar obter_valor_mercado
└── app/tests/test_valor_mercado_manual.py               # CRIAR

src/frontend/src/app/features/veiculos/
└── (componente de detalhe — criar se não existe)        # MODIFICAR
```

## Checklist do Dev

- [ ] 13.1 concluída (nomenclatura PT-BR).
- [ ] Migration aplicada.
- [ ] Função `obter_valor_mercado()` é a ÚNICA forma de obter valor (validar com grep).
- [ ] Endpoints PUT e DELETE com permissão correta + audit log.
- [ ] Frontend mostra badge + botão de override.
- [ ] Dashboards usam novo valor após override.

## Notas

- Complexidade **Baixa** — boa story pra colocar no meio do épico como respiro entre as complexas (13.8, 13.9).
- Justificativa obrigatória ajuda no compliance/auditoria.
