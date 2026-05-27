"""ServicoConfiguracao — leitura/escrita tipada de `config.configuracoes_sistema`.

Story 13.4. Esta é a única porta de entrada para parâmetros de negócio
(percentuais, limites, dias) — todos os motores do Epic 13 consomem daqui.

Comportamento:
- `obter_*` busca primeiro override do tenant atual, depois config global
  (empresa_id IS NULL). Se nada existir, devolve o `padrao` fornecido. Não
  levanta exceção — fallback é sempre seguro.
- `definir` cria/atualiza override para o tenant atual e invalida o cache.
- Cache em Redis com TTL de 60s (chave `config:{empresa_id|global}:{slug}`).
- Conversão de tipo confia no CHECK constraint do banco: `valor` sempre case
  com `tipo_valor` (a aplicação só revalida no `definir` antes de mandar pro
  banco — defesa em profundidade).

Tipos suportados: string, inteiro, decimal, booleano, json.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.config import ConfiguracaoSistema


CACHE_TTL_SECONDS = 60

TIPOS_VALIDOS = ("string", "inteiro", "decimal", "booleano", "json")


class TipoConfiguracaoInvalidoError(ValueError):
    """Levantado quando `tipo_valor` não está na lista permitida ou `valor`
    não casa com o tipo declarado."""


class ServicoConfiguracao:
    def __init__(
        self,
        session: AsyncSession,
        empresa_id: UUID | None,
        redis: Redis | None = None,
    ) -> None:
        self.session = session
        self.empresa_id = empresa_id
        self.redis = redis

    # ──────────────────────────────────────────────────────────────────
    # Leitura tipada
    # ──────────────────────────────────────────────────────────────────

    async def obter_string(self, slug: str, modulo: str, padrao: str) -> str:
        valor = await self._obter_bruto(slug)
        return valor if valor is not None else padrao

    async def obter_inteiro(self, slug: str, modulo: str, padrao: int) -> int:
        valor = await self._obter_bruto(slug)
        if valor is None:
            return padrao
        try:
            return int(valor)
        except ValueError:
            return padrao

    async def obter_decimal(self, slug: str, modulo: str, padrao: Decimal) -> Decimal:
        valor = await self._obter_bruto(slug)
        if valor is None:
            return padrao
        try:
            return Decimal(valor)
        except InvalidOperation:
            return padrao

    async def obter_booleano(self, slug: str, modulo: str, padrao: bool) -> bool:
        valor = await self._obter_bruto(slug)
        if valor is None:
            return padrao
        return valor == "true"

    async def obter_json(self, slug: str, modulo: str, padrao: dict) -> dict:
        valor = await self._obter_bruto(slug)
        if valor is None:
            return padrao
        try:
            parsed = json.loads(valor)
            return parsed if isinstance(parsed, dict) else padrao
        except json.JSONDecodeError:
            return padrao

    # ──────────────────────────────────────────────────────────────────
    # Escrita tipada
    # ──────────────────────────────────────────────────────────────────

    async def definir(
        self,
        slug: str,
        modulo: str,
        valor: Any,
        tipo_valor: str,
        atualizado_por_id: UUID | None = None,
        descricao: str | None = None,
    ) -> ConfiguracaoSistema:
        """Cria ou atualiza override do tenant atual.

        Levanta `TipoConfiguracaoInvalidoError` se `tipo_valor` for inválido
        ou `valor` não casar com o tipo. Validação dupla: aqui em Python +
        CHECK constraint no banco.
        """
        if tipo_valor not in TIPOS_VALIDOS:
            raise TipoConfiguracaoInvalidoError(
                f"tipo_valor='{tipo_valor}' inválido. Aceitos: {TIPOS_VALIDOS}"
            )

        valor_str = self._serializar(valor, tipo_valor)

        result = await self.session.execute(
            select(ConfiguracaoSistema).where(
                ConfiguracaoSistema.empresa_id == self.empresa_id,
                ConfiguracaoSistema.slug == slug,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.valor = valor_str
            existing.tipo_valor = tipo_valor
            existing.modulo = modulo
            existing.atualizado_em = datetime.now(timezone.utc)
            if descricao is not None:
                existing.descricao = descricao
            if atualizado_por_id is not None:
                existing.atualizado_por_id = atualizado_por_id
            await self.session.flush()
            config = existing
        else:
            config = ConfiguracaoSistema(
                empresa_id=self.empresa_id,
                modulo=modulo,
                slug=slug,
                tipo_valor=tipo_valor,
                valor=valor_str,
                descricao=descricao,
                atualizado_por_id=atualizado_por_id,
            )
            self.session.add(config)
            await self.session.flush()

        await self._invalidar_cache(slug)
        return config

    # ──────────────────────────────────────────────────────────────────
    # Listagem (para tela admin)
    # ──────────────────────────────────────────────────────────────────

    async def listar(self, modulo: str | None = None) -> list[ConfiguracaoSistema]:
        """Lista configs visíveis ao tenant atual (override + globais).

        Quando há override e global com mesmo slug, devolve apenas o override
        (o que efetivamente vale para este tenant).
        """
        stmt = select(ConfiguracaoSistema)
        if modulo:
            stmt = stmt.where(ConfiguracaoSistema.modulo == modulo)
        stmt = stmt.order_by(ConfiguracaoSistema.modulo, ConfiguracaoSistema.slug)
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())

        # Quando o mesmo slug aparece em override + global, mantém apenas o override
        by_slug: dict[str, ConfiguracaoSistema] = {}
        for r in rows:
            if r.slug in by_slug:
                # Já tem — só substitui se o atual for override (empresa_id != NULL)
                if r.empresa_id is not None:
                    by_slug[r.slug] = r
            else:
                by_slug[r.slug] = r
        return list(by_slug.values())

    # ──────────────────────────────────────────────────────────────────
    # Internals
    # ──────────────────────────────────────────────────────────────────

    async def _obter_bruto(self, slug: str) -> str | None:
        """Devolve o `valor` (string) para o slug, considerando cache + override."""
        cache_key = self._cache_key(slug)
        if self.redis is not None:
            cached = await self.redis.get(cache_key)
            if cached is not None:
                if cached == b"__none__" or cached == "__none__":
                    return None
                return cached.decode() if isinstance(cached, bytes) else cached

        # Override do tenant primeiro
        override = await self.session.execute(
            select(ConfiguracaoSistema.valor).where(
                ConfiguracaoSistema.empresa_id == self.empresa_id,
                ConfiguracaoSistema.slug == slug,
            )
        )
        valor = override.scalar_one_or_none()

        # Fallback: config global (empresa_id IS NULL)
        if valor is None and self.empresa_id is not None:
            globalc = await self.session.execute(
                select(ConfiguracaoSistema.valor).where(
                    ConfiguracaoSistema.empresa_id.is_(None),
                    ConfiguracaoSistema.slug == slug,
                )
            )
            valor = globalc.scalar_one_or_none()

        if self.redis is not None:
            await self.redis.setex(cache_key, CACHE_TTL_SECONDS, valor if valor is not None else "__none__")

        return valor

    async def _invalidar_cache(self, slug: str) -> None:
        if self.redis is not None:
            await self.redis.delete(self._cache_key(slug))

    def _cache_key(self, slug: str) -> str:
        tenant = str(self.empresa_id) if self.empresa_id else "global"
        return f"config:{tenant}:{slug}"

    @staticmethod
    def _serializar(valor: Any, tipo_valor: str) -> str:
        """Serializa `valor` para string conforme `tipo_valor`. Garante que
        o que vai pro banco vai passar no CHECK constraint."""
        if tipo_valor == "string":
            return str(valor)
        if tipo_valor == "inteiro":
            try:
                return str(int(valor))
            except (ValueError, TypeError) as e:
                raise TipoConfiguracaoInvalidoError(
                    f"valor='{valor}' não é inteiro válido"
                ) from e
        if tipo_valor == "decimal":
            try:
                return str(Decimal(str(valor)))
            except InvalidOperation as e:
                raise TipoConfiguracaoInvalidoError(
                    f"valor='{valor}' não é decimal válido"
                ) from e
        if tipo_valor == "booleano":
            if isinstance(valor, bool):
                return "true" if valor else "false"
            if isinstance(valor, str) and valor.lower() in ("true", "false"):
                return valor.lower()
            raise TipoConfiguracaoInvalidoError(
                f"valor='{valor}' não é booleano (use True/False ou 'true'/'false')"
            )
        if tipo_valor == "json":
            try:
                if isinstance(valor, str):
                    json.loads(valor)
                    return valor
                return json.dumps(valor)
            except (TypeError, json.JSONDecodeError) as e:
                raise TipoConfiguracaoInvalidoError(
                    f"valor não é JSON serializável: {e}"
                ) from e
        raise TipoConfiguracaoInvalidoError(f"tipo_valor '{tipo_valor}' inválido")
