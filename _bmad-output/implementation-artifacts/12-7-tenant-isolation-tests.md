---
epic: 12
story: 7
title: "Tenant Isolation Tests — Verify No Cross-Tenant Data Leakage"
type: "Core Refactor"
status: ready-for-dev
priority: critical
depends_on: "12.5"
---

# Story 12.7: Tenant Isolation Tests — Verify No Cross-Tenant Data Leakage

## User Story
As a Developer,
I want a comprehensive test suite that proves empresa A can never see or modify empresa B's data in any endpoint or background task,
So that we have evidence-based confidence in the multi-tenancy implementation before going to production.

## Context
This story is the validation gate for Epic 12. It must run after 12.5 (RLS) and covers all layers: API endpoints, repository queries, RLS policies, and Celery tasks. **Depends on 12.5. Can run partially in parallel with 12.6.**

## Acceptance Criteria

1. Test fixture creates two companies (`empresa_a`, `empresa_b`) with independent users, clients, vehicles, contracts, and titles.
2. For every API endpoint that returns a list, test that empresa_a user cannot see empresa_b data.
3. For every API endpoint that returns a single entity, test that empresa_a user gets 404 (not 403) when requesting empresa_b's entity ID.
4. For every write endpoint (POST/PATCH/DELETE), test that empresa_a user cannot modify empresa_b's entities.
5. RLS test: direct DB query without JWT/context returns only empresa_a rows when `app.empresa_id` is set to empresa_a.
6. RLS test: direct DB query with empresa_b `app.empresa_id` does not return empresa_a rows.
7. RLS test: query without `app.empresa_id` set returns empty result set (not all rows).
8. Task test: `gerar_titulos_mensais(empresa_id=empresa_a_id)` generates titles only for empresa_a contracts.
9. Task test: `gerar_despesas_recorrentes(empresa_id=empresa_a_id)` generates payables only for empresa_a templates.
10. Global data test: `cadastro.categorias_despesa` with `empresa_id IS NULL` visible to both empresas.
11. All isolation tests pass with `pytest -x`.
12. Coverage of tenant isolation paths ≥ 90%.

## Test Fixture Structure

```python
# tests/conftest.py (additions)
import pytest
from uuid import uuid4

@pytest.fixture(scope="function")
async def duas_empresas(session):
    """Cria duas empresas completamente isoladas com dados em todas as tabelas."""
    empresa_a = Empresa(razao_social="Empresa Alpha", cnpj="11111111000100", email="a@test.com")
    empresa_b = Empresa(razao_social="Empresa Beta", cnpj="22222222000100", email="b@test.com")
    session.add_all([empresa_a, empresa_b])
    await session.flush()

    # Usuários admin para cada empresa
    user_a = Usuario(empresa_id=empresa_a.id, email="admin@alpha.com", senha_hash="...", nome_completo="Admin A")
    user_b = Usuario(empresa_id=empresa_b.id, email="admin@beta.com", senha_hash="...", nome_completo="Admin B")
    session.add_all([user_a, user_b])

    # Dados completos em todas as tabelas para empresa_a e empresa_b
    # (cliente, veiculo, contrato, titulo_receber, titulo_pagar, etc.)
    # ...

    await session.commit()
    return {"empresa_a": empresa_a, "empresa_b": empresa_b, "user_a": user_a, "user_b": user_b}

@pytest.fixture
def token_a(duas_empresas):
    """JWT para usuário da empresa_a."""
    return gerar_jwt(duas_empresas["user_a"])

@pytest.fixture
def token_b(duas_empresas):
    """JWT para usuário da empresa_b."""
    return gerar_jwt(duas_empresas["user_b"])
```

## Test Cases Structure

