---
epic: 13
story: 5
title: "Infraestrutura Base dos Workers (Filas, Idempotência, Observabilidade)"
type: "Infraestrutura"
status: ready-for-dev
priority: critical
depends_on: "13.4"
authored_by: "Amelia (dev) via bmad-create-story"
created_at: "2026-05-27"
---

# Story 13.5: Infraestrutura Base dos Workers

## História de Usuário

**Como** engenheiro de plataforma,
**eu quero** a infraestrutura base do worker Celery com filas separadas, observabilidade e idempotência,
**para que** todos os motores do épico tenham fundação confiável e diagnosticável.

## Contexto

Hoje há **uma fila única** Celery com várias tasks competindo. Para o Epic 13, motores precisam ser **isolados** (uma falha em cobrança não bloqueia notificações), **idempotentes** (workers reiniciam sem duplicar ação) e **observáveis** (gestor vê o que rodou e o que falhou).

Esta story estabelece **7 filas isoladas**, **3 camadas de idempotência**, tabelas de observabilidade (`execucoes_motor`, `lembretes_enviados`) e padrão **fan-out coordinator** com lotes de 50.

## Critérios de Aceite

1. `workers/celeryconfig.py` consolidado com **7 filas** isoladas:

| Fila | Concurrency | Propósito |
|---|---|---|
| `fila_cobranca` | 4 workers × 4 threads | Geração, encargos, cobrança |
| `fila_notificacoes` | 2 workers × 4 threads | WhatsApp/email/SSE com rate-limit |
| `fila_verificacao` | 2 workers × 4 threads | OCR, reconciliação, comprovantes |
| `fila_contratos` | 2 workers × 2 threads | Ciclo de vida de contratos |
| `fila_frota` | 2 workers × 2 threads | GPS, FIPE, documentos |
| `fila_padrao` | 2 workers × 2 threads | Coordinators, manutenção |
| `fila_whatsapp_entrada` | 2 workers × 4 threads | Inbound prioridade máxima |
| `fila_agente` | 2 workers × 1 thread/processo | LLM I/O-bound |

2. `docker-compose.yml` com serviço `beat` (replicas=1 — fixo) + serviços de worker por fila escaláveis.
3. **Padrão fan-out**: coordinator no Beat consulta IDs elegíveis, distribui em lotes de 50 via `group()`/`chord()` do Celery — falha em uma empresa não bloqueia as demais.
4. **3 camadas de idempotência** obrigatórias em toda task de cobrança:
   - `SELECT FOR UPDATE SKIP LOCKED` no PostgreSQL
   - Redis lock `titulo:{id}:{operacao}` com TTL 60s
   - Colunas `proxima_acao_em TIMESTAMPTZ` e `acoes_de_cobranca INTEGER` na tabela `titulos_receber`

5. Tabela `execucoes_motor` para observabilidade:

```sql
CREATE TABLE execucoes_motor (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome_tarefa     VARCHAR(100) NOT NULL,
    empresa_id      UUID REFERENCES comercial.empresas(id),
    iniciado_em     TIMESTAMPTZ NOT NULL,
    finalizado_em   TIMESTAMPTZ,
    total_registros INTEGER DEFAULT 0,
    total_erros     INTEGER DEFAULT 0,
    situacao        VARCHAR(20) NOT NULL DEFAULT 'executando',
    detalhes        JSONB,
    CONSTRAINT ck_situacao CHECK (situacao IN ('executando','concluido','erro'))
);
```

6. Tabela `lembretes_enviados` para idempotência de envios:

```sql
CREATE TABLE lembretes_enviados (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    titulo_id   UUID NOT NULL REFERENCES financeiro.titulos_receber(id),
    tipo        VARCHAR(30) NOT NULL,
    canal       VARCHAR(30) NOT NULL,
    enviado_em  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sucesso     BOOLEAN NOT NULL,
    erro        TEXT,
    UNIQUE(titulo_id, tipo, DATE(enviado_em))
);
```

7. Endpoint `GET /api/v1/motor/execucoes` lista histórico paginado com filtros `nome_tarefa`, `empresa_id`, `situacao`, `data_inicio` (role `admin`).
8. Configuração de retry e dead-letter queue: `acks_late=True`, `reject_on_worker_lost=True`, `max_retries=3` com backoff exponencial.
9. Testes: 2 workers competindo pelo mesmo título → apenas um processa (SKIP LOCKED); worker crasha após processar → não duplica execução (acks_late).

## Contexto Técnico

### Filas Celery — routing

Em `celeryconfig.py`:
```python
task_routes = {
    'app.workers.tasks.gerar_titulos_mensais': {'queue': 'fila_cobranca'},
    'app.workers.tasks.processar_titulos_vencidos': {'queue': 'fila_cobranca'},
    'app.workers.tasks.alertar_vencimentos_proximos': {'queue': 'fila_notificacoes'},
    # ...
}
```

### Padrão fan-out coordinator

```python
@app.task(bind=True, queue='fila_padrao')
def coordinator_processar_vencidos(self):
    empresas = listar_empresas_ativas()
    chord([
        processar_vencidos_empresa.s(empresa.id)
        for empresa in empresas
    ])(consolidar_execucao.s(nome_tarefa='processar_titulos_vencidos'))
```

### Multi-tenant em workers

Toda task recebe `empresa_id` explícito e seta `app.empresa_id` via `SET LOCAL` (alinhado com Story 12.5 RLS).

## Arquivos a Criar/Modificar

```
src/backend-api/
├── alembic/versions/0024_execucoes_motor_lembretes.py
├── app/workers/
│   ├── celeryconfig.py                                  # MODIFICAR — 7 filas
│   ├── idempotencia.py                                  # CRIAR — helpers SKIP LOCKED + Redis lock
│   └── coordenadores/
│       └── fan_out.py                                   # CRIAR — padrão coordinator
├── app/infrastructure/db/models/
│   ├── execucao_motor.py                                # CRIAR
│   └── lembrete_enviado.py                              # CRIAR
├── app/api/v1/
│   └── motor_routes.py                                  # CRIAR — endpoint execuções
├── docker-compose.yml                                   # MODIFICAR — serviços de worker por fila
└── app/tests/test_idempotencia_workers.py               # CRIAR
```

## Checklist do Dev

- [ ] 13.4 (`sistema-configuracoes-tipadas`) `done` — workers vão consumir.
- [ ] Migration aplicada com sucesso.
- [ ] 7 filas definidas em celeryconfig e visíveis em `celery inspect active_queues`.
- [ ] `docker-compose up` sobe workers por fila isolados.
- [ ] Teste de SKIP LOCKED com 2 workers concorrentes (passa).
- [ ] Teste de Redis lock (ttl 60s) com 2 workers concorrentes (passa).
- [ ] Endpoint `/motor/execucoes` retorna paginado.
- [ ] Audit/log estruturado em todas as tasks via `structlog`.

## Notas

- Esta story é **fundação** — todos os motores 13.6 a 13.9 e 13.13 vão usar.
- Não implementa motor algum — só base.
- Justifica complexidade pelo blast radius zero: cada motor depois é "fill in the blank".
