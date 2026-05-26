"""Conversation CRUD and message endpoints (Epic 6)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import CurrentUserDep, SessionDep
from app.application.shared.audit_logger import AuditLogger
from app.core.agent.conversation_store import ConversationStore
from app.infrastructure.db.models.conversation import Conversation

log = structlog.get_logger()

router = APIRouter(prefix="/conversations", tags=["conversations"])


# --- Schemas ---

class ConversationResponse(BaseModel):
    id: str
    channel: str
    status: str
    phone_e164: str | None = None
    customer_id: str | None = None
    user_id: str | None = None
    unread_count: int = 0
    agent_active: bool = True
    last_message_at: str | None = None
    created_at: str

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content_text: str | None = None
    media_url: str | None = None
    media_mime: str | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    sent_by: str | None = None
    status: str | None = None
    sent_at: str
    created_at: str

    model_config = {"from_attributes": True}


class SendMessageRequest(BaseModel):
    content_text: str = Field(..., min_length=1, max_length=5000)


class TakeoverRequest(BaseModel):
    active: bool = False


class PaginatedConversations(BaseModel):
    items: list[ConversationResponse]
    total: int
    page: int
    page_size: int


# --- Endpoints ---

@router.get("", response_model=PaginatedConversations)
async def list_conversations(
    session: SessionDep,
    user: CurrentUserDep,
    channel: str | None = Query(None),
    unread: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedConversations:
    """List conversations with pagination and filters."""
    store = ConversationStore(session, user.empresa_id)
    conversations, total = await store.list_conversations(
        channel=channel,
        unread_only=unread,
        page=page,
        page_size=page_size,
    )

    items = []
    for conv in conversations:
        items.append(
            ConversationResponse(
                id=str(conv.id),
                channel=conv.canal,
                status=conv.situacao,
                phone_e164=conv.telefone,
                customer_id=str(conv.cliente_id) if conv.cliente_id else None,
                user_id=None,  # user_id removed in migration 0015
                unread_count=conv.nao_lidas,
                agent_active=conv.agente_ativo,
                last_message_at=conv.ultima_mensagem_em.isoformat() if conv.ultima_mensagem_em else None,
                created_at=conv.criado_em.isoformat(),
            )
        )

    return PaginatedConversations(items=items, total=total, page=page, page_size=page_size)


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    conversation_id: UUID,
    session: SessionDep,
    user: CurrentUserDep,
    before: UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> list[MessageResponse]:
    """Get messages for a conversation with cursor pagination."""
    store = ConversationStore(session, user.empresa_id)
    messages = await store.get_messages(conversation_id, before=before, limit=limit)

    return [
        MessageResponse(
            id=str(msg.id),
            conversation_id=str(msg.conversa_id),
            role=msg.direcao,
            content_text=msg.conteudo_texto,
            media_url=msg.midia_url,
            media_mime=msg.midia_mime,
            tool_call_id=None,   # removed in migration 0015
            tool_name=None,      # removed in migration 0015
            sent_by=msg.enviado_por,
            status=msg.status,
            sent_at=msg.enviado_em.isoformat() if msg.enviado_em else "",
            created_at=msg.criado_em.isoformat() if msg.criado_em else "",
        )
        for msg in messages
    ]


@router.post("/{conversation_id}/messages", response_model=MessageResponse, status_code=201)
async def send_message(
    conversation_id: UUID,
    body: SendMessageRequest,
    session: SessionDep,
    user: CurrentUserDep,
) -> MessageResponse:
    """Send a message in a conversation (human operator)."""
    store = ConversationStore(session, user.empresa_id)

    msg = await store.append_message(
        conversation_id,
        role="user",
        content_text=body.content_text,
        sent_by=f"human:{user.id}",
    )

    await session.commit()

    return MessageResponse(
        id=str(msg.id),
        conversation_id=str(msg.conversa_id),
        role=msg.direcao,
        content_text=msg.conteudo_texto,
        media_url=msg.midia_url,
        media_mime=msg.midia_mime,
        tool_call_id=None,   # removed in migration 0015
        tool_name=None,      # removed in migration 0015
        sent_by=msg.enviado_por,
        status=msg.status,
        sent_at=msg.enviado_em.isoformat() if msg.enviado_em else "",
        created_at=msg.criado_em.isoformat() if msg.criado_em else "",
    )


@router.post("/{conversation_id}/read", status_code=200)
async def mark_read(
    conversation_id: UUID,
    session: SessionDep,
    user: CurrentUserDep,
) -> dict:
    """Mark all messages in a conversation as read."""
    store = ConversationStore(session, user.empresa_id)
    await store.mark_read(conversation_id)
    await session.commit()
    return {"status": "ok"}


@router.post("/{conversation_id}/takeover", status_code=200)
async def human_takeover(
    conversation_id: UUID,
    body: TakeoverRequest,
    session: SessionDep,
    user: CurrentUserDep,
) -> dict:
    """Toggle human takeover (pause/resume agent) on a conversation."""
    store = ConversationStore(session, user.empresa_id)
    await store.set_agent_active(conversation_id, body.active)

    audit = AuditLogger(session)
    await audit.record(
        action="conversation.takeover",
        user_id=str(user.id),
        entity="conversation",
        entity_id=str(conversation_id),
        payload_after={"agent_active": body.active},
    )

    await session.commit()

    status = "agent_active" if body.active else "human_takeover"
    return {"status": status, "agent_active": body.active}
