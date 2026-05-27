"""Endpoints REST para `comunicacao.templates_mensagem` (Story 13.10).

Role-gated: somente Admin pode listar/criar/atualizar. Preview disponível
para qualquer admin testar template antes de salvar.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentUserDep, SessionDep
from app.infrastructure.db.models.template_mensagem import TemplateMensagem
from app.infrastructure.mensageria.renderizador_template import (
    CONTEXTO_EXEMPLO,
    RenderizadorTemplate,
    TemplateRenderError,
)


router = APIRouter(prefix="/templates-mensagem", tags=["templates-mensagem"])


class TemplateOut(BaseModel):
    id: str
    nome: str
    canal: str
    conteudo: str
    descricao: str | None
    ativo: bool
    escopo: str  # 'global' | 'tenant'


class TemplateCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=100)
    canal: str = Field(default="whatsapp")
    conteudo: str = Field(min_length=1)
    descricao: str | None = None
    ativo: bool = True


class TemplateUpdate(BaseModel):
    conteudo: str | None = None
    descricao: str | None = None
    ativo: bool | None = None


class PreviewRequest(BaseModel):
    conteudo: str
    contexto: dict | None = None  # se None, usa CONTEXTO_EXEMPLO


class PreviewResponse(BaseModel):
    rendered: str


def _check_admin(current_user) -> None:
    roles = [(p.nome or "").lower() for p in (current_user.perfis or [])]
    if "admin" not in roles:
        raise HTTPException(
            status_code=403, detail="Apenas administradores podem gerenciar templates"
        )


def _to_out(row: TemplateMensagem) -> TemplateOut:
    return TemplateOut(
        id=str(row.id),
        nome=row.nome,
        canal=row.canal,
        conteudo=row.conteudo,
        descricao=row.descricao,
        ativo=row.ativo,
        escopo="global" if row.empresa_id is None else "tenant",
    )


@router.get("", response_model=list[TemplateOut])
async def listar_templates(
    session: SessionDep,
    current_user: CurrentUserDep,
) -> list[TemplateOut]:
    _check_admin(current_user)
    # RLS já filtra; pega tudo visível ao tenant (override + globais)
    result = await session.execute(
        select(TemplateMensagem).order_by(TemplateMensagem.nome, TemplateMensagem.canal)
    )
    rows = list(result.scalars().all())

    # Se override e global existirem com mesmo (nome, canal), devolve só o override
    by_key: dict[tuple[str, str], TemplateMensagem] = {}
    for r in rows:
        key = (r.nome, r.canal)
        if key in by_key:
            if r.empresa_id is not None:
                by_key[key] = r
        else:
            by_key[key] = r

    return [_to_out(t) for t in by_key.values()]


@router.post("", response_model=TemplateOut)
async def criar_template(
    body: TemplateCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> TemplateOut:
    """Cria um override do template para o tenant atual.

    Se já existir override (empresa_id, nome, canal), retorna 409.
    """
    _check_admin(current_user)

    result = await session.execute(
        select(TemplateMensagem).where(
            TemplateMensagem.empresa_id == current_user.empresa_id,
            TemplateMensagem.nome == body.nome,
            TemplateMensagem.canal == body.canal,
        )
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Template '{body.nome}' canal={body.canal} já existe para este tenant. Use PUT para atualizar.",
        )

    template = TemplateMensagem(
        empresa_id=current_user.empresa_id,
        nome=body.nome,
        canal=body.canal,
        conteudo=body.conteudo,
        descricao=body.descricao,
        ativo=body.ativo,
    )
    session.add(template)
    await session.flush()
    await session.commit()
    await session.refresh(template)
    return _to_out(template)


@router.put("/{template_id}", response_model=TemplateOut)
async def atualizar_template(
    template_id: UUID,
    body: TemplateUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> TemplateOut:
    _check_admin(current_user)

    result = await session.execute(
        select(TemplateMensagem).where(
            TemplateMensagem.id == template_id,
            TemplateMensagem.empresa_id == current_user.empresa_id,
        )
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(
            status_code=404,
            detail="Template não encontrado (ou pertence a outro tenant / é global).",
        )

    if body.conteudo is not None:
        template.conteudo = body.conteudo
    if body.descricao is not None:
        template.descricao = body.descricao
    if body.ativo is not None:
        template.ativo = body.ativo
    template.atualizado_em = datetime.now(timezone.utc)

    await session.flush()
    await session.commit()
    await session.refresh(template)
    return _to_out(template)


@router.post("/preview", response_model=PreviewResponse)
async def preview_template(
    body: PreviewRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> PreviewResponse:
    """Renderiza `conteudo` com `contexto` (ou contexto de exemplo) — para
    testar template na UI antes de salvar. Não persiste nada."""
    _check_admin(current_user)
    renderizador = RenderizadorTemplate(session, current_user.empresa_id)
    contexto = body.contexto if body.contexto is not None else CONTEXTO_EXEMPLO
    try:
        rendered = await renderizador.preview(body.conteudo, contexto)
    except TemplateRenderError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return PreviewResponse(rendered=rendered)
