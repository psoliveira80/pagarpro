"""Celery task: gerar TítulosPagar a partir de DespesasRecorrentes (story 5.3, refatorada em 12-6).

Executa diariamente às 04:00 UTC via Celery Beat, **uma vez por empresa ativa**
(orquestrado por `dispatch_por_empresa`). Para cada template ativo da empresa
cujo ``proxima_geracao_em <= hoje`` e ainda dentro de `data_fim` (ou sem
`data_fim`), cria um ``TituloPagar`` com status ``'rascunho'`` e avança o
``proxima_geracao_em`` do template — **gerando todos os atrasados** no mesmo run.

Idempotência: usa `FOR UPDATE SKIP LOCKED` para evitar dupla geração quando
duas instâncias do worker rodam concorrentes (re-deploy, race no beat scheduler).

Isolamento tenant: a task recebe ``empresa_id`` como primeiro argumento, seta
contexto Python + `app.empresa_id` no Postgres para RLS.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from uuid import UUID

import structlog
from sqlalchemy import or_, select, text

from app.core.tenant_context import reset_empresa_id, set_empresa_id
from app.infrastructure.db import models  # noqa: F401
from app.infrastructure.db.models.financeiro import DespesaRecorrente, TituloPagar
from app.workers import celery_app

log = structlog.get_logger()


# Catch-up tem teto pra evitar laço infinito caso `_avancar_data` regrida.
_MAX_PARCELAS_POR_RUN = 60


def _adicionar_meses(d: date, meses: int) -> date:
    mes = d.month - 1 + meses
    ano = d.year + mes // 12
    mes = mes % 12 + 1
    dias_no_mes = [
        31,
        29 if ano % 4 == 0 and (ano % 100 != 0 or ano % 400 == 0) else 28,
        31, 30, 31, 30, 31, 31, 30, 31, 30, 31,
    ]
    dia = min(d.day, dias_no_mes[mes - 1])
    return date(ano, mes, dia)


def _avancar_data(atual: date, periodicidade: str, dia_do_mes: int | None = None) -> date:
    """Avança a data conforme a periodicidade.

    Periodicidades aceitas: `mensal`, `quinzenal`, `semanal`. Valores
    desconhecidos **lançam ValueError** — silenciosamente cair em mensal era
    bug: um typo `"anual"` faturava 12x por ano em vez de 1.
    """
    if periodicidade == "mensal":
        prox = _adicionar_meses(atual, 1)
        if dia_do_mes:
            try:
                prox = prox.replace(day=dia_do_mes)
            except ValueError:
                pass  # Dia não existe no mês alvo (ex.: 31 em fev) — mantém calculado.
        return prox
    if periodicidade == "quinzenal":
        return atual + timedelta(weeks=2)
    if periodicidade == "semanal":
        return atual + timedelta(weeks=1)
    raise ValueError(
        f"Periodicidade desconhecida: {periodicidade!r}. "
        "Aceitas: 'mensal', 'quinzenal', 'semanal'."
    )


async def _run(empresa_id: UUID) -> dict[str, int]:
    from app.infrastructure.db.session import get_sessionmaker

    hoje = date.today()
    session_factory = get_sessionmaker()
    sumario = {"generated": 0, "skipped": 0, "failed": 0}

    async with session_factory() as session:
        await session.execute(
            text("SELECT set_config('app.empresa_id', :eid, true)"),
            {"eid": str(empresa_id)},
        )

        stmt = (
            select(DespesaRecorrente)
            .where(
                DespesaRecorrente.empresa_id == empresa_id,
                DespesaRecorrente.ativo.is_(True),
                DespesaRecorrente.proxima_geracao_em.is_not(None),
                DespesaRecorrente.proxima_geracao_em <= hoje,
                # Templates encerrados (data_fim < hoje) não geram mais —
                # bug pré-fix: continuavam gerando indefinidamente.
                or_(
                    DespesaRecorrente.data_fim.is_(None),
                    DespesaRecorrente.data_fim >= hoje,
                ),
            )
            .with_for_update(skip_locked=True)
        )
        templates = list((await session.execute(stmt)).scalars().all())

        for tpl in templates:
            # Savepoint por template — erro num template (periodicidade
            # inválida, FK quebrada) não derruba o lote.
            try:
                async with session.begin_nested():
                    geradas = await _processar_template(tpl, session, hoje)
                sumario["generated"] += geradas
            except Exception as exc:
                log.exception(
                    "template_recorrente_falhou",
                    template_id=str(tpl.id),
                    empresa_id=str(empresa_id),
                    error=str(exc),
                )
                sumario["failed"] += 1

        await session.commit()

    log.info(
        "gerar_despesas_recorrentes_complete",
        empresa_id=str(empresa_id),
        **sumario,
    )
    return sumario


async def _processar_template(
    tpl: DespesaRecorrente,
    session,
    hoje: date,
) -> int:
    """Gera TODAS as parcelas atrasadas do template (catch-up).

    Returns: contagem de parcelas geradas.
    """
    geradas = 0
    for _ in range(_MAX_PARCELAS_POR_RUN):
        data_vencimento = tpl.proxima_geracao_em
        # `assert` foi substituído por check explícito — assert é dropado com -O.
        if data_vencimento is None or data_vencimento > hoje:
            break
        # data_fim respeitado também no loop interno: a primeira parcela
        # pode estar dentro do contrato, mas as próximas podem cair fora.
        if tpl.data_fim is not None and data_vencimento > tpl.data_fim:
            break

        titulo = TituloPagar(
            empresa_id=tpl.empresa_id,
            fornecedor_id=tpl.fornecedor_id,
            categoria_id=tpl.categoria_id,
            descricao=tpl.descricao,
            valor=tpl.valor,
            data_vencimento=data_vencimento,
            status="rascunho",
            template_id=tpl.id,
            criado_por_id=tpl.criado_por_id,
        )
        session.add(titulo)
        tpl.proxima_geracao_em = _avancar_data(
            data_vencimento,
            tpl.periodicidade,
            tpl.dia_do_mes,
        )
        geradas += 1
    return geradas


@celery_app.task(name="app.workers.tasks.gerar_despesas_recorrentes.executar")
def executar(empresa_id: str) -> dict[str, int]:
    eid = UUID(empresa_id)
    set_empresa_id(eid)
    try:
        return asyncio.run(_run(eid))
    finally:
        reset_empresa_id()
