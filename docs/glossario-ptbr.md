# Glossário PT-BR — Convenção de Tradução

> **Propósito:** Tabela única de tradução para manter consistência em todos os artefatos de planejamento (PRD, ARCHITECTURE, épicos, stories) e código.
> **Autoridade:** Esta tabela vence sobre qualquer outra escolha de tradução nos documentos. Em caso de dúvida, consulte aqui ou pergunte ao Pablo.

## Regras gerais

1. **Termos de domínio (negócio) traduzem SEMPRE para PT-BR.**
2. **Termos técnicos consagrados ficam em inglês** (HTTP, JWT, REST, JSONB, etc.).
3. **Nomes próprios não traduzem** (FIPE, Pix, OFX, LGPD, Pluggy, Asaas, Z-API, etc.).
4. **Identificadores de código (classes, arquivos, IDs de stories, FR-XX) não traduzem.**
5. Em código novo, **sempre PT-BR** para campos, métodos e variáveis de domínio (ver [feedback-naming-convention-pt]).

## Domínio (sempre traduzir)

| Inglês | PT-BR | Notas |
|---|---|---|
| asset | ativo | módulo genérico (carro, imóvel, equipamento) |
| tracker | rastreador | dispositivo GPS no veículo |
| installment | título a receber, parcela | em finanças = título; em contrato = parcela |
| receivable | título a receber | sinônimo de installment em CR |
| payable | título a pagar | nota: já era PT-BR no domínio |
| customer | cliente | |
| vehicle | veículo | |
| contract | contrato | |
| attachment | anexo | |
| recurring (expense) | despesa recorrente | |
| (message) template | modelo de mensagem | "template" cru fica em código |
| aggregate | agregado | DDD |
| write-off | baixa | de título |
| partial write-off | baixa parcial | |
| bulk write-off | baixa em lote | |
| renegotiate | renegociar | |
| reverse (write-off) | estornar | nunca "reverter" para evitar ambiguidade |
| bank account | conta bancária | |
| bank transaction | transação bancária | |
| reconciliation | conciliação | |
| divergence | divergência | em conciliação |
| supplier | fornecedor | |
| expense category | categoria de despesa | |
| broadcast | aviso em massa, disparo | "broadcast" também aceito como termo técnico |
| conversation | conversa | inbox WhatsApp |
| inbox | caixa de entrada | |
| message | mensagem | |
| dashboard | painel, dashboard | ambos aceitos |
| report | relatório | |
| audit log | log de auditoria | |
| module | módulo | |
| hook | hook | mantém em inglês (termo técnico consagrado) |
| backup | backup | mantém |
| score | score | mantém (termo consagrado em crédito) |
| onboarding | onboarding | mantém |
| owner | proprietário, dono | |
| guarantor | fiador | |
| down payment | entrada | |
| grace period | carência | |
| interest | juros | |
| fine | multa | |
| discount | desconto | |
| due date | data de vencimento | |
| paid amount | valor pago | |
| payment method | forma de pagamento | |
| draft (status) | rascunho | |
| active (contract) | vigente | NÃO "ativo" — evita ambiguidade com "ativo" (asset) |
| suspended | suspenso | |
| terminated | encerrado | |
| rescinded | rescindido | |
| cancelled | cancelado | |
| open (installment) | em aberto | |
| paid | pago | |
| partially paid | pago parcial | |
| overdue | vencido | título; "em atraso" também aceito |
| pending verification | aguardando verificação | |
| receipt | comprovante | de pagamento |

## Operacional / Processo

| Inglês | PT-BR | Notas |
|---|---|---|
| collection (cobrança) | cobrança | |
| automated collection | cobrança automatizada | |
| collection cycle | ciclo de cobrança | |
| escalation | escalonamento | |
| dunning | régua de cobrança | |
| outreach | contato, comunicação | |
| handover, takeover | assumir conversa | quando humano assume do agente |
| resume agent | retomar agente | |
| validator | validador | |
| operator | operador | |
| auditor | auditor | |
| admin | administrador | |
| settings | configurações | |

## Técnico (manter em inglês)

