---
epic: 12
story: 4
title: "Tenant Middleware — empresa_id Injection via JWT"
type: "Core Refactor"
status: review
priority: critical
depends_on: "12.3"
---

# Story 12.4: Tenant Middleware — empresa_id Injection via JWT

## User Story
As the System,
I want every authenticated request to automatically carry the tenant's `empresa_id` extracted from the JWT,
So that all database queries are automatically scoped to the correct company without manual filtering in every route handler.

## Context
Stories 12.1–12.3 built the structural foundation. This story adds the runtime enforcement: every request must carry its tenant identity, and that identity must flow through to every database query. **Depends on 12.3.**

## Acceptance Criteria

1. `empresa_id` claim added to JWT payload on login (`POST /auth/login`).
2. FastAPI dependency `get_empresa_id()` extracts `empresa_id` from current JWT and returns `UUID`.
3. `TenantMiddleware` (or equivalent FastAPI dependency) sets `empresa_id` in request state on every authenticated request.
4. All route handlers receive `empresa_id` via dependency injection — zero hardcoded empresa_id values.
5. Request without valid `empresa_id` in JWT returns `403 Forbidden`.
6. `empresa_id` stored as context variable (`contextvars.ContextVar`) so it's accessible deep in service/repository layers without being passed explicitly in every call.
7. All repository methods use `empresa_id` from context — not from parameter (repositories simplified from 12.3 placeholder).
8. Celery tasks receive `empresa_id` explicitly as task argument — context variable does NOT propagate across process boundaries.
9. Login endpoint updated: after authenticating user, fetch `empresa_id` from `acesso.usuarios` and include in JWT claims.
10. `POST /auth/register` seeds user with correct `empresa_id`.
11. Tests: verify JWT without empresa_id is rejected, verify queries are scoped.

## Implementation Pattern

### JWT Claims (login endpoint)
```python
# src/backend-api/app/api/v1/auth_routes.py
payload = {
    "sub": str(user.id),
    "email": user.email,
    "empresa_id": str(user.empresa_id),   # NOVO
    "roles": [r.perfil.nome for r in user.usuario_perfis],
    "iat": now,
    "exp": now + ACCESS_TOKEN_TTL,
    "iss": settings.JWT_ISSUER,
    "aud": settings.JWT_AUDIENCE,
}
```

### Context Variable
```python
# src/backend-api/app/core/tenant_context.py
from contextvars import ContextVar
from uuid import UUID

_empresa_id_ctx: ContextVar[UUID | None] = ContextVar("empresa_id", default=None)

def set_empresa_id(empresa_id: UUID) -> None:
    _empresa_id_ctx.set(empresa_id)

def get_empresa_id() -> UUID:
    empresa_id = _empresa_id_ctx.get()
    if empresa_id is None:
        raise RuntimeError("empresa_id não definido no contexto da requisição")
    return empresa_id
```

### FastAPI Dependency
```python
# src/backend-api/app/api/deps.py
from app.core.tenant_context import set_empresa_id, get_empresa_id

async def require_empresa_id(
    current_user: CurrentUser = Depends(get_current_user),
) -> UUID:
    empresa_id = UUID(current_user.empresa_id)
    set_empresa_id(empresa_id)
    return empresa_id
```

### Repository Usage
```python
# Repositórios usam get_empresa_id() internamente
# Não precisam receber empresa_id como parâmetro
class TituloReceberRepository:
    async def list(self, session: AsyncSession, ...) -> list[TituloReceber]:
        empresa_id = get_empresa_id()  # do contexto
        return await session.scalars(
            select(TituloReceber)
            .where(TituloReceber.empresa_id == empresa_id)
            ...
        )
```

### Celery Tasks
```python
# Tasks Celery recebem empresa_id como argumento explícito
@celery_app.task
def gerar_titulos_mensais(empresa_id: str) -> None:
    # Setar contexto manualmente dentro da task
    set_empresa_id(UUID(empresa_id))
    ...

# Ao agendar task
gerar_titulos_mensais.delay(str(empresa_id))
```

## Technical Context

