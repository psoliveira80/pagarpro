# Manual do Desenvolvedor Técnico — FrotaUber

> Autor: Amelia (Senior SWE). Última atualização: 2026-05-24.
> Público-alvo: dev que está chegando hoje no projeto e precisa entender **o que cada coisa faz, onde fica, e por que fica assim**.
> Pré-requisitos: Python 3.12+, Docker, conhecimento básico de FastAPI, SQLAlchemy async e Celery.

---

## 1. Stack e visão de 30 segundos

| Camada | Tecnologia | Versão | Por quê |
|---|---|---|---|
| Linguagem backend | Python | 3.12+ | Type hints estritos, asyncio maduro |
| Web framework | FastAPI | 0.115+ | Async-first, OpenAPI gratuito, dependency injection |
| ORM | SQLAlchemy async | 2.0+ | Único ORM Python sério com async real |
| Banco | PostgreSQL | 16 + pgvector | JSONB, schemas, triggers, RLS futuro |
| Cache/queue broker | Redis | 7 | Celery broker, rate-limit, idempotência |
| Storage | MinIO (S3-compat) | latest | Anexos, comprovantes, PDFs |
| Worker | Celery | 5.4+ | Recorrência, fan-out, eventos |
| Frontend | Angular | 21 standalone | Signals, OnPush, zero NgModules |
| Auth | JWT RS256 + refresh cookie | PyJWT 2.9 | Stateless, refresh em HttpOnly |
| Logging | structlog | 24+ | JSON estruturado, correlation_id |

**Ponto de entrada:** `c:/DEV/Angular/FrotaUber/src/backend-api/app/main.py` cria a app FastAPI, registra módulos de asset, ferramentas do agente, e monta routers `/api/v1/*`.

Tudo roda em Docker. Não há runtime local — `cd raiz && docker compose up`.

---

## 2. Estrutura de pastas

```
c:/DEV/Angular/FrotaUber/
├── docker-compose.yml          # api, worker, beat, db, redis, minio
├── docs/                       # Documentação viva (este arquivo)
├── src/
│   ├── backend-api/
│   │   ├── alembic/            # Migrations versionadas (0001…0019…)
│   │   ├── alembic.ini
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── app/
│   │       ├── main.py         # create_app(), lifespan, registra routers
│   │       ├── api/            # Camada de transporte HTTP
│   │       │   ├── deps.py     # SessionDep, CurrentUserDep
│   │       │   ├── middleware.py
│   │       │   ├── sse.py
│   │       │   └── v1/         # Rotas REST agrupadas por domínio
│   │       ├── application/    # Casos de uso / orquestração
│   │       │   ├── auth/
│   │       │   ├── customers/
│   │       │   └── shared/
│   │       ├── domain/         # Núcleo do negócio — SEM IO
│   │       │   ├── finance/    # Cálculos puros (juros, multa, schedule)
│   │       │   ├── identity/
│   │       │   ├── ports/      # Protocols (interfaces) de integração externa
│   │       │   └── shared/     # value_objects, exceptions
│   │       ├── infrastructure/ # Adapters concretos + DB + observabilidade
│   │       │   ├── adapters/   # Implementações dos ports (FIPE, OCR, etc.)
│   │       │   ├── db/
│   │       │   │   ├── base.py        # Base, Mixins
│   │       │   │   ├── session.py     # engines async + sync
│   │       │   │   ├── models/        # ORM por schema PostgreSQL
│   │       │   │   └── repositories/  # CRUD por agregado
│   │       │   ├── observability/
│   │       │   ├── parsing/
│   │       │   ├── security/   # jwt, argon2, rate_limit
│   │       │   └── settings.py # Pydantic Settings (env vars)
│   │       ├── core/           # Plumbing reusável entre módulos
│   │       │   ├── assets/     # IAssetModule + registry (módulos plugáveis)
│   │       │   ├── channels/   # ChannelRegistry (WhatsApp/Email/SMS)
│   │       │   ├── agent/      # Orquestrador ReAct + tools
│   │       │   ├── events/     # DomainEvent dataclasses
│   │       │   ├── config.py
│   │       │   ├── correlation.py
│   │       │   └── di.py
│   │       ├── modules/        # Verticais plugáveis
│   │       │   └── vehicles/   # Veículos: VehicleModule (IAssetModule)
│   │       │       ├── module.py
│   │       │       ├── routes.py
│   │       │       ├── hooks.py
│   │       │       ├── adapters/   # FIPE, tracker (GPS)
│   │       │       ├── ports/      # Interfaces específicas do módulo
│   │       │       └── services/
│   │       ├── workers/        # Celery
│   │       │   ├── __init__.py # celery_app + beat_schedule
│   │       │   └── tasks/      # Uma task por arquivo
│   │       ├── cli/            # Scripts utilitários (seed, admin)
│   │       └── tests/          # pytest async
│   └── frontend/               # Angular 21 standalone
```

**Regra de ouro:** quanto **mais para dentro**, **menos dependências externas**. `domain/` não importa `infrastructure/`. `application/` orquestra ports (não adapters). `api/` é casca fina.

---

## 3. Arquitetura geral (Hexagonal / Ports & Adapters)

```
            ┌──────────────────────────────────────────────────────┐
            │  API (FastAPI routers)         WORKERS (Celery)      │
            │  HTTP/SSE/Webhooks             Tasks/Beat            │
            └────────────────┬───────────────────────┬─────────────┘
                             │                       │
                             ▼                       ▼
            ┌──────────────────────────────────────────────────────┐
            │              APPLICATION (use cases)                 │
            │   Orquestra ports + repositórios + commits           │
            └────────────────┬───────────────────────┬─────────────┘
                             │                       │
                             ▼                       ▼
            ┌──────────────────────────────────────────────────────┐
            │   DOMAIN (núcleo puro)                               │
            │   ─ entidades, value objects, cálculos               │
            │   ─ ports (Protocols) — contratos de integração      │
            │   ─ ZERO dependências de I/O, requests, SQLAlchemy   │
            └──────────────────────────────────────────────────────┘
                             ▲                       ▲
                             │  implementa           │  usa
            ┌────────────────┴───────────────────────┴─────────────┐
            │   INFRASTRUCTURE                                     │
            │   ─ adapters (FIPE, Z-API, Whisper, Asaas, …)        │
            │   ─ DB models, repositories, sessões                 │
            │   ─ security primitives (JWT, Argon2id)              │
            │   ─ observability (structlog, correlation)           │
            └──────────────────────────────────────────────────────┘
```