`HTTP`, `HTTPS`, `REST`, `JSON`, `JSONB`, `XML`, `YAML`, `TOML`, `JWT`, `OAuth`, `RSA`, `Argon2`, `Argon2id`, `SHA-256`, `HMAC`, `TLS`, `mTLS`, `CORS`, `CSRF`, `XSS`, `OWASP`, `SSE`, `WebSocket`, `polling`, `webhook`, `endpoint`, `middleware`, `request`, `response`, `payload`, `header`, `body`, `query`, `path`, `cookie`, `session`, `token`, `refresh token`, `access token`.

`FastAPI`, `Pydantic`, `SQLAlchemy`, `Alembic`, `Celery`, `Redis Streams`, `Redis`, `PostgreSQL`, `MinIO`, `S3`, `Docker`, `docker-compose`, `Kubernetes`, `Nginx`, `Uvicorn`, `pytest`, `Ruff`, `Mypy`, `Angular`, `TypeScript`, `Signals`, `RxJS`, `Tailwind`, `Heroicons`, `Jest`.

`ASGI`, `WSGI`, `ORM`, `DTO`, `DDD`, `CQRS`, `RBAC`, `ABAC`, `ADR` (Architecture Decision Record), `OOP`, `FP`, `CI/CD`, `PR` (pull request), `CRUD`.

`repository`, `adapter`, `port`, `hexagonal`, `aggregate root` (use em DDD strict), `event bus`, `event sourcing`, `materialized view`, `index`, `query`, `transaction`, `savepoint`, `rollback`, `commit`, `migration`, `pipeline`, `worker`, `task`, `queue`, `cron`, `cronjob`, `schedule`.

`UUID`, `ENUM`, `TIMESTAMPTZ`, `BIGINT`, `NUMERIC`, `TEXT`, `BOOLEAN`, `pgvector`, `pg_trgm`, `unaccent`, `citext`, `pgcrypto`.

## Nomes próprios (não traduzir)

- **Marcas/produtos:** FIPE, Pix, OFX, LGPD, Asaas, Stripe, Efi, Pluggy, Z-API, Uazapi, Evolution API, WhatsApp, Telegram, Slack, Google, Anthropic, Claude, OpenAI, ChatGPT, Heroicons, Leaflet, OpenStreetMap.
- **Acrônimos brasileiros:** CPF, CNPJ, CEP, ViaCEP, CNH, RG, IPVA, Renavam, DRE.
- **Tecnologias por sigla:** GPS, OCR, PDF, CSV, OFX, BRCode.

## Convenções de tradução tricky

- **"asset" sempre vira "ativo" no contexto de negócio.** Quando "ativo" colidir com "active", usar:
  - `active contract` → `contrato vigente` (não "ativo")
  - `active module` → `módulo ativado` ou `is_active = true` em código (mantém EN)
- **"draft"** = rascunho (status). Em código (UI/state machine), o slug é `rascunho`.
- **"open" (installment)** = "em aberto" (PT-BR). Em código, status é `em_aberto`.
- **"installment"** dependendo do contexto:
  - Em finanças/lifecycle: **título** (a receber/a pagar)
  - Em contrato: **parcela** (do plano de pagamento)
  - Em código: campo é `titulo_*` para entidade, `parcela_*` para item dentro de contrato
- **"validator"** (papel humano que valida comprovantes) = **validador**.
- **"score"** em crédito/risco = **score** (mantém).
- **"hook" / "hooks"** = **hook** (não "gancho" — termo técnico consagrado).

## Domínio Financeiro — Tabela de Renames EN→PT-BR (Story 13.1)

Convenção de nomes para código **novo** do Epic 13 em diante. Nomes EN listados aqui ainda existem como **aliases backward-compat** em `app/core/events/domain_events.py` para preservar serialização de eventos persistidos (Redis Streams + `audit_log`). Migração completa para PT-BR canonical fica como débito técnico — exige replay/reescrita de eventos antigos.

### Workers Celery (tasks)

| Nome antigo (EN) | Nome novo (PT-BR) | Status |
|---|---|---|
| `generate_monthly_installments` | `gerar_titulos_mensais` | ✅ aplicado (Story 12.6) |
| `check_overdue_installments` | `processar_titulos_vencidos` | ✅ aplicado |
| `check_upcoming_due_dates` | `alertar_vencimentos_proximos` | 🔵 a criar (Story 13.7) |
| `check_paid_installments` | `conciliar_pagamentos_recebidos` | 🔵 a criar (Story 13.9) |
| `calculate_customer_scores` | `atualizar_scores_clientes` | ✅ aplicado |
| `generate_recurring_payables` | `gerar_contas_pagar_recorrentes` | ⚠️ parcial (atual: `gerar_despesas_recorrentes`) |
| `check_channel_health` | `monitorar_saude_canais` | ⚠️ parcial (atual: `verificar_saude_canais`) |
| `refresh_materialized_views` | `atualizar_visoes_materializadas` | ⚠️ parcial (atual: `atualizar_views`) |