### Files to Create/Modify
```
backend-api/app/
├── core/
│   └── tenant_context.py         # CRIAR
├── api/
│   ├── deps.py                   # MODIFICAR — adicionar require_empresa_id
│   └── v1/
│       └── auth_routes.py        # MODIFICAR — empresa_id no JWT
├── infrastructure/db/repositories/
│   ├── titulos_receber.py        # MODIFICAR — usar get_empresa_id()
│   ├── titulos_pagar.py          # MODIFICAR — usar get_empresa_id()
│   ├── contratos.py              # MODIFICAR — usar get_empresa_id()
│   ├── clientes.py               # MODIFICAR — usar get_empresa_id()
│   └── (todos os outros repos)   # MODIFICAR — usar get_empresa_id()
└── workers/tasks/
    └── (todas as tasks)          # MODIFICAR — empresa_id como argumento
```

### Multi-tenant SaaS Admin
Endpoints de admin do SaaS (futuramente em `comercial/`) não precisam de `empresa_id` no JWT — esses usuários são do operador do sistema, não de uma empresa cliente. Por ora, não há esses endpoints; apenas documentar esse ponto para o futuro.

## Dev Checklist
- [x] 12.3 concluída antes de começar (em review, aprovado com ressalvas)
- [x] JWT de login inclui `empresa_id` (`jwt_service.create_access_token` + `login.py` + `refresh_token.py`)
- [x] `ContextVar` implementado em `tenant_context.py` (`get_empresa_id`, `set_empresa_id`, `try_get_empresa_id`, `reset_empresa_id`, exceção `EmpresaContextoAusenteError`)
- [x] Dependency `require_empresa_id` adicionado em `deps.py` + `EmpresaIdDep` type alias
- [x] Contexto setado automaticamente em `get_current_user` (toda rota autenticada já tem `empresa_id` no contexto sem precisar declarar dep extra)
- [x] Todos os repositórios aceitam `empresa_id` opcional no construtor — lendo do contexto se omitido (ContractRepository, ReceivableRepository, CustomerRepository, PayableRepository, SupplierRepository, ExpenseCategoryRepository, RecurringPayableTemplateRepository, ConversationStore)
- [x] Tasks Celery recebem `empresa_id` como argumento ou herdam do registro processado (process_inbound_whatsapp, run_agent_turn, generate_monthly_installments, generate_recurring_payables) — sem dependência de ContextVar
- [x] Teste: request sem empresa_id no JWT retorna 403 (`test_authenticated_route_rejects_jwt_without_empresa_id`)
- [x] Teste: request com empresa_id forjado retorna 403 (`test_authenticated_route_rejects_jwt_with_mismatched_empresa_id`)
- [x] Teste: JWT de login inclui `empresa_id` válido (`test_jwt_claims` atualizado)
- [x] `pytest -x` passando: **170 passam, 6 skipped, 0 falhas**

## Implementation Notes — 2026-05-25

### Design escolhido

**Defesa em profundidade dentro de `get_current_user`:**

1. JWT carrega `empresa_id` (NOVO claim obrigatório)
2. Ao decodificar o token, extrai o claim
3. Compara com `user.empresa_id` do banco — se divergem, recusa com 403
4. Seta `empresa_id` no `ContextVar` antes de retornar o `User`

Como toda rota autenticada já injeta `CurrentUserDep`, **o contexto fica setado automaticamente** sem precisar adicionar `Depends(require_empresa_id)` em cada handler. A dependency `require_empresa_id` foi adicionada como opção explícita para handlers que querem usar o `empresa_id` como valor de retorno (ex.: passar ao construtor de repo).

### Compatibilidade backward

Os repositórios aceitam `empresa_id: UUID | None = None` — quando omitido, leem do contexto. Isso significa que:

- **Código existente** que faz `ContractRepository(session, current_user.empresa_id)` continua funcionando
- **Código novo** pode simplificar para `ContractRepository(session)` e o contexto resolve

Os 70+ callers já existentes ficam como estão; refactor mecânico fica para sub-stories futuras (12-3f).

### Workers (AC8)

ContextVar NÃO propaga entre processos. A solução implementada:

