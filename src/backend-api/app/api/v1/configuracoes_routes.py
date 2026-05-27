"""Endpoints REST para `config.configuracoes_sistema` (Story 13.4).

Role-gated: somente Admin pode listar/atualizar. Mutações geram audit log
com `category='configuracao'` e diff antes/depois.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import select

from app.api.deps import CurrentUserDep, SessionDep
from app.application.services.servico_configuracao import (
    ServicoConfiguracao,
    TipoConfiguracaoInvalidoError,
)
from app.application.shared.audit_logger import AuditLogger
from app.core.correlation import get_correlation_id
from app.infrastructure.db.models.config import ConfiguracaoSistema
from app.infrastructure.settings import get_settings


router = APIRouter(prefix="/configuracoes", tags=["configuracoes"])


class ConfiguracaoOut(BaseModel):
    id: str
    modulo: str
    slug: str
    tipo_valor: str
    valor: str
    descricao: str | None
    escopo: str  # 'global' | 'tenant'


class ConfiguracaoUpdate(BaseModel):
    valor: Any
    tipo_valor: str
    modulo: str | None = None
    descricao: str | None = None


def _check_admin(current_user) -> None:
    roles = [(p.nome or "").lower() for p in (current_user.perfis or [])]
    if "admin" not in roles:
        raise HTTPException(
            status_code=403, detail="Apenas administradores podem gerenciar configurações"
        )


def _to_out(row: ConfiguracaoSistema) -> ConfiguracaoOut:
    return ConfiguracaoOut(
        id=str(row.id),
        modulo=row.modulo,
        slug=row.slug,
        tipo_valor=row.tipo_valor,
        valor=row.valor,
        descricao=row.descricao,
        escopo="global" if row.empresa_id is None else "tenant",
    )


@router.get("", response_model=list[ConfiguracaoOut])
async def listar_configuracoes(
    session: SessionDep,
    current_user: CurrentUserDep,
    modulo: str | None = Query(None, description="Filtrar por módulo (financeiro, frota, comunicacao)"),
) -> list[ConfiguracaoOut]:
    _check_admin(current_user)
    settings = get_settings()
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        servico = ServicoConfiguracao(session, current_user.empresa_id, redis=redis)
        configs = await servico.listar(modulo=modulo)
        return [_to_out(c) for c in configs]
    finally:
        await redis.aclose()


@router.put("/{slug}", response_model=ConfiguracaoOut)
async def atualizar_configuracao(
    slug: str,
    body: ConfiguracaoUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ConfiguracaoOut:
    _check_admin(current_user)
    settings = get_settings()
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        servico = ServicoConfiguracao(session, current_user.empresa_id, redis=redis)

        # Captura valor anterior para o audit log (lookup direto p/ override do tenant)
        result = await session.execute(
            select(ConfiguracaoSistema).where(
                ConfiguracaoSistema.empresa_id == current_user.empresa_id,
                ConfiguracaoSistema.slug == slug,
            )
        )
        existing = result.scalar_one_or_none()
        valor_antes = existing.valor if existing else None
        modulo_efetivo = body.modulo or (existing.modulo if existing else "geral")

        try:
            atualizada = await servico.definir(
                slug=slug,
                modulo=modulo_efetivo,
                valor=body.valor,
                tipo_valor=body.tipo_valor,
                atualizado_por_id=current_user.id,
                descricao=body.descricao,
            )
        except TipoConfiguracaoInvalidoError as e:
            raise HTTPException(status_code=422, detail=str(e))

        audit = AuditLogger(session)
        await audit.record(
            action="configuracao.atualizada",
            user_id=str(current_user.id),
            entity="configuracoes_sistema",
            entity_id=slug,
            payload_before={"valor": valor_antes} if valor_antes is not None else None,
            payload_after={"valor": atualizada.valor, "tipo_valor": atualizada.tipo_valor},
            ip=None,
            correlation_id=get_correlation_id(),
            module="config",
            category="configuracao",
        )

        await session.commit()
        await session.refresh(atualizada)
        return _to_out(atualizada)
    finally:
        await redis.aclose()
