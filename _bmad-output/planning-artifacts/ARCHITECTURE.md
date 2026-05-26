# ARCHITECTURE — {{product_name}} (Fullstack)

> **Método:** BMAD — Architect Phase (Winston)
> **Tipo:** Greenfield Fullstack
> **Stack Confirmada:** Python 3.12 + FastAPI + PostgreSQL 16 + Redis 7 + MinIO | Angular 21+ Standalone + Signals + Tailwind v4 + Heroicons
> **Tema Central:** Plug-and-Play através de **Ports & Adapters** (Hexagonal Architecture) com **Asset Abstraction Layer** para módulos verticais
> **Versão:** 2.0
> **Data:** 07/05/2026
> **Documentos relacionados:** `PRD.md`, `angular-structure.md`, `frontend_architecture_manifesto.md`

---

## 1. Introdução

### 1.1 Propósito

Este documento descreve **a arquitetura técnica completa** do {{product_name}}, transformando os requisitos do PRD em um blueprint executável: estilo arquitetural, tecnologias precisas, modelos de dados, contratos de API, estrutura de pastas, fluxos críticos, padrões de erro, segurança, performance, testes e deploy. É a fonte única da verdade para qualquer dev humano ou agente AI implementar features sem ambiguidade.

{{product_name}} é uma **plataforma genérica de cobrança recorrente e gestão de recebimentos** com módulos verticais plugáveis por tipo de ativo. O primeiro módulo vertical é **Vehicles** (gestão de frotas de aluguel), mas a arquitetura suporta qualquer vertical — imóveis, equipamentos, maquinário, etc. — sem alteração no Core.

### 1.2 Filosofia Arquitetural

- **Domain-Driven Design (DDD) leve**: domínio puro no centro, infraestrutura na periferia, dependências apontam para dentro.
- **Hexagonal (Ports & Adapters)**: toda integração externa é uma Port (interface) com 1+ Adapter implementando-a; troca de fornecedor não toca regras de negócio.
- **Core + Module Separation**: o núcleo da plataforma (billing, collections, reconciliation, auth) é completamente independente de qualquer vertical de ativo. Módulos verticais se registram via `IAssetModule` e reagem a Domain Events do Core.
- **CQRS leve onde fizer sentido**: leituras de relatórios podem usar projections/views materializadas; escritas no domínio rico.
- **Event sourcing seletivo**: contratos e títulos têm log de eventos imutável (`contract_events`, `installment_adjustments`, `audit_log`); o resto é state-based clássico.
- **Async first**: FastAPI async, SQLAlchemy 2 async, Celery para jobs longos, fila Redis Streams para eventos de webhook.
- **Functional Core, Imperative Shell**: cálculos financeiros (juros, multa, score, ROI) são funções puras testáveis; I/O fica nos services.
- **Boring tech wins**: PostgreSQL faz tudo (relacional, JSONB, full-text, vetorial via `pgvector`, fila leve via `LISTEN/NOTIFY` opcional). Apenas adicionamos especialista quando PG não dá conta.
- **Default payment = Pix via WhatsApp (custo zero)**: o sistema gera QR Code Pix estático/dinâmico próprio e envia via WhatsApp. Gateways de pagamento (Asaas, Stripe, Efi) são **plugins opcionais** — nunca obrigatórios.

### 1.3 Decisões Arquiteturais Críticas (Sumário)

| Decisão                                  | Escolha                       | Justificativa Curta                                                              |
|------------------------------------------|-------------------------------|----------------------------------------------------------------------------------|
| Real-time geral (notificações, dashboards) | **SSE**                      | Unidirecional, leve, reconexão nativa, atrás de proxy reverso fácil.             |
| Real-time chat WhatsApp                  | **WebSocket**                 | Bidirecional, baixíssima latência para typing/leitura/envio.                     |
| Polling                                  | **Fallback only**             | Apenas se SSE/WS falhar (degraded mode).                                         |
| ORM                                      | **SQLAlchemy 2 (async + typed)** | Ecossistema maduro, migrations Alembic, suporte completo a PG.                  |
| Workers                                  | **Celery + Redis**            | Ecossistema vasto, beat embutido para cron, retry policies prontas.              |
| Vetorial (RAG)                           | **pgvector**                  | Roda no PG já presente, evita Qdrant/Weaviate como dependência separada.         |
| Storage de arquivos                      | **MinIO** (S3-compatible)     | Self-hosted, plug-and-play para AWS S3 / R2 / B2 sem alterar código.             |
| Auth                                     | **JWT RS256 + refresh cookie**| Stateless, segredo só no backend (chave privada), refresh em cookie HttpOnly.    |
| Frontend state                           | **Signals + resource() API**  | Conforme manifesto do cliente; zero NgRx; estado local-first.                    |
| Estilo                                   | **Tailwind v4 + tokens shadcn-like** | Conforme manifesto; tudo via variáveis CSS.                                |
| LLM default                              | **OpenAI GPT-4o (config-able)** | Custo/qualidade/latência atual; trocável por adapter para Claude/Gemini/Ollama. |
| WhatsApp default                         | **Evolution API (self-hosted)**| Open-source, custo zero por mensagem, sob controle do cliente.                  |
| Bank reconciliation default              | **OFX + PDF parsing local**   | Sem custo recorrente; Pluggy é adapter opcional pago.                            |
| Containerização                          | **Docker** (compose dev / k8s ou Coolify prod) | Ubíquo, simples.                                                |
| Pagamento default                        | **Pix via WhatsApp (sem gateway)**| Custo zero; gateways são plugins opcionais.                                 |
| Modularização de ativos                  | **Asset Abstraction Layer + IAssetModule** | Core genérico; verticais plugáveis por asset_type.                   |

### 1.4 Glossário

- **Port**: interface (Protocol em Python, abstract class) que define contrato com mundo externo.
- **Adapter**: implementação concreta de uma Port (ex.: `EvolutionApiAdapter` implementa `IWhatsAppGateway`).
- **Use Case** (alias: Service / Application Service): orquestra lógica de domínio + adapters para resolver uma intenção do usuário.
- **Repository**: porta para persistência (esconde SQL).
- **Domain Event**: fato imutável que ocorreu no domínio (ex.: `InstallmentPaid`, `InstallmentOverdue`).
- **Module Hook**: handler registrado por um módulo vertical que reage a Domain Events do Core, roteado por `asset_type`.
- **DTO**: Data Transfer Object — Pydantic models para entrada/saída de API.
- **Schema**: SQLAlchemy ORM model (na infraestrutura).
- **Entity**: objeto de domínio com identidade (ex.: `Customer`).
- **Value Object**: objeto imutável sem identidade (ex.: `Money`, `Cpf`, `PhoneE164`).
- **Asset**: entidade genérica representando qualquer bem sob contrato recorrente (veículo, imóvel, equipamento).
- **Vertical Module**: pacote plugável que especializa o comportamento do Core para um tipo de ativo (ex.: `vehicles`, `properties`).

#### Termos do Domínio Financeiro (Épico 12+, nomenclatura PT-BR)

- **parcela**: título de pagamento mensal gerado para cobrir o uso do veículo durante o período de locação. Não é uma prestação de financiamento — é a contraprestação pelo uso.
- **opcao_compra**: título único e opcional gerado ao final do contrato. Se pago pelo cliente, transfere a propriedade do veículo. Apenas 1 por contrato (enforced por unique index).
- **saldo_devedor**: soma dos títulos do tipo `parcela` em status `vencido` de um determinado contrato. Calculado como `SUM(titulos WHERE tipo='parcela' AND status='vencido')`. NÃO é o valor residual total do contrato — é apenas o montante em atraso no momento da consulta.
- **passivo_inoperante**: saldo em atraso de um contrato já encerrado. O contrato não existe mais operacionalmente, mas a dívida persiste vinculada ao CPF do cliente. Registrado na tabela `passivos_inoperantes`.
- **politica_cobranca**: conjunto de parâmetros que regem a automatização do motor de cobrança (carência, multa, juros, limites de suspensão e encerramento). Única por empresa.
- **motor de cobrança**: conjunto de workers Celery (coordinators + workers de lote) responsável por gerar títulos, aplicar encargos, enviar notificações e acionar bloqueios de acordo com a política configurada.
- **coordinator**: task Celery leve que roda no Beat, consulta IDs elegíveis via `SELECT FOR UPDATE SKIP LOCKED`, e fragmenta o trabalho em lotes (chunks de 50) despachados para workers especializados. Não executa lógica de negócio diretamente.
- **execucao_motor**: registro de auditoria de cada rodada do motor de cobrança; armazena totais processados, erros e duração.

### 1.5 Change Log

| Data       | Versão | Descrição                                                          | Autor |
|------------|--------|--------------------------------------------------------------------|-------|
| 07/05/2026 | 1.0    | Criação inicial a partir do PRD                                    | Winston (Architect) |
| 07/05/2026 | 2.0    | Reescrita completa: Core genérico + Asset Abstraction Layer + Modules | Winston (Architect) |
| 22/05/2026 | 3.0    | Adição: arquitetura de 7 filas Celery; padrão fan-out coordinator; inventário de 32 tasks; modelo de negócio locação com opção de compra; novas tabelas (tipo_titulo, politica_cobranca, passivos_inoperantes, execucoes_motor); máquina de estados do contrato (7 transições); ADR sobre Python vs Go para workers; convenção PT-BR para domínio financeiro (Épico 12+); expansão do glossário | Winston (Architect) |

---

## 2. Arquitetura em Alto Nível

### 2.1 Visão Geral em uma Frase

> {{product_name}} é uma **plataforma web fullstack de cobrança recorrente e gestão de recebimentos** com SPA Angular consumindo API REST/SSE/WebSocket FastAPI, persistindo em PostgreSQL e MinIO, com workers Celery processando webhooks, jobs agendados e um **Agent Orchestrator IA** multi-canal (WhatsApp + chat in-app) com tools gated por RBAC (cobrança como caso de uso primário), **abstraindo todo fornecedor externo via Ports & Adapters e todo vertical de ativo via Asset Abstraction Layer com módulos plugáveis** — sendo o primeiro módulo **Vehicles** (gestão de frotas).

### 2.2 Diagrama de Sistemas (C4 — Nível 1)

```mermaid
flowchart LR
    User[Usuário Gestor / Operador / Validador] -->|HTTPS| Web[Angular SPA<br/>frontend]
    Client[Cliente / Locatário] -->|WhatsApp| WAGW[(WhatsApp Gateway<br/>Evolution / Z-API / Cloud)]
    Web -->|REST + SSE + WS| API[FastAPI<br/>api]
    API <-->|SQL| DB[(PostgreSQL 16<br/>+ pgvector)]
    API <-->|Cache + Pub/Sub| Redis[(Redis 7)]
    API <-->|Object Store| MinIO[(MinIO / S3)]
    API -->|Enqueue| Workers[Celery Workers]
    Workers <-->|Read/Write| DB
    Workers <-->|Cache| Redis
    Workers <-->|Files| MinIO
    Workers <-->|HTTP| WAGW
    Workers <-->|HTTP| ModuleAPIs[(Module-specific APIs<br/>FIPE, Tracker, etc.)]
    Workers <-->|HTTP| OF[(Open Finance / Pluggy)]
    Workers <-->|HTTP| LLM[(LLM Provider<br/>OpenAI / Claude / Gemini / Ollama)]
    Workers <-->|HTTP| PIX[(Gateway Pix opcional<br/>Asaas / Efi / Stripe)]
    WAGW -->|Webhook| API
    OF -->|Webhook| API
    PIX -->|Webhook| API
```

### 2.3 Diagrama de Containers (C4 — Nível 2)

```mermaid
flowchart TB
    subgraph Browser["Browser do Usuário"]
        SPA[Angular SPA<br/>Standalone + Signals]
        SW[Service Worker<br/>PWA]
    end

    subgraph Edge["Edge / Reverse Proxy"]
        NG[Nginx / Traefik / Caddy<br/>TLS, rate limit, gzip]
    end

    subgraph App["Application Tier"]
        API[FastAPI<br/>uvicorn workers async]
        WS[WebSocket Hub<br/>FastAPI + Redis Pub/Sub]
        BEAT[Celery Beat<br/>scheduler]
        WORK[Celery Workers<br/>X processes]
    end

    subgraph Data["Data Tier"]
        PG[(PostgreSQL 16<br/>com pgvector)]
        RD[(Redis 7<br/>cache + queue + pubsub)]
        MN[(MinIO<br/>S3-compatible)]
    end

    subgraph Adapters["External (via Adapters)"]
        EV[Evolution API]
        MAPI[Module APIs<br/>FIPE, Tracker, etc.]
        OF[Pluggy]
        LL[LLM Provider]
    end

    SPA --> NG
    NG --> API
    NG --> WS
    SPA -.SSE/WS.-> NG
    API --> PG
    API --> RD
    API --> MN
    API --> WS
    WS --> RD
    BEAT --> WORK
    WORK --> PG
    WORK --> RD
    WORK --> MN
    WORK --> EV
    WORK --> MAPI
    WORK --> OF
    WORK --> LL
    EV -.webhook.-> NG
    OF -.webhook.-> NG
```

### 2.4 Padrão Arquitetural por Camada (Backend)

```mermaid
flowchart TB
    HTTP[HTTP Layer<br/>FastAPI Routers + DTOs] --> APP[Application Layer<br/>Use Cases / Services]
    APP --> DOM[Domain Layer<br/>Entities + VOs + Domain Services<br/>+ Ports + Events]
    APP --> INFRA[Infrastructure Layer<br/>Adapters + Repositories<br/>+ External Clients]
    APP --> MOD[Modules Layer<br/>Vertical Modules<br/>vehicles / properties / ...]
    INFRA -.implements.-> DOM
    MOD -.implements IAssetModule.-> DOM
    MOD -.listens to Domain Events.-> DOM
    style DOM fill:#fef3c7,stroke:#92400e
    style APP fill:#dbeafe,stroke:#1e40af
    style HTTP fill:#dcfce7,stroke:#166534
    style INFRA fill:#fce7f3,stroke:#9f1239
    style MOD fill:#e0e7ff,stroke:#3730a3
```

**Regra de dependência**: setas só apontam para dentro (HTTP -> APP -> DOM <- INFRA/MOD). O domínio nunca importa nada de infraestrutura. Adapters e Modules implementam ports definidos no domínio.

### 2.5 Padrão Arquitetural por Camada (Frontend)

Conforme `frontend_architecture_manifesto.md`:

```mermaid
flowchart TB
    PAGES[Feature Components<br/>features/system/...] --> SHARED[Shared Components<br/>shared/components/...]
    PAGES --> CORE[Core Services<br/>core/services + signals]
    SHARED --> CORE
    CORE --> API[API Client<br/>HttpClient + interceptors]
    style CORE fill:#fef3c7,stroke:#92400e
    style PAGES fill:#dcfce7,stroke:#166534
    style SHARED fill:#dbeafe,stroke:#1e40af
    style API fill:#fce7f3,stroke:#9f1239
```

- **Estado**: signals locais nos componentes; signal services em `core/` apenas para estado verdadeiramente global (auth, theme, notifications, current-user).
- **Data fetching**: API `resource()` do Angular 21 (substitui RxJS para casos comuns), com `inject(HttpClient)`.
- **Roteamento**: lazy loading por feature shell (`auth.routes.ts`, `system.routes.ts`).
- **Reatividade**: `computed()` para derivações; `effect()` apenas em side-effects controlados.

### 2.6 Preocupações Transversais

- **Logging**: `structlog` no Python emitindo JSON em stdout, capturado por loki/promtail ou outro sink.
- **Tracing**: OpenTelemetry SDK auto-instrumenting FastAPI/SQLAlchemy/HTTPX/Celery; export OTLP para Tempo/Jaeger.
- **Métricas**: `prometheus-fastapi-instrumentator` em `/metrics`.
- **Correlation ID**: middleware injeta UUID por request; propagado via header `X-Request-Id` para workers e adapters.
- **i18n**: backend devolve códigos de erro estruturados; frontend traduz com Angular i18n nativo (compile-time).
- **Feature flags**: tabela `feature_flags` + serviço simples; flags lidas em runtime sem deploy.

---

## 3. Tech Stack — Tabela Definitiva

> **REGRA**: nenhum membro do time (humano ou IA) pode introduzir tecnologia fora desta tabela sem ADR aprovado em `docs/adrs/`.

### 3.1 Backend

| Categoria              | Tecnologia                            | Versão           | Propósito                                              | Notas |
|------------------------|---------------------------------------|------------------|--------------------------------------------------------|-------|
| Linguagem              | Python                                | 3.12+            | Runtime                                                | Type hints obrigatórios. |
| Web Framework          | FastAPI                               | >= 0.115          | API REST + WebSocket + SSE                             | Async-first.            |
| ASGI Server            | uvicorn (com `--workers`) ou Granian | >= 0.30           | Process model                                          | Granian opcional para perf. |
| Validação / DTO        | Pydantic                              | v2 (>= 2.9)       | Schemas in/out                                         | `model_config` strict. |
| ORM                    | SQLAlchemy                            | 2.x async        | Persistência                                            | `Mapped[T]` typed. |
| Migrations             | Alembic                               | >= 1.13           | Versionamento de schema                                | Gerenciado por scripts. |
| Banco                  | PostgreSQL                            | 16+              | Banco principal                                         | + extensões `pgcrypto`, `pg_trgm`, `pgvector`, `unaccent`. |
| Cache + Queue + PubSub | Redis                                 | 7+               | Caching, broker Celery, fila webhook, pubsub WS        |  |
| Workers                | Celery                                | >= 5.4            | Jobs assíncronos + cron                                 | Beat para agendados. |
| HTTP Client            | httpx                                 | >= 0.27           | Chamadas a adapters externos                           | Async, retries via `tenacity`. |
| Resilience             | tenacity                              | >= 9              | Retry/backoff/circuit breaker                          |  |
| Auth Tokens            | python-jose                           | >= 3.3            | JWT RS256                                              |  |
| Hashing                | argon2-cffi                           | >= 23             | Senhas                                                  |  |
| OCR                    | pytesseract + opencv-python           | latest           | Leitura de comprovantes                                 | Pré-processamento OpenCV. |
| Audio Transcription    | openai (Whisper API)                  | >= 1.40           | Transcrição de áudio para texto                         | Port `IAudioTranscriber`; alternativas: whisper.cpp local, Google Speech, Azure Speech. |
| LLM SDK                | LiteLLM **ou** próprio                | >= 1.40           | Abstração multi-provider                                | LiteLLM facilita troca. |
| PDF Render             | WeasyPrint                            | >= 62             | Contratos                                              | Templates Jinja2. |
| PDF Read               | pdfplumber                            | >= 0.11           | Extratos PDF                                            |  |
| OFX Parser             | ofxparse                              | >= 0.21           | Importação OFX                                         |  |
| Pix BR Code            | pix-utils (ou própria)                | latest           | QR Code estático                                        |  |
| Storage SDK            | boto3                                 | >= 1.34           | Cliente S3-compatible                                   | Configurável endpoint MinIO. |
| Logs                   | structlog                             | >= 24             | JSON logs                                               |  |
| Tracing                | OpenTelemetry SDK                     | >= 1.27           | Instrumentação                                          |  |
| Metrics                | prometheus-fastapi-instrumentator     | >= 7              | `/metrics`                                              |  |
| Test Framework         | pytest + pytest-asyncio + pytest-cov  | latest           | Tests                                                   |  |
| Test DB / containers   | testcontainers                        | latest           | Postgres real em CI                                     |  |
| Contract Tests         | schemathesis                          | >= 3.36           | Property tests sobre OpenAPI                            |  |
| Lint                   | ruff                                  | latest           | Linter + formatter                                      |  |
| Type Check             | mypy strict                           | latest           | Type safety                                             |  |
| Dependency Mgmt        | uv                                    | latest           | Resolver + virtualenv ultrarrápido                      | Alternativa: poetry. |

### 3.2 Frontend

| Categoria              | Tecnologia                       | Versão        | Propósito                            | Notas |
|------------------------|----------------------------------|---------------|---------------------------------------|-------|
| Linguagem              | TypeScript                       | >= 5.6         | Tudo                                   | `strict: true`. |
| Framework              | Angular                          | 21+ standalone| SPA                                    | Sem NgModules. |
| Reatividade            | Signals + resource() + rxjs (legacy mínimo) | nativo Angular 21 | Estado e dados | RxJS apenas onde resource não cobre. |
| Styling                | Tailwind CSS                     | v4            | Utility-first                          | Tudo via classes utilitárias. |
| Design System          | Tokens shadcn-like (próprio)     | —             | Variáveis CSS em `:root`               | Conforme manifesto. |
| Ícones                 | @ng-icons/core + @ng-icons/heroicons | latest    | Iconografia única                       |  |
| Forms                  | Reactive Forms tipados           | nativo        | Forms                                   |  |
| Routing                | Angular Router                   | nativo        | Lazy by feature                         |  |
| HTTP                   | HttpClient + interceptors         | nativo        | API calls                               |  |
| WebSocket              | RxJS WebSocketSubject **ou** native WebSocket wrapper | nativo | Chat WhatsApp |  |
| SSE                    | EventSource API + wrapper         | nativo        | Notificações                            |  |
| Drag-and-Drop          | @angular/cdk/drag-drop            | nativo CDK    | Conciliação, schedule builder           |  |
| Charts                 | ngx-echarts (ECharts)             | latest        | Gráficos sofisticados                   | Alternativa: Chart.js. |
| Map                    | Leaflet + @asymmetrik/ngx-leaflet | latest        | Mapa de ativos (ex.: frota)            | OSM tiles default. |
| PDF Viewer (in-app)    | ngx-extended-pdf-viewer           | latest        | Visualizar contratos                    |  |
| Image Crop             | ngx-image-cropper                 | latest        | Foto perfil cliente                     |  |
| Rich Text Editor       | Tiptap                            | latest        | Cláusulas de contrato + templates IA    |  |
| Toast / Notifications  | Próprio em `shared/components/toast` | —          | Stack unificada                         |  |
| Date utils             | date-fns                          | >= 3           | Datas                                   | ISO + tz America/Sao_Paulo. |
| BR Validators          | @brazilian-utils/brazilian-utils  | latest        | CPF, CNPJ, CEP, placa                   |  |
| Build                  | Angular CLI + esbuild             | latest        | Bundler                                 |  |
| Testing                | Vitest + @ngneat/spectator        | latest        | Unit / component                        |  |
| E2E                    | Playwright                        | latest        | Fluxos críticos                         |  |
| Lint                   | ESLint + @angular-eslint          | latest        | Lint                                    |  |
| Format                 | Prettier                          | latest        | Format                                  |  |
| Style Lint             | stylelint                         | latest        | CSS                                     |  |
| Storybook              | Storybook for Angular             | latest        | Catálogo de componentes                 |  |

### 3.3 Infraestrutura e Operações

| Categoria              | Tecnologia                       | Propósito                              |
|------------------------|----------------------------------|-----------------------------------------|
| Container              | Docker + BuildKit                | Imagens                                  |
| Orquestração (dev)     | docker-compose                    | Stack local                              |
| Orquestração (prod)    | Coolify / Dokploy / k8s          | A definir com cliente                    |
| Reverse Proxy          | Caddy ou Traefik                  | TLS automático                           |
| CI/CD                  | GitHub Actions                    | Pipeline                                 |
| Observability          | Prometheus + Grafana + Loki + Tempo | Métricas/logs/traces                  |
| Secrets                | HashiCorp Vault ou Doppler        | Gerenciamento                            |
| Backup                 | wal-g + s3 ou rclone              | DB + Object store                        |

---

## 4. Modelos de Dados (Domínio)

### 4.1 Bounded Contexts

```mermaid
flowchart LR
    Identity[Identity & Access<br/>users, roles, permissions, audit_log]
    Assets[Asset Registry<br/>assets, asset_modules,<br/>module_hooks_config]
    Catalog[Catalog<br/>customers, suppliers,<br/>expense_categories]
    Contracts[Contracts<br/>contracts, installments,<br/>contract_events]
    Finance[Finance<br/>payables, recurring_payables,<br/>installment_adjustments,<br/>bank_transactions]
    Collections[Collections<br/>conversations, messages,<br/>agent_runs, score_history]
    Integrations[Integrations<br/>webhook_events_raw,<br/>integration_credentials]
    Reports[Reports<br/>saved_reports]
    VehiclesMod[Module: Vehicles<br/>vehicles, vehicle_acquisitions,<br/>tracker_devices]

    Contracts --> Catalog
    Contracts --> Assets
    Finance --> Contracts
    Finance --> Catalog
    Collections --> Catalog
    Collections --> Finance
    Reports --> Finance
    Reports --> Contracts
    Reports --> Collections
    VehiclesMod -.-> Assets
    VehiclesMod -.-> Integrations
```

### 4.2 Entidades e Value Objects (visão de domínio)

#### Identidade

- **User** (Entity): `id`, `email`, `password_hash`, `full_name`, `is_active`, `is_mfa_enabled`, `mfa_secret_encrypted`, timestamps. Relacionamento N:N com `Role` via `user_roles`.
- **Role** (Entity): `id`, `name`, `description`. Relacionamento N:N com `Permission`.
- **Permission** (Value-like): `id`, `code` (`customers.create`, `installments.write_off`, etc), `description`.
- **AuditLogEntry** (immutable): `id`, `user_id`, `action`, `entity`, `entity_id`, `payload_before` (JSONB), `payload_after` (JSONB), `ip`, `user_agent`, `signature_hmac`, `created_at`. Append-only.

#### Registro de Ativos (Core)

- **Asset** (Entity, genérico): `id`, `asset_type` (ex.: `vehicle`, `property`, `equipment`), `name`, `status` (`disponivel`/`em_contrato`/`manutencao`/`inativo`), `metadata` (JSONB — campos universais), `module_data` (JSONB — dados específicos do módulo), `created_by_user_id`, timestamps, soft delete.
- **AssetModule** (Entity, registry): `id`, `asset_type`, `display_name`, `is_active`, `config` (JSONB), `hooks_class_path`, `routes_module_path`.
- **ModuleHooksConfig** (Entity): `id`, `asset_module_id`, `event_type` (ex.: `InstallmentOverdue`), `policy` (JSONB — ex.: `{auto_block: true, min_days_overdue: 15, requires_approval: true}`), `is_active`.

#### Catálogo

