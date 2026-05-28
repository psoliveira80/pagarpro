"""Endpoints REST para conciliação bancária (Story 13.20).

`POST /conciliacao/importar`        — upload OFX/PDF/CSV → cria sessão.
`GET  /conciliacao/sessoes`         — lista sessões do tenant.
`GET  /conciliacao/sessoes/{id}`    — detalhe + sugestões de match.
`POST /conciliacao/aplicar`         — gestor confirma 1 match.
`POST /conciliacao/aplicar-lote`    — aplica todos matches verdes (≥ 95%).
`POST /conciliacao/desfazer/{id}`   — desfaz match em até 30 dias.
`POST /conciliacao/finalizar/{id}`  — marca sessão como concluída (read-only).
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentUserDep, SessionDep
from app.application.services.servico_conciliacao import (
    ConciliacaoInvalidaError,
    SessaoJaExistenteError,
    ServicoConciliacao,
    SugestaoMatch,
)
from app.infrastructure.conciliacao.dto import FormatoOrigem
from app.infrastructure.db.models.conta_bancaria import (
    MatchConciliacao,
    SessaoConciliacao,
    TransacaoBancaria,
)


router = APIRouter(prefix="/conciliacao", tags=["conciliacao"])


def _check_pode_conciliar(current_user) -> None:
    roles = [(p.nome or "").lower() for p in (current_user.perfis or [])]
    if not any(r in roles for r in ("admin", "financeiro")):
        raise HTTPException(
            status_code=403,
            detail="Apenas admin ou financeiro podem fazer conciliação",
        )


# ───────── Schemas ─────────

class SessaoOut(BaseModel):
    id: str
    conta_id: str
    periodo_inicio: date
    periodo_fim: date
    status: str
    total_transacoes: int
    total_conciliadas: int
    nome_arquivo_origem: str | None
    formato_origem: str | None
    criado_em: datetime
    concluida_em: datetime | None


class TransacaoOut(BaseModel):
    id: str
    fitid: str
    lancado_em: date
    valor: float
    descricao_bruta: str | None
    tipo: str | None
    status: str
    conciliado_com_id: str | None


class SugestaoOut(BaseModel):
    transacao_id: str
    titulo_id: str | None
    score: float
    motivo: str
    ja_existia_via_comprovante: bool
    comprovante_id: str | None


class DetalheSessaoOut(BaseModel):
    sessao: SessaoOut
    transacoes: list[TransacaoOut]
    sugestoes: list[SugestaoOut]


class AplicarMatchRequest(BaseModel):
    sessao_id: str
    transacao_id: str
    titulo_id: str
    score: float = Field(ge=0, le=1)
    motivo: str
    ja_existia_via_comprovante: bool = False


class AplicarLoteRequest(BaseModel):
    sessao_id: str
    score_minimo: float = Field(0.95, ge=0, le=1)


class AplicarLoteResponse(BaseModel):
    aplicados: int
    pulados_score_baixo: int
    pulados_erro: int
    erros: list[str]


class DesfazerMatchRequest(BaseModel):
    motivo: str


class MatchOut(BaseModel):
    id: str
    transacao_id: str
    titulo_id: str
    score_match: float
    motivo_match: str | None
    aplicado_em: datetime
    desfeito_em: datetime | None
    motivo_desfazer: str | None


# ───────── Helpers ─────────

def _sessao_to_out(s: SessaoConciliacao) -> SessaoOut:
    return SessaoOut(
        id=str(s.id),
        conta_id=str(s.conta_id),
        periodo_inicio=s.periodo_inicio,
        periodo_fim=s.periodo_fim,
        status=s.status,
        total_transacoes=s.total_transacoes,
        total_conciliadas=s.total_conciliadas,
        nome_arquivo_origem=s.nome_arquivo_origem,
        formato_origem=s.formato_origem,
        criado_em=s.criado_em,
        concluida_em=s.concluida_em,
    )


def _tx_to_out(t: TransacaoBancaria) -> TransacaoOut:
    return TransacaoOut(
        id=str(t.id),
        fitid=t.fitid,
        lancado_em=t.lancado_em,
        valor=float(t.valor),
        descricao_bruta=t.descricao_bruta,
        tipo=t.tipo,
        status=t.status,
        conciliado_com_id=str(t.conciliado_com_id) if t.conciliado_com_id else None,
    )


def _sug_to_out(s: SugestaoMatch) -> SugestaoOut:
    return SugestaoOut(
        transacao_id=str(s.transacao_id),
        titulo_id=str(s.titulo_id) if s.titulo_id else None,
        score=s.score,
        motivo=s.motivo,
        ja_existia_via_comprovante=s.ja_existia_via_comprovante,
        comprovante_id=str(s.comprovante_id) if s.comprovante_id else None,
    )


# ───────── Endpoints ─────────

@router.post("/importar", response_model=SessaoOut)
async def importar_extrato(
    session: SessionDep,
    current_user: CurrentUserDep,
    conta_id: str = Form(...),
    formato: str = Form(...),  # 'ofx' | 'pdf' | 'csv'
    arquivo: UploadFile = File(...),
    mapeamento_csv: str | None = Form(None),  # JSON string quando formato=csv
):
    """Upload e import de extrato bancário.

    Idempotente: mesmo arquivo (mesmo hash SHA-256) na mesma conta retorna
    a sessão existente (200), não duplica.
    """
    _check_pode_conciliar(current_user)

    bytes_arquivo = await arquivo.read()
    if not bytes_arquivo:
        raise HTTPException(status_code=400, detail="Arquivo vazio")

    try:
        formato_enum = FormatoOrigem(formato.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Formato inválido: {formato}. Aceitos: ofx, pdf, csv",
        )

    mapeamento_dict = None
    if formato_enum == FormatoOrigem.CSV:
        if not mapeamento_csv:
            raise HTTPException(
                status_code=400,
                detail="CSV exige campo `mapeamento_csv` com mapeamento de colunas",
            )
        try:
            mapeamento_dict = json.loads(mapeamento_csv)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="mapeamento_csv inválido (não é JSON)")

    servico = ServicoConciliacao(session, current_user.empresa_id)
    try:
        sessao = await servico.importar(
            conta_id=UUID(conta_id),
            bytes_arquivo=bytes_arquivo,
            nome_arquivo=arquivo.filename or "extrato",
            formato=formato_enum,
            criado_por_id=current_user.id,
            mapeamento_csv=mapeamento_dict,
        )
    except SessaoJaExistenteError as ja_existe:
        await session.rollback()
        return _sessao_to_out(ja_existe.sessao_existente)
    except ConciliacaoInvalidaError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await session.commit()
    await session.refresh(sessao)
    return _sessao_to_out(sessao)


@router.get("/sessoes", response_model=list[SessaoOut])
async def listar_sessoes(
    session: SessionDep,
    current_user: CurrentUserDep,
):
    _check_pode_conciliar(current_user)
    rows = await session.execute(
        select(SessaoConciliacao)
        .where(SessaoConciliacao.empresa_id == current_user.empresa_id)
        .order_by(SessaoConciliacao.criado_em.desc())
    )
    return [_sessao_to_out(s) for s in rows.scalars().all()]


@router.get("/sessoes/{sessao_id}", response_model=DetalheSessaoOut)
async def detalhar_sessao(
    sessao_id: UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Retorna sessão + transações pendentes + sugestões de match."""
    _check_pode_conciliar(current_user)

    sessao = (await session.execute(
        select(SessaoConciliacao).where(
            SessaoConciliacao.id == sessao_id,
            SessaoConciliacao.empresa_id == current_user.empresa_id,
        )
    )).scalar_one_or_none()
    if sessao is None:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    transacoes = list((await session.execute(
        select(TransacaoBancaria).where(
            TransacaoBancaria.empresa_id == current_user.empresa_id,
            TransacaoBancaria.conta_id == sessao.conta_id,
            TransacaoBancaria.lancado_em >= sessao.periodo_inicio,
            TransacaoBancaria.lancado_em <= sessao.periodo_fim,
        ).order_by(TransacaoBancaria.lancado_em)
    )).scalars().all())

    servico = ServicoConciliacao(session, current_user.empresa_id)
    sugestoes = await servico.listar_sugestoes(sessao_id)

    return DetalheSessaoOut(
        sessao=_sessao_to_out(sessao),
        transacoes=[_tx_to_out(t) for t in transacoes],
        sugestoes=[_sug_to_out(s) for s in sugestoes],
    )


