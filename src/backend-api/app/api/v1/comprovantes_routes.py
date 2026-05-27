"""Endpoints REST para análise/homologação de comprovantes (Story 13.19).

`POST /comprovantes/analisar` — upload + pipeline + persistência.
`POST /comprovantes/{id}/homologar` — gestor aprova → dispara ServicoTituloPago.
`POST /comprovantes/{id}/rejeitar` — gestor rejeita com motivo.
`GET  /comprovantes` — lista paginada com filtros (status, score mínimo).
`GET  /comprovantes/{id}` — detalhe (com texto_bruto_ocr para auditoria).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import boto3
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import CurrentUserDep, SessionDep
from app.application.services.servico_analise_comprovante import (
    ComprovanteJaAnalisadoError,
    ServicoAnaliseComprovante,
)
from app.application.services.servico_titulo_pago import ServicoTituloPago
from app.infrastructure.db.models.comprovante_pagamento import ComprovantePagamento
from app.infrastructure.settings import get_settings


router = APIRouter(prefix="/comprovantes", tags=["comprovantes"])


# ───────── Schemas ─────────

class ComprovanteOut(BaseModel):
    id: str
    titulo_id: str | None
    cliente_id: str | None
    arquivo_url: str
    tipo_arquivo: str
    metodo_analise: str | None
    score_confianca: float
    valor_detectado: float | None
    data_detectada: datetime | None
    pix_e2e_id: str | None
    pix_txid: str | None
    banco_emissor: str | None
    beneficiario_nome: str | None
    beneficiario_cnpj: str | None
    pagador_nome: str | None
    pagador_documento: str | None
    chave_pix_usada: str | None
    avisos: list[str]
    status: str
    origem: str
    criado_em: datetime
    homologado_em: datetime | None
    rejeitado_em: datetime | None
    motivo_rejeicao: str | None


class ListagemResponse(BaseModel):
    items: list[ComprovanteOut]
    total: int
    page: int
    size: int
    pages: int


class RejeitarRequest(BaseModel):
    motivo: str


class HomologarResponse(BaseModel):
    comprovante: ComprovanteOut
    titulo_atualizado: dict


# ───────── Helpers ─────────

def _check_pode_homologar(current_user) -> None:
    roles = [(p.nome or "").lower() for p in (current_user.perfis or [])]
    if not any(r in roles for r in ("admin", "financeiro")):
        raise HTTPException(
            status_code=403,
            detail="Apenas admin ou financeiro podem homologar/rejeitar comprovantes",
        )


def _to_out(c: ComprovantePagamento) -> ComprovanteOut:
    return ComprovanteOut(
        id=str(c.id),
        titulo_id=str(c.titulo_id) if c.titulo_id else None,
        cliente_id=str(c.cliente_id) if c.cliente_id else None,
        arquivo_url=c.arquivo_url,
        tipo_arquivo=c.tipo_arquivo,
        metodo_analise=c.metodo_analise,
        score_confianca=float(c.score_confianca),
        valor_detectado=float(c.valor_detectado) if c.valor_detectado else None,
        data_detectada=c.data_detectada,
        pix_e2e_id=c.pix_e2e_id,
        pix_txid=c.pix_txid,
        banco_emissor=c.banco_emissor,
        beneficiario_nome=c.beneficiario_nome,
        beneficiario_cnpj=c.beneficiario_cnpj,
        pagador_nome=c.pagador_nome,
        pagador_documento=c.pagador_documento,
        chave_pix_usada=c.chave_pix_usada,
        avisos=c.avisos or [],
        status=c.status,
        origem=c.origem,
        criado_em=c.criado_em,
        homologado_em=c.homologado_em,
        rejeitado_em=c.rejeitado_em,
        motivo_rejeicao=c.motivo_rejeicao,
    )


async def _upload_s3(bytes_arquivo: bytes, key: str, content_type: str) -> str:
    """Sobe arquivo no MinIO/S3 e retorna URL pública (presigned em prod)."""
    settings = get_settings()
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
    )
    s3.put_object(
        Bucket=settings.S3_BUCKET,
        Key=key,
        Body=bytes_arquivo,
        ContentType=content_type,
    )
    return f"{settings.S3_ENDPOINT_URL}/{settings.S3_BUCKET}/{key}"


# ───────── Endpoints ─────────

@router.post("/analisar", response_model=ComprovanteOut)
async def analisar_comprovante(
    session: SessionDep,
    current_user: CurrentUserDep,
    arquivo: UploadFile = File(...),
    titulo_id: str | None = Form(None),
    cliente_id: str | None = Form(None),
):
    """Recebe imagem/PDF de comprovante, roda pipeline e retorna resultado.

    Idempotente: enviar 2× o mesmo arquivo retorna o registro existente
    (status 200) sem reprocessar.
    """
    bytes_arquivo = await arquivo.read()
    if not bytes_arquivo:
        raise HTTPException(status_code=400, detail="Arquivo vazio")

    tipo_mime = arquivo.content_type or "application/octet-stream"
    if not (tipo_mime.startswith("image/") or tipo_mime == "application/pdf"):
        raise HTTPException(
            status_code=415,
            detail=f"Tipo não suportado: {tipo_mime}. Use imagem ou PDF.",
        )

    # Upload no S3/MinIO antes do pipeline (caso pipeline falhe, ainda temos o arquivo)
    ext = "pdf" if tipo_mime == "application/pdf" else tipo_mime.split("/")[1]
    s3_key = f"comprovantes/{current_user.empresa_id}/{uuid.uuid4()}.{ext}"
    try:
        arquivo_url = await _upload_s3(bytes_arquivo, s3_key, tipo_mime)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro no upload: {exc}")

    servico = ServicoAnaliseComprovante(session, current_user.empresa_id)
    try:
        comprovante = await servico.analisar(
            bytes_arquivo=bytes_arquivo,
            tipo_mime=tipo_mime,
            arquivo_url=arquivo_url,
            cliente_id=UUID(cliente_id) if cliente_id else None,
            titulo_id_sugerido=UUID(titulo_id) if titulo_id else None,
            origem="upload",
        )
    except ComprovanteJaAnalisadoError as ja_existe:
        await session.rollback()
        return _to_out(ja_existe.comprovante_existente)

    await session.commit()
    await session.refresh(comprovante)
    return _to_out(comprovante)


@router.get("", response_model=ListagemResponse)
async def listar_comprovantes(
    session: SessionDep,
    current_user: CurrentUserDep,
    status: str | None = Query(None, pattern="^(analisado|homologado|rejeitado|erro_analise)$"),
    score_minimo: float | None = Query(None, ge=0, le=1),
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=200),
):
    """Lista comprovantes do tenant com filtros."""
    stmt = select(ComprovantePagamento)
    count_stmt = select(func.count()).select_from(ComprovantePagamento)

    if status:
        stmt = stmt.where(ComprovantePagamento.status == status)
        count_stmt = count_stmt.where(ComprovantePagamento.status == status)
    if score_minimo is not None:
        stmt = stmt.where(ComprovantePagamento.score_confianca >= Decimal(str(score_minimo)))
        count_stmt = count_stmt.where(ComprovantePagamento.score_confianca >= Decimal(str(score_minimo)))

    stmt = stmt.order_by(ComprovantePagamento.criado_em.desc()).offset((page - 1) * size).limit(size)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = list((await session.execute(stmt)).scalars().all())

    return ListagemResponse(
        items=[_to_out(r) for r in rows],
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size if total > 0 else 0,
    )


@router.get("/{comprovante_id}", response_model=ComprovanteOut)
async def detalhar_comprovante(
    comprovante_id: UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    row = await session.execute(
        select(ComprovantePagamento).where(
            ComprovantePagamento.id == comprovante_id,
            ComprovantePagamento.empresa_id == current_user.empresa_id,
        )
    )
    comp = row.scalar_one_or_none()
    if comp is None:
        raise HTTPException(status_code=404, detail="Comprovante não encontrado")
    return _to_out(comp)


@router.post("/{comprovante_id}/homologar", response_model=HomologarResponse)
async def homologar_comprovante(
    comprovante_id: UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Gestor confirma o comprovante (1 clique). Marca como homologado +
    dispara `ServicoTituloPago.registrar_pagamento` no título vinculado."""
    _check_pode_homologar(current_user)

    row = await session.execute(
        select(ComprovantePagamento).where(
            ComprovantePagamento.id == comprovante_id,
            ComprovantePagamento.empresa_id == current_user.empresa_id,
        )
    )
    comp = row.scalar_one_or_none()
    if comp is None:
        raise HTTPException(status_code=404, detail="Comprovante não encontrado")
    if comp.status != "analisado":
        raise HTTPException(
            status_code=409,
            detail=f"Comprovante não está no status 'analisado' (atual: {comp.status})",
        )
    if comp.titulo_id is None:
        raise HTTPException(
            status_code=400,
            detail="Comprovante sem título vinculado — selecione manualmente o título antes de homologar",
        )
    if comp.valor_detectado is None:
        raise HTTPException(
            status_code=400,
            detail="Comprovante sem valor detectado — revise manualmente",
        )

    # Dispara fluxo da Story 13.9 (decisão integral/parcial → fundir/separar)
    servico = ServicoTituloPago(session, current_user.empresa_id)
    result = await servico.registrar_pagamento(
        titulo_id=comp.titulo_id,
        valor_pago=comp.valor_detectado,
        data_pagamento=comp.data_detectada.date() if comp.data_detectada else None,
        forma_pagamento="pix",
        ator_id=current_user.id,
    )

    comp.status = "homologado"
    comp.homologado_por_id = current_user.id
    comp.homologado_em = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(comp)
    return HomologarResponse(comprovante=_to_out(comp), titulo_atualizado=result)


@router.post("/{comprovante_id}/rejeitar", response_model=ComprovanteOut)
async def rejeitar_comprovante(
    comprovante_id: UUID,
    body: RejeitarRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Gestor rejeita o comprovante. Não altera título — só marca o registro."""
    _check_pode_homologar(current_user)

    row = await session.execute(
        select(ComprovantePagamento).where(
            ComprovantePagamento.id == comprovante_id,
            ComprovantePagamento.empresa_id == current_user.empresa_id,
        )
    )
    comp = row.scalar_one_or_none()
    if comp is None:
        raise HTTPException(status_code=404, detail="Comprovante não encontrado")

    comp.status = "rejeitado"
    comp.rejeitado_por_id = current_user.id
    comp.rejeitado_em = datetime.now(timezone.utc)
    comp.motivo_rejeicao = body.motivo

    await session.commit()
    await session.refresh(comp)
    return _to_out(comp)