- **Customer** (Entity): `id`, `full_name`, `cpf` (VO `Cpf`), `rg`, `cnh` (VO `Cnh` com number/category/expiry), `phone` (VO `PhoneE164`), `email`, `address` (VO `Address`), `birth_date`, `photo_url`, `status` (`ativo`/`inativo`/`bloqueado`), `score`, `tags` (JSONB), `notes`, `created_by_user_id`, soft delete.
- **CustomerAttachment** (Entity child): `id`, `customer_id`, `kind` (cnh/rg/comprovante/outros), `url`, `mime`, `size`, `uploaded_at`.
- **Supplier** (Entity): `id`, `name`, `document`, `contact`, `bank_data` (JSONB).
- **ExpenseCategory** (Entity): `id`, `parent_id`, `name`, `color`, `icon`, `is_active`.

#### Módulo: Veículos (vertical — não pertence ao Core)

- **Vehicle** (Entity, module-specific): `id`, `asset_id` (FK -> assets), `plate` (VO `Plate`), `renavam`, `chassis`, `brand`, `model`, `version`, `year_model`, `year_manufacture`, `color`, `fuel`, `km_initial`, `km_current`, `acquisition_date`, `purchase_value` (VO `Money`), `fipe_code`, `fipe_value_current` (Money), `fipe_value_updated_at`, `tracker_device_id`, `category`, `insurance_*`, `ipva_*`, `licensing_*`.
- **VehicleAcquisition** (Entity 1:1 com Vehicle): `id`, `vehicle_id`, `type` (`a_vista`/`financiamento`/`consorcio`/`custom`), `down_payment` (Money), `installments_definition` (JSONB), `interest_rate_pct_per_month`, `amortization_system` (`price`/`sac`/`null`), `notes`.
- **VehiclePhoto** (Entity child).
- **TrackerDevice** (Entity, module-specific): `id`, `external_id`, `vehicle_id`, `provider`, `last_seen_at`, `last_position` (JSONB com lat/lng/speed/ignition).

#### Contratos

- **Contract** (Aggregate Root): `id`, `customer_id`, `asset_id` (FK -> assets, genérico), `status`, `start_date`, `end_date`, `total_amount` (Money), `periodicity` (`diaria`/`semanal`/`quinzenal`/`mensal`), `due_day`, `late_interest_pct_per_day`, `late_fine_pct`, `grace_days`, `has_purchase_option`, `residual_value`, `terms_md`, `pdf_url`, `version`, `created_by_user_id`, `signed_at`, soft delete.
- **Installment** (Entity child de Contract): `id`, `contract_id`, `sequence`, `due_date`, `amount` (Money), `kind` (`regular`/`down_payment`/`extra_semestral`/`extra_anual`/`custom`), `status` (`em_aberto`/`vencido`/`pago_aguardando_verificacao`/`pago`/`pago_parcial`/`renegociado`/`cancelado`), `paid_at`, `paid_amount`, `payment_method`, `receipt_url`, `notes`.
- **InstallmentAdjustment** (Entity child de Installment, append-only): `id`, `installment_id`, `kind` (`discount`/`fine`/`interest`/`renegotiation`/`bulk_edit`/`partial_payment`/`reverse_write_off`), `amount_delta`, `reason`, `applied_by_user_id`, `applied_at`. Snapshot de cada mudança financeira. O kind `partial_payment` registra pagamento parcial e referencia o novo título gerado para a diferença.
- **ContractEvent** (Entity child, append-only): `id`, `contract_id`, `event_type`, `payload` (JSONB), `created_by_user_id`, `created_at`.

#### Máquina de Estados do Contrato

O contrato percorre os seguintes estados ao longo de seu ciclo de vida:

```
rascunho
    └─► ativo (ao ativar o contrato)
          ├─► suspenso (automático: limite_dias_suspensao atingido)
          │       └─► ativo (pagamento confirmado restaura)
          ├─► encerrado_sem_pendencia (cancelamento limpo — sem títulos em aberto)
          ├─► encerrado_com_pendencia (cancelamento com atraso → gera passivo_inoperante)
          ├─► encerrado_compra (opcao_compra paga → evento OpcaoCompraPaga → veículo alienado)
          └─► rescindido (acordo formal de rescisão)
```

**Regras de transição:**
- `rascunho → ativo`: apenas via `POST /contracts/{id}/activate`; gera parcelas + PDF.
- `ativo → suspenso`: automático pelo motor de cobrança após `politica_cobranca.limite_dias_suspensao` dias de atraso; registra `ContractEvent(event_type='suspenso')`.
- `suspenso → ativo`: automático ao confirmar pagamento que zera saldo devedor; registra `ContractEvent(event_type='reativado')`.
- `ativo → encerrado_compra`: ao confirmar pagamento de título do tipo `opcao_compra`; emite Domain Event `OpcaoCompraPaga` que o módulo Vehicles captura para alienar o veículo.
- `ativo/suspenso → encerrado_com_pendencia`: ao atingir `politica_cobranca.limite_dias_encerramento`; títulos restantes viram `passivos_inoperantes`.
- `ativo → rescindido`: via endpoint de rescisão com cálculo de proporcional.

#### Financeiro

- **Payable** (Entity): `id`, `description`, `supplier_id`, `category_id`, `asset_id` (nullable, FK -> assets), `amount` (Money), `due_date`, `status` (`em_aberto`/`pago`/`cancelado`), `paid_at`, `paid_amount`, `payment_method`, `attachment_url`, `notes`, `created_by_user_id`, `recurring_template_id` (nullable).
- **RecurringPayableTemplate** (Entity): `id`, `description`, `supplier_id`, `category_id`, `asset_id`, `amount`, `periodicity` (`mensal`/`bimestral`/`anual`), `day_of_month`, `start_date`, `end_date`, `is_active`.
- **BankTransaction** (Entity): `id`, `account_id`, `fitid`, `posted_at`, `amount` (signed), `description_raw`, `description_clean`, `type`, `status` (`pendente`/`conciliada`/`ignorada`), `reconciled_to_kind` (`installment`/`payable`/null), `reconciled_to_id`, `imported_from`, `imported_at`.
- **BankAccount** (Entity): `id`, `name`, `bank_code`, `agency`, `account_number`, `type`, `is_active`.

#### Orquestrador de Agentes e Mensageria (WhatsApp + Chat In-App)

- **Conversation** (Entity): `id`, `customer_id`, `channel` (`whatsapp`/`in_app`), `phone_e164` (nullable — only for WhatsApp), `user_id` (nullable — only for in-app), `last_message_at`, `unread_count`, `is_archived`, `agent_active` (bool), `agent_paused_until`.
- **Message** (Entity, append-only): `id`, `conversation_id`, `external_id`, `direction`, `kind` (`text`/`image`/`document`/`audio`/`pix_card`/`system`), `content_text`, `media_url`, `media_mime`, `transcription` (nullable — populated when kind=audio), `sent_at`, `delivered_at`, `read_at`, `sent_by`, `status`, `context` (JSONB), `embedding` (vector(1536), nullable, populado async).
- **AgentRun** (Entity, observability): `id`, `conversation_id`, `triggered_by_message_id`, `caller_id`, `caller_permissions` (JSONB snapshot), `provider`, `model`, `prompt_tokens`, `completion_tokens`, `latency_ms`, `tools_called` (JSONB), `tools_available` (JSONB — snapshot of permission-filtered tool list), `final_action`, `error`, `created_at`. Para auditoria e tuning.
- **CustomerScoreSnapshot** (Entity, daily): `id`, `customer_id`, `score`, `factors` (JSONB com breakdown), `taken_at`.
- **CollectionPolicy** (singleton config): `id`, `name`, `is_active`, `payload` (JSONB com toda a parametrização), `version`, `updated_by`, `updated_at`.

#### Integrações

- **WebhookEventRaw** (Entity, append-only): `id`, `provider`, `external_id`, `signature_valid` (bool), `payload` (JSONB), `received_at`, `processed_at`, `processing_status`. Idempotência por (`provider`, `external_id`).
- **IntegrationCredential** (Entity): `id`, `provider`, `is_active`, `config_encrypted` (bytea — JSON encriptado AES-256-GCM com chave master KMS), `last_tested_at`, `last_test_status`.
- **FeatureFlag** (Entity): `id`, `key`, `value` (JSONB — boolean ou regra), `description`, `updated_at`.

#### Relatórios

- **SavedReport** (Entity): `id`, `name`, `owner_user_id`, `definition` (JSONB com dimensions/measures/filters), `is_shared`, `created_at`.

### 4.3 Pagamentos Parciais (Domínio Financeiro)

Quando `paid_amount < installment.amount`, o sistema trata como **pagamento parcial**:

1. O título original recebe status `pago_parcial` e `paid_amount` registrado.
2. Um `InstallmentAdjustment` com `kind='partial_payment'` é criado, registrando o `amount_delta` (diferença) e o `new_installment_id` no campo `reason` (JSON).
3. Um novo título (Installment) é gerado automaticamente para a diferença (`installment.amount - paid_amount`), com `kind='regular'`, `due_date` = próximo vencimento (ou mesmo dia + grace_days), vinculado ao mesmo contrato.
4. O contrato incrementa seu `sequence` para acomodar o novo título.

```python
# domain/finance/calculations.py
from decimal import Decimal
from dataclasses import dataclass
from datetime import date, timedelta

@dataclass(frozen=True)
class PartialPaymentResult:
    original_new_status: str          # 'pago_parcial'
    remainder_amount: Decimal         # diferença a gerar novo título
    remainder_due_date: date          # vencimento do novo título
    adjustment_delta: Decimal         # valor pago (positivo)

def compute_partial_payment(
    title_amount: Decimal,
    paid_amount: Decimal,
    original_due_date: date,
    grace_days: int = 0,
) -> PartialPaymentResult:
    """Calcula resultado de pagamento parcial. Função pura, sem I/O."""
    assert Decimal("0") < paid_amount < title_amount, "Not a partial payment"
    remainder = title_amount - paid_amount
    remainder_due = original_due_date + timedelta(days=grace_days or 7)
    return PartialPaymentResult(
        original_new_status="pago_parcial",
        remainder_amount=remainder,
        remainder_due_date=remainder_due,
        adjustment_delta=paid_amount,
    )
```

### 4.4 Value Objects (Python — exemplos)

```python
# domain/shared/value_objects.py
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal  # 2 casas para BRL
    currency: str = "BRL"

    def __post_init__(self):
        if self.amount.as_tuple().exponent < -2:
            raise ValueError("Money supports max 2 decimal places")

    def __add__(self, other: "Money") -> "Money":
        if other.currency != self.currency:
            raise ValueError("currency mismatch")
        return Money(self.amount + other.amount, self.currency)

@dataclass(frozen=True, slots=True)
class Cpf:
    value: str  # 11 dígitos

    @classmethod
    def parse(cls, raw: str) -> "Cpf":
        digits = "".join(c for c in raw if c.isdigit())
        if len(digits) != 11 or not _valid_cpf_dv(digits):
            raise ValueError("invalid CPF")
        return cls(digits)

@dataclass(frozen=True, slots=True)
class PhoneE164:
    value: str  # ex: +5571999998888
    # validador no construtor

@dataclass(frozen=True, slots=True)
class Plate:
    value: str  # AAA0A00 ou AAA0000
```

---

## 5. Especificação da API

### 5.1 Convenções

- **Base URL** (prod): `https://api.{{product_name_slug}}.com/api/v1` (ou subpath em mesmo domínio do frontend).
- **Autenticação**: header `Authorization: Bearer <jwt>`; refresh via cookie `HttpOnly`.
- **Versionamento**: prefixo `/v1` na URL; breaking changes vão para `/v2`.
- **Paginação**: query `?page=1&size=50` para listas pequenas; cursor `?cursor=<id>&size=50` para listas grandes (mensagens, audit log).
- **Filtros**: query strings; filtros complexos via `POST /search` quando passar de 10 parâmetros.
- **Erros**: padrão **RFC 7807 Problem Details**.
  ```json
  {
    "type": "https://{{product_name_slug}}.com/errors/installment-not-editable",
    "title": "Installment cannot be edited",
    "status": 409,
    "detail": "Installment 1234 has status 'pago' and is immutable.",
    "instance": "/api/v1/installments/1234",
    "code": "INSTALLMENT_IMMUTABLE",
    "request_id": "01HX..."
  }
  ```
- **Códigos**: 200 (ok), 201 (created), 204 (no content), 400 (bad request), 401 (unauth), 403 (forbidden), 404 (not found), 409 (conflict — regra violada), 422 (validation), 429 (rate limit), 500 (internal).

### 5.2 Endpoints (visão consolidada)

> A documentação OpenAPI completa é gerada automaticamente em `/docs`. Esta tabela é o **mapa mental**.

#### Autenticação
| Método | Path                       | Descrição                              |
|--------|----------------------------|----------------------------------------|
| POST   | `/auth/login`              | Login email/senha                       |
| POST   | `/auth/refresh`            | Renova access token                     |
| POST   | `/auth/logout`             | Invalida refresh                        |
| POST   | `/auth/password/forgot`    | Inicia recuperação                      |
| POST   | `/auth/password/reset`     | Conclui reset com token                 |
| POST   | `/auth/mfa/enable`         | Ativa TOTP                              |
| POST   | `/auth/mfa/verify`         | Verifica código durante login           |

#### Clientes
| Método | Path                                | Descrição                               |
|--------|-------------------------------------|-----------------------------------------|
| GET    | `/customers`                        | Lista paginada com filtros               |
| POST   | `/customers`                        | Cria                                     |
| GET    | `/customers/{id}`                   | Detalhe                                  |
| PATCH  | `/customers/{id}`                   | Atualiza parcial                         |
| DELETE | `/customers/{id}`                   | Soft delete                              |
| GET    | `/customers/{id}/financials`        | KPIs financeiros do cliente              |
| GET    | `/customers/{id}/score-history`     | Histórico de score                        |
| POST   | `/customers/{id}/attachments`       | Upload anexo                             |
| GET    | `/customers/{id}/attachments`       | Lista anexos                             |
| DELETE | `/customers/{id}/attachments/{aid}` | Remove anexo                             |

#### Assets (Core — genérico)
| Método | Path                                  | Descrição                                |
|--------|---------------------------------------|------------------------------------------|
| GET    | `/assets`                             | Lista (filtrável por asset_type)          |
| POST   | `/assets`                             | Cria ativo genérico                       |
| GET    | `/assets/{id}`                        | Detalhe                                   |
| PATCH  | `/assets/{id}`                        | Atualiza                                  |
| GET    | `/assets/{id}/financials`             | KPIs financeiros do ativo                 |

#### Módulo: Veículos (registrado dinamicamente pelo módulo)
| Método | Path                                  | Descrição                                |
|--------|---------------------------------------|------------------------------------------|
| GET    | `/modules/vehicles`                   | Lista veículos                            |
| POST   | `/modules/vehicles`                   | Cria (cria asset + vehicle)               |
| GET    | `/modules/vehicles/{id}`              | Detalhe                                   |
| PATCH  | `/modules/vehicles/{id}`              | Atualiza                                  |
| GET    | `/modules/vehicles/{id}/financials`   | ROI, depreciação, payback                 |
| POST   | `/modules/vehicles/{id}/refresh-fipe` | Força atualização FIPE                    |
| GET    | `/modules/vehicles/{id}/position`     | Posição atual via tracker                 |
| GET    | `/modules/vehicles/{id}/position-history` | Histórico de posições                 |
| POST   | `/modules/vehicles/{id}/block`        | Bloqueia (gated)                          |
| POST   | `/modules/vehicles/{id}/unblock`      | Desbloqueia (gated)                       |
| POST   | `/modules/vehicles/{id}/photos`       | Upload foto                               |
| PUT    | `/modules/vehicles/{id}/acquisition`  | Define/atualiza forma de aquisição        |

#### FIPE (registrado pelo módulo Vehicles)
| Método | Path                                               | Descrição                          |
|--------|----------------------------------------------------|------------------------------------|
| GET    | `/modules/vehicles/fipe/brands?type=car`           | Lista marcas                        |
| GET    | `/modules/vehicles/fipe/models?type=car&brand=XX`  | Lista modelos                       |
| GET    | `/modules/vehicles/fipe/years?...`                 | Lista anos                          |
| GET    | `/modules/vehicles/fipe/price?...`                 | Preço atual                         |

#### Contratos
| Método | Path                                   | Descrição                                  |
|--------|----------------------------------------|--------------------------------------------|
| POST   | `/contracts/preview-schedule`          | Preview de parcelamento                     |
| GET    | `/contracts`                           | Lista                                       |
| POST   | `/contracts`                           | Cria (rascunho)                             |
| GET    | `/contracts/{id}`                      | Detalhe                                     |
| PATCH  | `/contracts/{id}`                      | Atualiza (somente rascunho)                 |
| POST   | `/contracts/{id}/activate`             | Vigente — gera parcelas + PDF                |
| POST   | `/contracts/{id}/terminate`            | Rescinde                                    |
| GET    | `/contracts/{id}/pdf?version=`         | PDF (URL pré-assinada)                      |
| GET    | `/contracts/{id}/events`               | Timeline                                     |
| POST   | `/contracts/{id}/installments/bulk-edit` | Edição em lote                            |

#### Títulos a Receber
| Método | Path                                           | Descrição                              |
|--------|------------------------------------------------|----------------------------------------|
| GET    | `/receivables`                                 | Lista filtrada                         |
| GET    | `/receivables/{id}`                            | Detalhe                                |
| GET    | `/receivables/{id}/updated-value?on_date=`     | Valor com juros/multa/desconto         |
| POST   | `/receivables/{id}/write-off`                  | Baixa manual (com upload de comprovante) |
| POST   | `/receivables/bulk-write-off`                  | Baixa em lote                           |
| POST   | `/receivables/{id}/partial-write-off`          | Baixa parcial (gera título da diferença) |
| POST   | `/receivables/{id}/reverse-write-off`          | Estorna baixa (Admin only)              |
| POST   | `/receivables/{id}/validate`                   | Aprova/rejeita comprovante (Validador)  |
| POST   | `/receivables/{id}/request-resubmission`       | Solicita reenvio                        |
| GET    | `/receivables/{id}/pix-qr`                     | QR Code Pix BR Code                     |
| POST   | `/receivables/renegotiate`                     | Renegocia conjunto                      |
| GET    | `/receivables/validation-queue`                | Fila de comprovantes pendentes          |

#### Títulos a Pagar
| Método | Path                              | Descrição                                |
|--------|-----------------------------------|------------------------------------------|
| GET    | `/payables`                       | Lista                                     |
| POST   | `/payables`                       | Cria                                      |
| GET    | `/payables/{id}`                  | Detalhe                                   |
| PATCH  | `/payables/{id}`                  | Atualiza                                  |
| POST   | `/payables/{id}/pay`              | Baixa                                     |
| POST   | `/payables/quick-pay`             | Cria + baixa atômico                       |
| GET    | `/recurring-payables`             | Lista templates recorrentes                |
| POST   | `/recurring-payables`             | Cria template                              |
| PATCH  | `/recurring-payables/{id}`        | Atualiza                                   |
| POST   | `/recurring-payables/{id}/run-now`| Gera título imediatamente                  |

#### Conciliação
| Método | Path                                          | Descrição                              |
|--------|-----------------------------------------------|----------------------------------------|
| POST   | `/reconciliation/import-ofx`                  | Upload OFX                              |
| POST   | `/reconciliation/import-pdf`                  | Upload PDF de extrato                   |
| POST   | `/reconciliation/sync-open-finance`           | Dispara sync via Pluggy                  |
| GET    | `/reconciliation/transactions`                | Lista transações pendentes               |
| GET    | `/reconciliation/match-suggestions`           | Sugestões de match (auto)                |
| POST   | `/reconciliation/match`                       | Confirma match (1:1, 1:N, N:1)           |
| POST   | `/reconciliation/transactions/{id}/ignore`    | Ignora transação                         |
| POST   | `/reconciliation/unmatched-as-payable`        | Converte transação em payable            |
| POST   | `/reconciliation/unmatched-as-revenue`        | Converte em receita avulsa               |

#### Cobranças (WhatsApp)
| Método | Path                                         | Descrição                              |
|--------|----------------------------------------------|----------------------------------------|
| GET    | `/conversations`                             | Lista                                   |
| GET    | `/conversations/{id}`                        | Detalhe                                 |
| GET    | `/conversations/{id}/messages?cursor=`       | Mensagens (paginação reversa)           |
| POST   | `/conversations/{id}/messages`               | Envia mensagem (humano)                 |
| POST   | `/conversations/{id}/agent/pause`            | Pausa agente                             |
| POST   | `/conversations/{id}/agent/resume`           | Retoma agente                            |
| POST   | `/conversations/{id}/mark-read`              | Marca como lida                          |
| POST   | `/broadcasts`                                | Disparo em massa                         |
| GET    | `/broadcasts/{id}`                           | Status do disparo                        |
| GET    | `/agent/runs`                                | Logs de execução do agente (auditoria)   |

#### Relatórios e Dashboards
| Método | Path                                         | Descrição                              |
|--------|----------------------------------------------|----------------------------------------|
| GET    | `/dashboard/main`                            | KPIs principais                          |
| GET    | `/dashboard/customer/{id}`                   | KPIs do cliente                          |
| GET    | `/dashboard/asset/{id}`                      | KPIs do ativo (ROI, etc)                 |
| GET    | `/reports/built-in/{slug}`                   | Relatório pronto                         |
| POST   | `/reports/saved`                             | Salva relatório custom                    |
| GET    | `/reports/saved`                             | Lista salvos                             |
| POST   | `/reports/run`                               | Executa relatório custom                  |
| GET    | `/reports/{id}/export?format=xlsx|pdf`       | Exporta                                   |

#### Admin / Configuração
| Método | Path                                         | Descrição                              |
|--------|----------------------------------------------|----------------------------------------|
| GET    | `/admin/integrations`                        | Lista status                             |
| PUT    | `/admin/integrations/{provider}`             | Atualiza credenciais                     |
| POST   | `/admin/integrations/{provider}/test`        | Teste de conexão                          |
| GET    | `/admin/users`                               | Lista usuários                           |
| POST   | `/admin/users`                               | Cria usuário                             |
| PATCH  | `/admin/users/{id}/roles`                    | Atualiza papéis                           |
| GET    | `/admin/audit-log?...`                       | Consulta auditoria                        |
| GET    | `/admin/settings`                            | Configurações gerais                      |
| PUT    | `/admin/settings`                            | Atualiza                                  |
| GET    | `/admin/agent/policy`                        | Política de cobrança                      |
| PUT    | `/admin/agent/policy`                        | Atualiza política                         |
| GET    | `/admin/modules`                             | Lista módulos registrados                 |
| PUT    | `/admin/modules/{asset_type}/config`         | Configura módulo                          |
| GET    | `/admin/modules/{asset_type}/hooks`          | Lista hooks do módulo                     |
| PUT    | `/admin/modules/{asset_type}/hooks/{event}`  | Configura política de hook                |

#### Webhooks (públicos, validados por assinatura)
| Método | Path                                         | Descrição                              |
|--------|----------------------------------------------|----------------------------------------|
| POST   | `/webhooks/whatsapp/{provider}`              | WhatsApp inbound                        |
| POST   | `/webhooks/payment-gateway/{provider}`       | Pix gateway plugin (Asaas/Efi/Stripe)   |
| POST   | `/webhooks/open-finance/{provider}`          | Open Finance                             |
| POST   | `/webhooks/module/{asset_type}/{provider}`   | Webhooks específicos de módulo (ex.: tracker) |

#### Real-time
| Path                       | Tipo       | Descrição                                              |
|----------------------------|------------|--------------------------------------------------------|
| `/sse/notifications`       | SSE        | Stream de eventos: nova mensagem, comprovante, alerta. |
| `/sse/dashboard`           | SSE        | Atualizações de KPI ao vivo.                            |
| `/sse/module/{asset_type}` | SSE        | Eventos específicos do módulo (ex.: posições de veículos). |
| `/ws/conversations`        | WebSocket  | Chat WhatsApp bidirecional.                             |

---

## 6. Componentes / Módulos do Backend

Estrutura modular por *bounded context*. Cada módulo tem seus próprios `routers/`, `use_cases/`, `domain/`, `repositories/`, `schemas/` (DTOs). Módulos verticais de ativo vivem em `app/modules/{asset_type}/`.

