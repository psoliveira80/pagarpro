---
epic: 13
story: 16
title: "Wizard de Contrato — Plano de Parcelas Detalhado (Intervalo, Multa, Juros, Correção, Parcela Final)"
type: "UX + Core Refactor + Worker"
status: ready-for-dev
priority: high
depends_on: "13.3, 13.4"
authored_by: "John (PM) — refinamento pós smoke-test com Pablo (PO)"
created_at: "2026-05-27"
---

# Story 13.16: Wizard de Contrato — Plano de Parcelas Detalhado

## História de Usuário

**Como** Gestor de frota cadastrando um contrato de aluguel com opção de compra,
**eu quero** definir o plano de parcelamento campo a campo — valor da parcela, intervalo (semanal/mensal/customizado), multa, juros, parcela final, e correção monetária —
**para que** o Motor de Cobrança Autônomo (Epic 13) gere e cobre os títulos com previsibilidade total, sem ambiguidade entre o que combinei com o cliente e o que o sistema executa.

## Contexto

Após smoke-test do wizard atual (Story 3-3, `done`), o PO identificou que a tela 2 do wizard não cobre o domínio real do negócio. O documento [`docs/wizard-contrato-detalhamento-ux.md`](../../docs/wizard-contrato-detalhamento-ux.md) tem a especificação completa.

**Esta story:**
- Reformula a **Tela 2** (Plano de Parcelas) do wizard `contrato-wizard.component`.
- Estende **espelho de parcelas** (Tela 3) e **revisão** (Tela 4) para refletir os novos campos.
- Adiciona campos faltantes ao **schema do contrato** (backend) e **migration**.
- Estende o **worker `gerar_titulos_mensais.py`** para suportar novos tipos de intervalo e geração de parcela final tipo `opcao_compra`.

**Pré-requisitos:**
- Story 13.3 (`tipo-titulo-opcao-compra`) precisa estar `done` — define enum `tipo_titulo` que esta story usa para gerar a parcela final.
- Story 13.4 (`sistema-configuracoes-tipadas`) precisa estar `done` ou em andamento — define como configurações tipadas (incluindo lista de índices de correção ativos) são lidas.

## Critérios de Aceite

### Frontend — Tela 2 reformulada

1. Campo **"Data de vencimento da primeira parcela"** (`<input type="date">`, obrigatório, futuro ou hoje).
2. Campo **"Valor da parcela"** (`<app-input-moeda>`, obrigatório, > 0).
3. Campo **"Quantidade de parcelas"** (`<input type="number">` com setas, inteiro ≥ 1, obrigatório).
4. Campo **"Intervalo entre parcelas"** (`<app-select>`, obrigatório) com 3 opções iniciais:
   - `semanal` → abre sub-campo "Dia da semana" (Seg..Dom).
   - `personalizado_dias` → abre sub-campo "Número de dias" (inteiro ≥ 1).
   - `mensal` → abre sub-campo "Dia do mês" (1..31).
   - Arquitetura preparada para adicionar `quinzenal`, `diaria`, `datas_customizadas` sem refator.
5. Campo **"Multa por atraso (%)"** (`<app-input-decimal>` com sufixo "%", 2 casas decimais, opcional, ≥ 0).
6. Campo **"Juros por atraso (% a.m.)"** (mesmo componente, opcional, ≥ 0).
7. Campo **"Valor da parcela final (opção de compra)"** (`<app-input-moeda>`, opcional, ≥ 0).
8. Toggle **"Aplicar índice de correção?"** (sim/não, default não):
   - Quando ligado, exibe `<app-select>` com índices de correção ativos (lê de `config.credenciais_integracao` categoria `correction_index`, `ativo=true`).
   - Quando nenhum índice ativo, toggle aparece desabilitado com mensagem orientativa.
9. Validação: botão "Próximo" só habilita quando todos os campos obrigatórios da tela 2 estão preenchidos e válidos.

### Frontend — Tela 3 (Espelho de Parcelas)

10. Chama `POST /api/v1/contracts/preview-schedule` com payload completo (todos os novos campos).
11. Renderiza tabela com colunas: Nº, Data de vencimento, Valor previsto (com correção aplicada se toggle ligado), Tipo (`Parcela` ou `Opção de Compra`).
12. Rodapé com sumário: total sem correção, total com correção (se aplicável), total final.

### Frontend — Tela 4 (Revisão)