```python
# tests/test_tenant_isolation.py

class TestIsolacaoTitulosReceber:
    async def test_lista_apenas_titulos_da_propria_empresa(self, client, token_a, duas_empresas):
        response = await client.get("/api/v1/titulos-receber", headers={"Authorization": f"Bearer {token_a}"})
        assert response.status_code == 200
        ids = [t["id"] for t in response.json()["items"]]
        # Nenhum ID pertence à empresa_b
        for id_ in ids:
            assert id_ not in duas_empresas["ids_empresa_b"]["titulos_receber"]

    async def test_nao_acessa_titulo_de_outra_empresa(self, client, token_a, duas_empresas):
        titulo_b_id = duas_empresas["ids_empresa_b"]["titulos_receber"][0]
        response = await client.get(
            f"/api/v1/titulos-receber/{titulo_b_id}",
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert response.status_code == 404  # não 403 — não deve revelar existência

    async def test_nao_pode_baixar_titulo_de_outra_empresa(self, client, token_a, duas_empresas):
        titulo_b_id = duas_empresas["ids_empresa_b"]["titulos_receber"][0]
        response = await client.post(
            f"/api/v1/titulos-receber/{titulo_b_id}/baixar",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"valor_pago": 100.0, "forma_pagamento": "pix"},
        )
        assert response.status_code == 404


class TestIsolacaoRLS:
    async def test_rls_impede_acesso_sem_empresa_id(self, session):
        # Sem setar app.empresa_id, RLS bloqueia todos os registros
        await session.execute(text("SELECT set_config('app.empresa_id', '', true)"))
        result = await session.scalars(select(TituloReceber))
        assert list(result) == []

    async def test_rls_isola_empresa_a_de_empresa_b(self, session, duas_empresas):
        empresa_a_id = str(duas_empresas["empresa_a"].id)
        await session.execute(
            text("SELECT set_config('app.empresa_id', :eid, true)"),
            {"eid": empresa_a_id}
        )
        titulos = await session.scalars(select(TituloReceber))
        for titulo in titulos:
            assert titulo.empresa_id == duas_empresas["empresa_a"].id


class TestIsolacaoTasks:
    async def test_gerar_titulos_apenas_para_empresa_alvo(self, session, duas_empresas):
        empresa_a_id = str(duas_empresas["empresa_a"].id)
        titulos_antes = await contar_titulos(session, duas_empresas["empresa_b"].id)

        await executar_task_sincrona(gerar_titulos_mensais, empresa_a_id)

        titulos_depois = await contar_titulos(session, duas_empresas["empresa_b"].id)
        assert titulos_depois == titulos_antes  # empresa_b não foi afetada


class TestCategoriasGlobais:
    async def test_categorias_globais_visiveis_para_ambas_empresas(self, client, token_a, token_b):
        resp_a = await client.get("/api/v1/categorias-despesa", headers={"Authorization": f"Bearer {token_a}"})
        resp_b = await client.get("/api/v1/categorias-despesa", headers={"Authorization": f"Bearer {token_b}"})
        # Ambas devem ver as categorias globais (empresa_id IS NULL)
        ids_a = {c["id"] for c in resp_a.json()["items"] if c["empresa_id"] is None}
        ids_b = {c["id"] for c in resp_b.json()["items"] if c["empresa_id"] is None}
        assert ids_a == ids_b
        assert len(ids_a) > 0
```

## Endpoints to Test for Isolation

Todos os endpoints abaixo devem ser cobertos:

```
GET  /titulos-receber            — lista isolada
GET  /titulos-receber/{id}       — 404 para ID de outra empresa
POST /titulos-receber/{id}/baixar
GET  /titulos-pagar
GET  /titulos-pagar/{id}
GET  /contratos
GET  /contratos/{id}
GET  /clientes
GET  /clientes/{id}
GET  /veiculos
GET  /veiculos/{id}
GET  /contas-bancarias
GET  /transacoes-bancarias
GET  /conversas
GET  /relatorios
```

## Technical Context

### Files to Create/Modify
```
backend-api/app/tests/
├── conftest.py                       # MODIFICAR — fixtures duas_empresas, token_a, token_b
├── test_tenant_isolation.py          # CRIAR
├── test_rls_policies.py              # CRIAR
└── test_task_isolation.py            # CRIAR
```

## Dev Checklist
- [ ] 12.5 concluída antes de começar
- [ ] Fixture `duas_empresas` cria dados completos em todas as tabelas relevantes
- [ ] Todos os endpoints de lista testados para isolamento
- [ ] Todos os endpoints de detalhe testados: retornam 404 (não 403) para ID de outra empresa
- [ ] Todos os endpoints de escrita testados para rejeição cross-tenant
- [ ] RLS testado diretamente no banco (sem camada de aplicação)
- [ ] Tasks testadas para não afetar empresas não-alvo
- [ ] Categorias globais visíveis para ambas as empresas
- [ ] Cobertura ≥ 90% nos paths de isolamento
- [ ] `pytest -x` passando com todos os testes de isolamento
