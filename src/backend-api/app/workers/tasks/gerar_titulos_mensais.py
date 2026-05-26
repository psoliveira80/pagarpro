"""Celery task: gerar parcelas mensais de contratos (story 10.1, refatorada em 12-6).

Executa diariamente às 06:00 UTC via Celery Beat, **uma vez por empresa ativa**
(orquestrado por `dispatch_por_empresa` — story 12-6). Para cada contrato da
empresa onde ``modo_geracao = 'mensal'`` e ``proxima_geracao_em <= hoje``:

1. Aplica o índice de correção do contrato (via ``ICorrectionIndexProvider``)
   ao ``valor_base_mensal`` para obter o valor corrigido.
2. Insere um novo ``TituloReceber`` com ``data_vencimento = proxima_geracao_em``.
3. Anexa um ``EventoContrato`` para rastreabilidade.
4. Avança ``proxima_geracao_em`` em um mês, preservando ``dia_geracao``.

**Catch-up:** se um contrato está atrasado mais de um mês (worker parou, novo
contrato com data antiga, etc.), o loop interno gera **todas** as parcelas em
atraso na mesma execução — não fica entregando uma por dia até alcançar.

**Savepoint por contrato:** erros de provider/integridade num contrato dão
rollback isolado (`begin_nested`) sem perder o lote da empresa.

Idempotência: cada vencimento é checado em `_titulo_existe_para_vencimento`
antes de inserir, e protegido pela `UniqueConstraint("empresa_id","contrato_id","sequencia")`.

Isolamento tenant: a task recebe ``empresa_id`` como primeiro argumento,
seta o contexto Python (``set_empresa_id``) e o ``app.empresa_id`` no Postgres
(para RLS — story 12-5).
"""

from __future__ import annotations

import asyncio
from calendar import monthrange
from datetime import date
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_context import reset_empresa_id, set_empresa_id
from app.domain.ports.correction_index_provider import (
    CorrectionIndexUnavailableError,
    ICorrectionIndexProvider,
)
from app.infrastructure.adapters.bcb_correction_adapter import BcbCorrectionAdapter

# Importing the models package ensures every ORM class (Cliente, Veiculo, etc.)
# is registered in SQLAlchemy's metadata before we issue Contrato queries.
from app.infrastructure.db import models  # noqa: F401
from app.infrastructure.db.models.contrato import Contrato, EventoContrato
from app.infrastructure.db.models.financeiro import TituloReceber
from app.workers import celery_app

log = structlog.get_logger()

# Contratos nesses status terminais/rascunho são ignorados pela geração mensal.
_STATUS_INATIVOS = ("rascunho", "encerrado", "rescindido", "cancelado")


def _avancar_um_mes(atual: date, dia_geracao: int) -> date:
    """Retorna ``atual`` + 1 mês, ajustado para ``dia_geracao``.

    Defensivo: se ``dia_geracao`` não existe no mês alvo (ex.: 31 em fev),
    clampa pro último dia do mês. A constraint atual de DB restringe a 1-28,
    mas backfills manuais podem violar — não queremos lançar `ValueError`
    no meio de um lote.
    """
    mes = atual.month + 1
    ano = atual.year
    if mes > 12:
        mes = 1
        ano += 1
    ultimo_dia = monthrange(ano, mes)[1]
    return date(ano, mes, min(dia_geracao, ultimo_dia))


def _aplicar_correcao(base: Decimal, taxa: Decimal) -> Decimal:
    """``corrigido = base * (1 + taxa/100)`` arredondado a 2 decimais."""
    fator = Decimal(1) + (taxa / Decimal(100))
    return (base * fator).quantize(Decimal("0.01"))


async def _proxima_sequencia(session: AsyncSession, contrato_id: UUID) -> int:
    stmt = select(func.coalesce(func.max(TituloReceber.sequencia), 0)).where(
        TituloReceber.contrato_id == contrato_id
    )
    atual = (await session.execute(stmt)).scalar_one()
    return int(atual) + 1


async def _titulo_existe_para_vencimento(
    session: AsyncSession, contrato_id: UUID, data_vencimento: date
) -> bool:
    stmt = select(TituloReceber.id).where(
        TituloReceber.contrato_id == contrato_id,
        TituloReceber.data_vencimento == data_vencimento,
    )
    return (await session.execute(stmt)).first() is not None