@router.post("/aplicar", response_model=MatchOut)
async def aplicar_match(
    body: AplicarMatchRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Gestor confirma 1 match. Dispara `ServicoTituloPago` (a menos que
    o pagamento já tenha vindo via comprovante PIX)."""
    _check_pode_conciliar(current_user)

    servico = ServicoConciliacao(session, current_user.empresa_id)
    try:
        match = await servico.aplicar_match(
            sessao_id=UUID(body.sessao_id),
            transacao_id=UUID(body.transacao_id),
            titulo_id=UUID(body.titulo_id),
            score=body.score,
            motivo=body.motivo,
            aplicado_por_id=current_user.id,
            ja_existia_via_comprovante=body.ja_existia_via_comprovante,
        )
    except ConciliacaoInvalidaError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await session.commit()
    await session.refresh(match)
    return MatchOut(
        id=str(match.id),
        transacao_id=str(match.transacao_id),
        titulo_id=str(match.titulo_id),
        score_match=float(match.score_match),
        motivo_match=match.motivo_match,
        aplicado_em=match.aplicado_em,
        desfeito_em=match.desfeito_em,
        motivo_desfazer=match.motivo_desfazer,
    )


@router.post("/aplicar-lote", response_model=AplicarLoteResponse)
async def aplicar_lote(
    body: AplicarLoteRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Aplica todos os matches da sessão com score ≥ `score_minimo` (default 0.95)."""
    _check_pode_conciliar(current_user)

    servico = ServicoConciliacao(session, current_user.empresa_id)
    sugestoes = await servico.listar_sugestoes(UUID(body.sessao_id))

    aplicados = 0
    pulados_baixo = 0
    pulados_erro = 0
    erros: list[str] = []

    for sug in sugestoes:
        if sug.score < body.score_minimo:
            pulados_baixo += 1
            continue
        if sug.titulo_id is None:
            pulados_baixo += 1
            continue
        try:
            await servico.aplicar_match(
                sessao_id=UUID(body.sessao_id),
                transacao_id=sug.transacao_id,
                titulo_id=sug.titulo_id,
                score=sug.score,
                motivo=sug.motivo,
                aplicado_por_id=current_user.id,
                ja_existia_via_comprovante=sug.ja_existia_via_comprovante,
            )
            aplicados += 1
        except ConciliacaoInvalidaError as exc:
            pulados_erro += 1
            erros.append(f"transacao_id={sug.transacao_id}: {exc}")

    await session.commit()
    return AplicarLoteResponse(
        aplicados=aplicados,
        pulados_score_baixo=pulados_baixo,
        pulados_erro=pulados_erro,
        erros=erros[:10],
    )


@router.post("/desfazer/{match_id}", response_model=MatchOut)
async def desfazer_match(
    match_id: UUID,
    body: DesfazerMatchRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    _check_pode_conciliar(current_user)
    servico = ServicoConciliacao(session, current_user.empresa_id)
    try:
        match = await servico.desfazer_match(
            match_id=match_id,
            motivo=body.motivo,
            desfeito_por_id=current_user.id,
        )
    except ConciliacaoInvalidaError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await session.commit()
    await session.refresh(match)
    return MatchOut(
        id=str(match.id),
        transacao_id=str(match.transacao_id),
        titulo_id=str(match.titulo_id),
        score_match=float(match.score_match),
        motivo_match=match.motivo_match,
        aplicado_em=match.aplicado_em,
        desfeito_em=match.desfeito_em,
        motivo_desfazer=match.motivo_desfazer,
    )


@router.post("/finalizar/{sessao_id}", response_model=SessaoOut)
async def finalizar_sessao(
    sessao_id: UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Marca sessão como concluída (read-only)."""
    _check_pode_conciliar(current_user)

    sessao = (await session.execute(
        select(SessaoConciliacao).where(
            SessaoConciliacao.id == sessao_id,
            SessaoConciliacao.empresa_id == current_user.empresa_id,
        )
    )).scalar_one_or_none()
    if sessao is None:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    if sessao.status == "concluida":
        raise HTTPException(status_code=409, detail="Sessão já está concluída")

    sessao.status = "concluida"
    sessao.concluida_em = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(sessao)
    return _sessao_to_out(sessao)
