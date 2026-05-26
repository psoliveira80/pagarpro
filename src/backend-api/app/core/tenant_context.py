"""Contexto de tenant (empresa) por requisição.

Usa `contextvars.ContextVar` para carregar o `empresa_id` do usuário autenticado
através da pilha de chamadas — rotas, services, repositórios — sem precisar
passar o valor explicitamente em cada assinatura.

Importante: `ContextVar` é por-task asyncio. Em FastAPI cada request roda em sua
própria task, então a isolação é garantida. Workers Celery rodam em processos
diferentes e NÃO herdam este contexto — cada task deve chamar `set_empresa_id()`
no início, passando o valor recebido como argumento explícito.
"""

from __future__ import annotations

from contextvars import ContextVar
from uuid import UUID

_empresa_id_ctx: ContextVar[UUID | None] = ContextVar("empresa_id", default=None)


class EmpresaContextoAusenteError(RuntimeError):
    """Levantada quando código tenta ler empresa_id sem estar setado."""


def set_empresa_id(empresa_id: UUID) -> None:
    """Define a empresa do contexto atual.

    Em HTTP: chamado por `require_empresa_id` ao validar o JWT.
    Em Celery: chamado no início de cada task que recebe `empresa_id` como argumento.
    """
    _empresa_id_ctx.set(empresa_id)


def get_empresa_id() -> UUID:
    """Recupera a empresa do contexto atual.

    Raise `EmpresaContextoAusenteError` se nenhuma empresa foi setada — sinal
    inequívoco de bug: alguém chamou código tenant-scoped sem passar pelo
    middleware HTTP nem pelo handshake da task Celery.
    """
    empresa_id = _empresa_id_ctx.get()
    if empresa_id is None:
        raise EmpresaContextoAusenteError(
            "empresa_id ausente no contexto da requisição. "
            "Em rotas HTTP, garanta Depends(require_empresa_id). "
            "Em tasks Celery, chame set_empresa_id() no início da task."
        )
    return empresa_id


def try_get_empresa_id() -> UUID | None:
    """Versão não-fatal de `get_empresa_id` — retorna None se não há contexto.

    Usar somente em código que pode rodar em ambos os modos (com e sem tenant),
    como handlers de webhook do sistema que ainda não sabem a qual empresa
    o evento pertence.
    """
    return _empresa_id_ctx.get()


def reset_empresa_id() -> None:
    """Remove a empresa do contexto. Útil em tests."""
    _empresa_id_ctx.set(None)


# Sentinela para distinguir "parâmetro omitido" de "None passado explícito" em
# construtores tenant-scoped. Sem ela, `Repo(session, empresa_id=None)` cairia
# no fallback do contexto silenciosamente — mascarando um bug do caller que
# tinha uma variável esperada-UUID que acabou None.
class _Unset:
    def __repr__(self) -> str:
        return "<UNSET>"


UNSET: _Unset = _Unset()


def resolve_empresa_id(value: UUID | None | _Unset = UNSET) -> UUID:
    """Resolve o `empresa_id` a partir do parâmetro do construtor.

    - **Omitido (UNSET)**: lê do contexto (`get_empresa_id`); raise `EmpresaContextoAusenteError`
      se contexto não está setado.
    - **UUID explícito**: usa direto.
    - **None explícito**: raise `ValueError` — sinal de bug no caller, que provavelmente
      tinha uma variável `empresa_id: UUID | None` esperada não-None.
    """
    if isinstance(value, _Unset):
        return get_empresa_id()
    if value is None:
        raise ValueError(
            "empresa_id=None explícito não é permitido. "
            "Omita o parâmetro para herdar do contexto, ou passe um UUID válido."
        )
    return value