### Hooks de Domínio (event handlers)

| Nome antigo (EN) | Nome novo (PT-BR) | Status |
|---|---|---|
| `on_installment_paid` | `quando_titulo_pago` | 🔵 a renomear (interface IAssetModule — story arquitetural própria) |
| `on_installment_overdue` | `quando_titulo_vencido` | 🔵 a renomear |
| `on_contract_created` | `quando_contrato_ativado` | 🔵 a renomear |
| `on_contract_terminated` | `quando_contrato_encerrado` | 🔵 a renomear |

### Eventos de Domínio (`app/core/events/domain_events.py`)

| Nome canonical (EN, mantém) | Alias preferencial para código novo (PT-BR) |
|---|---|
| `ContractCreatedEvent` | `EventoContratoAtivado` |
| `ContractTerminatedEvent` | `EventoContratoEncerrado` |
| `InstallmentOverdueEvent` | `EventoTituloVencido` |
| `InstallmentPaidEvent` | `EventoTituloPago` |
| `PaymentPartiallyReceivedEvent` | `EventoPagamentoParcialRecebido` |
| `ReconciliationCompletedEvent` | `EventoConciliacaoCompletada` |
| `CustomerScoreChangedEvent` | `EventoScoreClienteAlterado` |

**Regra:** em código novo, importar pelo alias PT-BR. Em código existente que faz `to_dict()` para persistência, o nome EN é preservado em `_type` (preserva replay de eventos antigos).

### Políticas e Renderizadores

| Nome antigo (EN) | Nome novo (PT-BR) | Status |
|---|---|---|
| `collection_policy` | `politica_cobranca` | 🔵 a aplicar |
| `template_renderer` | `renderizador_template` | 🔵 a criar (Story 13.10) |

### Interfaces (Ports do Hexagonal)

| Nome canonical (EN, mantém) | Alias preferencial pra código novo (PT-BR) | Status |
|---|---|---|
| `IAssetModule` | `IModuloVertical` | ✅ alias aplicado (Story 13.18) |
| `IMessageChannel` | `ICanalMensagem` | ✅ alias aplicado |
| `IPaymentGateway` | `IGatewayPagamento` | ✅ alias aplicado |
| `ITrackerGateway` | `IGatewayRastreador` | ✅ alias aplicado |

**Regra:** em código novo, importar pelo alias PT-BR. O nome EN é canonical (Protocol class) — alterar quebra `isinstance(x, IAssetModule)` checks existentes. Os aliases são `IModuloVertical = IAssetModule` (mesmo Protocol class), então `isinstance(x, IModuloVertical)` funciona idêntico.

Métodos individuais dos Protocols (ex.: `on_installment_paid`, `on_contract_created`) **permanecem em inglês** — renomear método de Protocol invalida todos os implementadores. Esse rename fica documentado como débito futuro de refactor coordenado.

### Legenda

- ✅ **aplicado** — rename já feito em sessão anterior, código consistente.
- ⚠️ **parcial** — nome em uso é PT-BR mas difere ligeiramente do alvo formal acima (ex.: `verificar_` em vez de `monitorar_`); ajuste cosmético.
- 🔵 **a aplicar/criar** — nome ainda em inglês ou função ainda não existe; será renomeado/criado nas stories indicadas.
- 🔵 **débito** — rename adiado para story arquitetural dedicada (blast radius cross-cutting).

---

## Padrões para títulos de documentos

- Seções de PRD/ARCHITECTURE/épicos: títulos em PT-BR (`Visão Geral`, `Requisitos Funcionais`, `Decisões Arquiteturais`).
- Tabelas: cabeçalhos em PT-BR.
- IDs de requisitos (`FR-CORE-CR-1`, `NFR-PERF-2`): não traduzem.
- IDs de stories (`12-3`, `10-1`): não traduzem.
- Comentários de código: PT-BR para "WHY" não óbvio (raros — ver CLAUDE.md global).

---

**Última atualização:** 2026-05-26 (Story 12.9)
