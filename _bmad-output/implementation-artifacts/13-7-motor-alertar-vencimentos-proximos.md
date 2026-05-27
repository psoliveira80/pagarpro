---
epic: 13
story: 7
title: "Motor `alertar_vencimentos_proximos`"
type: "Worker + Comunicação"
status: ready-for-dev
priority: medium
depends_on: "13.5, 13.4, 13.10"
authored_by: "Amelia (dev) via bmad-create-story"
created_at: "2026-05-27"
---

# Story 13.7: Motor `alertar_vencimentos_proximos`

## História de Usuário

**Como** cliente,
**eu quero** receber lembretes antes do vencimento,
**para que** eu pague em dia e evite encargos.

## Contexto

Lembrete proativo de vencimento — reduz inadimplência sem cobrança. Roda diariamente, busca títulos com vencimento próximo e envia mensagem via canal configurado (WhatsApp por default).

**Pré-requisitos:**
- 13.5 (infraestrutura) — fila `fila_notificacoes`, `lembretes_enviados`.
- 13.4 (configurações) — parâmetro `dias_antecedencia_lembrete`.
- 13.10 (renderizador de templates) — para formatar a mensagem.

## Critérios de Aceite

1. Task Celery `alertar_vencimentos_proximos` com schedule `crontab(hour=8, minute=0)`.
2. Busca títulos `tipo='parcela'`, `situacao='pendente'`, `data_vencimento` entre `hoje + 1` e `hoje + ServicoConfiguracao.obter_inteiro('dias_antecedencia_lembrete', 'financeiro', padrao=3)`. Ignora se já enviado hoje (`lembretes_enviados`).
3. Renderiza mensagem via `renderizador_template` com template `lembrete_vencimento`. Envia pelo `ServicoConfiguracao.obter_string('canal_cobranca_principal', 'comunicacao', padrao='whatsapp')`. Fallback para `canal_cobranca_fallback` se falhar.
4. Registra resultado em `lembretes_enviados` e métricas em `execucoes_motor`.
5. Coordinator + fan-out por empresa (padrão 13.5).
6. Testes: título com vencimento em 3 dias → lembrete enviado; título já lembrado hoje → não duplica; canal principal falha → fallback acionado.

## Contexto Técnico

### Idempotência

`UNIQUE(titulo_id, tipo, DATE(enviado_em))` na tabela `lembretes_enviados` previne duplicação no mesmo dia.

### Canal de envio

Carrega adapter dinamicamente via `IGatewayPagamento` registry (já existente). Default WhatsApp via `Z-API`/`Uazapi`/`Evolution`.

## Arquivos a Criar/Modificar

```
src/backend-api/app/workers/tasks/
└── alertar_vencimentos_proximos.py                      # CRIAR

src/backend-api/app/tests/
└── test_alertar_vencimentos.py                          # CRIAR
```

## Checklist do Dev

- [ ] 13.5, 13.4, 13.10 concluídas.
- [ ] Cron diário `08:00` ativo.
- [ ] Lembrete não duplica no mesmo dia.
- [ ] Fallback de canal funciona quando principal retorna erro.
- [ ] `execucoes_motor` populada.

## Notas

- Story **baixa complexidade** — boa pra entrar no meio do épico depois das críticas (13.4, 13.5).
- Mensagem amigável, não cobrança ("Olá Maria, lembrando que sua parcela vence em 3 dias...").
