"""Helpers de idempotência para os motores do Epic 13 (Story 13.5).

3 camadas de defesa contra processamento duplicado:

1. **Redis lock** (`LockOperacao`) — evita 2 workers pegarem o mesmo
   recurso ao mesmo tempo. TTL curto (60s default).
2. **SELECT FOR UPDATE SKIP LOCKED** — quando o motor varre uma fila de
   trabalho, dois workers competindo pegam linhas diferentes. Use
   `bloquear_lote_para_processar` helper.
3. **Estado canônico no banco** — `titulo.status`, `lembretes_enviados`,
   `contrato.status`. Mesmo se o lock expirar, o motor checa estado antes
   de mutar — no-op se já processado.

Uso típico em um motor:

    async with LockOperacao(redis, "cobranca_vencidos", str(titulo.id)) as lock:
        if not lock.adquirido:
            return  # outro worker já está nesse título
        # ... processa o título
"""

from __future__ import annotations

import secrets
from typing import Sequence
from uuid import UUID

import structlog
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


log = structlog.get_logger()


class LockOperacao:
    """Context manager async para Redis lock com expiração.

    Usa SET NX EX (atômico). Se outro worker já tem o lock, `adquirido=False`
    e o caller deve apenas pular o recurso silenciosamente — NÃO levanta
    exceção. Isso permite paralelismo seguro sem perda.

    Reentrância: o token randômico assegura que apenas quem adquiriu pode
    liberar (evita liberar o lock de outro worker que pegou após expiração).
    """

    def __init__(
        self,
        redis: Redis,
        operacao: str,
        recurso_id: str,
        ttl_segundos: int = 60,
    ) -> None:
        self.redis = redis
        self.chave = f"motor:lock:{operacao}:{recurso_id}"
        self.ttl_segundos = ttl_segundos
        self._token = secrets.token_hex(16)
        self.adquirido = False

    async def __aenter__(self) -> "LockOperacao":
        # SET key value NX EX ttl — atômico no Redis
        result = await self.redis.set(
            self.chave,
            self._token,
            nx=True,
            ex=self.ttl_segundos,
        )
        self.adquirido = bool(result)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if not self.adquirido:
            return
        # Libera apenas se o token bate (Lua script atômico)
        await self.redis.eval(
            """
            if redis.call('GET', KEYS[1]) == ARGV[1] then
                return redis.call('DEL', KEYS[1])
            end
            return 0
            """,
            1,
            self.chave,
            self._token,
        )


async def bloquear_lote_para_processar(
    session: AsyncSession,
    tabela: str,
    coluna_id: str = "id",
    filtros_where: str = "",
    parametros: dict | None = None,
    limit: int = 50,
) -> Sequence[UUID]:
    """Retorna IDs travados via `SELECT FOR UPDATE SKIP LOCKED`.

    Usado por coordinators que distribuem títulos para workers. O lock
    persiste pela duração da transação — o caller deve manter o session
    aberto enquanto processa, ou copiar os IDs e abrir transações
    individuais por ID (preferível para resiliência).

    Args:
        tabela: ex. "financeiro.titulos_receber".
        filtros_where: cláusula SQL adicional, ex.
            "status = 'em_atraso' AND empresa_id = :eid".
        parametros: dict com os bind params do filtros_where.
        limit: tamanho do lote.

    Returns:
        Lista de UUIDs travados (até `limit`).
    """
    where = f"WHERE {filtros_where}" if filtros_where else ""
    sql = f"""
        SELECT {coluna_id}
        FROM {tabela}
        {where}
        ORDER BY {coluna_id}
        LIMIT :__limit
        FOR UPDATE SKIP LOCKED
    """
    params = dict(parametros or {})
    params["__limit"] = limit
    result = await session.execute(text(sql), params)
    return [row[0] for row in result.all()]


def chave_lembrete_idempotencia(titulo_id: UUID, tipo: str, dia_iso: str) -> str:
    """Chave Redis legível para idempotência diária de envio de lembrete.

    Complementa o índice único do banco — Redis serve como cache rápido
    "já enviei hoje?" sem precisar bater no banco.
    """
    return f"lembrete:{titulo_id}:{tipo}:{dia_iso}"
