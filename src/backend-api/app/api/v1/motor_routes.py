"""Endpoint de observabilidade do motor (Story 13.5).

Retorna histórico de execuções (`motor.execucoes_motor`) com filtros.
Role admin obrigatório.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import CurrentUserDep, SessionDep
from app.infrastructure.db.models.execucao_motor import ExecucaoMotor


router = APIRouter(prefix="/motor", tags=["motor"])


class ExecucaoOut(BaseModel):
    id: str
    nome_tarefa: str
    empresa_id: str | None
    iniciado_em: datetime
    finalizado_em: datetime | None
    duracao_segundos: float | None
    total_registros: int
    total_erros: int
    situacao: str
    detalhes: dict | None


class ExecucoesResponse(BaseModel):
    items: list[ExecucaoOut]
    total: int
    page: int
    size: int
    pages: int


def _check_admin(current_user) -> None:
    roles = [(p.nome or "").lower() for p in (current_user.perfis or [])]
    if "admin" not in roles:
        raise HTTPException(
            status_code=403, detail="Apenas administradores podem ver execuções do motor"
        )


def _to_out(row: ExecucaoMotor) -> ExecucaoOut:
    duracao = None
    if row.finalizado_em and row.iniciado_em:
        duracao = (row.finalizado_em - row.iniciado_em).total_seconds()
    return ExecucaoOut(
        id=str(row.id),
        nome_tarefa=row.nome_tarefa,
        empresa_id=str(row.empresa_id) if row.empresa_id else None,
        iniciado_em=row.iniciado_em,
        finalizado_em=row.finalizado_em,
        duracao_segundos=duracao,
        total_registros=row.total_registros,
        total_erros=row.total_erros,
        situacao=row.situacao,
        detalhes=row.detalhes,
    )


class DisparoManualResponse(BaseModel):
    task_id: str
    nome_tarefa: str
    mensagem: str


@router.post("/gerar-titulos", response_model=DisparoManualResponse)
async def disparar_gerar_titulos(
    current_user: CurrentUserDep,
) -> DisparoManualResponse:
    """Dispara manualmente o motor `gerar_titulos_mensais` pro tenant atual.

    Use com cuidado — o motor é idempotente (não duplica), mas se houver
    contratos com `proxima_geracao_em <= hoje` que não foram processados
    pelo cron, esta chamada gera as parcelas em atraso (catch-up).
    """
    _check_admin(current_user)
    from app.workers import celery_app

    result = celery_app.send_task(
        "app.workers.tasks.gerar_titulos_mensais.executar",
        args=[str(current_user.empresa_id)],
    )
    return DisparoManualResponse(
        task_id=result.id,
        nome_tarefa="gerar_titulos_mensais",
        mensagem="Motor disparado em background. Acompanhe em /api/v1/motor/execucoes.",
    )


@router.get("/execucoes", response_model=ExecucoesResponse)
async def listar_execucoes(
    session: SessionDep,
    current_user: CurrentUserDep,
    nome_tarefa: str | None = Query(None),
    situacao: str | None = Query(None, pattern="^(executando|concluido|erro)$"),
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=200),
) -> ExecucoesResponse:
    _check_admin(current_user)

    stmt = select(ExecucaoMotor)
    count_stmt = select(func.count()).select_from(ExecucaoMotor)

    if nome_tarefa:
        stmt = stmt.where(ExecucaoMotor.nome_tarefa == nome_tarefa)
        count_stmt = count_stmt.where(ExecucaoMotor.nome_tarefa == nome_tarefa)
    if situacao:
        stmt = stmt.where(ExecucaoMotor.situacao == situacao)
        count_stmt = count_stmt.where(ExecucaoMotor.situacao == situacao)

    stmt = stmt.order_by(ExecucaoMotor.iniciado_em.desc()).offset((page - 1) * size).limit(size)

    total = (await session.execute(count_stmt)).scalar_one()
    rows = list((await session.execute(stmt)).scalars().all())

    return ExecucoesResponse(
        items=[_to_out(r) for r in rows],
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size if total > 0 else 0,
    )