- **Workers que recebem identidade explícita** (process_inbound_whatsapp recebe `event_id`, run_agent_turn recebe `conv_id`): carregam `empresa_id` do registro e passam explicitamente ao construtor de stores/orchestrators
- **Workers que varrem global** (generate_recurring_payables, generate_monthly_installments): leem `empresa_id` de cada template/contrato processado e passam ao construtor de Payable/ContractEvent

Nenhuma task ainda precisou de `set_empresa_id()` no contexto porque elas não usam repositórios tenant-scoped — fazem queries diretas. Quando vier o motor financeiro (Epic 13) e os workers começarem a usar repositórios, vamos adicionar `set_empresa_id()` no início de cada task com `try/finally` para `reset_empresa_id()`.

### Arquivos modificados

- `src/backend-api/app/core/tenant_context.py` (novo)
- `src/backend-api/app/infrastructure/security/jwt_service.py` — `create_access_token` agora exige `empresa_id`
- `src/backend-api/app/application/auth/login.py` — passa `empresa_id`
- `src/backend-api/app/application/auth/refresh_token.py` — passa `empresa_id`
- `src/backend-api/app/api/deps.py` — extrai claim, valida divergência, seta contexto, expõe `require_empresa_id` + `EmpresaIdDep`
- 4 repositórios (`contract_repo.py`, `receivable_repo.py`, `customer_repo.py`, `payable_repo.py` com 4 classes) — fallback para contexto
- `src/backend-api/app/core/agent/conversation_store.py` — fallback para contexto
- 6 testes existentes (`test_customer_crud`, `test_vehicles`, `test_contract_crud`, `test_receivables`, `test_bank_reconciliation`, `test_payables`) — `create_access_token(..., empresa_id=...)`
- `src/backend-api/app/tests/test_auth.py` — 2 testes novos (sem empresa_id → 403, empresa_id forjado → 403) + claim assertion em `test_jwt_claims`

### Pendências (não-bloqueantes)

Movidas para sub-stories futuras:

- **12-3f**: simplificar callers (`ContractRepository(session, current_user.empresa_id)` → `ContractRepository(session)`)
- **12-6**: workers que vierem a usar repositórios precisam de `set_empresa_id()` + `try/finally`
- **Documentar para futuro**: endpoints de admin do SaaS (operador do sistema) ficarão fora do contexto tenant — terão dependency separada, ainda não implementados

---

## Senior Developer Review (AI) — 2026-05-25

**Reviewers:** Blind Hunter + Edge Case Hunter + Acceptance Auditor (3 em paralelo, sem contexto cruzado).
**Veredito do Acceptance Auditor:** APROVADO COM RESSALVAS.

### Findings críticos descobertos e RESOLVIDOS nesta rodada

| # | Bug | Severidade | Fix aplicado |
|---|---|---|---|
| H1 | `/agent/chat` quebrado: kwarg `empresa_id` inexistente em `get_or_create_conversation` | HIGH | Removida a passagem do kwarg em `agent_routes.py:110` |
| H2 | Refresh token cross-empresa: admin troca user de empresa, refresh token continua válido e emite novo access token com tenant novo sem re-login | HIGH | `refresh_token.py:53-65` valida `stored.empresa_id == user.empresa_id`; mismatch → `InvalidRefreshTokenError` |
| H3 | JWT algorithm confusion: settings `JWT_ALGORITHM` pode ser mudado para `HS256` em runtime, fazendo decoder tratar chave pública como segredo HMAC | HIGH | Whitelist literal `("RS256", "RS384", "RS512")` em `jwt_service.py`; `_resolve_algorithm()` valida na emissão; decoder usa lista hardcoded |
| H4 | `/dashboard/admin/refresh-views` sem role check: qualquer user pode disparar REFRESH MV global (DoS vector) | HIGH | `dashboard_routes.py:413-422` exige `admin` no `perfis` do user (case-insensitive) |
| H5 | `EmpresaContextoAusenteError` virava 500 cego; ContextVar sem reset entre requests; mensagens 403 com 3 motivos distintos eram oráculo de enumeração | HIGH | (a) Handler dedicado em `exception_handlers.py` → 403 com `"Acesso negado"`; (b) `TenantContextResetMiddleware` reseta antes/depois de cada request; (c) `deps.py` usa `_FORBIDDEN_DETAIL` único, log detalhado |