13. Card "Cliente e Veículo" — nome + CPF/CNPJ + placa/marca/modelo.
14. Card "Vigência" — data de início (1ª parcela), data de término (última parcela ou opção de compra), período total ("X meses" ou "Y dias").
15. Card "Plano de Cobrança" formato `80 × R$ 800,00 = R$ 64.000,00`. Se houver parcela final: linha extra `+ 1 × R$ 20.000,00 (opção de compra)`. Total geral com correção aplicada se aplicável.
16. Intervalo expresso em PT-BR: "Mensal, dia 15" / "Semanal, quarta-feira" / "A cada 15 dias".
17. Linha de multa/juros se preenchidos: "Multa 2,00% · Juros 1,00% a.m.".
18. Linha de correção: "Aplicado: IGPM" ou "Sem correção".
19. Botão duplo: "Salvar como rascunho" (default) ou "Salvar e ativar".

### Backend — Schema + Migration

20. Migration Alembic nova adiciona em `contrato.contratos`:
    - `valor_parcela: NUMERIC(12,2) NULL`
    - `valor_parcela_final: NUMERIC(12,2) NULL`
    - `tipo_intervalo: TEXT NULL` (renomeação de `periodicidade` mantendo dados; usar `ALTER COLUMN ... RENAME`).
    - `dia_semana: SMALLINT NULL` (0..6, check constraint).
    - `dia_mes: SMALLINT NULL` (1..31, check constraint).
    - `intervalo_dias: INTEGER NULL` (≥ 1, check constraint).
    - `multa_atraso_pct: NUMERIC(5,2) NULL` (default 0).
    - `juros_atraso_pct: NUMERIC(5,2) NULL` (default 0).
21. `ContratoCreate` (Pydantic) aceita todos os novos campos. Validação cross-field: se `tipo_intervalo='semanal'`, `dia_semana` obrigatório; se `'mensal'`, `dia_mes`; se `'personalizado_dias'`, `intervalo_dias`.
22. `PreviewPlanilhaRequest` (Pydantic) aceita os mesmos novos campos (mais `indice_correcao: str | None`).
23. `ContratoCreate.indice_correcao: str | None` — campo já existe no modelo, expor no schema.

### Backend — Worker e Lógica

24. Worker `gerar_titulos_mensais.py` (renomear para `gerar_titulos.py` se quiser refletir generalização — opcional) suporta:
    - `tipo_intervalo='semanal'` + `dia_semana` → próxima data = primeiro `dia_semana` ≥ data anterior + 1.
    - `tipo_intervalo='mensal'` + `dia_mes` → mesma lógica de hoje, com fallback para último dia útil quando `dia_mes` > dias do mês.
    - `tipo_intervalo='personalizado_dias'` + `intervalo_dias` → próxima data = data anterior + `intervalo_dias`.
25. Quando `contrato.valor_parcela_final > 0` na finalização: gera **N+1 títulos** — N do `tipo='parcela'` + 1 do `tipo='opcao_compra'` na data seguinte à última parcela (intervalo igual).
26. Cálculo de valor atualizado de título em atraso usa `contrato.multa_atraso_pct` e `contrato.juros_atraso_pct` (substitui constantes globais se existirem).

### Componente novo

27. Criar `<app-input-decimal>` em `shared/components/input-decimal/` com:
    - Comportamento idêntico ao `<app-input-moeda>` (máscara live, sem spinner, só dígitos).
    - `@Input prefix?: string` e `@Input suffix?: string` (opcionais).
    - Refatorar `<app-input-moeda>` para ser caso particular: `<app-input-decimal prefix="R$">`.

### Validação geral

28. `ng build --configuration=production` passa sem erros.
29. `pytest -x` passa (incluindo testes novos para os tipos de intervalo).
30. Smoke test manual: criar contrato com parcela final + correção IGPM → ver espelho de parcelas correto + 21 títulos gerados (20 parcelas + 1 opção de compra).

## Contexto Técnico

### Documento de referência
- `docs/wizard-contrato-detalhamento-ux.md` — especificação UX completa com mockups em texto, regras condicionais, gaps mapeados.

### Arquivos a Criar/Modificar