**Regras de dependência:**

1. `domain/` é o coração. **Não pode** importar `infrastructure/`, `application/`, `api/`, `workers/`, `core/`.
2. `domain/ports/` define `Protocol` (interface). `infrastructure/adapters/` herda **explicitamente** desse Protocol.
3. `application/` depende de `domain/` (ports + entidades) e nada mais.
4. `api/` e `workers/` são camadas de **entrada** — fazem dependency injection dos adapters concretos no use case.
5. `core/` é "plumbing horizontal" (registries, correlation, agent runtime) — pode importar `domain/` mas não `application/`.

**Exemplo prático — ports e adapters de gateway de pagamento:**

- Port: `c:/DEV/Angular/FrotaUber/src/backend-api/app/domain/ports/payment_gateway.py`

```python
@runtime_checkable
class IPaymentGateway(Protocol):
    async def create_charge(self, amount: Decimal, description: str,
                            customer_id: str, metadata: dict | None = None) -> dict: ...
    async def get_charge_status(self, charge_id: str) -> dict: ...
    async def refund(self, charge_id: str, amount: Decimal | None = None) -> dict: ...
```

- Adapter no-op (dev/test): `c:/DEV/Angular/FrotaUber/src/backend-api/app/infrastructure/adapters/noop_payment_gateway.py`
- Adapter real (Asaas, MercadoPago, Stripe) entra na mesma pasta seguindo o **mesmo Protocol**. Plugado via `config.credenciais_integracao` (categoria=`pagamento`, provedor=`asaas|...`).

Outros ports já implementados (`c:/DEV/Angular/FrotaUber/src/backend-api/app/domain/ports/`):
- `audio_transcriber.py` — `IAudioTranscriber` (Whisper API / Console fallback)
- `correction_index_provider.py` — `ICorrectionIndexProvider` (BCB / mock)
- `email_sender.py` — `IEmailSender` (SMTP / Console)
- `llm_provider.py` — `ILlmProvider` (OpenAI / Anthropic / Groq / Gemini / Ollama)
- `message_channel.py` — `IMessageChannel` (WhatsApp Z-API / Uazapi / Evolution)
- `ocr_provider.py` — `IOcrProvider` (Tesseract / Vision API)
- `whatsapp_gateway.py` — port legado de WhatsApp (será absorvido por `message_channel.py`)

**Padrão obrigatório**: adapter herda do Protocol via `class XAdapter(IPort):` — nunca duck typing implícito.

---

## 4. Modelo de dados — 12 schemas PostgreSQL

A partir da migration `0015_schema_restructure.py` o banco foi reorganizado em **schemas PostgreSQL** nomeados em PT-BR. Cada schema corresponde a um arquivo em `app/infrastructure/db/models/`.

| Schema | Arquivo de models | Tabelas principais | Responsabilidade |
|---|---|---|---|
| `comercial` | `comercial.py` | `empresas` | Tenant raiz (Modelo A multi-tenancy) |
| `acesso` | `acesso.py` | `usuarios`, `perfis`, `permissoes`, `perfil_permissoes`, `usuario_perfis`, `refresh_tokens` | Identity & access management |
| `cadastro` | `cadastro.py` | `clientes`, `anexos_cliente`, `fornecedores`, `categorias_despesa` | Cadastros básicos |
| `veiculos` | `veiculos.py` | `veiculos`, `aquisicoes_veiculo`, `dispositivos_rastreamento` | Frota (asset vertical) |
| `contrato` | `contrato.py` | `contratos`, `eventos_contrato`, `lotes_geracao` | Locação + máquina de estados |
| `financeiro` | `financeiro.py` | `titulos_receber`, `movimentos_titulo_receber`, `titulos_pagar`, `despesas_recorrentes` | Contas a receber / pagar |
| `conta_bancaria` | `conta_bancaria.py` | `contas_bancarias`, `transacoes_bancarias`, `sessoes_conciliacao` | Conciliação OFX |
| `cobranca` | `cobranca.py` | `conversas`, `mensagens`, `configuracoes_agente`, `execucoes_agente`, `scores_clientes`, `campanhas_disparo` | Cobrança via WhatsApp + agent |
| `config` | `config.py` | `configuracoes_sistema`, `politicas_eventos_modulo`, `credenciais_integracao` | Multi-provider config tipada |
| `relatorios` | `relatorios.py` | `relatorios_salvos` | Relatórios persistidos pelo usuário |
| `notificacoes` | `notificacoes.py` | `webhooks_brutos` | Inbox de webhooks (idempotência) |
| `logs` | `logs.py` | `log_auditoria`, `log_eventos` | Audit append-only + outbox de eventos |

### Como declarar uma model corretamente

Todo model **DEVE**:

1. Herdar `Base` + os mixins corretos (`UUIDPrimaryKeyMixin`, `TimestampMixin`, `SoftDeleteMixin` quando aplicável).
2. Declarar `__tablename__` em PT-BR.
3. Declarar `__table_args__ = {"schema": "<schema_name>"}` (ou tupla com constraints + dict de schema).
4. Ter coluna `empresa_id` com `ForeignKey("comercial.empresas.id")` se for tenant-scoped.
5. Usar ForeignKey **qualificado** com schema, ex.: `ForeignKey("cadastro.clientes.id")`.

**Exemplo canônico** (`app/infrastructure/db/models/cadastro.py`):

```python
class Cliente(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "clientes"
    __table_args__ = (
        UniqueConstraint("empresa_id", "cpf_cnpj", name="uq_clientes_empresa_cpf_cnpj"),
        {"schema": "cadastro"},
    )

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    nome_completo: Mapped[str] = mapped_column(Text, nullable=False)
    cpf_cnpj: Mapped[str] = mapped_column(Text, nullable=False)
    ...

    # --- Compat aliases (Story 12.3 transition) ---
    full_name = synonym("nome_completo")
    phone = synonym("telefone")
    ...
```

### Mixins canônicos

`c:/DEV/Angular/FrotaUber/src/backend-api/app/infrastructure/db/base.py`:

```python
class UUIDPrimaryKeyMixin:
    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

class TimestampMixin:
    criado_em: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    # synonyms criado_em -> created_at, atualizado_em -> updated_at

class SoftDeleteMixin:
    excluido_em: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    # synonym excluido_em -> deleted_at
```

**Soft delete por padrão.** Toda query padrão de repo filtra `WHERE excluido_em IS NULL`. Rascunhos (`status='rascunho'`) podem ser DELETADOS de verdade.

