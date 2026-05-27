---
epic: 13
story: 18
title: "Rename de Interfaces (Ports) para PT-BR — Aliases sem Breaking Change"
type: "Refactor + Glossário"
status: review
priority: medium
depends_on: "13.1"
authored_by: "Amelia (dev)"
created_at: "2026-05-27"
---

# Story 13.18: Rename de Interfaces para PT-BR

## História de Usuário

**Como** desenvolvedor escrevendo código novo do Epic 13,
**eu quero** importar Interfaces pelos nomes PT-BR (`IModuloVertical`, `ICanalMensagem`, `IGatewayPagamento`, `IGatewayRastreador`),
**para que** a base permaneça consistente com o glossário sem precisar de refactor cross-cutting de todos os implementadores existentes.

## Contexto

Story 13.1 documentou que renomear classes Protocol invalida ~30 imports + `isinstance` checks em runtime, virando um refactor coordenado de alto risco. Esta story resolve o problema com **alias de módulo** — duas variáveis apontando para a mesma classe Protocol.

## Solução

```python
# app/core/assets/module_interface.py
class IAssetModule(Protocol):
    ...
IModuloVertical = IAssetModule  # mesma classe

# Uso intercambiável:
from app.core.assets.module_interface import IModuloVertical
isinstance(modulo_veiculo, IModuloVertical)  # funciona como antes
```

Métodos dos Protocols (`on_installment_paid`, `on_contract_created`, etc.) **permanecem em inglês** — renomear método quebra todos os implementadores ao mesmo tempo (refactor coordenado fica para o futuro, sem urgência operacional).

## Critérios de Aceite

1. ✅ `IModuloVertical` exportado em `app/core/assets/module_interface.py` apontando para `IAssetModule`.
2. ✅ `ICanalMensagem` exportado em `app/domain/ports/message_channel.py` apontando para `IMessageChannel`.
3. ✅ `IGatewayPagamento` exportado em `app/domain/ports/payment_gateway.py` apontando para `IPaymentGateway`.
4. ✅ `IGatewayRastreador` exportado em `app/modules/vehicles/ports/tracker_gateway.py` apontando para `ITrackerGateway`.
5. ✅ Glossário `docs/glossario-ptbr.md` atualizado (status débito → alias aplicado).
6. ✅ `isinstance(x, IModuloVertical)` retorna o mesmo que `isinstance(x, IAssetModule)`.
7. ✅ Zero regressão em testes existentes.

## Arquivos Modificados

- `src/backend-api/app/core/assets/module_interface.py` (alias `IModuloVertical`)
- `src/backend-api/app/domain/ports/message_channel.py` (alias `ICanalMensagem`)
- `src/backend-api/app/domain/ports/payment_gateway.py` (alias `IGatewayPagamento`)
- `src/backend-api/app/modules/vehicles/ports/tracker_gateway.py` (alias `IGatewayRastreador`)
- `docs/glossario-ptbr.md` (status atualizado)

## Validação

- `python -c` direto: `assert IAssetModule is IModuloVertical` (e demais) passa.
- `pytest --ignore=test_vehicles.py`: 220 passed, 6 skipped (mesma contagem; +0 testes; +0 regressões).

## Notas

- **Não cria story de motores nova** — apenas habilita os motores 13.6–13.9 a importarem os aliases PT-BR sem fricção.
- Refactor de **métodos** dos Protocols fica como débito documentado (`docs/glossario-ptbr.md` — seção "Métodos individuais permanecem em inglês").