async def _gerar_uma_parcela(
    session: AsyncSession,
    contrato: Contrato,
    provider: ICorrectionIndexProvider,
    hoje: date,
) -> bool:
    """Gera UM título para o `proxima_geracao_em` atual e avança a data.

    Retorna True se inseriu, False se pulou (idempotência ou falta de campos).
    """
    if contrato.proxima_geracao_em is None or contrato.dia_geracao is None:
        log.warning(
            "contrato_mensal_sem_campos",
            contrato_id=str(contrato.id),
            numero=contrato.numero,
        )
        return False
    if contrato.valor_base_mensal is None:
        log.warning(
            "contrato_mensal_sem_valor_base",
            contrato_id=str(contrato.id),
        )
        return False

    data_vencimento = contrato.proxima_geracao_em

    if await _titulo_existe_para_vencimento(session, contrato.id, data_vencimento):
        log.info(
            "titulo_mensal_ja_existe",
            contrato_id=str(contrato.id),
            data_vencimento=data_vencimento.isoformat(),
        )
        contrato.proxima_geracao_em = _avancar_um_mes(
            data_vencimento, contrato.dia_geracao
        )
        return False

    base = contrato.valor_base_mensal
    if contrato.indice_correcao:
        taxa = await provider.get_current_rate(contrato.indice_correcao, hoje)
        corrigido = _aplicar_correcao(base, taxa)
    else:
        taxa = Decimal("0")
        corrigido = base

    sequencia = await _proxima_sequencia(session, contrato.id)
    titulo = TituloReceber(
        empresa_id=contrato.empresa_id,
        contrato_id=contrato.id,
        sequencia=sequencia,
        data_vencimento=data_vencimento,
        valor=corrigido,
        valor_pago=Decimal("0"),
        status="em_aberto",
    )
    session.add(titulo)
    session.add(
        EventoContrato(
            empresa_id=contrato.empresa_id,
            contrato_id=contrato.id,
            tipo="titulo_mensal_gerado",
            payload={
                "description": (
                    f"Parcela {sequencia} gerada automaticamente "
                    f"(índice={contrato.indice_correcao or 'nenhum'}, taxa={taxa}%)."
                ),
                "sequencia": sequencia,
                "data_vencimento": data_vencimento.isoformat(),
                "indice_correcao": contrato.indice_correcao,
                "taxa_percentual": str(taxa),
                "valor_base": str(base),
                "valor_corrigido": str(corrigido),
            },
        )
    )
    contrato.proxima_geracao_em = _avancar_um_mes(
        data_vencimento, contrato.dia_geracao
    )
    return True


async def _processar_contrato(
    session: AsyncSession,
    contrato: Contrato,
    provider: ICorrectionIndexProvider,
    hoje: date,
) -> tuple[int, int]:
    """Gera TODAS as parcelas em atraso do contrato (catch-up).

    Loop interno: enquanto `proxima_geracao_em <= hoje`, gera mais uma.
    Limite defensivo de 60 iterações pra evitar loop infinito em caso
    de bug onde `_avancar_um_mes` não avança (já provou-se sólida, mas
    proteção barata vale a pena).

    Retorna `(geradas, puladas)` para o sumário.
    """
    geradas = 0
    puladas = 0
    for _ in range(60):
        if contrato.proxima_geracao_em is None or contrato.proxima_geracao_em > hoje:
            break
        if await _gerar_uma_parcela(session, contrato, provider, hoje):
            geradas += 1
        else:
            puladas += 1
    return geradas, puladas


async def _run(
    empresa_id: UUID,
    provider: ICorrectionIndexProvider | None = None,
) -> dict[str, int]:
    from app.infrastructure.db.session import get_sessionmaker
    from app.infrastructure.settings import get_settings

    hoje = date.today()
    session_factory = get_sessionmaker()
    sumario = {"generated": 0, "skipped": 0, "failed": 0}
    redis = None
    provider_dispose_local = False

    try:
        if provider is None:
            # Criação do Redis movida pra dentro do try — se falhar antes,
            # nada vaza. Caller que passe provider explícito (tests) reusa
            # o próprio Redis.
            from redis.asyncio import Redis

            settings = get_settings()
            redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
            provider = BcbCorrectionAdapter(redis=redis)
            provider_dispose_local = True

        async with session_factory() as session:
            # Seta `app.empresa_id` para o RLS (story 12-5) filtrar tudo no DB.
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(empresa_id)},
            )

            stmt = (
                select(Contrato)
                .where(
                    Contrato.empresa_id == empresa_id,
                    Contrato.modo_geracao == "mensal",
                    Contrato.proxima_geracao_em <= hoje,
                    Contrato.excluido_em.is_(None),
                    Contrato.status.notin_(_STATUS_INATIVOS),
                )
                .with_for_update(skip_locked=True)
            )
            contratos = list((await session.execute(stmt)).scalars().all())
            for contrato in contratos:
                # Savepoint por contrato — erro num contrato (provider fora do ar,
                # violação de constraint) dá rollback ISOLADO e os demais seguem.
                try:
                    async with session.begin_nested():
                        geradas, puladas = await _processar_contrato(
                            session, contrato, provider, hoje
                        )
                except CorrectionIndexUnavailableError as exc:
                    log.error(
                        "indice_correcao_indisponivel",
                        contrato_id=str(contrato.id),
                        error=str(exc),
                    )
                    sumario["failed"] += 1
                    continue
                except Exception as exc:
                    log.exception(
                        "contrato_processamento_falhou",
                        contrato_id=str(contrato.id),
                        error=str(exc),
                    )
                    sumario["failed"] += 1
                    continue
                sumario["generated"] += geradas
                sumario["skipped"] += puladas

            await session.commit()
    finally:
        if redis is not None and provider_dispose_local:
            await redis.aclose()

    log.info(
        "geracao_titulos_mensais_complete",
        empresa_id=str(empresa_id),
        **sumario,
    )
    return sumario


@celery_app.task(name="app.workers.tasks.gerar_titulos_mensais.executar")
def executar(empresa_id: str) -> dict[str, int]:
    """Entry point da task Celery.

    Args:
        empresa_id: UUID da empresa (em string) injetado pelo orquestrador
            `dispatch_por_empresa`.
    """
    eid = UUID(empresa_id)
    set_empresa_id(eid)
    try:
        return asyncio.run(_run(eid))
    finally:
        # Workers Celery reusam processos — limpa o ContextVar pra não
        # vazar empresa entre execuções consecutivas no mesmo worker.
        reset_empresa_id()
