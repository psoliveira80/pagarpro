---
epic: 13
story: 6
title: "Motor `gerar_titulos_mensais`"
type: "Worker + Domínio"
status: ready-for-dev
priority: high
depends_on: "13.5, 13.4, 13.3"
authored_by: "Amelia (dev) via bmad-create-story"
created_at: "2026-05-27"
---

# Story 13.6: Motor `gerar_titulos_mensais`

## História de Usuário

**Como** sistema financeiro,
**eu quero** gerar títulos mensais automaticamente com aplicação de índice de correção,
**para que** o ciclo de cobrança seja autônomo e o gestor não precise lembrar de criar parcelas mês a mês.

## Contexto

Existe parcialmente em `src/backend-api/app/workers/tasks/gerar_titulos_mensais.py` (Story 12.6 review). Esta story **finaliza e endurece** o motor com idempotência, multi-tenant, observabilidade e suporte completo a índices de correção.

**Pré-requisitos:**
- 13.5 (`infraestrutura-base-workers`) — fila `fila_cobranca` + tabelas de observabilidade.
- 13.4 (`sistema-configuracoes-tipadas`) — para ler `proxima_data_geracao` e parâmetros.
- 13.3 (`tipo-titulo-opcao-compra`) — geração diferencia parcela regular de opção de compra.

## Critérios de Aceite

1. Task Celery `gerar_titulos_mensais` com schedule `crontab(hour=3, minute=0, day_of_month=1)`.
2. Lógica: busca contratos com `situacao='ativo'` e `modo_geracao='mensal'` e `proxima_data_geracao <= hoje`. Para cada contrato: verifica idempotência por `(contrato_id, competencia)` → cria título com correção monetária aplicada → avança `proxima_data_geracao`.
3. Tabela `tabela_indices_economicos(indice, competencia, percentual, UNIQUE(indice, competencia))` para armazenamento de IGPM/IPCA/INPC.
4. Contratos com índice configurado mas valor ausente: título gerado com valor base + alerta em `alertas_sistema`.
5. Idempotente: execuções repetidas no mesmo mês não geram duplicatas.
6. Endpoint `POST /api/v1/motor/gerar-titulos` para disparo manual (role `admin`).
7. Coordinator + fan-out por empresa (padrão estabelecido em 13.5).
8. Registra em `execucoes_motor` com totais (registros processados, erros, tempo).
9. Testes: contrato 1 ativo gera N títulos no mês; contrato suspenso ignorado; execução repetida no mesmo mês não duplica; aplicação de índice IGPM correta.

## Contexto Técnico

### Estado atual

`gerar_titulos_mensais.py` já existe (Story 12.6) com:
- `_aplicar_correcao(base, taxa)` — função utilitária.
- Loop por contratos.
- Idempotência por `(contrato_id, competencia)`.

### O que esta story adiciona

- Coordinator + fan-out (não roda direto, distribui por empresa).
- Persistência em `execucoes_motor`.
- Endpoint manual para disparo (`admin`).
- Suporte a `personalizado_dias` (Story 13.16 estende isso).
- Geração da opção de compra (último mês do contrato + 1).

### Cálculo de correção

```python
# A partir da 2ª parcela:
if contrato.indice_correcao and numero_parcela > 1:
    indice_atual = repo_indices.obter(contrato.indice_correcao, competencia_atual)
    if indice_atual:
        valor_corrigido = base * (1 + indice_atual.percentual / 100)
    else:
        # Valor base + alerta
        alertas.publicar(...)
        valor_corrigido = base
```

## Arquivos a Criar/Modificar

```
src/backend-api/
├── alembic/versions/0025_tabela_indices_economicos.py
├── app/infrastructure/db/models/
│   ├── tabela_indice_economico.py                       # CRIAR
│   └── contrato.py                                      # MODIFICAR — proxima_data_geracao, modo_geracao
├── app/workers/tasks/
│   └── gerar_titulos_mensais.py                         # MODIFICAR — coordinator, exec_motor, opcao_compra
├── app/api/v1/motor_routes.py                           # MODIFICAR — endpoint manual
└── app/tests/test_monthly_generation.py                 # MODIFICAR — novos casos
```

## Checklist do Dev

- [ ] 13.5, 13.4, 13.3 concluídas.
- [ ] Migration de `tabela_indices_economicos` aplicada com seed de IGPM/IPCA/INPC vazios.
- [ ] Cron `crontab(hour=3, minute=0, day_of_month=1)` ativo em Beat.
- [ ] Disparo manual via endpoint `admin` funciona e respeita idempotência.
- [ ] `execucoes_motor` populada após cada execução.
- [ ] Testes cobrem: contrato ativo, suspenso, com índice, sem índice, execução duplicada.

## Notas

- A geração de **opção de compra** (Story 13.3) só acontece **na última parcela**. O motor verifica `numero_parcela == total_parcelas` e gera o título adicional.
- Story 13.16 estende este motor para suportar `personalizado_dias` (intervalos não-mensais).