```
src/frontend/src/app/
├── features/contratos/contrato-wizard/
│   ├── contrato-wizard.component.ts        # MODIFICAR — signals novos, payload novo
│   ├── contrato-wizard.component.html      # MODIFICAR — tela 2 reformulada, tela 3 e 4 ajustadas
│   └── contrato-wizard.component.css       # MODIFICAR — estilos para campos condicionais
├── shared/components/input-decimal/         # CRIAR — componente novo
│   ├── input-decimal.component.ts
│   ├── input-decimal.component.html
│   └── input-decimal.component.css
└── shared/components/input-moeda/
    └── input-moeda.component.ts            # MODIFICAR — refatorar para usar input-decimal

src/backend-api/
├── alembic/versions/0021_contrato_plano_parcelas.py  # CRIAR
├── app/infrastructure/db/models/contrato.py          # MODIFICAR — novos colunas
├── app/api/v1/schemas/contracts.py                   # MODIFICAR — ContratoCreate + PreviewPlanilhaRequest
├── app/workers/tasks/gerar_titulos_mensais.py        # MODIFICAR — suporte aos novos tipos
└── app/tests/test_monthly_generation.py              # MODIFICAR — adicionar casos por tipo_intervalo
```

### Decisões arquiteturais

- **`valor_total` permanece no contrato** — frontend calcula como `valor_parcela × quantidade_parcelas + valor_parcela_final`. Backend pode validar consistência.
- **`tipo_intervalo`** substitui `periodicidade` semanticamente. Migration usa `RENAME COLUMN` (mantém dados existentes). Workers já suportam `mensal`/`semanal`/`quinzenal` — adicionar `personalizado_dias`.
- **Índice de correção** lê de `config.credenciais_integracao` categoria `correction_index` (já implementado: BCBCorrectionAdapter com IGPM/IPCA/INPC).
- **Cálculo de correção** aplicado a partir da 2ª parcela (mantém regra atual de `_aplicar_correcao` em `gerar_titulos_mensais.py`).
- **Tipo de título** usa enum `tipo_titulo` da Story 13.3 (valores: `parcela`, `opcao_compra`, `multa`, `taxa`, `ajuste`).

### Subdivisão recomendada (tasks)

| Sub-task | Escopo | Estimativa relativa |
|---|---|---|
| 13.16-a | Migration + schemas Pydantic + modelo SQLAlchemy | M |
| 13.16-b | Endpoint `preview-schedule` estendido + lógica de cálculo de correção | M |
| 13.16-c | Wizard Tela 2: novos campos + condicionais | L |
| 13.16-d | Wizard Telas 3 e 4: espelho com correção + revisão formatada | M |
| 13.16-e | Worker `gerar_titulos_mensais`: suporte a `personalizado_dias` + geração de `opcao_compra` | M |
| 13.16-f | Componente `<app-input-decimal>` + refator de `<app-input-moeda>` | S |
| 13.16-g | Testes (backend pytest + frontend smoke manual) | M |

## Checklist do Dev

- [ ] 13.3 (`tipo-titulo-opcao-compra`) está `done`.
- [ ] 13.4 (`sistema-configuracoes-tipadas`) está `done` ou avançada.
- [ ] Migration roda em DB de teste sem perda de dados (`periodicidade` → `tipo_intervalo`).
- [ ] Schema Pydantic valida cross-field corretamente (rejeita `tipo_intervalo='semanal'` sem `dia_semana`).
- [ ] Worker gera títulos com data correta para cada tipo de intervalo (testes unitários cobrindo bordas — fevereiro, ano bissexto).
- [ ] Wizard renderiza condicionais sem flicker (signals + computed).
- [ ] Preview de parcelas corrigidas bate com cálculo manual (validar com IGPM real do mês).
- [ ] Tela de revisão usa máscara R$ correta em todos os totais.
- [ ] Geração de título `opcao_compra` herda dia/intervalo da última parcela.
- [ ] `ng build --configuration=production` verde.
- [ ] `pytest -x` verde.
- [ ] Smoke test manual com Pablo — contrato real de teste com correção ligada.

## Notas

- **Reconciliação com Stories existentes:**
  - Story 13.2 (máquina de estados do contrato) tem que estar consistente — esta story não altera estados, apenas estende campos do contrato.
  - Story 13.6 (motor gerar títulos mensais) provavelmente vai reciclar `gerar_titulos_mensais.py` — coordenar sequenciamento.
- **Story 3.4 e 3.6 (done):** não alterar histórico. Esta story é evolução pós-feedback de usuário real.
- **Story 12.10 (refactor estrutural frontend, done):** já consolidou a estrutura de pastas e nomes PT-BR. Esta story usa essa estrutura.
