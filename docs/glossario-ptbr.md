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

## Padrões para títulos de documentos

- Seções de PRD/ARCHITECTURE/épicos: títulos em PT-BR (`Visão Geral`, `Requisitos Funcionais`, `Decisões Arquiteturais`).
- Tabelas: cabeçalhos em PT-BR.
- IDs de requisitos (`FR-CORE-CR-1`, `NFR-PERF-2`): não traduzem.
- IDs de stories (`12-3`, `10-1`): não traduzem.
- Comentários de código: PT-BR para "WHY" não óbvio (raros — ver CLAUDE.md global).

---

**Última atualização:** 2026-05-26 (Story 12.9)