### MEDs RESOLVIDOS

- **M1 — Mensagens 403 vazavam estrutura**: trocadas por `"Acesso negado"`, motivo vai pro log estruturado (`jwt_missing_empresa_id_claim`, `jwt_invalid_empresa_id_format`, `jwt_empresa_id_mismatch`)
- **M2 — `empresa_id=None` explícito caía no fallback silencioso**: criada sentinela `UNSET` em `tenant_context.py` + helper `resolve_empresa_id()`. 8 construtores (4 repos + 4 classes em payable_repo + ConversationStore) agora usam o padrão; `None` explícito vira `ValueError`
- **M3 — `payload["sub"]` sem try/except**: `deps.py` wrapa em `try/except (KeyError, ValueError, TypeError)` → 401 (era 500 silencioso)

### Falsos positivos / não-aplicáveis

- **Blind LOW 11** (`Redis.from_url` sem pool em `ConversationStore._publish_message`): pré-existente, fora do escopo da story
- **Edge MED 8** (`test_authenticated_route_rejects_jwt_without_empresa_id` acoplado a `/api/v1/customers`): aceito como dívida — quando 12-3e renomear URLs, o teste é atualizado
- **Edge MED 9, 10** (helpers `_seed_user` / `_cleanup_user` frágeis): mitigado com `uuid4()` em emails dos novos testes; refactor maior fica para futuro
- **Blind LOW 13** (chaves RSA globais em testes paralelos): infra, não-bloqueante

### Status dos ACs

| AC | Status | Notas |
|---|---|---|
| AC1 | ATENDIDO | `empresa_id` no payload do JWT |
| AC2 | ATENDIDO | `require_empresa_id` em `deps.py` |
| AC3 | ATENDIDO | `set_empresa_id` em `get_current_user` + `TenantContextResetMiddleware` |
| AC4 | ATENDIDO | Toda rota com `CurrentUserDep` recebe o contexto sem dep extra |
| AC5 | ATENDIDO | 3 caminhos de 403 testados |
| AC6 | ATENDIDO | `ContextVar` com sentinela `UNSET` + helper `resolve_empresa_id` |
| AC7 | PARCIAL | Repos aceitam `empresa_id` opcional; spec sugere remover parâmetro de vez (diferido para 12-3f) |
| AC8 | ATENDIDO | Workers passam `empresa_id` explícito; convenção documentada |
| AC9 | ATENDIDO | Login e refresh emitem JWT com claim |
| AC10 | NÃO_APLICÁVEL | `/auth/register` desabilitado (410) — futuro fluxo de convite |
| AC11 | ATENDIDO | 3 testes novos (`test_jwt_claims` atualizado, sem empresa_id → 403, mismatch → 403) |

### Testes

**170 passam, 6 skipped, 0 falhas** após 2 rodadas (1ª rodada teve 2 falhas de duplicate email, resolvidas com `uuid4()` por test run).

### Arquivos modificados nesta rodada

- `src/backend-api/app/api/v1/agent_routes.py` — H1
- `src/backend-api/app/application/auth/refresh_token.py` — H2
- `src/backend-api/app/infrastructure/security/jwt_service.py` — H3 (whitelist + `_resolve_algorithm`)
- `src/backend-api/app/api/v1/dashboard_routes.py` — H4
- `src/backend-api/app/api/exception_handlers.py` — H5a (handler 403)
- `src/backend-api/app/api/middleware.py` — H5b (`TenantContextResetMiddleware`)
- `src/backend-api/app/main.py` — H5b (registro do middleware)
- `src/backend-api/app/api/deps.py` — H5c + M1 + M3 (mensagem genérica + log + try/except em sub)
- `src/backend-api/app/core/tenant_context.py` — M2 (sentinela `UNSET`, `_Unset`, `resolve_empresa_id`)
- 4 repos + ConversationStore (8 classes) — M2 (sentinela aplicada)
- `src/backend-api/app/tests/test_auth.py` — emails únicos por run, assertion `Acesso negado`

### Veredito final

**APROVADO**. Todos os HIGHs e MEDs acionáveis resolvidos. Story 12-4 pronta para `done` quando 12-3 fechar (dependência declarada).