```
app/
├── api/                            # camada HTTP (FastAPI routers)
│   ├── v1/
│   │   ├── auth_routes.py
│   │   ├── customer_routes.py
│   │   ├── asset_routes.py         # CRUD genérico de assets
│   │   ├── contract_routes.py
│   │   ├── receivable_routes.py
│   │   ├── payable_routes.py
│   │   ├── reconciliation_routes.py
│   │   ├── conversation_routes.py
│   │   ├── dashboard_routes.py
│   │   ├── report_routes.py
│   │   ├── admin_routes.py
│   │   ├── module_routes.py        # monta rotas de módulos dinamicamente
│   │   └── webhook_routes.py
│   ├── sse.py
│   ├── ws.py
│   ├── deps.py                     # FastAPI dependencies (auth, current_user, db_session)
│   ├── exception_handlers.py
│   └── middleware.py
│
├── application/                    # use cases (orquestração)
│   ├── auth/
│   │   ├── login.py
│   │   ├── refresh_token.py
│   │   └── ...
│   ├── customers/
│   │   ├── create_customer.py
│   │   ├── update_customer.py
│   │   └── ...
│   ├── assets/
│   │   ├── create_asset.py
│   │   ├── update_asset.py
│   │   └── ...
│   ├── contracts/
│   │   ├── preview_schedule.py
│   │   ├── create_contract.py
│   │   ├── activate_contract.py
│   │   ├── bulk_edit_installments.py
│   │   ├── terminate_contract.py
│   │   └── render_pdf.py
│   ├── finance/
│   │   ├── write_off_installment.py
│   │   ├── partial_write_off.py    # pagamento parcial
│   │   ├── reverse_write_off.py
│   │   ├── validate_receipt.py
│   │   ├── renegotiate.py
│   │   ├── pay_payable.py
│   │   ├── quick_pay.py
│   │   └── ...
│   ├── reconciliation/
│   │   ├── import_ofx.py
│   │   ├── import_pdf.py
│   │   ├── sync_open_finance.py
│   │   ├── auto_match.py
│   │   ├── confirm_match.py
│   │   └── ...
│   ├── collections/
│   │   ├── send_message.py
│   │   ├── handle_inbound_message.py
│   │   ├── run_agent_turn.py
│   │   ├── pause_agent.py
│   │   ├── compute_score.py
│   │   ├── broadcast_send.py
│   │   └── ...
│   ├── reports/
│   │   ├── run_built_in.py
│   │   ├── run_custom.py
│   │   └── export_xlsx.py
│   └── shared/
│       ├── audit_logger.py
│       └── notification_dispatcher.py
│
├── domain/                         # núcleo puro (sem I/O) — CORE GENÉRICO
│   ├── shared/
│   │   ├── value_objects.py        # Money, Cpf, PhoneE164, Address
│   │   ├── exceptions.py           # DomainError, NotFound, RuleViolation
│   │   └── events.py               # base DomainEvent + dispatcher
│   ├── identity/
│   │   ├── entities.py             # User, Role, Permission
│   │   └── policies.py             # password rules, mfa rules
│   ├── assets/
│   │   ├── asset.py                # Asset entity (genérico)
│   │   ├── asset_module.py         # IAssetModule Protocol
│   │   └── events.py               # AssetCreated, AssetStatusChanged
│   ├── catalog/
│   │   ├── customer.py
│   │   └── ...
│   ├── contracts/
│   │   ├── contract.py
│   │   ├── installment.py
│   │   ├── schedule_calculator.py  # PURO — calcula parcelas
│   │   └── events.py               # ContractCreated, InstallmentsGenerated, ContractTerminated
│   ├── finance/
│   │   ├── calculations.py         # PURO — juros, multa, score, ROI, partial payment
│   │   ├── policies.py             # write_off rules, immutable rules
│   │   └── events.py               # InstallmentPaid, InstallmentOverdue, WriteOffReversed, PartialPaymentApplied
│   ├── collections/
│   │   ├── conversation.py
│   │   ├── message.py
│   │   ├── score.py
│   │   ├── policy.py               # CollectionPolicy domain object
│   │   └── events.py
│   └── ports/                      # INTERFACES (PROTOCOLS)
│       ├── asset_module.py         # IAssetModule protocol
│       ├── whatsapp_gateway.py
│       ├── bank_reconciliation_provider.py
│       ├── payment_gateway.py      # plugin opcional
│       ├── llm_provider.py
│       ├── ocr_provider.py
│       ├── pdf_renderer.py
│       ├── storage_provider.py
│       └── repositories.py         # ICustomerRepo, IAssetRepo, IContractRepo, ...
│
├── modules/                        # MÓDULOS VERTICAIS (plugáveis)
│   └── vehicles/                   # primeiro módulo
│       ├── __init__.py
│       ├── module.py               # VehicleModule(IAssetModule) — registration
│       ├── hooks.py                # VehicleHook — reage a Domain Events
│       ├── routes.py               # rotas específicas: /modules/vehicles/...
│       ├── models.py               # Vehicle, VehicleAcquisition, TrackerDevice (SQLAlchemy)
│       ├── schemas.py              # DTOs Pydantic
│       ├── services/
│       │   ├── fipe_service.py
│       │   ├── tracker_service.py
│       │   ├── block_vehicle.py
│       │   ├── unblock_vehicle.py
│       │   └── vehicle_roi.py
│       ├── ports/
│       │   ├── fipe_provider.py    # IFipeProvider
│       │   └── tracker_gateway.py  # ITrackerGateway
│       ├── adapters/
│       │   ├── fipe/
│       │   │   ├── apifipe_br_adapter.py
│       │   │   ├── fipeapi_br_adapter.py
│       │   │   └── fallback_adapter.py
│       │   └── tracker/
│       │       ├── generic_rest_adapter.py
│       │       ├── mqtt_rest_adapter.py
│       │       └── suntech_adapter.py
│       └── agent_tools.py          # tools do agente específicas de veículos
│
├── infrastructure/                 # adapters (implementam ports do Core)
│   ├── db/
│   │   ├── base.py                 # SQLAlchemy declarative base
│   │   ├── session.py              # AsyncSession factory
│   │   ├── models/                 # ORM mapping (Core)
│   │   │   ├── user.py
│   │   │   ├── customer.py
│   │   │   ├── asset.py
│   │   │   ├── contract.py
│   │   │   ├── installment.py
│   │   │   ├── payable.py
│   │   │   ├── conversation.py
│   │   │   ├── audit_log.py
│   │   │   └── ...
│   │   └── repositories/           # implementam IXxxRepo
│   │       ├── customer_repo.py
│   │       ├── asset_repo.py
│   │       ├── contract_repo.py
│   │       ├── installment_repo.py
│   │       ├── conversation_repo.py
│   │       └── ...
│   ├── integrations/
│   │   ├── whatsapp/
│   │   │   ├── evolution_api_adapter.py
│   │   │   ├── zapi_adapter.py
│   │   │   ├── uazapi_adapter.py
│   │   │   ├── wpp_connect_adapter.py
│   │   │   └── meta_cloud_adapter.py
│   │   ├── bank/
│   │   │   ├── pluggy_adapter.py
│   │   │   ├── belvo_adapter.py
│   │   │   └── tecnospeed_adapter.py
│   │   ├── payment/               # PLUGINS opcionais (custo por transação)
│   │   │   ├── noop_gateway.py    # default: sem gateway, Pix próprio
│   │   │   ├── asaas_adapter.py
│   │   │   ├── efi_adapter.py
│   │   │   ├── stripe_adapter.py
│   │   │   └── pagbank_adapter.py
│   │   ├── llm/
│   │   │   ├── openai_adapter.py
│   │   │   ├── anthropic_adapter.py
│   │   │   ├── gemini_adapter.py
│   │   │   ├── ollama_adapter.py
│   │   │   └── litellm_adapter.py     # adapter "umbrella" usando LiteLLM
│   │   ├── ocr/
│   │   │   ├── tesseract_adapter.py
│   │   │   └── llm_vision_adapter.py
│   │   └── storage/
│   │       └── s3_compatible_adapter.py  # MinIO + AWS + R2 + B2
│   ├── pdf/
│   │   ├── weasyprint_renderer.py
│   │   └── templates/
│   │       └── contract.html.j2
│   ├── parsing/
│   │   ├── ofx_parser.py
│   │   ├── pdf_extract_parser.py    # heurísticas por banco
│   │   └── pix_receipt_classifier.py
│   ├── messaging/                   # eventos internos (in-process)
│   │   ├── event_bus.py             # publish/subscribe + module dispatcher
│   │   └── handlers/                # handlers reagindo a eventos
│   ├── security/
│   │   ├── jwt_service.py
│   │   ├── password_hasher.py
│   │   ├── encryption.py            # AES-256-GCM com chave KMS
│   │   └── totp.py
│   ├── observability/
│   │   ├── logging.py               # structlog config
│   │   ├── tracing.py               # OTel setup
│   │   └── metrics.py
│   └── settings.py                  # Pydantic Settings
│
├── workers/                        # Celery
│   ├── celery_app.py
│   ├── beat_schedule.py            # cron jobs
│   ├── tasks/
│   │   ├── recurring_payables.py   # diário: gera recorrentes
│   │   ├── score_recompute.py      # diário: score
│   │   ├── send_preventive_collection.py  # cron diário
│   │   ├── handle_inbound_whatsapp.py
│   │   ├── run_agent_turn.py
│   │   ├── render_contract_pdf.py
│   │   ├── ocr_receipt.py
│   │   ├── auto_match_reconciliation.py
│   │   ├── parse_pdf_extract.py
│   │   ├── generate_report.py
│   │   ├── dispatch_module_hooks.py  # despacha Domain Events para modules
│   │   ├── backup.py
│   │   └── ...
│   └── retry_policies.py
│
├── core/
│   ├── config.py                   # carrega Settings, expõe constants
│   ├── di.py                       # container de DI
│   ├── module_registry.py          # registro e bootstrap de módulos
│   ├── correlation.py              # context vars correlation_id
│   └── feature_flags.py
│
├── cli/
│   ├── seed.py
│   ├── create_user.py
│   └── recompute_score.py
│
└── main.py                         # uvicorn entry: cria app FastAPI, monta routers + modules, lifespan
```

### 6.1 Padrões de Código (Backend)

**Use case template:**

```python
# application/finance/write_off_installment.py
from dataclasses import dataclass
from decimal import Decimal
from datetime import date

from app.domain.finance.calculations import compute_updated_value
from app.domain.finance.policies import ensure_writable
from app.domain.ports.repositories import IInstallmentRepo, IContractRepo
from app.domain.ports.storage_provider import IStorageProvider
from app.domain.ports.ocr_provider import IOcrProvider
from app.domain.shared.value_objects import Money

@dataclass
class WriteOffInstallmentInput:
    installment_id: str
    paid_amount: Money
    paid_at: date
    payment_method: str
    receipt_bytes: bytes | None
    receipt_mime: str | None
    actor_user_id: str

@dataclass
class WriteOffInstallmentOutput:
    installment_id: str
    new_status: str
    receipt_url: str | None
    ocr_extracted: dict | None
    remainder_installment_id: str | None  # se pagamento parcial

class WriteOffInstallment:
    def __init__(
        self,
        installments: IInstallmentRepo,
        contracts: IContractRepo,
        storage: IStorageProvider,
        ocr: IOcrProvider,
        audit: AuditLogger,
        event_bus: EventBus,
        clock: Clock,
    ):
        self.installments = installments
        self.contracts = contracts
        self.storage = storage
        self.ocr = ocr
        self.audit = audit
        self.event_bus = event_bus
        self.clock = clock

    async def execute(self, cmd: WriteOffInstallmentInput) -> WriteOffInstallmentOutput:
        installment = await self.installments.get_or_404(cmd.installment_id)
        contract = await self.contracts.get_or_404(installment.contract_id)
        ensure_writable(installment)  # raises if 'pago'

        receipt_url = None
        ocr_data = None
        if cmd.receipt_bytes:
            receipt_url = await self.storage.put_receipt(
                installment_id=cmd.installment_id,
                bytes_=cmd.receipt_bytes,
                mime=cmd.receipt_mime,
            )
            if cmd.payment_method == "pix":
                ocr_data = await self.ocr.extract_pix_receipt(
                    cmd.receipt_bytes, cmd.receipt_mime
                )

        remainder_id = None
        # Partial payment handling
        if cmd.paid_amount.amount < installment.amount:
            from app.domain.finance.calculations import compute_partial_payment
            partial = compute_partial_payment(
                installment.amount, cmd.paid_amount.amount,
                installment.due_date, contract.grace_days,
            )
            remainder = installment.create_remainder(
                amount=partial.remainder_amount,
                due_date=partial.remainder_due_date,
            )
            await self.installments.save(remainder)
            remainder_id = remainder.id
            new_status = "pago_parcial"
        else:
            new_status = "pago_aguardando_verificacao"

        installment.write_off(
            paid_amount=cmd.paid_amount,
            paid_at=cmd.paid_at,
            method=cmd.payment_method,
            receipt_url=receipt_url,
            new_status=new_status,
        )
        await self.installments.save(installment)

        # Emit domain event — modules will react
        await self.event_bus.publish(InstallmentPaid(
            installment_id=installment.id,
            contract_id=contract.id,
            asset_id=contract.asset_id,
            paid_amount=cmd.paid_amount.amount,
            is_partial=remainder_id is not None,
        ))

        await self.audit.record(
            user_id=cmd.actor_user_id,
            action="installment.write_off",
            entity="installment",
            entity_id=cmd.installment_id,
            payload_after=installment.to_audit_payload(),
        )
        return WriteOffInstallmentOutput(
            installment_id=installment.id,
            new_status=new_status,
            receipt_url=receipt_url,
            ocr_extracted=ocr_data,
            remainder_installment_id=remainder_id,
        )
```

**Router (HTTP layer):**

```python
# api/v1/receivable_routes.py
from fastapi import APIRouter, Depends, UploadFile, File, Form
from app.api.deps import get_current_user, get_use_case
from app.application.finance.write_off_installment import (
    WriteOffInstallment, WriteOffInstallmentInput
)
from app.api.v1.schemas.receivables import WriteOffResponse
from app.domain.shared.value_objects import Money
from decimal import Decimal
from datetime import date

router = APIRouter(prefix="/receivables", tags=["receivables"])

@router.post("/{installment_id}/write-off", response_model=WriteOffResponse)
async def write_off(
    installment_id: str,
    paid_amount: Decimal = Form(...),
    paid_at: date = Form(...),
    payment_method: str = Form(...),
    receipt: UploadFile | None = File(None),
    user = Depends(get_current_user),
    uc: WriteOffInstallment = Depends(get_use_case(WriteOffInstallment)),
):
    receipt_bytes = await receipt.read() if receipt else None
    out = await uc.execute(WriteOffInstallmentInput(
        installment_id=installment_id,
        paid_amount=Money(paid_amount),
        paid_at=paid_at,
        payment_method=payment_method,
        receipt_bytes=receipt_bytes,
        receipt_mime=receipt.content_type if receipt else None,
        actor_user_id=user.id,
    ))
    return WriteOffResponse(**asdict(out))
```

---

## 7. Arquitetura de Módulos (Asset Abstraction Layer)

### 7.1 IAssetModule Protocol

O Core define uma interface que todo módulo vertical deve implementar:

```python
# domain/ports/asset_module.py
from typing import Protocol, Any
from fastapi import APIRouter

class IAssetModule(Protocol):
    """Protocol that every vertical asset module must implement."""

    @property
    def asset_type(self) -> str:
        """Unique identifier: 'vehicle', 'property', 'equipment', etc."""
        ...

    @property
    def display_name(self) -> str:
        """Human-readable name for the UI."""
        ...

    def get_router(self) -> APIRouter:
        """Returns FastAPI router with module-specific endpoints."""
        ...

    def get_agent_tools(self) -> list[dict[str, Any]]:
        """Returns LLM tool definitions (JSON Schema) for the AI agent."""
        ...

    async def execute_agent_tool(self, tool_name: str, args: dict) -> Any:
        """Executes an agent tool call. Called by RunAgentTurn."""
        ...

    def get_hooks(self) -> "IModuleHooks":
        """Returns hooks instance that reacts to Core domain events."""
        ...

    async def on_asset_created(self, asset_id: str, data: dict) -> None:
        """Called when an asset of this type is created. Module creates its own records."""
        ...

    async def on_asset_deleted(self, asset_id: str) -> None:
        """Cleanup when asset is removed."""
        ...


class IModuleHooks(Protocol):
    """Hooks that react to Core domain events, routed by asset_type."""

    async def on_installment_overdue(self, event: "InstallmentOverdue") -> None: ...
    async def on_installment_paid(self, event: "InstallmentPaid") -> None: ...
    async def on_contract_terminated(self, event: "ContractTerminated") -> None: ...
    async def on_partial_payment(self, event: "PartialPaymentApplied") -> None: ...
```

### 7.2 Registro de Módulos no Bootstrap

Módulos são registrados no startup da aplicação via `ModuleRegistry`:

```python
# core/module_registry.py
from typing import Dict
from app.domain.ports.asset_module import IAssetModule

class ModuleRegistry:
    """Singleton registry of vertical asset modules."""

    _modules: Dict[str, IAssetModule] = {}

    @classmethod
    def register(cls, module: IAssetModule) -> None:
        if module.asset_type in cls._modules:
            raise ValueError(f"Module '{module.asset_type}' already registered")
        cls._modules[module.asset_type] = module

    @classmethod
    def get(cls, asset_type: str) -> IAssetModule | None:
        return cls._modules.get(asset_type)

    @classmethod
    def all(cls) -> Dict[str, IAssetModule]:
        return dict(cls._modules)

    @classmethod
    def get_all_agent_tools(cls) -> list[dict]:
        """Collects agent tools from all registered modules."""
        tools = []
        for module in cls._modules.values():
            tools.extend(module.get_agent_tools())
        return tools


# main.py — bootstrap
from app.core.module_registry import ModuleRegistry
from app.modules.vehicles.module import VehicleModule

def register_modules(app):
    """Register all vertical modules. Add new modules here."""
    vehicle_mod = VehicleModule(app.state.sessionmaker)
    ModuleRegistry.register(vehicle_mod)

    # Future modules:
    # from app.modules.properties.module import PropertyModule
    # ModuleRegistry.register(PropertyModule(app.state.sessionmaker))

    # Mount module routes dynamically
    for asset_type, module in ModuleRegistry.all().items():
        app.include_router(
            module.get_router(),
            prefix=f"/api/v1/modules/{asset_type}",
            tags=[f"module:{asset_type}"],
        )
```

### 7.3 Padrão de Despacho de Domain Events

O Core emite Domain Events quando fatos relevantes ocorrem. O `EventDispatcher` roteia eventos para os hooks do módulo correto baseado no `asset_type` do contrato/ativo envolvido:

```python
# domain/shared/events.py
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

@dataclass(frozen=True)
class DomainEvent:
    """Base for all domain events."""
    occurred_at: datetime = field(default_factory=datetime.utcnow)

@dataclass(frozen=True)
class InstallmentOverdue(DomainEvent):
    installment_id: str = ""
    contract_id: str = ""
    asset_id: str = ""
    asset_type: str = ""
    days_overdue: int = 0
    amount: Decimal = Decimal("0")
    customer_id: str = ""

@dataclass(frozen=True)
class InstallmentPaid(DomainEvent):
    installment_id: str = ""
    contract_id: str = ""
    asset_id: str = ""
    asset_type: str = ""
    paid_amount: Decimal = Decimal("0")
    is_partial: bool = False

@dataclass(frozen=True)
class ContractTerminated(DomainEvent):
    contract_id: str = ""
    asset_id: str = ""
    asset_type: str = ""
    reason: str = ""

@dataclass(frozen=True)
class PartialPaymentApplied(DomainEvent):
    installment_id: str = ""
    contract_id: str = ""
    asset_id: str = ""
    asset_type: str = ""
    paid_amount: Decimal = Decimal("0")
    remainder_amount: Decimal = Decimal("0")
    remainder_installment_id: str = ""


# core/events/event_bus.py
from celery import Celery
from app.domain.shared.events import DomainEvent

class CeleryEventBus:
    """Enqueues domain events for async processing via Celery.
    Events are dispatched to module hooks by asset_type in the worker."""

    def __init__(self, celery_app: Celery):
        self.celery = celery_app

    def publish(self, event: DomainEvent) -> str:
        """Serialize event and enqueue on 'events' queue. Returns task_id."""
        return self.celery.send_task(
            "tasks.handle_domain_event",
            args=[event.to_dict()],
            queue="events",
        )

# workers/tasks/handle_domain_event.py
import structlog
from app.core.assets.registry import ModuleRegistry
from app.domain.shared.events import DomainEvent
from app.infrastructure.db.repositories.event_log_repo import EventLogRepo
from app.infrastructure.db.repositories.hooks_config_repo import HooksConfigRepo

log = structlog.get_logger()

@celery_app.task(bind=True, max_retries=3, default_retry_delay=10, queue="events")
def handle_domain_event(self, event_dict: dict):
    event = DomainEvent.from_dict(event_dict)

    # Idempotency: skip if event_id already processed
    if EventLogRepo.exists(event.event_id):
        return {"status": "duplicate", "event_id": str(event.event_id)}

    EventLogRepo.create(event, status="processing")

    registry = ModuleRegistry.instance()
    for module in registry.get_modules_for_asset_type(event.asset_type):
        # Capability declaration: only dispatch events the module declared interest in
        if not module.handles_event(type(event)):
            continue
        # Check runtime config: is this hook active for this event type?
        policy = HooksConfigRepo.get_policy(module.asset_type, type(event).__name__)
        if policy and not policy.is_active:
            continue
        try:
            actions = module.dispatch_event(event, policy.payload if policy else {})
            for action in actions:
                action.execute()  # each action is also idempotent
        except Exception as exc:
            log.error("hook_failed", module=module.asset_type,
                      event=type(event).__name__, error=str(exc))
            EventLogRepo.mark_failed(event.event_id, str(exc))
            raise self.retry(exc=exc)

    EventLogRepo.mark_completed(event.event_id)
```

### 7.4 Exemplo Concreto: Hooks do Módulo Vehicles

```python
# modules/vehicles/hooks.py
import structlog
from app.domain.shared.events import (
    InstallmentOverdue, InstallmentPaid, ContractTerminated, PartialPaymentApplied
)
from app.modules.vehicles.services.tracker_service import TrackerService

log = structlog.get_logger()

class VehicleHooks:
    """Reacts to Core domain events for vehicle assets."""

    def __init__(self, tracker: TrackerService, db_session_factory):
        self.tracker = tracker
        self.db_session_factory = db_session_factory

    async def on_installment_overdue(self, event: InstallmentOverdue) -> None:
        """When installment is overdue, evaluate blocking the vehicle via tracker."""
        log.info("vehicle_hook.installment_overdue",
                 asset_id=event.asset_id, days=event.days_overdue)

        # Load module hook config to decide action
        async with self.db_session_factory() as session:
            config = await self._load_hook_config(session, "InstallmentOverdue")
            if not config or not config.get("auto_block"):
                return

            min_days = config.get("min_days_overdue", 15)
            if event.days_overdue < min_days:
                return

            requires_approval = config.get("requires_approval", True)
            if requires_approval:
                # Create pending action for human approval
                await self._create_pending_action(
                    session, event.asset_id,
                    action="block_vehicle",
                    reason=f"Título vencido há {event.days_overdue} dias",
                )
            else:
                # Auto-block (rare, policy must explicitly allow)
                await self.tracker.block(event.asset_id, reason="auto:overdue")

    async def on_installment_paid(self, event: InstallmentPaid) -> None:
        """When installment is paid, consider unblocking vehicle if it was blocked."""
        if event.is_partial:
            log.info("vehicle_hook.partial_payment_no_unblock", asset_id=event.asset_id)
            return
        # Check if vehicle is currently blocked and all titles are current
        # If so, auto-unblock
        log.info("vehicle_hook.installment_paid", asset_id=event.asset_id)

    async def on_contract_terminated(self, event: ContractTerminated) -> None:
        """When contract ends, update vehicle status to 'disponivel'."""
        log.info("vehicle_hook.contract_terminated", asset_id=event.asset_id)
        async with self.db_session_factory() as session:
            await self._set_vehicle_status(session, event.asset_id, "disponivel")

    async def on_partial_payment(self, event: PartialPaymentApplied) -> None:
        """Partial payment — do not unblock, but log."""
        log.info("vehicle_hook.partial_payment",
                 asset_id=event.asset_id,
                 remainder=str(event.remainder_amount))
```

### 7.5 Agent Tools por Módulo (Permission-Gated)

O Agent Orchestrator possui tools genéricas do Core (consultar títulos, registrar baixa, enviar mensagem). Cada módulo registra tools **adicionais** que são injetadas dinamicamente no prompt do LLM. **Todas as tools são filtradas pelas permissões RBAC do caller** — o orchestrator só oferece ao LLM tools que o caller pode executar:

```python
# modules/vehicles/agent_tools.py

VEHICLE_AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bloquear_veiculo",
            "description": "Bloqueia o veículo do cliente via rastreador GPS. "
                           "Usar apenas quando política de cobrança autorizar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_id": {"type": "string", "description": "ID do ativo (veículo)"},
                    "reason": {"type": "string", "description": "Motivo do bloqueio"},
                },
                "required": ["asset_id", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verificar_localizacao",
            "description": "Consulta a localização atual do veículo via rastreador.",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_id": {"type": "string", "description": "ID do ativo (veículo)"},
                },
                "required": ["asset_id"],
            },
        },
    },
]

# Exemplo para um futuro módulo 'properties':
# PROPERTY_AGENT_TOOLS = [
#     {
#         "type": "function",
#         "function": {
#             "name": "agendar_vistoria",
#             "description": "Agenda vistoria do imóvel.",
#             "parameters": {...},
#         },
#     },
#     {
#         "type": "function",
#         "function": {
#             "name": "notificar_desocupacao",
#             "description": "Envia notificação de desocupação ao inquilino.",
#             "parameters": {...},
#         },
#     },
# ]
```

O `RunAgentTurn` use case coleta tools de todos os módulos, **filtradas pelas permissões do caller**:

```python
# application/collections/run_agent_turn.py (trecho)
from app.core.module_registry import ModuleRegistry
from app.domain.value_objects import AgentInput

class RunAgentTurn:
    async def execute(self, agent_input: AgentInput, ...):
        # AgentInput é agnóstico de canal:
        # AgentInput(text: str, media: list[Media], caller: Caller, permissions: set[str])

        # Core tools filtrados por RBAC do caller
        tools = [t for t in self._core_tools() if t.get("required_permission", "agent.basic") in agent_input.permissions]

        # Module tools (dinâmico + filtrado por RBAC)
        for module in ModuleRegistry.all().values():
            module_tools = module.get_agent_tools()
            tools.extend([t for t in module_tools if t.get("required_permission", "agent.basic") in agent_input.permissions])

        # Call LLM with permission-scoped tool set
        response = await self.llm.chat(messages=..., tools=tools)

        # Dispatch tool call
        if response.tool_call:
            tool_name = response.tool_call.name
            # Check if it's a module tool
            for module in ModuleRegistry.all().values():
                module_tool_names = [t["function"]["name"] for t in module.get_agent_tools()]
                if tool_name in module_tool_names:
                    result = await module.execute_agent_tool(tool_name, response.tool_call.args)
                    break
            else:
                result = await self._execute_core_tool(tool_name, response.tool_call.args)
```

### 7.5.1 Canal de Chat In-App

O mesmo Agent Orchestrator serve o canal **chat in-app** (web UI) sem nenhuma diferença de lógica:

- **Transporte**: HTTP `POST /api/v1/agent/chat` (request/response) ou WebSocket `/ws/agent-chat` (streaming).
- **Autenticação**: JWT do usuário logado — extrai `caller.permissions` do token.
- **Fluxo**: Frontend envia mensagem -> cria `Conversation(channel='in_app')` + `Message` -> enfileira `run_agent_turn` -> resposta via WebSocket ou HTTP response.
- **O orchestrator não sabe e não se importa** qual canal originou a mensagem. Ele vê apenas `AgentInput(text, media, caller, permissions)`.
- **Diferença única**: mensagens in-app não passam pelo `IWhatsAppGateway` para envio — a resposta é empurrada diretamente via WebSocket/SSE ao frontend.

### 7.6 Como Criar um Novo Módulo (Passo a Passo)

Para futuros devs que queiram adicionar um novo vertical (ex.: `properties` para imóveis):

1. **Crie a pasta do módulo**: `app/modules/properties/`
2. **Implemente `IAssetModule`** em `module.py`:
   - Defina `asset_type = "property"` e `display_name = "Imóveis"`
   - Implemente `get_router()` retornando um `APIRouter` com as rotas específicas
   - Implemente `get_agent_tools()` com as tools LLM do módulo
   - Implemente `get_hooks()` retornando uma instância de `PropertyHooks`
3. **Crie `hooks.py`** implementando `IModuleHooks`:
   - `on_installment_overdue` — ex.: agendar vistoria
   - `on_contract_terminated` — ex.: notificar desocupação