### Relacionamentos críticos

- `comercial.empresas` é a raiz multi-tenant. **Todo dado** referencia `empresa_id`.
- `acesso.usuarios.empresa_id` → 1 usuário pertence a **uma única** empresa (Modelo A). Email é **único global** (citext).
- `contrato.contratos.cliente_id` → `cadastro.clientes`
- `contrato.contratos.veiculo_id` → `veiculos.veiculos`
- `veiculos.veiculos.contrato_ativo_id` → `contrato.contratos` (FK circular resolvida via `use_alter=True` na migration 0015)
- `financeiro.titulos_receber.contrato_id` → `contrato.contratos`
- `financeiro.titulos_receber.titulo_origem_id` → self (parcela mãe → parcela filha após renegociação)
- `financeiro.titulos_pagar.titulo_receber_origem_id` → `financeiro.titulos_receber` (despesa gerada por título recebido, ex.: comissão)
- `cobranca.conversas.cliente_id` → `cadastro.clientes` (ON DELETE SET NULL — conversas sobrevivem ao soft delete do cliente)

**FK policy:** padrão é `ON DELETE RESTRICT` (Modelo A). Exceções explícitas: `CASCADE` em tabelas filhas tipo `anexos_cliente`, `dispositivos_rastreamento`, `eventos_contrato`, `lotes_geracao`. `SET NULL` em referências fracas como `conversas.cliente_id`, `sessoes_conciliacao.criado_por_id`.

### Estados das entidades

**Contrato** (`contrato.contratos.status`):
```
rascunho → ativo → (suspenso ⇄ ativo) → encerrado_sem_pendencia
                                       | encerrado_com_pendencia
                                       | encerrado_compra
                                       | rescindido
```

**Título a receber** (`financeiro.titulos_receber.status`) — 7 estados:
- `em_aberto` (default)
- `vencido`
- `pago`
- `pago_aguardando_verificacao` (merge de `pendente_verificacao` + `pago_aguardando_conciliacao`)
- `renegociado`
- `cancelado`
- `incobravel`

**Tipos de título** (`financeiro.titulos_receber.tipo`): `parcela | opcao_compra | multa | taxa | ajuste`.

### Decisão JSONB vs colunas

Use **JSONB** quando:
- Campo é variável por tenant/módulo (ex.: `clientes.metadata_extensoes`, `veiculos.aquisicoes.parcelas`)
- Snapshot histórico imutável (ex.: `movimentos_titulo_receber.snapshot_antes`)
- Configuração tipada com schema dinâmico (`configuracoes_sistema.valor`)
- Payload de evento ou webhook (`log_eventos.payload`, `webhooks_brutos.payload`)

Use **colunas dedicadas** quando:
- Campo é filtrado/ordenado/agregado com frequência
- Tem `UNIQUE` ou `FOREIGN KEY`
- Tem regra de negócio (CHECK constraint)
- Aparece em índice composto

Migration 0018 **reverteu** alguns campos de JSONB para colunas planas justamente porque a query precisava deles (`movimentos.valor_anterior`, `movimentos.valor_posterior`).

---

## 5. Padrões obrigatórios de código

### 5.1 Naming PT-BR

A partir da migration 0015 (épico 12) **tudo no domínio** é PT-BR:
- Tabelas: `clientes`, `contratos`, `titulos_receber`
- Colunas: `empresa_id`, `nome_completo`, `criado_em`, `excluido_em`
- Models SQLAlchemy: `Cliente`, `Contrato`, `TituloReceber`
- Hooks: `quando_titulo_pago`, `quando_titulo_vencido`, `quando_contrato_ativado`
- Eventos: `EventoTituloPago`, `EventoTituloVencido`, `EventoContratoAtivado`
- Tasks Celery: `processar_*`, `gerar_*`, `alertar_*`
- Ports/adapters: nomes em PT-BR (ex.: `IGatewayPagamento`, `AdaptadorAsaas`) — em migração

### 5.2 Synonyms PT-BR ↔ EN (transição da story 12.3)

Como o código tinha bases em inglês, foi adicionado `synonym(...)` para **toda** coluna renomeada. Exemplo:

```python
# Em cadastro.py
full_name = synonym("nome_completo")
phone = synonym("telefone")
zip_code = synonym("cep")
```

E em `app/infrastructure/db/models/__init__.py`:

```python
Customer = Cliente
Contract = Contrato
Installment = TituloReceber
...
```

**Regra:**
- Código novo: sempre PT-BR (`Cliente.nome_completo`, `TituloReceber.valor`).
- Código legado: pode usar o alias em inglês — funciona, mas vai ser refatorado.
- **Não** adicione synonyms novos sem necessidade. São ponte temporária.

### 5.3 Async/await em tudo

- Todo handler de rota é `async def`.
- Todo repo é `async def` usando `AsyncSession`.
- Todo adapter de IO (HTTP, Redis, S3 client) é async.
- **Exceção:** Celery tasks rodam síncronas → use `asyncio.run(_corotina())` no entry point. Nunca `get_event_loop().run_until_complete()` (algumas tasks legadas ainda fazem isso — corrigir ao tocar).

### 5.4 Sessão via dependency injection

Padrão em `c:/DEV/Angular/FrotaUber/src/backend-api/app/api/deps.py`:

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        yield session

SessionDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
```

Em rotas:

```python
@router.post("")
async def criar_cliente(
    body: ClienteCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ClienteResponse:
    repo = ClienteRepository(session)
    ...
    await session.commit()
```

**Commit é responsabilidade da rota**, não do repo. Repo só faz `await session.flush()`.

### 5.5 Empresa_id em todo lugar

Todo repo que lista deve receber `empresa_id` e filtrar. Padrão em `customer_repo.py`:

```python
async def list_paginated(
    self, *, search=None, status=None, empresa_id=None, page=1, size=20
) -> tuple[list[Customer], int]:
    query = self._base_query()
    if empresa_id:
        query = query.where(Customer.empresa_id == empresa_id)
    ...
```

Em rotas: usar **sempre** `current_user.empresa_id`. Nunca aceitar empresa_id do body/query do usuário final.

### 5.6 Paginação padronizada

Toda lista paginada retorna:

```json
{
  "items": [...],
  "total": 123,
  "page": 1,
  "size": 20,
  "pages": 7
}
```

Schema em `app/api/v1/schemas/*` usando `PaginatedResponse[T]` genérico. **Nunca** retorne array direto para listas.

### 5.7 Erros padronizados (RFC 7807)

`app/api/exception_handlers.py` registra handlers que convertem exceções de domínio em Problem+JSON:

```json
{
  "type": "https://errors/conflict",
  "title": "CPF/CNPJ already registered",
  "status": 409,
  "detail": "...",
  "instance": "/api/v1/customers"
}
```

Em rotas, use `HTTPException(status_code=409, detail="...")` ou levante exceções de domínio (`app/domain/shared/exceptions.py`).

### 5.8 Auditoria

Toda mutação relevante deve gerar entrada em `logs.log_auditoria`:

```python
audit = AuditLogger(session)
await audit.record(
    action="customer.created",
    user_id=str(current_user.id),
    entity="customer",
    entity_id=str(customer.id),
    payload_after={"full_name": ..., "cpf_cnpj": ...},
    correlation_id=get_correlation_id(),
    module="customers",
    category="data",   # ou "security" para login/permissões
    severity="info",
)
```

A tabela `log_auditoria` é **append-only** com trigger PG que bloqueia UPDATE/DELETE e HMAC-SHA256 para integridade.

### 5.9 Correlation ID

`CorrelationIdMiddleware` (`app/api/middleware.py`) injeta `X-Correlation-Id` em toda request e propaga via `contextvar`. Use:

```python
from app.core.correlation import get_correlation_id
cid = get_correlation_id()
```

Todos os logs structlog já incluem o cid automaticamente. Propague para tasks Celery passando como argumento explícito.

---

## 6. Workers Celery — recorrência e fan-out

### 6.1 Setup

`c:/DEV/Angular/FrotaUber/src/backend-api/app/workers/__init__.py`:

```python
celery_app = Celery("app",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND)

celery_app.conf.task_acks_late = True              # ack só após sucesso
celery_app.conf.task_reject_on_worker_lost = True  # requeue em caso de SIGKILL
celery_app.conf.worker_prefetch_multiplier = 1     # justiça entre tasks longas
celery_app.conf.include = [
    "app.workers.tasks.handle_domain_event",
    "app.workers.tasks.generate_monthly_installments",
    "app.workers.tasks.calculate_customer_scores",
    "app.workers.tasks.refresh_materialized_views",
    "app.workers.tasks.backup",
    ...
]
```

### 6.2 Filas (épico 12)

O comando do worker em `docker-compose.yml`:

```bash
celery -A app.workers worker -Q default,high,low,events,agent,ocr -l info
```

Filas previstas (épico 12, 7 filas separadas):
- `cobranca` — geração de cobranças, notificações de vencido
- `notificacoes` — email/SMS/WhatsApp outbound
- `verificacao` — conciliação OFX, validação de comprovante
- `contratos` — geração mensal, renovação, encerramento
- `frota` — webhooks de tracker, sincronização FIPE
- `padrao` (default) — fallback
- `whatsapp_entrada` — processamento de mensagem inbound (alta prioridade, baixa latência)

### 6.3 Beat schedule

```python
celery_app.conf.beat_schedule = {
    "calculate-customer-scores-daily": {
        "task": "...calculate_customer_scores",
        "schedule": 3600 * 24,
    },
    "refresh-materialized-views-hourly": {
        "task": "...refresh_materialized_views",
        "schedule": 3600,
    },
    "daily-backup-03utc": {
        "task": "backup.run_backup",
        "schedule": crontab(hour=3, minute=0),
    },
    "generate-monthly-installments-06utc": {
        "task": "...generate_monthly_installments",
        "schedule": crontab(hour=6, minute=0),
    },
}
```

**Regra:** use `crontab(hour=H, minute=M)` para horários exatos. Só use intervalos numéricos (segundos) para coisas verdadeiramente periódicas curtas (refresh de view).

### 6.4 Padrão fan-out coordinator → lotes de 50

Tasks pesadas (notificar 10 mil clientes) não rodam em uma única task. Padrão:

1. **Coordinator task** roda no beat, lê o trabalho a fazer, particiona em lotes de 50.
2. Dispara `N` **worker tasks** (uma por lote) via `.delay()`.
3. Worker task processa o lote, escreve resultados.

Exemplo em `generate_recurring_payables.py` e `calculate_customer_scores.py`.

### 6.5 Idempotência em 3 camadas

Toda task de mutação financeira aplica:

**Camada 1 — SQL `SELECT … FOR UPDATE SKIP LOCKED`:**

```python
stmt = (
    select(Contract)
    .where(
        Contract.generation_mode == "mensal",
        Contract.next_generation_date <= today,
        Contract.excluido_em.is_(None),
        Contract.status.notin_(_INACTIVE_STATUSES),
    )
    .with_for_update(skip_locked=True)
)
```

Worker B nunca vê linhas que worker A já travou. Veja `app/workers/tasks/generate_monthly_installments.py`.

**Camada 2 — Redis lock por chave de negócio:**

```python
async with redis.lock(f"installment:gen:{contract_id}:{due_date}", timeout=30):
    ...
```

Protege contra retry do mesmo `task_id` em workers diferentes.

**Camada 3 — `proxima_acao_em` / `proxima_geracao_em` na própria linha:**

Após processar com sucesso, avança o campo de "próximo processamento" — re-execução da query principal não enxerga a linha novamente.

**Bônus:** webhooks têm `webhooks_brutos.uq(empresa_id, provedor, external_id)` — duplicata de provider é descartada por constraint UNIQUE.

### 6.6 Worker em Python (não Go)

Decisão: as tasks são **I/O-bound** (chamadas a Asaas, Z-API, BCB, SMTP). Python+gevent (ou asyncio dentro de `asyncio.run()`) atende. Reescrever em Go seria over-engineering. **Não mude essa decisão sem benchmark concreto.**

---

## 7. Eventos de domínio + módulos de asset

### 7.1 DomainEvent

`c:/DEV/Angular/FrotaUber/src/backend-api/app/core/events/domain_events.py` define dataclasses imutáveis:

- `ContractCreatedEvent` / `EventoContratoAtivado`
- `ContractTerminatedEvent` / `EventoContratoEncerrado`
- `InstallmentPaidEvent` / `EventoTituloPago`
- `InstallmentOverdueEvent` / `EventoTituloVencido`
- `PaymentPartiallyReceivedEvent` / `EventoPagamentoParcialRecebido`
- `ReconciliationCompletedEvent` / `EventoReconciliacaoConcluida`
- `EventoOpcaoCompraPaga`
- `EventoScoreClienteAlterado`

Cada evento tem `event_id` (uuid4), `asset_type`, `tenant_id`, `payload`, `created_at`.

### 7.2 Outbox + handle_domain_event

Quando um use case emite um evento, ele grava em `logs.log_eventos` (status `pendente`). A task `handle_domain_event` consome o outbox, busca os módulos registrados que respondem àquele evento, e executa o hook apropriado.

`app/workers/tasks/handle_domain_event.py`:

```python
_EVENT_HANDLER_MAP = {
    ContractCreatedEvent: "on_contract_created",
    InstallmentOverdueEvent: "on_installment_overdue",
    InstallmentPaidEvent: "on_installment_paid",
    ...
}

# Idempotência via log_eventos.event_id UNIQUE
existing = await session.execute(
    select(EventLog).where(EventLog.event_id == event.event_id)
)
if existing.scalar_one_or_none():
    return {"status": "duplicate", ...}
```

### 7.3 IAssetModule — módulos verticais plugáveis

`c:/DEV/Angular/FrotaUber/src/backend-api/app/core/assets/module_interface.py` define o protocolo.

Módulo concreto exemplo: `c:/DEV/Angular/FrotaUber/src/backend-api/app/modules/vehicles/module.py` (`VehicleModule`).

Cada módulo expõe:
- `asset_type` (string única — `"vehicle"`, futuros: `"immovel"`, `"equipamento"`)
- `handles_event(event_type)` — quais eventos consome
- `on_*` callbacks que retornam `list[Action]`
- `get_asset_schema()` — campos extras do asset (frontend usa para gerar form)
- `get_dashboard_widgets()` — widgets que aparecem no dashboard quando o módulo está ativo
- `get_agent_tools()` — ferramentas que o agente pode chamar
- `get_custom_routes()` — `APIRouter` próprio do módulo

Registro em `main.py` lifespan:

```python
from app.core.assets.registry import register_module
from app.modules.vehicles.module import VehicleModule
register_module(VehicleModule())
```

Habilitação por tenant via `active_modules` (uma linha por `(empresa_id, module_id)`).

### 7.4 Hooks de domínio (convenção `quando_`)

Hooks principais:
- `quando_titulo_pago` → marca contrato em dia, dispara comissão, atualiza score
- `quando_titulo_vencido` → cria task de cobrança, marca contrato suspenso após N dias
- `quando_contrato_ativado` → libera veículo, gera primeira parcela
- `quando_contrato_encerrado` → bloqueia veículo (chain API → RPA → manual), encerra titulos
- `quando_contrato_suspenso` / `quando_contrato_reativado`
- `quando_reconciliacao_concluida` → marca títulos como pagos batch

Hooks vivem em `app/modules/<modulo>/hooks.py` (ex.: `VehicleHooks`).

---

## 8. Canais de mensageria

`c:/DEV/Angular/FrotaUber/src/backend-api/app/core/channels/registry.py` mantém um singleton `channel_registry`. Cada adapter implementa `IMessageChannel` (`app/domain/ports/message_channel.py`) — métodos: `send_text`, `send_media`, `parse_webhook`, `health_check`.

WhatsApp V1 tem 3 providers em `app/infrastructure/adapters/whatsapp/`:
- Z-API
- Uazapi
- Evolution API

Email tem 2: `smtp_email_adapter.py` (prod) e `console_email_adapter.py` (dev — imprime no log).

Canais futuros (SMS, Telegram, Discord) aparecem como **"Em breve"** no frontend até o adapter ser implementado.

---

## 9. Multi-tenancy (Modelo A)

**Decisão:** 1 usuário pertence a exatamente **1 empresa**. Email é **único global** (citext, case-insensitive).

Consequências:
- `acesso.usuarios.empresa_id` é `NOT NULL`.
- `acesso.usuarios.email` é `UNIQUE` global.
- Para o mesmo humano operar 2 empresas → 2 emails diferentes ou 2 usuários distintos. Aceito como trade-off de simplicidade.
- **Todo SELECT** de dado tenant-scoped precisa filtrar `WHERE empresa_id = :current_empresa_id`. Por hora isso é feito **explicitamente** nos repos.
- Próximo passo (épico 12 stories 12-4 a 12-7): middleware injeta `current_empresa_id` no contextvar + PostgreSQL Row Level Security (RLS) como cinto + suspensórios.

**Self-register desabilitado.** Apenas admin convida via email (token assinado). Endpoint de signup público existe mas retorna 403 fora de dev.

---

## 10. Autenticação

### 10.1 JWT RS256

- Access token: **15 min**, RS256, claims: `sub` (user_id), `email`, `roles`, `iat`, `exp`, `iss`, `aud`.
- Chaves: efêmeras geradas em memória em dev; arquivo PEM em prod via `JWT_PRIVATE_KEY_PATH` / `JWT_PUBLIC_KEY_PATH`.
- Implementação: `app/infrastructure/security/jwt_service.py`.

### 10.2 Refresh token

- TTL: **7 dias**, persistido em `acesso.refresh_tokens` (apenas o hash).
- Entregue como cookie HttpOnly com `secure=True` em prod, `secure=False` em dev (`APP_ENV`).
- Endpoint `/auth/refresh` lê cookie, valida, emite novo access token + rotaciona refresh.

### 10.3 Password hashing

Argon2id (`argon2-cffi`). **Nunca** bcrypt ou SHA. Implementação em `app/infrastructure/security/password.py`.

### 10.4 Rate limiting

Redis-based, **5 tentativas em 15 minutos** por (email + IP). Bloqueio aplicado em login, password-reset, verify-email. `app/infrastructure/security/rate_limit.py`.

### 10.5 Restauração de sessão

`GET /api/v1/auth/me` valida access token e retorna o usuário. Frontend usa no `APP_INITIALIZER` para reidratar sessão no F5.

---

## 11. Rotas (API v1)

Todas em `app/api/v1/` com prefixo `/api/v1/`. Lista atual:

| Arquivo | Prefix | Domínio |
|---|---|---|
| `auth_routes.py` | `/auth` | Login, register, refresh, verify-email, forgot/reset password |
| `customer_routes.py` | `/customers` | CRUD de clientes, anexos |
| `customer_data_routes.py` | `/customers/data` | LGPD: export, anonymize, delete |
| `contract_routes.py` | `/contracts` | CRUD contratos, transitions de estado |
| `receivable_routes.py` | `/receivables` | Títulos a receber, pagamento, renegociação |
| `payable_routes.py` | `/payables` | Despesas, fornecedores, recorrentes |
| `bank_account_routes.py` | `/bank-accounts` | Contas bancárias |
| `reconciliation_routes.py` | `/reconciliation` | OFX import, conciliação |
| `webhook_routes.py` | `/webhooks` | Webhooks de pagamento (Asaas, etc.) |
| `webhook_whatsapp_routes.py` | `/webhooks/whatsapp` | Inbound WhatsApp |
| `conversation_routes.py` | `/conversations` | Inbox de conversas |
| `broadcast_routes.py` | `/broadcasts` | Campanhas em massa |
| `agent_routes.py` | `/agent` | Tools, run, config do agente |
| `dashboard_routes.py` | `/dashboard` | KPIs, charts |
| `report_routes.py` | `/reports` | Relatórios exportáveis (XLSX, PDF) |
| `admin_routes.py` | `/admin` | Integrações, audit log, módulos, settings, backup, metrics |
| `search_routes.py` | `/search` | Global search (Ctrl+K) |
| `modules/vehicles/routes.py` | `/vehicles` | CRUD veículos, FIPE, tracker |

Schemas Pydantic em `app/api/v1/schemas/<dominio>.py`. Convenção:
- `<Entity>Create` — body de POST
- `<Entity>Update` — body de PUT/PATCH (todos campos opcionais)
- `<Entity>Response` — output (com `id`, `criado_em`, etc.)
- `<Entity>ListItem` — versão enxuta para listas
- `PaginatedResponse[T]` — wrapper paginado

---

## 12. Testes

### 12.1 Stack

- `pytest>=8.0`
- `pytest-asyncio>=0.24` em `asyncio_mode = "auto"` (`pyproject.toml`)
- Sem `pytest-asyncio` marker manual — toda função async é coroutine de teste automaticamente.

### 12.2 Conftest

`c:/DEV/Angular/FrotaUber/src/backend-api/app/tests/conftest.py`:

```python
@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.DefaultEventLoopPolicy()

@pytest.fixture(autouse=True)
async def reset_engine():
    yield
    await dispose_engine()
```

`dispose_engine()` é **crítico**: sem ele, conexões SQLAlchemy abertas em loop A vazam para loop B do próximo teste e dão `Future attached to a different loop`.

### 12.3 Cleanup com FK RESTRICT

Como FKs são `ON DELETE RESTRICT` (Modelo A), testes que truncam tabelas precisam respeitar ordem:

```
log_auditoria → log_eventos → movimentos_titulo_receber → titulos_receber
→ titulos_pagar → lotes_geracao → eventos_contrato → contratos
→ aquisicoes_veiculo → veiculos → anexos_cliente → clientes
→ refresh_tokens → usuario_perfis → usuarios → empresas
```

Ou alternativa: usar `TRUNCATE ... CASCADE` (perigoso fora de teste).

Para `log_auditoria` (trigger imutável), desabilitar/reabilitar o trigger em volta do cleanup:

```sql
ALTER TABLE logs.log_auditoria DISABLE TRIGGER trg_audit_log_immutable;
TRUNCATE logs.log_auditoria;
ALTER TABLE logs.log_auditoria ENABLE TRIGGER trg_audit_log_immutable;
```

### 12.4 Limpeza Redis

Limpar **todas** as keys entre testes — não apenas as conhecidas:

```python
async for key in redis.scan_iter("*"):
    await redis.delete(key)
```

Algumas tasks criam keys de lock/idempotência com prefixos imprevisíveis.

### 12.5 Status atual (épico 12)

168 testes verdes (12-1, 12-2, 12-3 done). 12-4 a 12-8 abrem novos testes de isolamento por tenant.

---

## 13. Migrations (Alembic)

Localização: `c:/DEV/Angular/FrotaUber/src/backend-api/alembic/versions/`. Comando:

```bash
docker compose exec api alembic upgrade head
docker compose exec api alembic revision --autogenerate -m "descrição"
```

**Quando criar migration:**
- Sempre que tocar em uma model: novo campo, novo índice, mudança de tipo, nova tabela.
- Mudança de constraint (UNIQUE, CHECK).
- Renomear coluna (lembre de manter `synonym(...)` no model para compat).

**Quando NÃO criar migration:**
- Mudança puramente de runtime (cache, env var).
- Adicionar `synonym(...)` no model (synonym vive só no Python).

**Histórico-chave:**
- `0015_schema_restructure.py` — grande refactor PT-BR e schemas
- `0016_fix_multi_tenant_uniques.py` — UNIQUEs incluindo `empresa_id`
- `0017_rename_fks_and_conversa_fields.py` — FKs qualificados pelo novo schema
- `0018_add_legacy_columns_to_models.py` — restaurou colunas que tinham virado JSONB
- `0019_contrato_observacoes.py` — restaurou `contratos.observacoes`

DDL canônica de referência: `c:/DEV/Angular/FrotaUber/docs/ddl/schema_v2.sql`.

---

## 14. Configuração por env vars

`c:/DEV/Angular/FrotaUber/src/backend-api/app/infrastructure/settings.py` (Pydantic Settings). Vars principais:

| Var | Default | Função |
|---|---|---|
| `APP_ENV` | `dev` | Em prod (`prod|staging`) o validator exige `SECRET_KEY` e S3 reais |
| `DATABASE_URL` | `postgresql+asyncpg://app:app@db:5432/app` | URL async — Celery converte para `psycopg2` |
| `REDIS_URL` | `redis://redis:6379/0` | Cache + rate limit |
| `CELERY_BROKER_URL` | `redis://redis:6379/1` | DB 1 — isola do cache |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/2` | DB 2 |
| `S3_*` | minio defaults | Storage |
| `JWT_*` | RS256 | Auth |
| `LOGIN_MAX_ATTEMPTS` / `LOGIN_LOCKOUT_MINUTES` | 5 / 15 | Rate limit login |
| `SMTP_*` | vazio | Email outbound |
| `FRONTEND_URL` | `http://localhost:4200` | Reset password links |
| `CORS_ORIGINS` | `["*"]` | `*` em dev, lista explícita em prod |
| `FIPE_PROVIDER` | `brasilapi` | `brasilapi | mock` |
| `LLM_PROVIDER` / `LLM_API_KEY` / `LLM_MODEL` | OpenAI gpt-4o | Agente |
| `WHATSAPP_PROVIDER` | vazio | `zapi | uazapi | evolution_api` |
| `AGENT_DRY_RUN` | `false` | Se true, o agente não envia mensagens reais |

### Configuração tipada em DB

`config.configuracoes_sistema` substitui a antiga `politica_cobranca`. Estrutura:
- `empresa_id`
- `chave` (slug, ex.: `cobranca.juros_mora_pct`, `notificacao.canal_default`)
- `valor` (JSONB com schema validado por CHECK no PostgreSQL ou no Python ao ler)
- `descricao`

Categorias por convenção: `modulo + slug + tipo_valor` (`string | inteiro | decimal | booleano | json`). Regex CHECK constraints garantem tipo no banco.

---

## 15. Frontend (resumo)

Pasta: `c:/DEV/Angular/FrotaUber/src/frontend/`.

- Angular 21+, **standalone components**, zero NgModules.
- 3 arquivos por componente (`.ts`, `.html`, `.css`).
- `ChangeDetectionStrategy.OnPush` em **todos**.
- Estado: **Signals + computed() + resource()**. Zero NgRx.
- Serviços globais em `core/services/`. Zero services dentro de `features/`.
- Tailwind v4 via `@tailwindcss/postcss`.
- Cores **sempre** via CSS variables (`bg-[var(--surface)]`).
- Dark mode via `[data-theme="dark"]`.

### Padrões UI obrigatórios

- CRUD: **wizard multi-step** (nunca side drawer).
- Asterisco vermelho em obrigatório: `<span class="text-[var(--danger)]">*</span>`.
- **Nunca** `<select>` nativo → `CustomSelectComponent` (CDK Overlay).
- Seleção de entidade → `SearchableSelectComponent` com busca server-side, debounce 300ms, virtual scroll.
- Toast para feedback. **Nunca** `alert()`.
- Confirmação via `ConfirmService` (SweetAlert2). **Nunca** `confirm()`.
- Modais via `<app-modal>` (`shared/components/modal/`). **Nunca** inline.
- Mobile-first. Sidebar: seta `<` para recolher (desktop) / hamburger overlay (mobile).

### Auth no frontend

- Access token em **memória** (signal). **Nunca** localStorage.
- Refresh token via HttpOnly cookie.
- `APP_INITIALIZER` → `tryRestoreSession()` (chama `GET /auth/me`).
- JWT interceptor com silent refresh + lock de concorrência (impede 2 refreshes simultâneos).

### Proxy

`proxy.conf.json` aponta `/api/*` para `127.0.0.1:8100` (porta da API em dev).

---

## 16. Domain — cálculos financeiros puros

`c:/DEV/Angular/FrotaUber/src/backend-api/app/domain/finance/`:

- `calculations.py` — `compute_updated_value(...)` calcula juros + multa + desconto antecipado. Pura, sem IO.
- `schedule_calculator.py` — gera cronograma de parcelas a partir de contrato.
- `termination_calculator.py` — calcula valor de rescisão (multa + saldo devedor).
- `pix_brcode.py` — gera BR Code para PIX dinâmico.
- `pix_receipt_parser.py` — extrai dados de comprovante PIX (OCR + regex).

Exemplo de `compute_updated_value`:

```python
def compute_updated_value(
    original_value: Decimal,
    due_date: date,
    payment_date: date | None = None,
    interest_rate_monthly: Decimal = Decimal("0.02"),
    fine_rate: Decimal = Decimal("0.02"),
    discount_early_days: int = 0,
    discount_rate: Decimal = Decimal("0"),
) -> dict:
    # Vencido → multa + juros diários pro-rata; antes → desconto se aplicável
    ...
    return {"original": ..., "interest": ..., "fine": ..., "discount": ..., "total": ...}
```

**Toda matemática financeira mora aqui.** Repos e rotas chamam essas funções. Nunca calcule juros direto em uma rota.

---

## 17. Agente conversacional

`c:/DEV/Angular/FrotaUber/src/backend-api/app/core/agent/`:

- `orchestrator.py` — `AgentOrchestrator` em loop **ReAct** (Reason → Act → Observe), max 10 iterações.
- `tool_interface.py` — `Tool` Protocol + `ToolResult`.
- `tool_registry.py` — `AgentToolRegistry` (registra/lookup de tools).
- `conversation_store.py` — persiste histórico em `cobranca.mensagens`.
- `tools/` — tools específicas (consultar saldo, gerar boleto, bloquear veículo, etc.).

**Vision:** agente é um orquestrador **genérico** (texto/áudio/imagem, qualquer canal). Permissões gated por `required_permissions` em cada `AgentTool` → usuário só pode disparar tool para a qual tem permissão.

Modos de operação (épico 11 — backlog):
- `ia-full` — sempre LLM
- `ia-eco` — LLM só quando regex stack falha
- `ia-zero` — apenas templates + regex, sem LLM

---

## 18. Observabilidade

- **Logs:** structlog JSON, todos com `correlation_id`, `tenant_id`, `user_id` quando disponíveis. Setup em `app/infrastructure/observability/logging.py` chamado no lifespan.
- **Health:** `GET /health` valida DB, Redis e MinIO. Retorna `{"status": "ok|degraded", "db": ..., "redis": ..., "storage": ...}`.
- **Métricas:** endpoints em `/admin/metrics` (épico 9) expõem contadores de tasks, latência, erros.
- **Sentry:** previsto, ainda não integrado.

---

## 19. Decisões arquiteturais para guardar

1. **Modelo A multi-tenant** — 1 usuário = 1 empresa. Email único global. FK ON DELETE RESTRICT.
2. **PT-BR no domínio** — tudo (tabelas, colunas, models, hooks, events, tasks, ports). Synonyms EN como ponte temporária durante refactor.
3. **7 filas Celery separadas** — isolamento por SLA e blast radius.
4. **Fan-out coordinator → lotes de 50** — escala horizontal sem locks longos.
5. **3 camadas de idempotência** — SKIP LOCKED + Redis lock + `proxima_acao_em`.
6. **Worker em Python (gevent)** — I/O-bound, não compensa Go.
7. **Self-register desabilitado** — admin convida via email.
8. **Config tipada via `config.configuracoes_sistema`** — substitui `politica_cobranca` legada.
9. **Asset modules plugáveis** (`IAssetModule`) — adicionar imóveis ou equipamentos é criar um módulo, não mexer no core.
10. **Canais plugáveis** (`IMessageChannel`) — WhatsApp/Email/SMS/Telegram via mesmo Protocol.
11. **Hexagonal** — adapter herda Protocol explicitamente; ports vivem em `domain/ports/`.
12. **Soft delete por padrão** — `excluido_em` em tudo. DELETE real só em rascunho.
13. **Audit log append-only com HMAC** — trigger PG bloqueia UPDATE/DELETE.
14. **JWT RS256 + refresh em HttpOnly cookie** — access token vive 15min, refresh 7d.
15. **Argon2id** para senhas — nunca bcrypt.

---

## 20. Workflow de desenvolvimento

### Setup local

```bash
cd c:/DEV/Angular/FrotaUber
docker compose up -d db redis minio
docker compose up api worker beat   # primeiro plano para ver logs
```

Portas:
- API: **8100**
- Postgres: **5433** (usuário `app`, senha `app`, db `app`)
- Redis: **6380**
- MinIO: **9000** (API) / **9001** (console)

### Rodar testes

```bash
docker compose exec api pytest -x
docker compose exec api pytest app/tests/test_customer_crud.py -v
```

### Aplicar migration

```bash
docker compose exec api alembic upgrade head
```

### Gerar migration

```bash
docker compose exec api alembic revision --autogenerate -m "add_xpto_to_clientes"
# Revise SEMPRE o arquivo gerado. Autogenerate erra em renames e em coisas com synonym.
```

### Lint/typecheck

```bash
docker compose exec api ruff check .
docker compose exec api mypy app
```

### Console Python no container

```bash
docker compose exec api python -i
>>> from app.infrastructure.db.session import get_sessionmaker
>>> import asyncio
>>> sm = get_sessionmaker()
>>> ...
```

---

## 21. Checklist para PR

- [ ] Code está em PT-BR (nomes novos) ou usa synonyms para compat.
- [ ] Toda nova model tem `empresa_id` (se tenant-scoped), mixins corretos, `__table_args__` com schema.
- [ ] FK qualificado com schema (`ForeignKey("cadastro.clientes.id")`).
- [ ] Repo filtra por `empresa_id` em todo SELECT.
- [ ] Rota usa `current_user.empresa_id` — nunca aceita do client.
- [ ] Mutação relevante gera `LogAuditoria` com `correlation_id`.
- [ ] Lista paginada usa `PaginatedResponse`.
- [ ] Task Celery é idempotente (SKIP LOCKED + Redis lock).
- [ ] Migration criada e revisada.
- [ ] Teste pytest cobrindo happy path + erro principal.
- [ ] Sem `print()` — usar `structlog.get_logger()`.
- [ ] Sem credencial hardcoded — sempre via `Settings` / `credenciais_integracao`.

---

## 22. Onde aprender mais

| Pergunta | Arquivo |
|---|---|
| Como montar um router novo? | `app/main.py` (final do `create_app`) + `app/api/v1/customer_routes.py` |
| Como declarar uma model? | `app/infrastructure/db/models/cadastro.py` (`Cliente` é o template) |
| Como escrever um port? | `app/domain/ports/payment_gateway.py` |
| Como escrever um adapter? | `app/infrastructure/adapters/whisper_api_adapter.py` |
| Como criar uma task Celery? | `app/workers/tasks/generate_monthly_installments.py` |
| Como criar um asset module? | `app/modules/vehicles/module.py` + `app/core/assets/module_interface.py` |
| Como criar um canal de mensageria? | `app/core/channels/registry.py` + `app/domain/ports/message_channel.py` |
| Como funciona o agente? | `app/core/agent/orchestrator.py` |
| Cálculos financeiros canônicos | `app/domain/finance/calculations.py` |
| Convenções globais (Pablo) | `CLAUDE.md` global em `C:\Users\Pablo\.claude\` |
| Estado do projeto / épicos | `_bmad-output/` |
| DDL completa do banco | `docs/ddl/schema_v2.sql` |
| Arquitetura de mensageria | `docs/architecture-messaging-channels.md` |
| Recorrência + cobrança | `docs/architecture-recurrence-and-collection.md` |

---

## 23. Antipadrões a evitar (visto em PRs já rejeitados)

1. **Importar `infrastructure/` dentro de `domain/`** — quebra hexagonal. Se precisar de IO no domínio, está modelando errado.
2. **Calcular juros/multa dentro de rota** — sempre delegue a `app/domain/finance/calculations.py`.
3. **Filtrar por `empresa_id` na rota e esquecer no repo** — quebra isolamento. Filtre no repo.
4. **`get_event_loop().run_until_complete()` em task Celery** — use `asyncio.run()`. Deprecado em Python 3.12.
5. **Salvar segredos em colunas plain** — use `credenciais_integracao.config` JSONB (e idealmente criptografe com `mfa_secret_enc` style).
6. **Adicionar campo direto em JSONB porque "é mais rápido"** — se vai filtrar ou indexar, vire coluna.
7. **Criar repo novo sem `_base_query()` filtrando `excluido_em IS NULL`** — vaza dados soft-deleted.
8. **Esquecer de propagar `correlation_id` para Celery** — perde rastreabilidade ponta-a-ponta.
9. **Body de request aceitando `empresa_id`** — buraco de segurança. Sempre derive de `current_user`.
10. **`alert()` ou `confirm()` no frontend** — proibido. Use `ToastService` / `ConfirmService`.

---

## 24. Glossário rápido PT-BR ↔ EN

| PT-BR (canônico) | EN (legado / synonym) |
|---|---|
| `empresa` | `tenant`, `company` |
| `usuario` | `user` |
| `perfil` | `role` |
| `permissao` | `permission` |
| `cliente` | `customer` |
| `fornecedor` | `supplier` |
| `veiculo` | `vehicle`, `asset` |
| `contrato` | `contract` |
| `titulo_receber` | `installment`, `receivable` |
| `titulo_pagar` | `payable` |
| `movimento_titulo_receber` | `installment_adjustment` |
| `lote_geracao` | `installment_generation`, `batch` |
| `evento_contrato` | `contract_event` |
| `conversa` | `conversation` |
| `mensagem` | `message` |
| `configuracao_sistema` | `system_setting` |
| `credencial_integracao` | `integration_credential` |
| `log_auditoria` | `audit_log` |
| `log_eventos` | `event_log` |
| `webhook_bruto` | `webhook_event_raw` |
| `criado_em / atualizado_em / excluido_em` | `created_at / updated_at / deleted_at` |

Quando em dúvida sobre o nome: olhe `app/infrastructure/db/models/__init__.py` — todos os aliases EN→PT estão lá.

---

**Fim.** Se algo neste documento divergir do código real, **o código vence** — abra PR atualizando o documento.