4. **Crie `models.py`** com tabelas module-specific (ex.: `properties` com FK para `assets.id`)
5. **Crie `schemas.py`** com DTOs Pydantic para a API
6. **Crie `agent_tools.py`** com definições de tools para o agente IA
7. **Crie migração Alembic** para as tabelas do módulo
8. **Registre no bootstrap** em `main.py`:
   ```python
   from app.modules.properties.module import PropertyModule
   ModuleRegistry.register(PropertyModule(app.state.sessionmaker))
   ```
9. **Insira na tabela `asset_modules`** via seed ou migração
10. **Configure hooks** na tabela `module_hooks_config` para o novo `asset_type`

Nenhuma alteração no Core é necessária. O módulo é self-contained.

---

## 8. APIs Externas e Adapters (Plug-and-Play)

### 8.1 Filosofia

**Toda API externa entra pela porta da frente** (Port no domínio) e tem **uma ou mais implementações** (Adapters na infra). Trocar de fornecedor é:

1. Implementar nova classe que satisfaça o Protocol.
2. Registrá-la no DI container.
3. Apontar a env `XYZ_PROVIDER` ou config no banco para o novo nome.
4. Pronto. Domínio nunca soube que houve mudança.

### 8.2 Mapa de Ports e Adapters

| Port (Interface)               | Default Adapter             | Alternativos                                       | Ativável |
|--------------------------------|------------------------------|----------------------------------------------------|----------|
| `IWhatsAppGateway`             | `EvolutionApiAdapter`        | `ZapiAdapter`, `UazapiAdapter`, `WppConnectAdapter`, `MetaCloudApiAdapter` | sempre |
| `IBankReconciliationProvider`  | `LocalImportProvider` (OFX+PDF) | `PluggyAdapter`, `BelvoAdapter`, `TecnoSpeedAdapter`, `KlaviAdapter` | opcional |
| `IPaymentGateway`              | `NoOpPaymentGateway`         | `AsaasAdapter`, `EfiAdapter`, `StripeAdapter`, `PagBankAdapter` | **plugin opcional** (custo) |
| `ILLMProvider`                 | `OpenAiAdapter` (gpt-4o)     | `AnthropicAdapter`, `GeminiAdapter`, `OllamaAdapter`, `LiteLlmAdapter` (umbrella) | sempre (com fallback) |
| `IOcrProvider`                 | `TesseractOcrAdapter`        | `LlmVisionOcrAdapter`, `GoogleVisionAdapter` (futuro) | sempre |
| `IAudioTranscriber`            | `WhisperApiAdapter` (OpenAI) | `LocalWhisperAdapter` (whisper.cpp), `GoogleSpeechAdapter`, `AzureSpeechAdapter` | sempre |
| `IPdfRenderer`                 | `WeasyPrintRenderer`         | `BrowserlessRenderer`, `GotenbergRenderer`         | sempre |
| `IStorageProvider`             | `S3CompatibleAdapter` apontando MinIO | mesmo adapter para AWS/R2/B2/Azure | sempre |

**Ports específicas de módulo** (vivem dentro do módulo, não no Core):

| Port (Module)                  | Default Adapter             | Alternativos                                       | Módulo |
|--------------------------------|------------------------------|----------------------------------------------------|--------|
| `IFipeProvider`                | `ApiFipeBrAdapter`           | `FipeApiBrAdapter`, `FipeOnlineAdapter`, `FallbackAdapter` (tenta em ordem) | vehicles |
| `ITrackerGateway`              | `GenericRestTrackerAdapter`  | `Suntech...`, `Positron...`, `MqttRestAdapter` (genérico configurável), `RpaTrackerAdapter` (Playwright headless), `ManualNotifyAdapter` (notifica Admin quando nenhuma API/RPA disponível) | vehicles |

**Fallback chain para ITrackerGateway:** API adapter -> RPA adapter (Playwright headless) -> Manual notification adapter (notifica Admin para ação manual).

### 8.3 Pagamento Default: Pix via WhatsApp (Sem Gateway)

O **padrão de pagamento** da plataforma é **Pix via WhatsApp com custo zero**:

1. O sistema gera QR Code Pix (BR Code estático ou dinâmico) usando a biblioteca `pix-utils` — sem gateway, sem custo por transação.
2. O QR Code é enviado ao cliente via WhatsApp (Evolution API — também sem custo por mensagem).
3. O cliente paga com o app do banco e envia comprovante de volta pelo WhatsApp.
4. O comprovante é processado via OCR + validação humana + conciliação bancária.

**Gateways de pagamento (Asaas, Efi, Stripe, PagBank) são plugins opcionais** — úteis para:
- Confirmação automática via webhook (elimina validação manual)
- Clientes VIP ou contratos de alto valor
- Habilitáveis por cliente ou por contrato individual

```python
# domain/ports/payment_gateway.py
from typing import Protocol
from decimal import Decimal

class IPaymentGateway(Protocol):
    """Plugin opcional. Default é NoOp (Pix próprio sem gateway)."""

    async def create_charge(self, amount: Decimal, description: str,
                            payer_cpf: str, due_date: str) -> dict:
        """Creates a charge. NoOp returns empty dict (Pix próprio)."""
        ...

    async def get_charge_status(self, charge_id: str) -> str: ...
    async def cancel_charge(self, charge_id: str) -> bool: ...


# infrastructure/integrations/payment/noop_gateway.py
class NoOpPaymentGateway:
    """Default: no payment gateway. System uses own Pix QR Code."""

    async def create_charge(self, amount, description, payer_cpf, due_date):
        return {}  # No external charge — Pix próprio

    async def get_charge_status(self, charge_id):
        return "not_applicable"

    async def cancel_charge(self, charge_id):
        return True
```

### 8.4 Detalhes por Integração

#### WhatsApp (Evolution API default)

- **Inbound**: webhook em `POST /webhooks/whatsapp/evolution`. Validação por `apikey` header. Idempotência por `messageId`.
- **Outbound**: `send_text`, `send_image`, `send_document`, `send_pix_card` (helper que monta um *list message* ou *button message* com QR + texto Copia e Cola embutido).
- **Mídias recebidas**: o adapter baixa para MinIO antes de sinalizar processado.
- **Cuidado**: respeitar rate limit do WhatsApp (delay configurável entre envios — 1s default, 3s se número novo) e janela horária (não enviar 22h-7h).

#### Módulo: Vehicles — FIPE

- Endpoints REST simples: marcas -> modelos -> anos -> preço.
- Cache **Redis** com TTL de 30 dias (chave `fipe:{type}:{brand}:{model}:{year}`).
- Job mensal (Celery Beat: `0 3 5 * *`) percorre veículos ativos e atualiza `fipe_value_current`.
- Erros transitórios -> retry exponencial (tenacity, 3 tentativas).
- Erros persistentes -> cai para adapter alternativo via `FallbackAdapter`.

#### Módulo: Vehicles — Rastreador

- **Adapter genérico** parametrizável por:
  - URL base
  - Auth (header / token / basic / OAuth2)
  - Mapeamento JSONPath dos campos (lat, lng, speed, ignition, last_update)
  - URL de comando bloqueio/desbloqueio + payload template
- Para rastreadores que usam **MQTT** para comandos: adapter MQTT+REST que publica em tópico do broker do fornecedor e lê posição via REST.
- **Comandos sensíveis** (bloqueio/desbloqueio): exigem perfil Admin + senha + 2-step na UI; gravam evento de auditoria com `reason` e horário programado.

#### Open Finance (Pluggy default — opcional)

- Fluxo OAuth-like via widget Pluggy embarcado no frontend (script Pluggy Connect).
- Backend recebe `item_id` do widget, persiste em `IntegrationCredential`, e dispara primeiro sync.
- Sync incremental a cada 6h via Celery; webhook Pluggy notifica novas transações.
- Transações chegam estruturadas -> entram diretamente em `bank_transactions` com `imported_from='open_finance'`.

#### Gateway Pix (Asaas / Efi / Stripe — plugin opcional)

- **Padrão**: desabilitado (`NoOpPaymentGateway`). Sistema gera QR estático/dinâmico próprio (sem custo).
- Quando habilitado como plugin: cria charge no provedor -> recebe `id` -> grava em `installment.external_charge_id`.
- Webhook recebe confirmação -> busca por `external_charge_id` -> marca `pago` direto (pula validação manual).
- Configurável **por cliente ou por contrato**: ex.: somente clientes VIP usam Asaas; resto usa fluxo Pix próprio.

#### Provedor LLM e Agent Orchestrator

- **Padrão**: OpenAI GPT-4o (custo/qualidade ótimos para PT-BR).
- **Agent Orchestrator multi-canal**: o orchestrator é agnóstico de canal. Recebe `AgentInput(text, media, caller, permissions)` — não sabe se veio de WhatsApp ou chat in-app. Transporte WhatsApp usa webhook; transporte in-app usa HTTP/WebSocket.
- **Permission-gated tool composition**: a cada turno, a lista de tools é construída dinamicamente com base nas permissões RBAC do caller:
  ```python
  # Composição de tools por turno (RunAgentTurn)
  tools = core_tools.filter_by_permissions(caller.permissions)
  for module in ModuleRegistry.all().values():
      tools += [t for t in module.get_agent_tools() if caller.has_permission(t["required_permission"])]
  ```
  Admin recebe todos os tools. Motorista/Cliente recebe apenas consultas dos próprios dados + envio de comprovante.
- **Tools** definidas como JSON Schemas e injetadas no prompt; Core tools + Module tools (dinâmico, filtrado por RBAC). Quando o LLM responde com `tool_call`, o use case `RunAgentTurn` despacha para a função real — seja do Core ou do módulo.
- **Function calling** com guardrails:
  - `bloquear_veiculo` (module tool) exige condições satisfeitas (score, dias atraso, política).
  - Tools **financeiras** (registrar baixa, conceder desconto) são logadas com extra rigor em `agent_runs`.
- **Custo**: cada turno gasta tokens; sistema calcula e mostra em Configurações o gasto mensal estimado.
- **Fallback**: se OpenAI falha, agente cai para `OllamaAdapter` local (modelo menor) — qualidade reduzida mas operação continua.

#### Transcrição de Áudio (IAudioTranscriber)

- **Port**:
  ```python
  class IAudioTranscriber(Protocol):
      async def transcribe(self, audio_bytes: bytes, mime: str, language: str = "pt-BR") -> TranscriptionResult: ...
  ```
- **Default adapter**: `WhisperApiAdapter` (OpenAI Whisper API).
- **Alternativas**: `LocalWhisperAdapter` (whisper.cpp — self-hosted, custo zero, mais lento), `GoogleSpeechAdapter`, `AzureSpeechAdapter`.
- **Pipeline de áudio inbound**: quando uma mensagem chega com `kind=audio` (de qualquer canal), o worker executa transcrição ANTES de passar ao orchestrator:
  1. Download do áudio (MinIO ou direto do provider).
  2. `transcriber.transcribe(audio_bytes, mime)` -> `TranscriptionResult(text, confidence, duration_ms)`.
  3. Persiste `transcription` na Message.
  4. Passa `text` como conteúdo textual ao `RunAgentTurn`.
- **Configurável**: provider, language, modelo (whisper-1, large-v3, etc.) — em Configurações > Agente IA > Transcrição.

#### OCR (Tesseract default)

- Pré-processamento OpenCV: deskew, denoise, contrast, threshold adaptativo.
- Linguagem: `por+eng`.
- Pós-processamento: regex específicas para Pix (valor, data, ID transação, banco emissor).
- **Fallback opcional**: se confiança baixa, chama LLM Vision (`gpt-4o` ou Claude com imagem) — paga só na exceção.

#### PDF Renderer (WeasyPrint default)

- Templates Jinja2 com CSS print-ready.
- Suporta marca d'água, paginação, footer com hash do PDF.
- **Alternativos** (caso WeasyPrint não dê conta de algum CSS moderno): Browserless (Chromium headless via Docker) ou Gotenberg (LibreOffice + Chromium).

---

## 8. Fluxos Principais (Diagramas de Sequência)

### 8.1 Login

```mermaid
sequenceDiagram
    participant U as Usuário (Browser)
    participant W as Angular SPA
    participant A as FastAPI
    participant DB as PostgreSQL
    participant R as Redis

    U->>W: digita email + senha
    W->>A: POST /auth/login
    A->>DB: SELECT user WHERE email
    DB-->>A: user record
    A->>A: verify Argon2id
    A->>R: SADD attempts:{email} ts (rate limit)
    A->>A: gera JWT (15min) + refresh (7d)
    A->>DB: insert audit_log(action='login_success')
    A-->>W: { access_token, user } + Set-Cookie refresh
    W->>W: armazena access em signal authState()
    W-->>U: navega /dashboard
```

### 8.2 Criar Contrato (com geração de PDF assíncrona)

```mermaid
sequenceDiagram
    participant U as Gestor
    participant W as Angular SPA
    participant A as FastAPI
    participant DB as PostgreSQL
    participant Q as Celery (Redis)
    participant K as Worker
    participant S as MinIO

    U->>W: preenche wizard de contrato (seleciona asset)
    W->>A: POST /contracts/preview-schedule (debounced)
    A-->>W: preview de N parcelas
    U->>W: confirma
    W->>A: POST /contracts (status=rascunho, asset_id=...)
    A->>DB: INSERT contract + installments (em transação)
    A->>DB: INSERT contract_event(created)
    A-->>W: 201 { contract_id }
    W->>A: POST /contracts/{id}/activate
    A->>DB: UPDATE contract.status='vigente'
    A->>Q: enqueue render_contract_pdf(contract_id)
    A->>Q: enqueue dispatch_module_hooks(ContractActivated)
    A-->>W: 200 { status: 'vigente', pdf: 'rendering' }
    W->>W: polling SSE /sse/notifications
    K->>DB: SELECT contract + installments + customer + asset
    K->>K: render Jinja2 -> HTML -> WeasyPrint -> PDF
    K->>S: PUT contracts/{id}/v1.pdf
    K->>DB: UPDATE contract.pdf_url
    K->>DB: INSERT contract_event(pdf_generated, hash)
    K->>R: PUBLISH sse:user:{user_id} {event:'contract.pdf_ready', contract_id}
    A-->>W: SSE event recebido
    W-->>U: toast "PDF pronto" + link
```

### 8.3 Recebimento de Comprovante via WhatsApp + Baixa Primária + Validação

```mermaid
sequenceDiagram
    participant M as Cliente
    participant WA as Evolution API
    participant API as FastAPI Webhook
    participant Q as Celery Queue
    participant W1 as Worker (inbound)
    participant AT as IAudioTranscriber
    participant W2 as Worker (agent)
    participant DB as PostgreSQL
    participant LLM as OpenAI
    participant V as Validador (Humano)

    M->>WA: envia print do comprovante (ou áudio)
    WA->>API: POST /webhooks/whatsapp/evolution {messageId, image/audio}
    API->>DB: INSERT webhook_events_raw (idempotente)
    API->>Q: enqueue handle_inbound_whatsapp
    API-->>WA: 200 OK
    W1->>WA: GET media (download imagem ou áudio)
    W1->>DB: persist message(direction=in, media_url)
    alt kind == audio
        W1->>AT: transcribe(audio_bytes, mime, "pt-BR")
        AT-->>W1: TranscriptionResult(text, confidence)
        W1->>DB: UPDATE message.transcription = text
    end
    W1->>Q: enqueue run_agent_turn(AgentInput with caller.permissions)
    W2->>DB: load contexto cliente + títulos abertos + últimas N msgs + caller.permissions
    W2->>W2: build permission-gated tool list
    W2->>W2: classifica imagem como comprovante (se imagem)
    W2->>W2: OCR Tesseract -> valor R$X, data Y, txid Z
    W2->>LLM: prompt com contexto + tools (filtrados por RBAC)
    LLM-->>W2: tool_call: registrar_baixa_primaria(install_id, valor, data)
    W2->>DB: UPDATE installment.status='pago_aguardando_verificacao'
    W2->>DB: INSERT installment_adjustment(kind='write_off_pending')
    W2->>LLM: tool_result + pede mensagem de confirmação
    LLM-->>W2: "Recebi seu comprovante! ..."
    W2->>WA: send_text (resposta) [ou WebSocket se canal=in_app]
    W2->>DB: persist message(direction=out)
    W2->>R: PUBLISH sse:user:{gestor} {event:'validation.new'}
    Note over V: Validador entra na fila
    V->>API: POST /receivables/{id}/validate {decision:'approve'}
    API->>DB: UPDATE installment.status='pago_aguardando_verificacao'
    API->>Q: enqueue dispatch_module_hooks(InstallmentPaid)
    API->>DB: INSERT audit_log(validated_by)
    API-->>V: 200
```

### 8.4 Conciliação Bancária Drag-and-Drop

```mermaid
sequenceDiagram
    participant U as Gestor
    participant W as Angular SPA
    participant A as FastAPI
    participant DB as PostgreSQL

    U->>W: upload OFX
    W->>A: POST /reconciliation/import-ofx
    A->>A: parse OFX -> list[Transaction]
    A->>DB: INSERT bank_transactions (idempotente por fitid)
    A-->>W: 200 { imported: 47 }
    W->>A: GET /reconciliation/transactions?status=pendente
    A->>DB: SELECT bank_transactions
    A-->>W: lista
    W->>A: GET /reconciliation/match-suggestions
    A->>A: algoritmo: para cada txn, busca installment com valor +/-0% e data +/-3d
    A-->>W: sugestões com score 0..1
    W-->>U: tabelas com sugestões pintadas em verde
    U->>W: arrasta txn sobre installment (manual)
    W->>A: POST /reconciliation/match { txn_id, install_id, kind: '1to1' }
    A->>DB: UPDATE bank_transaction.status='conciliada', reconciled_to
    A->>DB: UPDATE installment.status='pago' (final imutável)
    A->>DB: INSERT audit_log
    A-->>W: 200
```

### 8.5 Cobrança Preventiva Automática (Cron)

```mermaid
sequenceDiagram
    participant Beat as Celery Beat
    participant W as Worker
    participant DB as PostgreSQL
    participant LLM as LLM Provider
    participant WA as WhatsApp Gateway

    Note over Beat: cron diário 9h
    Beat->>W: schedule send_preventive_collection
    W->>DB: SELECT installments WHERE due_date = today + 2 AND status = 'em_aberto'
    DB-->>W: lista de N
    loop para cada installment
        W->>DB: load policy + customer + score
        W->>W: gera QR Code Pix (custo zero)
        W->>LLM: prompt "gere mensagem preventiva amigável com link Pix"
        LLM-->>W: texto
        W->>WA: send_pix_card (QR + mensagem)
        W->>DB: persist message + audit
        W->>W: sleep delay configurável (anti-ban)
    end
```

### 8.6 Bloqueio Remoto via Module Hook (Veículos — com Guardrails)

```mermaid
sequenceDiagram
    participant Core as Core (EventBus)
    participant Hook as VehicleHook
    participant Pol as Module Hook Config
    participant DB as DB
    participant U as Gestor (UI)
    participant TR as Tracker

    Note over Core: InstallmentOverdue emitido
    Core->>Hook: dispatch on_installment_overdue(event)
    Hook->>Pol: load module_hooks_config for 'InstallmentOverdue'
    Pol->>DB: load config (auto_block, min_days, requires_approval)
    Pol-->>Hook: { auto_block: true, min_days: 15, requires_approval: true }
    alt requires_human_approval
        Hook->>DB: insert pending_action (kind='block_vehicle', asset_id)
        Hook->>U: SSE notification "ação pendente: bloqueio do veículo X"
        U->>U: revisa + aprova com senha
        U->>API: POST /modules/vehicles/{id}/block (approval=true)
        API->>TR: POST /command/block
        TR-->>API: ok
        API->>DB: insert audit_log(actor=user, reason=...)
    else autopilot (raro, política liberou)
        Hook->>TR: POST /command/block
        TR-->>Hook: ok
        Hook->>DB: insert audit_log(actor=module:vehicles, justification)
    end
```

### 8.7 Pagamento Parcial

```mermaid
sequenceDiagram
    participant U as Gestor/Agente
    participant A as FastAPI
    participant DB as PostgreSQL
    participant EB as EventBus
    participant MH as Module Hook

    U->>A: POST /receivables/{id}/write-off (paid_amount < amount)
    A->>A: detect partial: paid_amount < installment.amount
    A->>A: compute_partial_payment()
    A->>DB: UPDATE installment status='pago_parcial', paid_amount
    A->>DB: INSERT installment_adjustment(kind='partial_payment')
    A->>DB: INSERT new installment for remainder amount
    A->>EB: publish PartialPaymentApplied(asset_id, remainder_amount)
    EB->>MH: dispatch to module hook by asset_type
    MH->>MH: log / take action (ex.: not unblock vehicle)
    A-->>U: 200 { new_status, remainder_installment_id }
```

---

## 9. Schema de Banco de Dados (PostgreSQL DDL)

> Este é o **schema canônico** que servirá de base para a primeira migração Alembic. Tipos personalizados, índices, constraints e triggers de imutabilidade incluídos. Convenção: `snake_case`, PKs `id UUID DEFAULT gen_random_uuid()`, timestamps `TIMESTAMPTZ`.

### 9.1 Extensions e Types

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;       -- gen_random_uuid, encrypt
CREATE EXTENSION IF NOT EXISTS pg_trgm;        -- busca textual fuzzy
CREATE EXTENSION IF NOT EXISTS unaccent;       -- normaliza acentos
CREATE EXTENSION IF NOT EXISTS vector;         -- pgvector

-- ENUMs
CREATE TYPE customer_status AS ENUM ('ativo','inativo','bloqueado');
CREATE TYPE asset_status AS ENUM ('disponivel','em_contrato','manutencao','inativo');
CREATE TYPE contract_status AS ENUM ('rascunho','vigente','encerrado','rescindido');
CREATE TYPE periodicity AS ENUM ('diaria','semanal','quinzenal','mensal','custom_days');
CREATE TYPE installment_kind AS ENUM ('regular','down_payment','extra_semestral','extra_anual','custom');
CREATE TYPE installment_status AS ENUM (
  'em_aberto','vencido','pago_aguardando_verificacao',
  'pago','pago_parcial','renegociado','cancelado'
);
```

#### Máquina de Estados de Status do Installment (7 estados)

| # | Status | Significado | Mutável? |
|---|---|---|---|
| 1 | `em_aberto` | Gerado, aguardando pagamento | Sim — editável, cancelável |
| 2 | `vencido` | Após data de vencimento (cron diário) | Sim — editável, cancelável |
| 3 | `pago_aguardando_verificacao` | Pagamento recebido (comprovante, dinheiro ou gateway), aguardando verificação (validação humana OU conciliação bancária) | Não — apenas validador avança |
| 4 | `pago` | Verificado e confirmado | Não — IMUTÁVEL (PG trigger) |
| 5 | `pago_parcial` | Pago parcialmente; diferença gerada como novo título | Não — IMUTÁVEL (PG trigger) |
| 6 | `renegociado` | Substituído por renegociação; original congelado | Não — IMUTÁVEL |
| 7 | `cancelado` | Cancelado (edição em lote, rollback, rescisão) | Não — estado terminal |

Transições:
- em_aberto → vencido (cron diário)
- em_aberto/vencido → pago_aguardando_verificacao (comprovante recebido, dinheiro atestado ou gateway notificou)
- em_aberto/vencido → pago_parcial (pagamento parcial recebido)
- em_aberto/vencido → renegociado (renegociação substitui)
- em_aberto/vencido → cancelado (cancelamento em lote, rollback, rescisão)
- pago_aguardando_verificacao → pago (verificado: validador aprova, conciliação bate ou gateway confirma)
- pago_aguardando_verificacao → em_aberto (validador rejeita — volta para aberto)
- pago_parcial → gera filho em_aberto para a diferença

```sql
CREATE TYPE payment_method AS ENUM ('pix','dinheiro','transferencia','cartao','outros');
CREATE TYPE payable_status AS ENUM ('em_aberto','pago','cancelado');
CREATE TYPE bank_txn_status AS ENUM ('pendente','conciliada','ignorada');
CREATE TYPE direction AS ENUM ('in','out');
CREATE TYPE message_kind AS ENUM ('text','image','document','audio','pix_card','system');
CREATE TYPE message_status AS ENUM ('sent','delivered','read','failed');

-- Module-specific ENUMs (Vehicles)
CREATE TYPE vehicle_status AS ENUM ('disponivel','alugado','manutencao','vendido','inativo');
CREATE TYPE acquisition_type AS ENUM ('a_vista','financiamento','consorcio','custom');
CREATE TYPE amortization AS ENUM ('price','sac');
```

### 9.2 Identidade

```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           CITEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    full_name       TEXT NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    is_mfa_enabled  BOOLEAN NOT NULL DEFAULT FALSE,
    mfa_secret_enc  BYTEA,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);
CREATE INDEX idx_users_active ON users(is_active) WHERE deleted_at IS NULL;

CREATE TABLE roles (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT UNIQUE NOT NULL,
    description TEXT
);

CREATE TABLE permissions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code        TEXT UNIQUE NOT NULL,    -- ex: 'customers.create'
    description TEXT
);

CREATE TABLE role_permissions (
    role_id        UUID REFERENCES roles(id) ON DELETE CASCADE,
    permission_id  UUID REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE user_roles (
    user_id  UUID REFERENCES users(id) ON DELETE CASCADE,
    role_id  UUID REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE refresh_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT UNIQUE NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    revoked_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_refresh_user ON refresh_tokens(user_id) WHERE revoked_at IS NULL;

CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    user_id         UUID REFERENCES users(id),
    action          TEXT NOT NULL,           -- 'installment.write_off' etc
    entity          TEXT,
    entity_id       TEXT,
    payload_before  JSONB,
    payload_after   JSONB,
    ip              INET,
    user_agent      TEXT,
    correlation_id  TEXT,
    module          TEXT,                    -- 'core', 'vehicles', 'auth', etc.
    category        TEXT NOT NULL DEFAULT 'info',  -- 'financial','navigation','error','info','security'
    severity        TEXT NOT NULL DEFAULT 'info',  -- 'debug','info','warning','error','critical'
    signature_hmac  BYTEA NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_audit_user_created ON audit_log(user_id, created_at DESC);
CREATE INDEX idx_audit_entity ON audit_log(entity, entity_id);

-- audit_log é append-only: trigger bloqueia UPDATE/DELETE
CREATE OR REPLACE FUNCTION block_audit_mutation() RETURNS TRIGGER AS $$
BEGIN RAISE EXCEPTION 'audit_log is append-only'; END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER audit_no_update BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION block_audit_mutation();
```

### 9.3 Registro de Ativos (Core)

```sql
-- Generic asset table — all verticals register here
CREATE TABLE assets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_type      TEXT NOT NULL,              -- 'vehicle', 'property', 'equipment', ...
    name            TEXT NOT NULL,              -- human-readable (ex.: 'ABC1D23 - Fiat Strada')
    status          asset_status NOT NULL DEFAULT 'disponivel',
    metadata        JSONB NOT NULL DEFAULT '{}', -- universal fields
    module_data     JSONB NOT NULL DEFAULT '{}', -- module-specific denormalized data
    created_by_user_id UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);
CREATE INDEX idx_assets_type ON assets(asset_type) WHERE deleted_at IS NULL;
CREATE INDEX idx_assets_status ON assets(status) WHERE deleted_at IS NULL;
CREATE INDEX idx_assets_name_search ON assets USING gin (
  (lower(unaccent(name))) gin_trgm_ops
);

-- Registry of installed modules
CREATE TABLE asset_modules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_type      TEXT UNIQUE NOT NULL,
    display_name    TEXT NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    config          JSONB NOT NULL DEFAULT '{}',
    hooks_class_path TEXT,                     -- 'app.modules.vehicles.hooks.VehicleHooks'
    routes_module_path TEXT,                   -- 'app.modules.vehicles.routes'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Per-module event hook policies
CREATE TABLE module_hooks_config (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_module_id UUID NOT NULL REFERENCES asset_modules(id) ON DELETE CASCADE,
    event_type      TEXT NOT NULL,             -- 'InstallmentOverdue', 'InstallmentPaid', etc.
    policy          JSONB NOT NULL DEFAULT '{}', -- ex: {auto_block: true, min_days_overdue: 15}
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (asset_module_id, event_type)
);
```

### 9.4 Catálogo

```sql
CREATE TABLE customers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name       TEXT NOT NULL,
    cpf             VARCHAR(11) UNIQUE NOT NULL,
    rg              TEXT,
    cnh_number      TEXT,
    cnh_category    VARCHAR(5),
    cnh_expires_at  DATE,
    phone_e164      VARCHAR(20),
    email           CITEXT,
    birth_date      DATE,
    address_zip     VARCHAR(8),
    address_street  TEXT,
    address_number  TEXT,
    address_comp    TEXT,
    address_neighbor TEXT,
    address_city    TEXT,
    address_state   VARCHAR(2),
    photo_url       TEXT,
    status          customer_status NOT NULL DEFAULT 'ativo',
    score           INT NOT NULL DEFAULT 100 CHECK (score BETWEEN 0 AND 100),
    tags            JSONB NOT NULL DEFAULT '[]',
    notes           TEXT,
    created_by_user_id UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);
CREATE INDEX idx_customers_search ON customers USING gin (
  (lower(unaccent(full_name))) gin_trgm_ops
);
CREATE INDEX idx_customers_cpf ON customers(cpf);
CREATE INDEX idx_customers_status ON customers(status) WHERE deleted_at IS NULL;

CREATE TABLE customer_attachments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id     UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    kind            TEXT NOT NULL,
    filename        TEXT NOT NULL,
    url             TEXT NOT NULL,
    mime            TEXT,
    size_bytes      BIGINT,
    uploaded_by     UUID REFERENCES users(id),
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_attach_customer ON customer_attachments(customer_id);

CREATE TABLE suppliers (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    document    TEXT,
    contact     TEXT,
    bank_data   JSONB,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE expense_categories (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_id   UUID REFERENCES expense_categories(id),
    name        TEXT NOT NULL,
    color       VARCHAR(7),
    icon        TEXT,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order  INT DEFAULT 0
);
```

### 9.5 Módulo: Veículos (tabelas module-specific)

```sql
-- Vehicles table: module-specific, linked to generic assets
CREATE TABLE vehicles (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id          UUID UNIQUE NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    plate             VARCHAR(8) UNIQUE NOT NULL,
    renavam           VARCHAR(11) UNIQUE,
    chassis           VARCHAR(17) UNIQUE,
    brand             TEXT NOT NULL,
    model             TEXT NOT NULL,
    version           TEXT,
    year_model        INT NOT NULL,
    year_manufacture  INT NOT NULL,
    color             TEXT,
    fuel              TEXT,
    km_initial        INT NOT NULL DEFAULT 0,
    km_current        INT NOT NULL DEFAULT 0,
    acquisition_date  DATE,
    purchase_value    NUMERIC(12,2),
    fipe_code         TEXT,
    fipe_value_current NUMERIC(12,2),
    fipe_value_updated_at TIMESTAMPTZ,
    tracker_device_id TEXT,
    status            vehicle_status NOT NULL DEFAULT 'disponivel',
    category          TEXT,
    insurance_provider TEXT,
    insurance_policy   TEXT,
    insurance_expires_at DATE,
    ipva_paid_until   DATE,
    licensing_expires_at DATE,
    notes             TEXT,
    created_by_user_id UUID REFERENCES users(id),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at        TIMESTAMPTZ
);
CREATE INDEX idx_vehicles_status ON vehicles(status) WHERE deleted_at IS NULL;
CREATE INDEX idx_vehicles_plate_search ON vehicles USING gin (plate gin_trgm_ops);
CREATE INDEX idx_vehicles_asset ON vehicles(asset_id);

CREATE TABLE vehicle_acquisitions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_id          UUID UNIQUE NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    type                acquisition_type NOT NULL,
    down_payment        NUMERIC(12,2),
    installments_def    JSONB,                -- lista de parcelas
    interest_rate_pct_per_month NUMERIC(6,4),
    grace_days          INT DEFAULT 0,
    amortization_system amortization,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE vehicle_photos (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_id  UUID NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    url         TEXT NOT NULL,
    is_primary  BOOLEAN NOT NULL DEFAULT FALSE,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE tracker_devices (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id     TEXT UNIQUE NOT NULL,
    vehicle_id      UUID REFERENCES vehicles(id),
    provider        TEXT NOT NULL,
    last_seen_at    TIMESTAMPTZ,
    last_position   JSONB,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE
);
```

### 9.6 Contratos

```sql
CREATE TABLE contracts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id     UUID NOT NULL REFERENCES customers(id),
    asset_id        UUID NOT NULL REFERENCES assets(id),   -- genérico (não vehicle_id)
    status          contract_status NOT NULL DEFAULT 'rascunho',
    start_date      DATE NOT NULL,
    end_date        DATE,
    total_amount    NUMERIC(12,2) NOT NULL,
    periodicity     periodicity NOT NULL,
    due_day         INT,
    custom_days_interval INT,              -- only used when periodicity = 'custom_days'
    late_interest_pct_per_day NUMERIC(6,4) NOT NULL DEFAULT 0.0033, -- 1% ao mês ~ 0.0333%/dia
    late_fine_pct   NUMERIC(6,4) NOT NULL DEFAULT 0.02,
    grace_days      INT NOT NULL DEFAULT 0,
    has_purchase_option BOOLEAN NOT NULL DEFAULT FALSE,
    residual_value  NUMERIC(12,2),
    terms_md        TEXT,
    pdf_url         TEXT,
    version         INT NOT NULL DEFAULT 1,
    created_by_user_id UUID REFERENCES users(id),
    signed_at       TIMESTAMPTZ,
    terminated_at   TIMESTAMPTZ,
    termination_reason TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);
CREATE INDEX idx_contracts_customer ON contracts(customer_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_contracts_asset ON contracts(asset_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_contracts_status ON contracts(status) WHERE deleted_at IS NULL;

CREATE TABLE installment_generations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id     UUID NOT NULL REFERENCES contracts(id),
    batch_label     TEXT,
    installment_count INT NOT NULL,
    total_amount    NUMERIC(12,2) NOT NULL,
    has_financial_activity BOOLEAN NOT NULL DEFAULT FALSE,
    created_by_user_id UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    rolled_back_at  TIMESTAMPTZ,
    rolled_back_by  UUID REFERENCES users(id)
);
CREATE INDEX idx_gen_contract ON installment_generations(contract_id);

CREATE TABLE installments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id     UUID NOT NULL REFERENCES contracts(id) ON DELETE RESTRICT,
    generation_id   UUID REFERENCES installment_generations(id),
    sequence        INT NOT NULL,
    due_date        DATE NOT NULL,
    amount          NUMERIC(12,2) NOT NULL,
    kind            installment_kind NOT NULL DEFAULT 'regular',
    status          installment_status NOT NULL DEFAULT 'em_aberto',
    paid_at         TIMESTAMPTZ,
    paid_amount     NUMERIC(12,2),
    payment_method  payment_method,
    receipt_url     TEXT,
    notes           TEXT,
    external_charge_id TEXT,                  -- se gateway Pix plugin ativo
    parent_installment_id UUID REFERENCES installments(id),  -- se gerado por partial payment
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (contract_id, sequence)
);
CREATE INDEX idx_inst_contract ON installments(contract_id);
CREATE INDEX idx_inst_due_status ON installments(due_date, status);
CREATE INDEX idx_inst_status ON installments(status);
CREATE INDEX idx_inst_parent ON installments(parent_installment_id) WHERE parent_installment_id IS NOT NULL;

-- Trigger de imutabilidade: status='pago' não pode ser alterado
CREATE OR REPLACE FUNCTION enforce_paid_immutability() RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status = 'pago' AND (
       NEW.amount <> OLD.amount OR
       NEW.due_date <> OLD.due_date OR
       NEW.paid_at <> OLD.paid_at OR
       NEW.paid_amount <> OLD.paid_amount OR
       NEW.status <> OLD.status
    ) THEN
        -- exceção: status pode ir para 'cancelado' apenas via reverse_write_off
        IF NEW.status = 'cancelado' AND current_setting('app.reverse_write_off', TRUE) = 'true' THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'paid installments are immutable; use reverse_write_off';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_inst_immutable BEFORE UPDATE ON installments
  FOR EACH ROW EXECUTE FUNCTION enforce_paid_immutability();

CREATE TABLE installment_adjustments (
    id              BIGSERIAL PRIMARY KEY,
    installment_id  UUID NOT NULL REFERENCES installments(id),
    kind            TEXT NOT NULL,    -- 'discount','fine','interest','renegotiation','bulk_edit','partial_payment','reverse_write_off'
    amount_delta    NUMERIC(12,2),
    snapshot_before JSONB,
    snapshot_after  JSONB,
    reason          TEXT,             -- JSON for partial_payment: {"remainder_installment_id": "..."}
    applied_by_user_id UUID REFERENCES users(id),
    applied_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_adj_install ON installment_adjustments(installment_id, applied_at DESC);

CREATE TABLE contract_events (
    id              BIGSERIAL PRIMARY KEY,
    contract_id     UUID NOT NULL REFERENCES contracts(id),
    event_type      TEXT NOT NULL,    -- 'created','signed','installments_generated','bulk_edit','terminated','pdf_generated'
    payload         JSONB NOT NULL,
    pdf_hash        TEXT,             -- apenas em pdf_generated
    created_by_user_id UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_ctr_events ON contract_events(contract_id, created_at DESC);
```

### 9.7 Financeiro (Títulos a Pagar + Conciliação)

```sql
CREATE TABLE payables (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    description     TEXT NOT NULL,
    supplier_id     UUID REFERENCES suppliers(id),
    category_id     UUID REFERENCES expense_categories(id),
    asset_id        UUID REFERENCES assets(id),        -- custo por ativo (genérico)
    amount          NUMERIC(12,2) NOT NULL,
    due_date        DATE NOT NULL,
    status          payable_status NOT NULL DEFAULT 'em_aberto',
    paid_at         TIMESTAMPTZ,
    paid_amount     NUMERIC(12,2),
    payment_method  payment_method,
    attachment_url  TEXT,
    notes           TEXT,
    created_by_user_id UUID REFERENCES users(id),
    recurring_template_id UUID,
    linked_installment_id UUID REFERENCES installments(id),  -- for reversals
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_pay_due_status ON payables(due_date, status);
CREATE INDEX idx_pay_asset ON payables(asset_id);

CREATE TABLE recurring_payable_templates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    description     TEXT NOT NULL,
    supplier_id     UUID REFERENCES suppliers(id),
    category_id     UUID REFERENCES expense_categories(id),
    asset_id        UUID REFERENCES assets(id),
    amount          NUMERIC(12,2) NOT NULL,
    periodicity     TEXT NOT NULL,   -- 'mensal','bimestral','anual'
    day_of_month    INT,
    start_date      DATE NOT NULL,
    end_date        DATE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE bank_accounts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    bank_code       VARCHAR(5),
    agency          VARCHAR(10),
    account_number  VARCHAR(20),
    type            TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE bank_transactions (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id         UUID REFERENCES bank_accounts(id),
    fitid              TEXT,                       -- FITID do OFX
    posted_at          DATE NOT NULL,
    amount             NUMERIC(12,2) NOT NULL,     -- signed
    description_raw    TEXT,
    description_clean  TEXT,
    type               TEXT,
    status             bank_txn_status NOT NULL DEFAULT 'pendente',
    reconciled_to_kind TEXT,        -- 'installment'|'payable'|'revenue'|'expense'
    reconciled_to_id   UUID,
    imported_from      TEXT NOT NULL,  -- 'ofx','pdf','open_finance','manual'
    imported_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (account_id, fitid)
);
CREATE INDEX idx_btx_status ON bank_transactions(status) WHERE status='pendente';
CREATE INDEX idx_btx_posted ON bank_transactions(posted_at DESC);
```

### 9.8 Cobranças

```sql
CREATE TABLE whatsapp_conversations (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id        UUID REFERENCES customers(id),
    phone_e164         VARCHAR(20) UNIQUE NOT NULL,
    last_message_at    TIMESTAMPTZ,
    unread_count       INT NOT NULL DEFAULT 0,
    is_archived        BOOLEAN NOT NULL DEFAULT FALSE,
    agent_active       BOOLEAN NOT NULL DEFAULT TRUE,
    agent_paused_until TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_wac_customer ON whatsapp_conversations(customer_id);
CREATE INDEX idx_wac_last_msg ON whatsapp_conversations(last_message_at DESC);

CREATE TABLE whatsapp_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES whatsapp_conversations(id) ON DELETE CASCADE,
    external_id     TEXT,
    direction       direction NOT NULL,
    kind            message_kind NOT NULL,
    content_text    TEXT,
    media_url       TEXT,
    media_mime      TEXT,
    sent_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered_at    TIMESTAMPTZ,
    read_at         TIMESTAMPTZ,
    sent_by         TEXT,                    -- 'agent' ou 'human:{user_id}'
    status          message_status NOT NULL DEFAULT 'sent',
    context         JSONB DEFAULT '{}',      -- {installment_ids:[],...}
    embedding       VECTOR(1536),            -- preenchido async
    UNIQUE (external_id)
);
CREATE INDEX idx_wam_conv ON whatsapp_messages(conversation_id, sent_at DESC);
CREATE INDEX idx_wam_unread ON whatsapp_messages(conversation_id) WHERE direction='in' AND read_at IS NULL;
CREATE INDEX idx_wam_embedding ON whatsapp_messages USING ivfflat (embedding vector_cosine_ops);

CREATE TABLE agent_runs (
    id                  BIGSERIAL PRIMARY KEY,
    conversation_id     UUID REFERENCES whatsapp_conversations(id),
    triggered_by_message_id UUID REFERENCES whatsapp_messages(id),
    provider            TEXT,
    model               TEXT,
    prompt_tokens       INT,
    completion_tokens   INT,
    total_cost_usd      NUMERIC(10,6),
    latency_ms          INT,
    tools_called        JSONB,
    final_action        TEXT,
    error               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_agent_runs_conv ON agent_runs(conversation_id, created_at DESC);

CREATE TABLE customer_score_history (
    id          BIGSERIAL PRIMARY KEY,
    customer_id UUID NOT NULL REFERENCES customers(id),
    score       INT NOT NULL,
    factors     JSONB,
    taken_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_score_customer ON customer_score_history(customer_id, taken_at DESC);

CREATE TABLE collection_policies (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    is_active   BOOLEAN NOT NULL DEFAULT FALSE,
    payload     JSONB NOT NULL,
    version     INT NOT NULL DEFAULT 1,
    updated_by_user_id UUID REFERENCES users(id),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX idx_pol_active ON collection_policies(is_active) WHERE is_active=TRUE;
```

### 9.9 Integrações

```sql
CREATE TABLE webhook_events_raw (
    id              BIGSERIAL PRIMARY KEY,
    provider        TEXT NOT NULL,
    external_id     TEXT,
    signature_valid BOOLEAN,
    payload         JSONB NOT NULL,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at    TIMESTAMPTZ,
    processing_status TEXT NOT NULL DEFAULT 'pending',
    error           TEXT,
    UNIQUE (provider, external_id)
);
CREATE INDEX idx_webhook_processing ON webhook_events_raw(processing_status, received_at)
  WHERE processing_status = 'pending';

CREATE TABLE integration_credentials (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider        TEXT UNIQUE NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT FALSE,
    config_encrypted BYTEA,
    last_tested_at  TIMESTAMPTZ,
    last_test_status TEXT,
    updated_by_user_id UUID REFERENCES users(id),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE feature_flags (
    key         TEXT PRIMARY KEY,
    value       JSONB NOT NULL,
    description TEXT,
    updated_by_user_id UUID REFERENCES users(id),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 9.10 Relatórios

```sql
CREATE TABLE saved_reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    owner_user_id   UUID NOT NULL REFERENCES users(id),
    definition      JSONB NOT NULL,
    is_shared       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_saved_owner ON saved_reports(owner_user_id);
```

### 9.11 Motor de Cobrança — Novas Tabelas (Épico 12+)

```sql
-- Enum: tipo de título (discrimina parcela de opcao_compra e outros)
CREATE TYPE tipo_titulo AS ENUM ('parcela', 'opcao_compra', 'multa', 'taxa', 'ajuste');

-- Adicionar colunas ao installments existente
ALTER TABLE installments
    ADD COLUMN tipo tipo_titulo NOT NULL DEFAULT 'parcela',
    ADD COLUMN proxima_acao_em TIMESTAMPTZ,          -- camada 3 de idempotência
    ADD COLUMN acoes_de_cobranca INT NOT NULL DEFAULT 0,  -- contador de tentativas
    ADD COLUMN ultima_cobranca_enviada_em TIMESTAMPTZ;

-- Constraint: apenas 1 opcao_compra por contrato
CREATE UNIQUE INDEX uniq_opcao_compra_por_contrato
    ON installments(contract_id)
    WHERE tipo = 'opcao_compra';

-- politica_cobranca: parâmetros do motor, 1 por empresa
CREATE TABLE politica_cobranca (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id                  UUID NOT NULL REFERENCES empresas(id) UNIQUE,
    dias_antecedencia_lembrete  INTEGER NOT NULL DEFAULT 3,
    dias_carencia               INTEGER NOT NULL DEFAULT 0,
    percentual_multa            NUMERIC(5,2) NOT NULL DEFAULT 2.00,   -- % única na entrada em atraso
    percentual_juros_dia        NUMERIC(5,4) NOT NULL DEFAULT 0.0333, -- 1% ao mês ~ 0.0333%/dia
    limite_dias_suspensao       INTEGER NOT NULL DEFAULT 15,          -- dias até suspensão do contrato
    limite_dias_encerramento    INTEGER NOT NULL DEFAULT 60,          -- dias até encerramento com pendência
    atualizado_em               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_politica_empresa ON politica_cobranca(empresa_id);

-- passivos_inoperantes: dívidas de contratos encerrados, vinculadas ao CPF do cliente
CREATE TABLE passivos_inoperantes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id      UUID NOT NULL REFERENCES empresas(id),
    cliente_id      UUID NOT NULL REFERENCES customers(id),
    contrato_id     UUID NOT NULL REFERENCES contracts(id),
    titulo_id       UUID NOT NULL REFERENCES installments(id),
    valor_nominal   NUMERIC(12,2) NOT NULL,
    valor_encargos  NUMERIC(12,2) NOT NULL DEFAULT 0,
    situacao        VARCHAR(30) NOT NULL DEFAULT 'pendente',  -- 'pendente','quitado','prescrito','baixado'
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_passivo_cliente ON passivos_inoperantes(cliente_id);
CREATE INDEX idx_passivo_contrato ON passivos_inoperantes(contrato_id);
CREATE INDEX idx_passivo_situacao ON passivos_inoperantes(situacao) WHERE situacao = 'pendente';

-- execucoes_motor: registro de auditoria de cada rodada do motor de cobrança
CREATE TABLE execucoes_motor (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome_tarefa     VARCHAR(100) NOT NULL,
    empresa_id      UUID REFERENCES empresas(id),
    iniciado_em     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finalizado_em   TIMESTAMPTZ,
    total_registros INTEGER NOT NULL DEFAULT 0,
    total_erros     INTEGER NOT NULL DEFAULT 0,
    situacao        VARCHAR(20) NOT NULL DEFAULT 'executando'  -- 'executando','concluido','falhou'
);
CREATE INDEX idx_execucao_tarefa ON execucoes_motor(nome_tarefa, iniciado_em DESC);
CREATE INDEX idx_execucao_situacao ON execucoes_motor(situacao) WHERE situacao = 'executando';
```

> **Nota**: a tabela `empresas` referenciada acima será criada na implementação multi-tenant (V2 planejado). Em V1 single-tenant, `empresa_id` pode referenciar uma tabela de configuração básica ou ser omitido dos constraints até a migração multi-tenant.

### 9.12 Views Materializadas (relatórios pesados)

```sql
-- View: ROI por ativo (refresh manual ou job) — genérico, usa asset
CREATE MATERIALIZED VIEW mv_asset_roi AS
SELECT
    a.id AS asset_id,
    a.asset_type,
    a.name AS description,
    (a.module_data->>'purchase_value')::NUMERIC(12,2) AS purchase_value,
    (a.module_data->>'fipe_value_current')::NUMERIC(12,2) AS fipe_value_current,
    COALESCE(SUM(i.paid_amount) FILTER (WHERE i.status IN ('pago','pago_parcial')), 0) AS total_received,
    COALESCE(SUM(p.paid_amount) FILTER (WHERE p.asset_id=a.id AND p.status='pago'), 0) AS total_spent,
    CASE
      WHEN (a.module_data->>'purchase_value')::NUMERIC > 0 THEN
        ((COALESCE(SUM(i.paid_amount) FILTER (WHERE i.status IN ('pago','pago_parcial')),0) - COALESCE(SUM(p.paid_amount) FILTER (WHERE p.asset_id=a.id AND p.status='pago'),0)) / (a.module_data->>'purchase_value')::NUMERIC) * 100
      ELSE NULL
    END AS roi_pct,
    (a.module_data->>'purchase_value')::NUMERIC(12,2) - COALESCE((a.module_data->>'fipe_value_current')::NUMERIC(12,2), (a.module_data->>'purchase_value')::NUMERIC(12,2)) AS depreciation
FROM assets a
LEFT JOIN contracts c ON c.asset_id = a.id
LEFT JOIN installments i ON i.contract_id = c.id AND i.status IN ('pago','pago_parcial')
LEFT JOIN payables p ON p.asset_id = a.id AND p.status='pago'
WHERE a.deleted_at IS NULL
GROUP BY a.id;
CREATE UNIQUE INDEX ON mv_asset_roi (asset_id);
-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_asset_roi; (job diário)
```

---

## 10. Arquitetura do Frontend (Angular 21+)

> **Esta seção é a aplicação concreta do `frontend_architecture_manifesto.md` e do `angular-structure.md` ao {{product_name}}.** Toda regra do manifesto é não-negociável.

### 10.1 Estrutura de Pastas — Visão Completa

```
frontend/
├── public/                              # substitui src/assets
│   ├── favicon.ico
│   ├── robots.txt
│   ├── manifest.webmanifest
│   ├── images/
│   │   ├── logo.svg
│   │   ├── logo-dark.svg
│   │   └── empty-states/
│   ├── icons/                           # PWA icons
│   └── fonts/                           # Inter, JetBrains Mono (self-hosted)
├── src/
│   ├── main.ts
│   ├── index.html
│   ├── styles.css                       # @import tailwind + @theme {} variables
│   ├── environments/
│   │   ├── environment.ts
│   │   └── environment.prod.ts
│   └── app/
│       ├── app.component.ts
│       ├── app.component.html
│       ├── app.component.css            # ~vazio
│       ├── app.config.ts                # bootstrapApplication providers
│       ├── app.routes.ts                # rota raiz com lazy load
│       │
│       ├── core/                        # SINGLETONS / GLOBAL STATE
│       │   ├── guards/
│       │   │   ├── auth.guard.ts
│       │   │   └── role.guard.ts
│       │   ├── interceptors/
│       │   │   ├── jwt.interceptor.ts
│       │   │   ├── correlation-id.interceptor.ts
│       │   │   ├── error.interceptor.ts
│       │   │   └── api-base-url.interceptor.ts
│       │   ├── tokens/
│       │   │   ├── api-base-url.token.ts
│       │   │   └── ws-base-url.token.ts
│       │   └── services/
│       │       ├── auth.service.ts             # signal authState() — global
│       │       ├── theme.service.ts            # signal theme()
│       │       ├── notification.service.ts     # toast queue + audio
│       │       ├── current-user.service.ts     # me + permissões
│       │       ├── permission.service.ts       # can('action')
│       │       ├── sse.service.ts              # EventSource singleton
│       │       ├── ws.service.ts               # WebSocket singleton (chat)
│       │       ├── feature-flag.service.ts
│       │       ├── module.service.ts           # lista módulos ativos do backend
│       │       ├── i18n.service.ts             # carrega traduções (futuro)
│       │       └── breadcrumb.service.ts
│       │
│       ├── shared/                      # UI REUSABLE
│       │   ├── components/
│       │   │   ├── icon/                       # <ui-icon name="HeroXMark" />
│       │   │   │   ├── icon.component.ts
│       │   │   │   ├── icon.component.html
│       │   │   │   └── icon.component.css
│       │   │   ├── button/
│       │   │   ├── input-text/
│       │   │   ├── input-number/
│       │   │   ├── input-money/                # tabular-nums + formatação BR
│       │   │   ├── input-date/
│       │   │   ├── input-cpf/
│       │   │   ├── input-cnpj/
│       │   │   ├── input-plate/
│       │   │   ├── input-phone/
│       │   │   ├── select/
│       │   │   ├── select-async/               # com search server-side
│       │   │   ├── checkbox/
│       │   │   ├── toggle/
│       │   │   ├── modal/                      # base
│       │   │   ├── drawer/
│       │   │   ├── command-palette/            # Ctrl+K
│       │   │   ├── data-table/                 # tabela genérica com sort/filter/paging
│       │   │   ├── data-list/                  # cards reutilizáveis
│       │   │   ├── kpi-card/
│       │   │   ├── badge/
│       │   │   ├── skeleton/
│       │   │   ├── empty-state/
│       │   │   ├── confirm-dialog/
│       │   │   ├── toast/
│       │   │   ├── tabs/
│       │   │   ├── stepper/
│       │   │   ├── drag-list/                  # wrapper sobre CDK Drag-Drop
│       │   │   ├── file-dropzone/
│       │   │   ├── image-cropper-modal/
│       │   │   ├── pdf-viewer/
│       │   │   ├── chart-card/                 # wrapper ngx-echarts
│       │   │   ├── leaflet-map/                # base
│       │   │   ├── loading-overlay/
│       │   │   ├── score-gauge/
│       │   │   └── timeline/
│       │   ├── pipes/
│       │   │   ├── currency-br.pipe.ts
│       │   │   ├── cpf-mask.pipe.ts
│       │   │   ├── cnpj-mask.pipe.ts
│       │   │   ├── phone-br.pipe.ts
│       │   │   ├── relative-date.pipe.ts        # "há 2 horas"
│       │   │   ├── safe-html.pipe.ts
│       │   │   └── installment-status.pipe.ts   # enum -> label
│       │   ├── directives/
│       │   │   ├── pulse-alert.directive.ts
│       │   │   ├── click-outside.directive.ts
│       │   │   ├── focus-trap.directive.ts
│       │   │   ├── shortcut.directive.ts
│       │   │   └── auto-resize-textarea.directive.ts
│       │   ├── models/
│       │   │   ├── api-response.model.ts        # padrão envelope se houver
│       │   │   ├── pagination.model.ts
│       │   │   ├── filter.model.ts
│       │   │   └── enums.ts
│       │   └── services/
│       │       ├── ui-helper.service.ts          # scroll, viewport, debounce helpers
│       │       └── form-error.service.ts         # mapping de erros pra labels
│       │
│       └── features/                    # BUSINESS DOMAINS
│           ├── auth/                              # AUTH SHELL
│           │   ├── auth.component.ts              # layout simples (sem sidebar)
│           │   ├── auth.component.html
│           │   ├── auth.component.css
│           │   ├── auth.routes.ts                 # AUTH_ROUTES exported
│           │   ├── login/
│           │   │   ├── login.component.ts
│           │   │   ├── login.component.html
│           │   │   └── login.component.css
│           │   ├── forgot-password/
│           │   ├── reset-password/
│           │   └── mfa/
│           │
│           ├── landing-page/                      # PUBLIC SHELL (futuro)
│           │   ├── landing-page.component.ts
│           │   ├── landing-page.routes.ts
│           │   └── components/
│           │       ├── hero/
│           │       ├── features/
│           │       └── footer/
│           │
│           └── system/                            # APP PROTEGIDO (DASHBOARD)
│               ├── system.component.ts            # layout shell: sidebar + header + outlet
│               ├── system.component.html
│               ├── system.component.css
│               ├── system.routes.ts               # SYSTEM_ROUTES (lazy children)
│               │
│               ├── components/                    # componentes do shell (sidebar, header)
│               │   ├── sidebar/
│               │   ├── header/
│               │   ├── user-menu/
│               │   ├── notification-bell/
│               │   └── theme-toggle/
│               │
│               ├── dashboard/                     # /system/dashboard
│               │   ├── dashboard.component.ts
│               │   ├── dashboard.component.html
│               │   └── dashboard.component.css
│               │
│               ├── customers/
│               │   ├── customers-list.component.ts
│               │   ├── customer-form.component.ts            # drawer
│               │   ├── customer-detail.component.ts          # rota com tabs
│               │   ├── customer-tabs/
│               │   │   ├── customer-overview-tab.component.ts
│               │   │   ├── customer-contracts-tab.component.ts
│               │   │   ├── customer-receivables-tab.component.ts
│               │   │   ├── customer-score-tab.component.ts
│               │   │   ├── customer-documents-tab.component.ts
│               │   │   ├── customer-conversations-tab.component.ts
│               │   │   └── customer-audit-tab.component.ts
│               │   └── customers.routes.ts
│               │
│               ├── assets/                        # views genéricas de asset
│               │   ├── assets-list.component.ts
│               │   ├── asset-detail.component.ts
│               │   └── assets.routes.ts
│               │
│               ├── vehicles/                      # módulo: vehicles UI
│               │   ├── vehicles-list.component.ts
│               │   ├── vehicle-wizard.component.ts           # 4 passos
│               │   ├── vehicle-detail.component.ts
│               │   ├── vehicle-tabs/
│               │   │   ├── vehicle-overview-tab.component.ts
│               │   │   ├── vehicle-acquisition-tab.component.ts
│               │   │   ├── vehicle-roi-tab.component.ts
│               │   │   ├── vehicle-location-tab.component.ts
│               │   │   └── ...
│               │   ├── components/
│               │   │   ├── fipe-selector/
│               │   │   ├── acquisition-form/                # entrada + N parcelas + extras
│               │   │   └── photo-gallery/
│               │   └── vehicles.routes.ts
│               │
│               ├── fleet-map/
│               │   ├── fleet-map.component.ts
│               │   ├── fleet-map.component.html
│               │   └── fleet-map.component.css
│               │
│               ├── contracts/
│               │   ├── contracts-list.component.ts
│               │   ├── contract-wizard.component.ts          # 4 passos
│               │   ├── contract-detail.component.ts
│               │   ├── components/
│               │   │   ├── schedule-builder/                 # DRAG-AND-DROP central
│               │   │   ├── schedule-preview/
│               │   │   ├── installment-bulk-edit-modal/
│               │   │   ├── contract-pdf-viewer/
│               │   │   └── contract-events-timeline/
│               │   └── contracts.routes.ts
│               │
│               ├── finance/
│               │   ├── receivables/
│               │   │   ├── receivables-list.component.ts
│               │   │   ├── write-off-modal.component.ts
│               │   │   ├── partial-write-off-modal.component.ts
│               │   │   ├── validation-queue.component.ts     # aprovação rápida
│               │   │   ├── pix-qr-modal.component.ts
│               │   │   ├── renegotiation-modal.component.ts
│               │   │   └── receivables.routes.ts
│               │   ├── payables/
│               │   │   ├── payables-list.component.ts
│               │   │   ├── payable-form.component.ts
│               │   │   ├── recurring-list.component.ts
│               │   │   ├── recurring-form.component.ts
│               │   │   ├── quick-pay-modal.component.ts
│               │   │   └── payables.routes.ts
│               │   ├── reconciliation/
│               │   │   ├── reconciliation.component.ts       # DRAG-AND-DROP split
│               │   │   ├── components/
│               │   │   │   ├── transactions-pane/
│               │   │   │   ├── pending-titles-pane/
│               │   │   │   ├── match-suggestion-card/
│               │   │   │   ├── ofx-uploader/
│               │   │   │   └── pdf-uploader/
│               │   │   └── reconciliation.routes.ts
│               │   └── dre/
│               │       ├── dre.component.ts
│               │       └── components/
│               │           └── dre-table/
│               │
│               ├── inbox/                                    # WhatsApp Inbox
│               │   ├── inbox.component.ts                    # 3-painéis
│               │   ├── components/
│               │   │   ├── conversation-list/
│               │   │   ├── chat-thread/
│               │   │   ├── chat-message/                     # bolha verde/branca
│               │   │   ├── chat-input/                       # com áudio + anexo + emoji
│               │   │   ├── customer-context-pane/
│               │   │   ├── agent-toggle/
│               │   │   └── broadcast-modal/
│               │   └── inbox.routes.ts
│               │
│               ├── reports/
│               │   ├── reports-list.component.ts             # cards de relatórios
│               │   ├── report-viewer.component.ts
│               │   ├── report-builder.component.ts           # DRAG-AND-DROP de dimensões
│               │   ├── components/
│               │   │   ├── dimension-palette/
│               │   │   ├── filter-pane/
│               │   │   └── visualization/                    # tabela + gráfico
│               │   └── reports.routes.ts
│               │
│               ├── audit/
│               │   ├── audit-list.component.ts
│               │   ├── audit-detail-modal.component.ts
│               │   └── audit.routes.ts
│               │
│               └── config/                                   # CONFIGURAÇÕES
│                   ├── config.component.ts                   # tabs gerais
│                   ├── general/
│                   ├── company/
│                   ├── billing-rules/                        # juros, multa, score
│                   ├── agent/                                # parametrização do agente IA
│                   │   ├── agent-config.component.ts
│                   │   ├── components/
│                   │   │   ├── persona-editor/
│                   │   │   ├── policy-editor/                # tabela score -> tolerância
│                   │   │   ├── template-editor/              # Tiptap
│                   │   │   └── agent-tester/
│                   │   └── ...
│                   ├── integrations/                         # painel plug-and-play
│                   │   ├── integrations.component.ts
│                   │   ├── components/
│                   │   │   ├── integration-card/
│                   │   │   ├── credentials-modal/
│                   │   │   └── test-connection-button/
│                   │   └── ...
│                   ├── modules/                              # configuração de módulos
│                   │   ├── modules-list.component.ts
│                   │   ├── module-hooks-config.component.ts
│                   │   └── ...
│                   ├── users/
│                   ├── permissions/
│                   ├── templates/
│                   └── config.routes.ts
```

> **Notas críticas (manifesto):**
> - Cada componente tem **3 arquivos** (TS/HTML/CSS), o `.css` praticamente vazio.
> - Estrutura **rasa**: `customers-list.component.ts` direto na pasta `customers/`, sem subpasta redundante.
> - **Nenhum service em `/features`**. Chamadas API ficam em `core/services/` (ex.: `customer.service.ts` se necessário globalmente OU diretamente no componente via `inject(HttpClient)` + `resource()`).
> - **Lazy loading** por feature shell (`customers.routes.ts`, `vehicles.routes.ts`, etc).
> - Cada componente compartilhado em `shared/components/{nome}/` com seus 3 arquivos.

### 10.2 Padrão de Componente — Exemplo Concreto

```typescript
// features/system/customers/customers-list.component.ts
import { Component, signal, computed, inject, resource } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { API_BASE_URL } from '@core/tokens/api-base-url.token';
import { DataTableComponent } from '@shared/components/data-table/data-table.component';
import { IconComponent } from '@shared/components/icon/icon.component';
import { BadgeComponent } from '@shared/components/badge/badge.component';
import { Customer } from '@shared/models/customer.model';
import { rxResource } from '@angular/core/rxjs-interop';
import { debounceTime, switchMap } from 'rxjs/operators';

@Component({
  selector: 'app-customers-list',
  standalone: true,
  imports: [RouterLink, FormsModule, DataTableComponent, IconComponent, BadgeComponent],
  templateUrl: './customers-list.component.html',
  styleUrl: './customers-list.component.css',
})
export class CustomersListComponent {
  private http = inject(HttpClient);
  private apiBase = inject(API_BASE_URL);
  private router = inject(Router);

  // Filtros locais (signals)
  readonly searchTerm = signal('');
  readonly statusFilter = signal<string[]>(['ativo']);
  readonly page = signal(1);
  readonly pageSize = signal(50);

  // resource() — Angular 21 native
  readonly customers = resource({
    request: () => ({
      search: this.searchTerm(),
      status: this.statusFilter(),
      page: this.page(),
      size: this.pageSize(),
    }),
    loader: ({ request, abortSignal }) => {
      const params = new URLSearchParams();
      if (request.search) params.set('search', request.search);
      request.status.forEach(s => params.append('status', s));
      params.set('page', String(request.page));
      params.set('size', String(request.pageSize ?? 50));
      return fetch(`${this.apiBase}/customers?${params}`, { signal: abortSignal })
        .then(r => r.json());
    },
  });

  readonly totalCount = computed(() => this.customers.value()?.total ?? 0);
  readonly isLoading = computed(() => this.customers.isLoading());

  openDetail(id: string) {
    this.router.navigate(['/system/customers', id]);
  }
}
```

```html
<!-- features/system/customers/customers-list.component.html -->
<div class="flex flex-col h-full bg-[var(--surface)] text-[var(--text-primary)]">
  <header class="flex items-center justify-between px-6 py-4 border-b border-[var(--border)]">
    <div>
      <h1 class="text-2xl font-semibold tracking-tight">Clientes</h1>
      <p class="text-sm text-[var(--text-muted)]">{{ totalCount() }} cadastrados</p>
    </div>
    <button
      class="inline-flex items-center gap-2 rounded-xl bg-[var(--accent)] px-4 py-2 text-sm font-medium text-[var(--accent-foreground)] hover:bg-[var(--accent-hover)] transition focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/40"
      (click)="openNew()">
      <ui-icon name="HeroPlus" class="h-4 w-4" />
      Novo Cliente
    </button>
  </header>

  <div class="px-6 py-3 border-b border-[var(--border-subtle)] flex gap-3">
    <input
      type="search"
      [ngModel]="searchTerm()"
      (ngModelChange)="searchTerm.set($event)"
      placeholder="Buscar por nome, CPF ou telefone..."
      class="flex-1 rounded-xl bg-[var(--surface-elevated)] border border-[var(--border)] px-3 py-2 text-sm placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/40" />
    <!-- ...filtros multi-select de status... -->
  </div>

  @if (isLoading()) {
    <ui-skeleton variant="table" />
  } @else if (customers.value()?.items?.length === 0) {
    <ui-empty-state
      title="Nenhum cliente ainda"
      description="Cadastre o primeiro cliente para começar"
      illustration="empty-customers" />
  } @else {
    <ui-data-table
      [columns]="columns"
      [rows]="customers.value()!.items"
      (rowClick)="openDetail($event.id)" />
  }
</div>
```

```css
/* customers-list.component.css — propositalmente quase vazio */

:host { display: block; height: 100%; }
```

### 10.3 `styles.css` Global — Tokens

```css
@import "tailwindcss";

@theme {
  /* Light theme defaults */
  --surface: #ffffff;
  --surface-elevated: #fafafa;
  --surface-overlay: rgba(255,255,255,0.85);
  --text-primary: #0a0a0a;
  --text-secondary: #404040;
  --text-muted: #737373;
  --border: #e5e5e5;
  --border-subtle: #f0f0f0;
  --accent: #6366f1;
  --accent-hover: #4f46e5;
  --accent-foreground: #ffffff;
  --success: #10b981;
  --warning: #f59e0b;
  --danger: #ef4444;
  --info: #06b6d4;
  --whatsapp-out: #d9fdd3;
  --whatsapp-in: #ffffff;

  --shadow-sm: 0 1px 2px 0 rgba(0,0,0,0.05);
  --shadow-md: 0 4px 12px -2px rgba(0,0,0,0.08);

  --font-sans: "Inter", ui-sans-serif, system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;
}

[data-theme="dark"] {
  --surface: #0a0a0a;
  --surface-elevated: #171717;
  --surface-overlay: rgba(10,10,10,0.85);
  --text-primary: #fafafa;
  --text-secondary: #a3a3a3;
  --text-muted: #737373;
  --border: #262626;
  --border-subtle: #1a1a1a;
  --accent: #818cf8;
  --accent-hover: #6366f1;
  --accent-foreground: #0a0a0a;
  --whatsapp-out: #005c4b;
  --whatsapp-in: #1f2937;
}

html, body {
  background: var(--surface);
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-feature-settings: "cv11", "ss01";
}

/* tabular numbers para colunas financeiras */
.tabular { font-variant-numeric: tabular-nums; }

/* respeita reduced motion */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0s !important;
    transition-duration: 0s !important;
  }
}
```

### 10.4 Estado Global vs Local — Regras

| Caso                                            | Onde mora                                            |
|-------------------------------------------------|-------------------------------------------------------|
| Auth (logged user, tokens, permissions)         | `core/services/auth.service.ts` (signal global)      |
| Tema dark/light                                 | `core/services/theme.service.ts`                      |
| Toasts e notificações                           | `core/services/notification.service.ts`               |
| Stream SSE/WS                                   | `core/services/{sse,ws}.service.ts`                   |
| Módulos ativos                                  | `core/services/module.service.ts`                     |
| Lista de clientes da tela atual                 | **componente** com `resource()`                        |
| Filtros da tela                                 | **componente** com signals                             |
| Form em wizard (multi-step)                      | **componente pai** (signals) ou um service local efêmero (não global) |
| Cache cross-tela (ex.: lista de fornecedores)   | `core/services/lookup.service.ts` (signal cache + invalidate) |

> Quando precisar de "service de feature", mantemos a regra do manifesto: **vai para `/core/services/`** (ex.: `customer.service.ts`), nunca em `/features/`. Mas na maioria dos casos, `inject(HttpClient)` + `resource()` direto no componente já é suficiente — Angular 21 reduziu drasticamente a necessidade de services pra dados.

### 10.5 Roteamento

```typescript
// app.routes.ts
import { Routes } from '@angular/router';
import { authGuard } from '@core/guards/auth.guard';

export const routes: Routes = [
  { path: '', redirectTo: 'system/dashboard', pathMatch: 'full' },
  {
    path: 'auth',
    loadChildren: () =>
      import('./features/auth/auth.routes').then(m => m.AUTH_ROUTES),
  },
  {
    path: 'system',
    canActivate: [authGuard],
    loadChildren: () =>
      import('./features/system/system.routes').then(m => m.SYSTEM_ROUTES),
  },
  { path: '**', loadComponent: () => import('./features/not-found/not-found.component').then(m => m.NotFoundComponent) },
];
```

```typescript
// features/system/system.routes.ts
import { Routes } from '@angular/router';
import { SystemComponent } from './system.component';

export const SYSTEM_ROUTES: Routes = [
  {
    path: '',
    component: SystemComponent,
    children: [
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
      {
        path: 'dashboard',
        loadComponent: () => import('./dashboard/dashboard.component').then(m => m.DashboardComponent),
      },
      {
        path: 'customers',
        loadChildren: () => import('./customers/customers.routes').then(m => m.CUSTOMERS_ROUTES),
      },
      {
        path: 'assets',
        loadChildren: () => import('./assets/assets.routes').then(m => m.ASSETS_ROUTES),
      },
      {
        path: 'vehicles',
        loadChildren: () => import('./vehicles/vehicles.routes').then(m => m.VEHICLES_ROUTES),
      },
      {
        path: 'fleet-map',
        loadComponent: () => import('./fleet-map/fleet-map.component').then(m => m.FleetMapComponent),
      },
      { path: 'contracts', loadChildren: () => import('./contracts/contracts.routes').then(m => m.CONTRACTS_ROUTES) },
      { path: 'finance/receivables', loadChildren: () => import('./finance/receivables/receivables.routes').then(m => m.RECEIVABLES_ROUTES) },
      { path: 'finance/payables', loadChildren: () => import('./finance/payables/payables.routes').then(m => m.PAYABLES_ROUTES) },
      { path: 'finance/reconciliation', loadChildren: () => import('./finance/reconciliation/reconciliation.routes').then(m => m.RECONCILIATION_ROUTES) },
      { path: 'finance/dre', loadComponent: () => import('./finance/dre/dre.component').then(m => m.DreComponent) },
      { path: 'inbox', loadChildren: () => import('./inbox/inbox.routes').then(m => m.INBOX_ROUTES) },
      { path: 'reports', loadChildren: () => import('./reports/reports.routes').then(m => m.REPORTS_ROUTES) },
      { path: 'audit', loadChildren: () => import('./audit/audit.routes').then(m => m.AUDIT_ROUTES) },
      { path: 'config', loadChildren: () => import('./config/config.routes').then(m => m.CONFIG_ROUTES) },
    ],
  },
];
```

### 10.6 SSE e WebSocket no Frontend

**SSE (notificações, dashboard, module-specific)**:

```typescript
// core/services/sse.service.ts
import { Injectable, inject, signal, DestroyRef } from '@angular/core';
import { AuthService } from './auth.service';
import { API_BASE_URL } from '@core/tokens/api-base-url.token';

export type SseEvent =
  | { type: 'installment.status_changed'; installment_id: string; new_status: string }
  | { type: 'comprovante.received'; conversation_id: string; message_id: string }
  | { type: 'module.event'; asset_type: string; payload: any }
  | { type: 'agent.action_pending'; action_id: string; description: string };

@Injectable({ providedIn: 'root' })
export class SseService {
  private auth = inject(AuthService);
  private base = inject(API_BASE_URL);
  private es?: EventSource;
  readonly connected = signal(false);
  readonly lastEvent = signal<SseEvent | null>(null);

  connect(channel: 'notifications' | 'dashboard' | `module/${string}`) {
    const token = this.auth.accessToken();
    if (!token) return;
    this.es?.close();
    // FastAPI aceita token via query string para SSE (cookie não funciona em EventSource cross-origin)
    this.es = new EventSource(`${this.base}/sse/${channel}?token=${token}`);
    this.es.onopen = () => this.connected.set(true);
    this.es.onerror = () => this.connected.set(false);
    this.es.onmessage = (msg) => {
      try {
        this.lastEvent.set(JSON.parse(msg.data));
      } catch {}
    };
  }

  disconnect() { this.es?.close(); this.connected.set(false); }
}
```

**WebSocket (chat WhatsApp)**:

```typescript
// core/services/ws.service.ts (esboço)
@Injectable({ providedIn: 'root' })
export class WsService {
  private ws?: WebSocket;
  readonly messages = signal<ChatMessage[]>([]);
  // ...connect, send, reconnect com backoff
}
```

### 10.7 Drag-and-Drop — Padrões de Uso

- **CDK `@angular/cdk/drag-drop`** para todos os casos (cobre 99%).
- Componente **wrapper** `<ui-drag-list>` em `shared/components/drag-list/` para casos genéricos (lista reordenável).
- Para conciliação (split com 2 listas): **2 `cdkDropList` conectadas** via `[cdkDropListConnectedTo]`.
- Anti-padrão: **não** usar libs externas (SortableJS, react-dnd-port etc.) — CDK é suficiente.

### 10.8 Acessibilidade

- Componente `<ui-icon>` aceita `aria-label`.
- Modais usam diretiva `focusTrap` própria.
- `<button>` por padrão é `type="button"` (evita submit acidental).
- `aria-live="polite"` no toast.
- `aria-current="page"` na sidebar.

---

## 11. Arquitetura do Backend (FastAPI)

### 11.1 Bootstrap e Lifespan

```python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.v1 import (
    auth_routes, customer_routes, asset_routes, contract_routes,
    receivable_routes, payable_routes, reconciliation_routes,
    conversation_routes, dashboard_routes, report_routes,
    admin_routes, webhook_routes, module_routes,
)
from app.api.sse import router as sse_router
from app.api.ws import router as ws_router
from app.api.exception_handlers import register_exception_handlers
from app.api.middleware import CorrelationIdMiddleware, AccessLogMiddleware
from app.core.config import settings
from app.core.module_registry import ModuleRegistry
from app.infrastructure.observability.logging import configure_logging
from app.infrastructure.observability.tracing import configure_tracing
from app.infrastructure.db.session import sessionmaker_factory, dispose_engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    configure_tracing(app)
    app.state.sessionmaker = sessionmaker_factory()
    # Register vertical modules
    _register_modules(app)
    yield
    await dispose_engine()

def _register_modules(app: FastAPI):
    """Bootstrap all vertical asset modules."""
    from app.modules.vehicles.module import VehicleModule
    vehicle_mod = VehicleModule(app.state.sessionmaker)
    ModuleRegistry.register(vehicle_mod)

    # Future: PropertyModule, EquipmentModule, etc.

    # Mount module routes dynamically
    for asset_type, module in ModuleRegistry.all().items():
        app.include_router(
            module.get_router(),
            prefix=f"/api/v1/modules/{asset_type}",
            tags=[f"module:{asset_type}"],
        )

def create_app() -> FastAPI:
    app = FastAPI(
        title="{{product_name}} API",
        version="2.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.add_middleware(GZipMiddleware, minimum_size=512)
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)

    api_prefix = "/api/v1"
    for r in [
        auth_routes.router, customer_routes.router, asset_routes.router,
        contract_routes.router, receivable_routes.router, payable_routes.router,
        reconciliation_routes.router, conversation_routes.router,
        dashboard_routes.router, report_routes.router,
        admin_routes.router, webhook_routes.router,
    ]:
        app.include_router(r, prefix=api_prefix)
    app.include_router(sse_router, prefix="/sse")
    app.include_router(ws_router)  # /ws/...
    return app

app = create_app()
```

### 11.2 Settings (Pydantic)

```python
# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_ENV: str = "dev"
    SECRET_KEY: str
    JWT_PRIVATE_KEY_PATH: str
    JWT_PUBLIC_KEY_PATH: str
    ACCESS_TOKEN_TTL_MIN: int = 15
    REFRESH_TOKEN_TTL_DAYS: int = 7
    CORS_ORIGINS: list[str] = ["http://localhost:4200"]

    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_BUCKET: str = "platform"
    S3_REGION: str = "us-east-1"

    # Adapters (Core)
    WHATSAPP_PROVIDER: str = "evolution"
    EVOLUTION_API_URL: str | None = None
    EVOLUTION_API_KEY: str | None = None
    EVOLUTION_INSTANCE: str | None = None
    LLM_PROVIDER: str = "openai"
    OPENAI_API_KEY: str | None = None
    LLM_MODEL: str = "gpt-4o"
    OCR_PROVIDER: str = "tesseract"
    BANK_PROVIDER: str = "local"          # 'local' | 'pluggy' | ...
    PLUGGY_CLIENT_ID: str | None = None
    PLUGGY_CLIENT_SECRET: str | None = None
    PAYMENT_GATEWAY_PROVIDER: str = "none" # default: no gateway (Pix próprio)

    # Module: Vehicles
    FIPE_PROVIDER: str = "apifipe_br"
    FIPE_API_TOKEN: str | None = None
    TRACKER_PROVIDER: str = "generic_rest"

    # Observability
    OTEL_EXPORTER_OTLP_ENDPOINT: str | None = None
    LOG_LEVEL: str = "INFO"

    # Encryption
    KMS_MASTER_KEY: bytes  # 32 bytes

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
```

### 11.3 Padrão de Injeção de Dependência

FastAPI nativo cobre o caso. Cada use case é registrado via `Depends`:

```python
# app/api/deps.py
from typing import Annotated, TypeVar, Type
from fastapi import Depends, Header, Cookie
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import SessionDep
from app.infrastructure.db.repositories.customer_repo import SqlCustomerRepo
from app.infrastructure.db.repositories.installment_repo import SqlInstallmentRepo
from app.infrastructure.integrations.storage.s3_compatible_adapter import S3StorageAdapter
from app.infrastructure.integrations.ocr.tesseract_adapter import TesseractOcrAdapter
from app.infrastructure.messaging.event_bus import EventBus
from app.application.finance.write_off_installment import WriteOffInstallment
# ...

T = TypeVar("T")

def get_use_case(uc_class: Type[T]) -> Type[T]:
    """Factory que devolve uma função 'Depends'-compatible para o use case dado."""
    if uc_class is WriteOffInstallment:
        async def _build(session: SessionDep) -> WriteOffInstallment:
            return WriteOffInstallment(
                installments=SqlInstallmentRepo(session),
                contracts=SqlContractRepo(session),
                storage=S3StorageAdapter(),
                ocr=TesseractOcrAdapter(),
                audit=AuditLogger(session),
                event_bus=EventBus(),
                clock=SystemClock(),
            )
        return _build
    # ... demais use cases ...
    raise ValueError(f"Unknown use case {uc_class}")
```

> Para projetos maiores, vale considerar `dishka` ou `wired` como container DI; no MVP, fábricas explícitas bastam.

### 11.4 Padrões de Erro e Exception Handlers

```python
# app/domain/shared/exceptions.py
class DomainError(Exception):
    code: str = "DOMAIN_ERROR"
    http_status: int = 400

class NotFoundError(DomainError):
    code = "NOT_FOUND"
    http_status = 404

class RuleViolation(DomainError):
    code = "RULE_VIOLATION"
    http_status = 409

class InstallmentImmutable(RuleViolation):
    code = "INSTALLMENT_IMMUTABLE"

class PartialPaymentInvalid(RuleViolation):
    code = "PARTIAL_PAYMENT_INVALID"

# app/api/exception_handlers.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.domain.shared.exceptions import DomainError

def register_exception_handlers(app: FastAPI):
    @app.exception_handler(DomainError)
    async def domain_handler(request: Request, exc: DomainError):
        return JSONResponse(
            status_code=exc.http_status,
            content={
                "type": f"https://{{product_name_slug}}.com/errors/{exc.code.lower().replace('_','-')}",
                "title": exc.__class__.__name__,
                "status": exc.http_status,
                "detail": str(exc),
                "instance": str(request.url),
                "code": exc.code,
                "request_id": request.state.correlation_id,
            },
            media_type="application/problem+json",
        )
    # handler genérico p/ Exception -> 500 com correlation_id (sem vazar stack)
```

### 11.5 Workers Celery — Estrutura e Arquitetura de Filas

#### 11.5.1 Arquitetura de 7 Filas

O sistema utiliza **7 filas especializadas** (mais a fila do agente) com configurações distintas de paralelismo, priorizando throughput onde necessário e isolamento onde crítico:

| Fila                     | Workers | Threads/Worker | Domínio                                         | Prioridade |
|--------------------------|---------|---------------|--------------------------------------------------|------------|
| `fila_cobranca`          | 4       | 4             | Geração de títulos, encargos, cobranças          | Alta       |
| `fila_notificacoes`      | 2       | 4             | Envio WhatsApp, email, SSE                        | Alta       |
| `fila_verificacao`       | 2       | 4             | OCR, reconciliação, comprovantes                  | Média      |
| `fila_contratos`         | 2       | 2             | Ciclo de vida de contratos                        | Média      |
| `fila_frota`             | 2       | 2             | GPS, FIPE, documentos de veículo                  | Média      |
| `fila_padrao`            | 2       | 2             | Coordinators, manutenção geral                    | Baixa      |
| `fila_whatsapp_entrada`  | 2       | 4             | Inbound WhatsApp (prioridade máxima)              | Máxima     |
| `fila_agente`            | 2       | 1 (por worker)| Turno do agente LLM (I/O-bound, sem paralelismo) | Média      |

> **Regra do Beat**: `replicas=1` SEMPRE para o Celery Beat. Escalar o Beat para 2+ réplicas resulta em disparo duplicado de tasks agendadas. Escalar apenas os workers.

#### 11.5.2 Padrão Fan-Out (Coordinator -> Lotes de 50)

Tasks pesadas seguem o padrão **coordinator -> lotes**: o coordinator é uma task leve que roda no Beat, consulta IDs elegíveis via `SELECT FOR UPDATE SKIP LOCKED` e dispara um `chord` de tasks de lote de até 50 registros cada.

```python
# workers/tasks/cobranca/coordinators.py
from celery import chord
from app.workers.celery_app import celery_app
from app.infrastructure.db.session import sync_session_factory

@celery_app.task(name="coordenador_processar_titulos_vencidos", queue="fila_padrao")
def coordenador_processar_titulos_vencidos():
    """
    Coordinator leve — roda no Beat.
    Não executa lógica de negócio; apenas fragmenta o trabalho.
    """
    with sync_session_factory() as db:
        ids = db.execute(
            "SELECT id FROM titulos "
            "WHERE status = 'em_aberto' AND data_vencimento < NOW()::DATE "
            "FOR UPDATE SKIP LOCKED"
        ).scalars().all()

    if not ids:
        return {"processados": 0}

    lotes = [ids[i:i+50] for i in range(0, len(ids), 50)]
    chord(
        [processar_lote_titulos_vencidos.s(lote) for lote in lotes],
        registrar_resultado_cobranca.s()
    ).apply_async(queue="fila_cobranca")

    return {"lotes_despachados": len(lotes), "total_ids": len(ids)}


@celery_app.task(
    name="processar_lote_titulos_vencidos",
    queue="fila_cobranca",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def processar_lote_titulos_vencidos(self, ids: list[str]):
    """Processa um lote de até 50 títulos vencidos."""
    import asyncio
    return asyncio.run(_processar_lote_async(ids))
```

#### 11.5.3 Três Camadas de Idempotência

Toda task do motor de cobrança implementa **3 camadas de idempotência** para evitar processamento duplicado em caso de retry, falha de rede ou reinício de worker:

1. **`SELECT FOR UPDATE SKIP LOCKED` no PostgreSQL** — o coordinator pega somente IDs não bloqueados por outra transação em andamento.
2. **Redis lock com TTL** — antes de processar um título individual, a task adquire `SET titulo:{id}:cobranca NX EX 60`. Se já existir, pula.
3. **Coluna `proxima_acao_em TIMESTAMPTZ` na tabela `titulos`** — a task verifica se `proxima_acao_em > NOW()` antes de processar. Se sim, o título já foi agendado para o futuro e não deve ser reprocessado agora.

```python
# Exemplo de idempotência em task individual
async def _aplicar_encargos_titulo(titulo_id: str, db, redis):
    # Camada 2: Redis lock
    lock_key = f"titulo:{titulo_id}:encargos"
    acquired = await redis.set(lock_key, "1", nx=True, ex=60)
    if not acquired:
        return {"status": "skipped", "reason": "lock_exists"}

    titulo = await db.get(Titulo, titulo_id)
    if not titulo:
        return {"status": "not_found"}

    # Camada 3: coluna proxima_acao_em
    if titulo.proxima_acao_em and titulo.proxima_acao_em > datetime.now(UTC):
        return {"status": "skipped", "reason": "scheduled_for_future"}

    # Lógica de negócio aqui...
```

#### 11.5.4 Inventário de Tasks (32 tasks — 9 existentes + 23 novas)

**Grupo 1 — Geração (fila_cobranca):**

| Task | Status | Descrição |
|------|--------|-----------|
| `gerar_titulos_mensais` | A implementar | Gera parcelas do mês seguinte para contratos ativos |
| `gerar_titulo_antecipado` | A implementar | Gera título fora do ciclo normal (ex.: antecipação) |
| `aplicar_encargos_vencidos` | **CRÍTICO** | Aplica multa + juros diários em títulos vencidos |
| `gerar_titulo_opcao_compra` | A implementar | Gera título de opção de compra ao final do contrato |

**Grupo 2 — Cobrança (fila_notificacoes + fila_cobranca):**

| Task | Status | Descrição |
|------|--------|-----------|
| `enviar_cobranca_titulo` | Existente | Envia cobrança (parcela) via WhatsApp |
| `alertar_vencimentos_proximos` | Existente | Lembrete preventivo N dias antes do vencimento |
| `enviar_cobranca_atraso` | **CRÍTICO** | Cobrança de título vencido com valor atualizado (multa + juros) |
| `enviar_aviso_encargos` | A implementar | Notifica cliente sobre encargos aplicados |
| `enviar_confirmacao_pagamento` | A implementar | Confirma recebimento após baixa |
| `enviar_campanha_disparo` | Existente | Disparo em massa (broadcast) |
| `enviar_alerta_opcao_compra` | A implementar | Alerta opção de compra próxima do vencimento |

**Grupo 3 — Verificação (fila_verificacao):**

| Task | Status | Descrição |
|------|--------|-----------|
| `verificar_comprovante_recebido` | Existente | Pipeline de validação de comprovante recebido |
| `processar_ocr_comprovante` | Existente | OCR Tesseract + OpenCV em imagem de comprovante |
| `reconciliar_pagamento_pix` | **CRÍTICO** | Reconciliação automática por valor + data + chave Pix |
| `conciliar_extrato_bancario` | Existente | Auto-match de transações OFX/Open Finance |
| `detectar_pagamento_parcial` | A implementar | Identifica se comprovante corresponde a pagamento parcial |

**Grupo 4 — Contratos (fila_contratos):**

| Task | Status | Descrição |
|------|--------|-----------|
| `verificar_contratos_encerrados` | A implementar | Detecta contratos no limite de encerramento |
| `gerar_pdf_contrato` | Existente | Renderiza PDF do contrato via WeasyPrint |
| `detectar_inadimplencia_grave` | A implementar | Aciona suspensão após `limite_dias_suspensao` |
| `reverter_inadimplencia` | A implementar | Reverte suspensão após pagamento confirmado |
| `calcular_rescisao_contrato` | A implementar | Calcula valor de rescisão com encargos proporcionais |

**Grupo 5 — Frota (fila_frota):**

| Task | Status | Descrição |
|------|--------|-----------|
| `bloquear_veiculo_gps` | **CRÍTICO** | Aciona bloqueio remoto via rastreador GPS |
| `desbloquear_veiculo_gps` | A implementar | Aciona desbloqueio remoto após pagamento |
| `atualizar_posicao_veiculo` | A implementar | Atualiza `last_position` de todos os rastreadores ativos |
| `atualizar_tabela_fipe` | Existente | Atualiza `fipe_value_current` de veículos ativos |
| `alertar_documentos_vencendo` | A implementar | Alerta sobre CNH, seguro, IPVA próximos do vencimento |
| `verificar_rastreador_offline` | A implementar | Detecta rastreadores sem sinal há mais de N horas |

**Grupo 6 — Infraestrutura (fila_padrao):**

| Task | Status | Descrição |
|------|--------|-----------|
| `atualizar_visoes_materializadas` | Existente | Refresh de `mv_asset_roi` e demais views |
| `backup_banco_dados` | Existente | Backup via wal-g |
| `atualizar_scores_clientes` | Existente | Recomputa score de todos os clientes |
| `transcrever_audio_whatsapp` | Existente | Transcrição de áudios recebidos via Whisper |
| `purgar_eventos_processados` | A implementar | Remove `webhook_events_raw` mais antigos que 90 dias |
| `monitorar_saude_integracoes` | A implementar | Health check de todos os adapters externos |
| `processar_evento_dominio` | Existente | Despacha Domain Events para module hooks |
| `executar_turno_agente` | Existente | Executa turno do agente LLM (fila_agente) |
| `processar_mensagem_entrada` | Existente | Pipeline de mensagem inbound WhatsApp (fila_whatsapp_entrada) |

#### 11.5.5 Celery App — Configuração Completa com 7 Filas

```python
# app/workers/celery_app.py
from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "platform",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.task_routes = {
    # Fila WhatsApp entrada — prioridade máxima
    "workers.tasks.messaging.processar_mensagem_entrada": {"queue": "fila_whatsapp_entrada"},

    # Fila cobrança — alta prioridade, alto throughput
    "workers.tasks.cobranca.*": {"queue": "fila_cobranca"},
    "workers.tasks.cobranca.coordinators.*": {"queue": "fila_padrao"},  # coordinators na fila padrão

    # Fila notificações
    "workers.tasks.notificacoes.*": {"queue": "fila_notificacoes"},

    # Fila verificação
    "workers.tasks.verificacao.*": {"queue": "fila_verificacao"},

    # Fila contratos
    "workers.tasks.contratos.*": {"queue": "fila_contratos"},

    # Fila frota (módulo: vehicles)
    "workers.tasks.frota.*": {"queue": "fila_frota"},

    # Fila agente LLM
    "workers.tasks.agente.*": {"queue": "fila_agente"},

    # Padrão
    "workers.tasks.*": {"queue": "fila_padrao"},
}

celery_app.conf.task_acks_late = True
celery_app.conf.task_reject_on_worker_lost = True
celery_app.conf.worker_prefetch_multiplier = 1  # crítico: garante distribuição justa entre workers

celery_app.autodiscover_tasks(["app.workers.tasks"])

# Beat schedule — REPLICAS=1 SEMPRE (duplicar = disparo duplo)
celery_app.conf.beat_schedule = {
    # Geração de títulos
    "gerar-titulos-mensais": {
        "task": "workers.tasks.cobranca.coordinators.coordenador_gerar_titulos_mensais",
        "schedule": crontab(hour=6, minute=0, day_of_month="1"),
    },
    # Encargos (crítico — roda todo dia)
    "aplicar-encargos-vencidos": {
        "task": "workers.tasks.cobranca.coordinators.coordenador_aplicar_encargos_vencidos",
        "schedule": crontab(hour=7, minute=0),
    },
    # Cobranças
    "alertar-vencimentos-proximos": {
        "task": "workers.tasks.cobranca.coordinators.coordenador_alertar_vencimentos",
        "schedule": crontab(hour=9, minute=0),
    },
    "enviar-cobrancas-atraso": {
        "task": "workers.tasks.cobranca.coordinators.coordenador_enviar_cobrancas_atraso",
        "schedule": crontab(hour=10, minute=0),
    },
    # Contratos
    "verificar-contratos-encerrados": {
        "task": "workers.tasks.contratos.coordinators.coordenador_verificar_contratos",
        "schedule": crontab(hour=8, minute=0),
    },
    # Reconciliação
    "auto-match-reconciliacao": {
        "task": "workers.tasks.verificacao.conciliar_extrato_bancario",
        "schedule": crontab(minute=15),
    },
    # Infra
    "atualizar-scores": {
        "task": "workers.tasks.infra.atualizar_scores_clientes",
        "schedule": crontab(hour=2, minute=0),
    },
    "atualizar-views": {
        "task": "workers.tasks.infra.atualizar_visoes_materializadas",
        "schedule": crontab(hour=3, minute=0),
    },
    "backup-db": {
        "task": "workers.tasks.infra.backup_banco_dados",
        "schedule": crontab(hour=3, minute=30),
    },
    # Frota (módulo: vehicles)
    "atualizar-fipe": {
        "task": "workers.tasks.frota.atualizar_tabela_fipe",
        "schedule": crontab(hour=3, minute=0, day_of_month="5"),
    },
    "verificar-rastreadores": {
        "task": "workers.tasks.frota.verificar_rastreador_offline",
        "schedule": crontab(minute="*/30"),
    },
    "purgar-eventos": {
        "task": "workers.tasks.infra.purgar_eventos_processados",
        "schedule": crontab(hour=4, minute=0, day_of_week="0"),  # domingo
    },
    "monitorar-integracoes": {
        "task": "workers.tasks.infra.monitorar_saude_integracoes",
        "schedule": crontab(minute="*/15"),
    },
}
```

#### 11.5.6 Docker Compose — Workers por Fila

```yaml
# No docker-compose.yml, cada tipo de worker é declarado separadamente:
services:
  worker-cobranca:
    build: ./backend-api
    env_file: .env
    command: >
      celery -A app.workers.celery_app worker
      -l info
      -Q fila_cobranca
      --concurrency=4
      --pool=gevent
      -n worker-cobranca@%h
    deploy:
      replicas: 4
    depends_on: [postgres, redis]

  worker-notificacoes:
    build: ./backend-api
    env_file: .env
    command: >
      celery -A app.workers.celery_app worker
      -l info
      -Q fila_notificacoes
      --concurrency=4
      --pool=gevent
      -n worker-notificacoes@%h
    deploy:
      replicas: 2

  worker-verificacao:
    build: ./backend-api
    env_file: .env
    command: >
      celery -A app.workers.celery_app worker
      -l info
      -Q fila_verificacao
      --concurrency=4
      --pool=gevent
      -n worker-verificacao@%h
    deploy:
      replicas: 2

  worker-contratos:
    build: ./backend-api
    env_file: .env
    command: >
      celery -A app.workers.celery_app worker
      -l info
      -Q fila_contratos
      --concurrency=2
      --pool=gevent
      -n worker-contratos@%h
    deploy:
      replicas: 2

  worker-frota:
    build: ./backend-api
    env_file: .env
    command: >
      celery -A app.workers.celery_app worker
      -l info
      -Q fila_frota
      --concurrency=2
      --pool=gevent
      -n worker-frota@%h
    deploy:
      replicas: 2

  worker-padrao:
    build: ./backend-api
    env_file: .env
    command: >
      celery -A app.workers.celery_app worker
      -l info
      -Q fila_padrao
      --concurrency=2
      --pool=gevent
      -n worker-padrao@%h
    deploy:
      replicas: 2

  worker-whatsapp-entrada:
    build: ./backend-api
    env_file: .env
    command: >
      celery -A app.workers.celery_app worker
      -l info
      -Q fila_whatsapp_entrada
      --concurrency=4
      --pool=gevent
      -n worker-wa-entrada@%h
    deploy:
      replicas: 2

  worker-agente:
    build: ./backend-api
    env_file: .env
    command: >
      celery -A app.workers.celery_app worker
      -l info
      -Q fila_agente
      --concurrency=1
      --pool=solo
      -n worker-agente@%h
    deploy:
      replicas: 2

  beat:
    build: ./backend-api
    env_file: .env
    command: celery -A app.workers.celery_app beat -l info
    deploy:
      replicas: 1  # NUNCA escalar o Beat
    depends_on: [redis]
```

### 11.6 Real-time: SSE e WS

**SSE com Redis Pub/Sub** (multi-process safe):

```python
# app/api/sse.py
from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse
import asyncio
import redis.asyncio as redis
from app.core.config import settings
from app.api.deps import get_current_user_query_token

router = APIRouter()

@router.get("/notifications")
async def sse_notifications(request: Request, user = Depends(get_current_user_query_token)):
    r = redis.from_url(settings.REDIS_URL)
    pubsub = r.pubsub()
    await pubsub.subscribe(f"sse:user:{user.id}")

    async def event_generator():
        try:
            yield {"event": "ready", "data": "{}"}
            async for msg in pubsub.listen():
                if await request.is_disconnected():
                    break
                if msg["type"] == "message":
                    yield {"event": "message", "data": msg["data"].decode()}
        finally:
            await pubsub.unsubscribe()
            await r.close()
    return EventSourceResponse(event_generator())

@router.get("/module/{asset_type}")
async def sse_module(asset_type: str, request: Request, user = Depends(get_current_user_query_token)):
    """SSE channel for module-specific events (e.g., vehicle tracker positions)."""
    r = redis.from_url(settings.REDIS_URL)
    pubsub = r.pubsub()
    await pubsub.subscribe(f"sse:module:{asset_type}")

    async def event_generator():
        try:
            yield {"event": "ready", "data": "{}"}
            async for msg in pubsub.listen():
                if await request.is_disconnected():
                    break
                if msg["type"] == "message":
                    yield {"event": "message", "data": msg["data"].decode()}
        finally:
            await pubsub.unsubscribe()
            await r.close()
    return EventSourceResponse(event_generator())
```

**WebSocket Hub para Chat**:

```python
# app/api/ws.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
import redis.asyncio as redis
import json
from app.core.config import settings
from app.api.deps import get_current_user_query_token

router = APIRouter()

@router.websocket("/ws/conversations")
async def ws_conversations(ws: WebSocket, user = Depends(get_current_user_query_token)):
    await ws.accept()
    r = redis.from_url(settings.REDIS_URL)
    pubsub = r.pubsub()
    await pubsub.subscribe("ws:conversations")  # broadcast para gestores
    try:
        async def from_redis():
            async for msg in pubsub.listen():
                if msg["type"] == "message":
                    await ws.send_text(msg["data"].decode())
        async def from_client():
            while True:
                data = await ws.receive_text()
                payload = json.loads(data)
                # ... processa ações do cliente ...
        await asyncio.gather(from_redis(), from_client())
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe()
        await r.close()
```

### 11.7 Idempotência de Webhooks

```python
# app/application/integrations/handle_webhook.py
async def handle_webhook(provider: str, external_id: str, payload: dict, signature_valid: bool, db):
    existing = await db.execute(
        select(WebhookEventRaw).where(
            WebhookEventRaw.provider == provider,
            WebhookEventRaw.external_id == external_id,
        )
    )
    if existing.first():
        return {"status": "duplicate"}
    # insert + dispatch
```

---

## 12. Estrutura do Projeto (Combinada)

```
project-root/                              # diretório raiz (sem product name nos paths)
├── docker-compose.yml                     # postgres + redis + minio + api + worker + beat + web
├── docker-compose.prod.yml                # produção (sem volumes locais, com TLS)
├── .env.example
├── README.md
├── backend-api/                           # backend (Python)
│   ├── pyproject.toml
│   ├── uv.lock                            # ou poetry.lock
│   ├── ruff.toml
│   ├── mypy.ini
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── app/                               # ver Seção 6
│   │   ├── modules/                       # módulos verticais (ver Seção 7)
│   │   │   └── vehicles/
│   │   └── ...
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   ├── contract/                      # schemathesis
│   │   ├── load/                          # k6 scripts
│   │   └── conftest.py
│   └── scripts/
│       ├── seed.py
│       ├── reset_db.sh
│       └── load_test.sh
└── frontend/                              # frontend (Angular)
    ├── package.json
    ├── angular.json
    ├── tsconfig.json
    ├── tsconfig.app.json
    ├── tsconfig.spec.json
    ├── tailwind.config.ts
    ├── eslint.config.js
    ├── prettier.config.js
    ├── stylelint.config.js
    ├── playwright.config.ts
    ├── vitest.config.ts
    ├── Dockerfile                         # multi-stage com nginx
    ├── nginx.conf
    ├── public/                            # ver Seção 10
    └── src/                               # ver Seção 10
```

---

## 13. Fluxo de Desenvolvimento

### 13.1 Pré-requisitos do Dev

- Docker + docker-compose.
- Python 3.12+ com `uv` (`curl -LsSf https://astral.sh/uv/install.sh | sh`).
- Node 20+ + pnpm (ou npm).
- Make.

### 13.2 Setup Local

```bash
git clone <repo>
cd project-root
cp .env.example .env
docker compose up -d postgres redis minio   # infra
# backend
cd backend-api
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
alembic upgrade head
python -m app.cli seed          # cria admin@platform.local / Admin@123
uvicorn app.main:app --reload
# frontend (em outra aba)
cd ../frontend
pnpm install
pnpm dev                         # ng serve em :4200
# workers (em outra aba)
cd ../api
celery -A app.workers.celery_app worker -l info
celery -A app.workers.celery_app beat -l info
```

### 13.3 Comandos Make Padronizados


```makefile
# Makefile
.PHONY: up down api web worker beat test lint format migrate seed

up:        ## sobe stack completa
	docker compose up -d

down:
	docker compose down

api:
	cd backend-api && uvicorn app.main:app --reload

web:
	cd frontend && pnpm dev

worker:
	cd backend-api && celery -A app.workers.celery_app worker -l info

beat:
	cd backend-api && celery -A app.workers.celery_app beat -l info

migrate:
	cd backend-api && alembic upgrade head

migration:
	cd backend-api && alembic revision --autogenerate -m "$(m)"

seed:
	cd backend-api && python -m app.cli seed

test:
	cd backend-api && pytest -v --cov=app --cov-report=term
	cd frontend && pnpm test

lint:
	cd backend-api && ruff check . && mypy app
	cd frontend && pnpm lint

format:
	cd backend-api && ruff format .
	cd frontend && pnpm format
```

### 13.4 Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks:
      - id: ruff
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.11.2
    hooks:
      - id: mypy
        files: ^backend-api/app/
        args: [--config-file=backend-api/mypy.ini]
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks: [{id: detect-secrets}]
  - repo: local
    hooks:
      - id: web-lint
        name: web lint
        entry: bash -c 'cd frontend && pnpm lint'
        language: system
        files: ^frontend/
        pass_filenames: false
```

### 13.5 Convenção de Branches e Commits

- `main` — protegida, deploys.
- `develop` — opcional; se simples, ir direto para `main` via PR.
- Features: `feat/{epic}-{story}-{slug}` (ex.: `feat/4-receivables-bulk-write-off`).
- Conventional Commits: `feat(receivables): bulk write-off endpoint`, `fix(reconciliation): ofx fitid dedupe`, `chore(ci): bump python 3.12`.

---

## 14. Arquitetura de Deploy

### 14.1 Ambientes

| Ambiente | Propósito                  | URL                                      |
|----------|----------------------------|------------------------------------------|
| dev      | Local                      | http://localhost:4200 / :8000             |
| staging  | Cliente revisar releases   | https://staging.example.com               |
| prod     | Operação                   | https://app.example.com                   |

### 14.2 Topologia de Produção

**Opção A — VPS único (recomendada inicialmente, sob Coolify/Dokploy):**

```mermaid
flowchart TB
    Internet -.HTTPS.-> Caddy[Caddy<br/>auto-TLS Let's Encrypt]
    Caddy --> Web[Container Angular<br/>nginx serve build]
    Caddy --> API[Container FastAPI<br/>uvicorn 4 workers]
    API --> PG[Container Postgres 16]
    API --> RD[Container Redis 7]
    API --> MN[Container MinIO]
    Worker[Container Celery Worker] --> PG
    Worker --> RD
    Worker --> MN
    Beat[Container Celery Beat] --> RD
    EvAPI[Container Evolution API] --> RD
    Caddy --> EvAPI
```

**Opção B — Kubernetes (quando crescer):**

- Deployments separados: `web`, `api`, `worker`, `beat`, `evolution`.
- Ingress NGINX/Traefik.
- Banco gerenciado (RDS, Supabase, Neon).
- Object store gerenciado (S3, R2).
- Redis gerenciado (Upstash, ElastiCache).

### 14.3 Dockerfiles

**API (multi-stage, slim):**

```dockerfile
# backend-api/Dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv venv /opt/venv && \
    . /opt/venv/bin/activate && \
    uv pip install --no-cache .

FROM python:3.12-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpangocairo-1.0-0 libpango-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
    tesseract-ocr tesseract-ocr-por libtesseract-dev libleptonica-dev \
    libpq5 curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /app
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD curl -f http://localhost:8000/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

**Web (Angular build + nginx):**

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM nginx:1.27-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist/frontend/browser /usr/share/nginx/html
EXPOSE 80
```

### 14.4 docker-compose (dev)

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: platform
      POSTGRES_PASSWORD: platform
      POSTGRES_DB: platform
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL","pg_isready -U platform"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minio
      MINIO_ROOT_PASSWORD: miniominio
    ports: ["9000:9000","9001:9001"]
    volumes: [miniodata:/data]

  evolution:
    image: atendai/evolution-api:latest
    environment:
      AUTHENTICATION_API_KEY: change-me
      DATABASE_PROVIDER: postgresql
      DATABASE_CONNECTION_URI: postgres://platform:platform@postgres:5432/evolution
    ports: ["8080:8080"]
    depends_on: [postgres, redis]

  api:
    build: ./backend-api
    env_file: .env
    depends_on: [postgres, redis, minio]
    ports: ["8000:8000"]
    volumes: ["./backend-api:/app"]

  worker:
    build: ./backend-api
    env_file: .env
    depends_on: [postgres, redis, minio]
    command: celery -A app.workers.celery_app worker -l info -Q default,high,low,agent,ocr

  beat:
    build: ./backend-api
    env_file: .env
    depends_on: [redis]
    command: celery -A app.workers.celery_app beat -l info

  web:
    build: ./frontend
    ports: ["4200:80"]

volumes:
  pgdata: {}
  miniodata: {}
```

### 14.5 CI/CD (GitHub Actions — sumário)

- `api-ci.yml`: triggers em PR tocando `backend-api/**` -> ruff + mypy + pytest com Postgres testcontainer + build Docker (push para registry em `main`).
- `web-ci.yml`: triggers em `frontend/**` -> eslint + vitest + build prod.
- `e2e.yml`: nightly em `main` rodando Playwright contra staging.
- `deploy-staging.yml`: ao push em `main`, deploy automático para staging.
- `deploy-prod.yml`: manual (release tag).

---

## 15. Segurança

### 15.1 Defesa em Camadas

| Camada                | Controles                                                                                  |
|-----------------------|--------------------------------------------------------------------------------------------|
| Edge (Caddy/Traefik)  | TLS 1.3, redirect 80->443, HSTS 1y, rate limit 100req/IP/min, body size 25MB.               |
| Aplicação             | CORS allow-list, CSP, X-Frame-Options DENY, X-Content-Type-Options nosniff, Permissions-Policy. |
| Auth                  | JWT RS256 15min, refresh rotation 7d em HttpOnly Secure SameSite=Lax, MFA TOTP opcional.   |
| Autorização           | RBAC por permissão (`code`); checks via `Depends(require_permission("..."))`.              |
| Dados em repouso      | AES-256-GCM em campos sensíveis (CPF, CNH, mfa_secret, integration_credentials.config).    |
| Banco                 | Conexões TLS, role mínimo (read/write nos schemas necessários), backups encriptados.        |
| Object Storage        | Buckets privados; URLs pré-assinadas com TTL 5min para downloads.                          |
| Logs                  | PII redactado (CPF mascarado XXX.XXX.XXX-99) por filtro em structlog.                       |
| Webhook validation    | Assinaturas HMAC (Evolution: apikey header; Pluggy: signature header SHA256).               |
| Secrets               | Vault ou Doppler (prod), `.env` nunca commitado (validado por detect-secrets pre-commit).   |

### 15.2 Modelo de Ameaças — Principais Vetores

| Ameaça                                  | Mitigação                                                                  |
|-----------------------------------------|-----------------------------------------------------------------------------|
| Furto de access token                   | TTL curto (15min); detection via geo-anomaly futuro.                        |
| Furto de refresh token                  | Rotação obrigatória; lista de revogação em Redis; HttpOnly impede XSS read. |
| XSS via templates                        | Angular sanitiza por padrão; `[innerHTML]` proibido sem `safeHtml.pipe`.    |
| SQL Injection                            | SQLAlchemy ORM com bind params; sem string concat em queries.               |
| CSRF                                     | SameSite=Lax + verificação de Origin em mutações públicas (webhooks).        |
| Comprovante falsificado                  | OCR + validação humana + conciliação bancária definitiva (3 camadas).       |
| Ação de módulo maliciosa (ex.: bloqueio) | Aprovação dupla (perfil + senha); audit_log assinado; rate limit por ativo.  |
| Vazamento de PII em log                  | Filtro structlog `mask_pii`; revisão CI por regex.                          |
| Webhook spoofing                         | Assinatura validada; idempotência por `(provider, external_id)`; insert-only inicial. |
| Replay de mensagem WhatsApp              | `external_id` UNIQUE + janela temporal.                                      |
| Bypass de imutabilidade de título pago   | Trigger PG `enforce_paid_immutability` + checks no domínio.                  |

### 15.3 LGPD

- **Consentimentos** registrados em tabela `consents` (futura) com tipo (uso de imagem, contato WhatsApp, localização) + timestamp.
- **Direito de acesso**: endpoint `GET /api/v1/customers/{id}/data-export` (Admin/dono dos dados) gera ZIP completo.
- **Direito de exclusão**: anonimização (não delete físico — financeiro precisa reter): substitui `full_name='[redigido]'`, mascara CPF, foto, etc., mantém histórico financeiro.
- **DPO**: e-mail de contato em footer + Configurações > Privacidade.

---

## 16. Performance

### 16.1 Targets

- API P50 <= 80 ms, P95 <= 300 ms (read), 500 ms (write).
- Frontend FCP <= 1.2s, TTI <= 2.5s em 4G.
- Lista de 10k títulos rola fluida.
- Mapa renderiza 200 marcadores com cluster sem travar.

### 16.2 Estratégias Backend

- **Query budget**: nenhum endpoint acima de 5 queries; usar `selectinload`/`joinedload` SQLAlchemy.
- **N+1 detection**: middleware em dev que loga selects > N por request.
- **Index coverage** (já no schema acima).
- **Cache Redis** (TTL):
  - Lookups estáticos (categorias, fornecedores) — 5 min.
  - FIPE (módulo: vehicles) — 30 dias.
  - Permissões do usuário — sessão.
- **Materialized views** para relatórios (`mv_asset_roi`).
- **Pagination cursor-based** em listas crescentes (mensagens, audit_log).
- **Background**: relatórios pesados via Celery + SSE notificação ao concluir.
- **Pool DB**: 20 conns por worker; total = workers x 20; ajustar conforme infra.

### 16.3 Estratégias Frontend

- Lazy loading por feature shell (já configurado).
- `@defer` blocks Angular 17+ para seções below-the-fold.
- Imagens em `next/image`-style (loading=lazy, srcset apropriado).
- Tree-shaking + esbuild.
- Service Worker cache-first para assets estáticos; network-first para API.
- Debounce em buscas (300ms).
- Virtual scrolling em listas > 200 itens (CDK Virtual Scroll).
- Memoization via `computed()` Signals.

---

## 17. Estratégia de Testes

### 17.1 Pirâmide de Testes

```
                  +------------------+
                  |  E2E (Playwright)  | ~5% — fluxos críticos
                  +--------+---------+
                  +--------+-------------+
                  | Component / Contract  | ~15% — schemathesis + ngneat/spectator
                  +--------+-------------+
                  +--------+-----------------+
                  | Integration (testcontainers)| ~25%
                  +--------+-----------------+
                  +--------+--------------------+
                  | Unit (pytest, vitest)        | ~55%
                  +-----------------------------+
```

### 17.2 Backend

- **Unit**: domínio puro 100% coberto (`calculations.py`, `schedule_calculator.py`, `policies.py`, module hooks).
- **Integration**: cada use case testado contra Postgres real (testcontainers); evita mocks de repositório.
- **Contract**: `schemathesis` rodando contra OpenAPI gera tests de propriedade.
- **Security**: testes específicos para imutabilidade (`test_paid_installment_cannot_be_updated`).
- **Modules**: cada módulo tem seus próprios testes em `tests/unit/modules/{asset_type}/` e `tests/integration/modules/{asset_type}/`.

### 17.3 Frontend

- **Unit (Vitest)**: services, pipes, signal-based logic.
- **Component (@ngneat/spectator)**: render + interaction.
- **E2E (Playwright)**: 5 fluxos críticos:
  1. Login -> criar contrato -> ativar -> ver PDF.
  2. Receber WhatsApp simulado -> validar -> conciliar.
  3. Importar OFX -> fazer match drag-and-drop.
  4. Pagamento parcial -> ver novo título gerado.
  5. Renegociar dois títulos vencidos.
- **Visual regression**: Storybook + Chromatic (opcional).

### 17.4 Cobertura Mínima

| Área                | Cobertura mínima |
|---------------------|-------------------|
| Domínio backend     | 90%               |
| Use cases backend   | 80%               |
| Adapters backend    | 60% (mocks externos) |
| Module hooks        | 80%               |
| Frontend services   | 70%               |
| Frontend components | 50% (smoke + interactions críticas) |

---

## 18. Padrões de Codificação

### 18.1 Backend

- **Python 3.12**, type hints em **tudo** (`mypy strict`).
- `ruff format` (88 cols).
- Imports ordenados: stdlib -> 3rd party -> app.
- **Domain layer não importa nada de `infrastructure/`**. Linter custom regra `ARCH001`.
- **Modules (`app/modules/*`) não importam diretamente de outros modules**. Comunicação via Domain Events.
- **Use cases** com sufixo descritivo (`WriteOffInstallment`, `RunAgentTurn`); 1 use case = 1 arquivo.
- **Pydantic v2** com `model_config = ConfigDict(frozen=True)` em VOs.
- Logs sempre estruturados: `log.info("event", install_id=..., user_id=...)`.
- Funções **assíncronas** por padrão na camada HTTP/use case.

### 18.2 Frontend

- **TypeScript strict**.
- Componentes **standalone** sempre.
- **Sem inline templates/styles** (manifesto).
- **CSS files vazios**, exceto exceções (keyframes complexas).
- **Tailwind classes** com `var(--token)` — proibido cor fixa.
- Imports com paths absolutos (`@core/...`, `@shared/...`, `@features/...` em `tsconfig.json`).
- **Reactive Forms tipados** (sem template-driven).
- **Signals** para estado local; **`resource()`** para data fetch; **`computed()`** para derivações; **`effect()`** apenas em side effects.
- **Sem RxJS** quando `resource()` resolve. Quando precisar, pelo menos `takeUntilDestroyed()`.
- **Atalhos** mapeados via diretiva `[shortcut]`.

### 18.3 Convenções de Nomenclatura

| Item                       | Convenção                              |
|----------------------------|----------------------------------------|
| Tabelas                    | snake_case plural (`customers`)         |
| Colunas                    | snake_case                              |
| Models SQLAlchemy          | PascalCase singular (`Customer`)        |
| Pydantic DTOs              | PascalCase + sufixo (`CustomerCreate`, `CustomerOut`) |
| Use cases                  | VerboPhrase (`WriteOffInstallment`)     |
| Endpoints REST             | kebab-case + recurso plural             |
| Eventos de domínio         | PastTense (`InstallmentPaid`)            |
| Module hooks               | on_snake_case (`on_installment_overdue`) |
| Componentes Angular        | kebab-case file (`customer-form.component.ts`) + PascalCase class |
| Signals                    | substantivo (`customers`, `searchTerm`); sem prefixo `$` |

---

## 19. Estratégia de Tratamento de Erros

### 19.1 Princípios

1. **Fail fast no domínio** — exceções de regra de negócio (`RuleViolation`) são levantadas imediatamente.
2. **Adaptadores devem traduzir erros externos** em `IntegrationError` (subclasse de `DomainError`) com `provider` no payload.
3. **Retries somente em transientes** (timeout, 503) via `tenacity`.
4. **Idempotência** em mutações expostas a webhook ou cliente sujeito a retry.
5. **Frontend trata RFC 7807** uniformemente via `error.interceptor.ts`.

### 19.2 Catálogo de Códigos de Erro

| code                              | http | quando                                              |
|-----------------------------------|------|-----------------------------------------------------|
| `VALIDATION_ERROR`                | 422  | Pydantic validation                                  |
| `NOT_FOUND`                       | 404  | Entidade não encontrada                              |
| `PERMISSION_DENIED`               | 403  | Falta permissão                                       |
| `UNAUTHENTICATED`                 | 401  | Sem token ou token inválido                          |
| `RULE_VIOLATION`                  | 409  | Regra de domínio violada (genérico)                   |
| `INSTALLMENT_IMMUTABLE`           | 409  | Tentativa de alterar título pago                       |
| `PARTIAL_PAYMENT_INVALID`         | 409  | Pagamento parcial com valor inválido                   |
| `CONTRACT_NOT_EDITABLE`           | 409  | Contrato encerrado/rescindido                         |
| `RECEIPT_AMBIGUOUS`               | 409  | OCR não conseguiu mapear para 1 título                |
| `INTEGRATION_UNAVAILABLE`         | 503  | Provedor externo caiu (todos os fallbacks)             |
| `INTEGRATION_WHATSAPP_FAILED`     | 502  | Gateway WhatsApp não respondeu                        |
| `RATE_LIMIT_EXCEEDED`             | 429  | Limit por IP/usuário                                  |
| `WEBHOOK_INVALID_SIGNATURE`       | 401  | Webhook sem assinatura válida                          |
| `OCR_LOW_CONFIDENCE`              | 200  | Não erro, mas flag para o agente pedir intervenção    |
| `MODULE_NOT_FOUND`                | 404  | Módulo vertical não registrado para asset_type         |

### 19.3 Padrão Frontend

```typescript
// core/interceptors/error.interceptor.ts
export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const notify = inject(NotificationService);
  return next(req).pipe(
    catchError((err: HttpErrorResponse) => {
      if (err.error?.code === 'INSTALLMENT_IMMUTABLE') {
        notify.error('Esta parcela já foi paga e não pode ser editada.');
      } else if (err.error?.code === 'PARTIAL_PAYMENT_INVALID') {
        notify.error('Valor do pagamento parcial inválido.');
      } else if (err.status === 401) {
        // já tratado pelo jwt.interceptor; só passa adiante
      } else if (err.error?.detail) {
        notify.error(err.error.detail);
      } else {
        notify.error('Algo deu errado. Tente novamente em instantes.');
      }
      return throwError(() => err);
    }),
  );
};
```

---

## 20. Monitoramento e Observabilidade

### 20.1 Pilares

1. **Logs estruturados** (JSON) -> Loki / CloudWatch / Better Stack.
2. **Métricas** (Prometheus) -> Grafana.
3. **Tracing** (OTLP) -> Tempo / Jaeger.
4. **Alerting** -> Alertmanager -> Slack/Telegram do gestor de TI.

### Regras de Taxonomia de Logging

- `category='financial'` — SEMPRE persistido, nunca filtrável off. Cobre: write-off, reversal, reconciliation, payment, generation, rollback.
- `category='security'` — SEMPRE persistido. Cobre: login, logout, falhas de tentativa, violações de permissão, re-autenticação Admin.
- `category='navigation'` — configurável ON/OFF em Configurações > Auditoria. OFF por padrão (economiza storage). Cobre: page views, API reads, search queries.
- `category='info'` — configurável ON/OFF. ON por padrão. Cobre: atividade geral do sistema.
- `category='error'` — SEMPRE persistido. Cobre: exceções, falhas de integração, timeout.

### 20.2 Métricas Chave

- `http_requests_total{method,route,status}` — taxa por rota.
- `http_request_duration_seconds{...}` — histograma.
- `celery_task_duration_seconds{task}` — duração jobs.
- `celery_queue_depth{queue}` — backlog.
- `db_pool_used / db_pool_size` — saturação do pool.
- `agent_runs_total{provider,model,status}` — execuções do agente.
- `whatsapp_messages_sent_total{provider,kind}` — outbound.
- `webhook_events_received_total{provider}` / `webhook_events_failed_total{provider}`.
- `installments_paid_total` — KPI de negócio.
- `partial_payments_total` — KPI de pagamentos parciais.
- `reconciliation_pending_count` — health financeiro.
- `module_hooks_dispatched_total{asset_type,event}` — atividade dos módulos.

### 20.3 Dashboards Grafana (versionados em `infra/observability/grafana/`)

1. **Visão geral da API**: RPS, latência P50/95/99, erros.
2. **DB**: connections, locks, slow queries, cache hit ratio.
3. **Workers**: queue depth, retry count, failed tasks.
4. **Negócio**: títulos pagos hoje, mensagens enviadas, score médio, comprovantes pendentes.
5. **Agente IA**: gasto USD/dia, tokens médio, erros LLM, distribuição de actions.
6. **Modules**: hooks dispatched, actions per module, errors per module.

### 20.4 Alertas (Alertmanager)

- API 5xx > 1% por 5 min.
- Latência P95 > 1s por 10 min.
- Celery queue > 1000 itens por 5 min.
- DB conn pool > 90% por 5 min.
- Disk > 85%.
- Webhook event failures > 5% por 10 min.
- Agente IA gasto diário > limite parametrizado.

---

## 21. Estratégia de Migração e Rollout

### 21.1 Migração de Dados do Excel

> O cliente já tem dezenas de linhas de Excel com clientes, ativos e contratos. **Esta migração é parte do go-live.**

**Story M1 — Importador One-Shot CLI**

- CLI `python -m app.cli import-excel --file=clientes.xlsx --sheet=Clientes` mapeia colunas -> `customers`.
- Idem para `veiculos.xlsx` (cria asset + vehicle), `contratos.xlsx`.
- Modo `--dry-run` valida sem persistir.
- Relatório com diferenças.
- Permite rerun (idempotente por CPF/placa).

### 21.2 Rollout Faseado

| Semana | Marco                                                                              |
|--------|------------------------------------------------------------------------------------|
| 1-2    | Épicos 1 (Foundation) + 2 (Cadastros) — gestor cadastra clientes/ativos.           |
| 3-4    | Épico 3 (Contratos) — gera contratos e emite PDF.                                  |
| 5-6    | Épicos 4 + 5 (CR/CP) — operação financeira completa, ainda manual.                  |
| 7-8    | Épico 7 (Conciliação) — reduz erro de baixa.                                        |
| 9-11   | Épico 6 (WhatsApp + Agente) — onboarding gradual: começa em **dry-run** (agente sugere, humano envia), evolui para autopilot. |
| 12     | Épico 8 (Dashboards) + Épico 9 (Hardening, integrações painel) — **GA**.            |

### 21.3 Estratégia de Banco de Dados

- Sempre via Alembic; nunca alterar schema manualmente.
- **Backward-compatible migrations**: adicionar coluna nullable + backfill + tornar NOT NULL em segunda migration.
- **Zero downtime** futuro: separar deploy de migration de deploy de código.

### 21.4 ADRs (Architecture Decision Records)

> Cada decisão importante vira um ADR em `docs/adrs/NNNN-titulo.md`. Lista inicial:

| #   | Título                                                         |
|-----|----------------------------------------------------------------|
| 0001 | Adotar Hexagonal Ports & Adapters como tema central             |
| 0002 | SSE como mecanismo primário de notificação; WS exclusivo para chat |
| 0003 | pgvector ao invés de Qdrant/Weaviate                             |
| 0004 | Celery ao invés de Dramatiq/Arq                                  |
| 0005 | Evolution API self-hosted como WhatsApp default                  |
| 0006 | Tesseract local como OCR default; LLM Vision como fallback       |
| 0007 | Pix via WhatsApp como pagamento default (custo zero); gateways como plugins opcionais |
| 0008 | Imutabilidade de título pago via trigger PG + domínio             |
| 0009 | Single-tenant first; multi-tenant em v2 se demandado              |
| 0010 | Core genérico + Asset Abstraction Layer + módulos verticais plugáveis |
| 0011 | Pagamentos parciais com geração automática de título remanescente  |
| 0012 | Domain Events para comunicação Core -> Modules (não importação direta) |
| 0013 | Manter Python para workers; não extrair microsserviço Go            |
| 0014 | Nomenclatura PT-BR para tasks, eventos e ports do domínio financeiro a partir do Épico 12 |

#### ADR-0013 — Manter Python para Workers (não Go)

**Contexto:** Com o crescimento do inventário de tasks (32 tasks), surgiu a proposta de extrair o motor de cobrança como microsserviço Go para ganhar performance.

**Decisão:** Manter Python + Celery + gevent pool para todos os workers.

**Justificativa:**
- O motor de cobrança é **I/O-bound** (PostgreSQL, WhatsApp API, LLM, OCR), não CPU-bound. O gargalo não é processamento de CPU — é latência de rede e espera de banco.
- Python + Celery + gevent pool = **1000+ green threads por processo**, adequado para a escala projetada (dezenas de milhares de títulos/dia, não milhões).
- Extrair um microsserviço Go exigiria **duplicar modelos de dados** (SQLAlchemy → GORM), **duplicar lógica de domínio** (calculations.py, policies.py, value objects) e manter sincronia entre dois codebases.
- O custo de manutenção dupla supera qualquer ganho de performance para a escala atual.

**Condição de revisão:** Extrair microsserviço Go **apenas se** profiling com carga real identificar gargalo CPU específico e mensurável em uma task específica. Até lá, a decisão permanece.

#### ADR-0014 — Nomenclatura PT-BR para Domínio Financeiro (Épico 12+)

**Contexto:** As tasks, eventos e ports do domínio financeiro foram originalmente nomeados em inglês (ex.: `send_preventive_collection`, `InstallmentPaid`). A partir do Épico 12, o domínio financeiro ganhou complexidade suficiente para justificar nomenclatura explícita no idioma do negócio.

**Decisão:** A partir do Épico 12, todos os **novos** nomes de tasks, eventos de domínio, hooks e ports do domínio financeiro são em PT-BR.

**Exemplos:**
- Tasks: `coordenador_processar_titulos_vencidos`, `aplicar_encargos_vencidos`, `enviar_cobranca_atraso`
- Eventos: `OpcaoCompraPaga`, `ContratoSuspenso`, `PassivoInoperanteGerado`
- Tabelas: `politica_cobranca`, `passivos_inoperantes`, `execucoes_motor`

**Escopo:** Somente domínio financeiro (Épico 12+). O Core existente (auth, assets, modules, reconciliation) mantém inglês para não gerar reescrita de código estável. Ver mapeamento completo em `docs/glossario_dominio.md`.

---

## 22. Riscos e Mitigações

| Risco                                                              | Prob | Impacto | Mitigação                                                                              |
|--------------------------------------------------------------------|------|---------|-----------------------------------------------------------------------------------------|
| Evolution API instável (bugs documentados)                          | Alta | Médio   | Adapter abstrato; ZapiAdapter como plano B; monitoramento agressivo de webhook failures. |
| Banimento do número WhatsApp                                        | Média | Alto    | Janela horária, rate limit, anti-spam guard (200/dia max), uso de número oficial Cloud API se necessário. |
| Erro de OCR em comprovante -> baixa errada                           | Média | Alto    | Sempre cai em fila de validação humana; conciliação bancária é palavra final.            |
| Custo LLM disparar                                                  | Média | Médio   | Métrica + alerta de gasto diário; fallback automático para Ollama local.                  |
| Módulo vertical mal implementado afeta Core                          | Baixa | Alto    | IAssetModule protocol enforced; modules não importam Core internals; Domain Events são one-way. |
| Pagamento parcial gera muitos títulos fragmentados                   | Média | Médio   | Política configurável: mínimo de pagamento parcial (ex.: 30% do valor); alerta no dashboard. |
| Open Finance Pluggy sair do ar                                      | Baixa | Baixo   | OFX e PDF continuam disponíveis; Pluggy é opcional.                                       |
| Cliente se arrepender da escolha de tom do agente                   | Média | Médio   | Tudo parametrizável + dry-run mode + interceptação humana sempre disponível.              |
| LGPD: cliente pedir exclusão de dados financeiros                   | Baixa | Médio   | Anonimização preservando histórico (não delete); processo documentado.                    |

---

## 23. Anexo — Comandos Úteis para o CLI

```bash
# Backend
uv pip install -e ".[dev]"                 # instala dev deps
alembic revision --autogenerate -m "add_x"
alembic upgrade head
alembic downgrade -1
pytest -k "write_off" -v
pytest -k "vehicle_hook" -v               # testes de hooks de módulo
ruff check . --fix
mypy app

# Frontend
pnpm dev                                    # ng serve
pnpm build                                  # ng build prod
pnpm test                                   # vitest
pnpm e2e                                    # playwright
pnpm lint:fix
ng generate component features/system/customers/customer-detail --skip-tests=false

# Docker
docker compose up -d
docker compose logs -f api
docker compose exec api alembic upgrade head
docker compose exec api python -m app.cli seed
docker compose exec postgres psql -U platform
```

---

## 24. Próximos Passos Pós-Architecture

### Para o Scrum Master / Dev Agent BMAD:

1. Ler PRD + ARCHITECTURE inteiro.
2. Iniciar Épico 1 / Story 1.1.
3. Para cada story:
   - Gerar branch `feat/{epic}-{story}-{slug}`.
   - Implementar respeitando os padrões (DDD, Hexagonal, manifesto Angular, Core/Module separation).
   - Escrever testes conforme matriz da seção 17.
   - Atualizar OpenAPI / docs se contrato muda.
   - Abrir PR com checklist de Definition of Done.
4. Ao final de cada épico, validar acceptance criteria com PO.

### Definition of Done (DoD) — checklist da story

- [ ] Acceptance Criteria 100% atendidos (cada item marcado).
- [ ] Testes unitários novos/atualizados (passando).
- [ ] Teste de integração (se aplicável).
- [ ] Sem regressão (CI verde).
- [ ] Sem violação de lint/type.
- [ ] Documentação ajustada (README, ADR, comentário em código).
- [ ] Logs estruturados nos pontos chave.
- [ ] Métricas relevantes adicionadas.
- [ ] Audit trail nas mutações.
- [ ] Domain Events emitidos quando aplicável (para module hooks).
- [ ] Validação manual no ambiente dev.

---

> *"A arquitetura é o conjunto de decisões difíceis de mudar depois. Acerte essas, e tudo o mais é detalhe."* — Winston, Architect (BMAD)
