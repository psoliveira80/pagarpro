"""Conversation store — persistence layer for conversations and messages."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog
from redis.asyncio import Redis
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.conversation import Conversation, ConversationMessage
from app.infrastructure.settings import get_settings

log = structlog.get_logger()


class ConversationStore:
    """Application service for conversation and message management.

    Tenant-scoped: empresa_id é aplicado em todas as queries de leitura
    (list/get/search) para evitar vazamento cross-tenant. Quando omitido no
    construtor, é lido do contexto da requisição (ver `app.core.tenant_context`).
    `None` explícito é erro (ValueError).
    """

    def __init__(self, session: AsyncSession, empresa_id: "UUID | _Unset" = None):  # type: ignore[assignment]
        from app.core.tenant_context import UNSET, _Unset, resolve_empresa_id

        if empresa_id is None:  # backward-compat: default antigo era None
            empresa_id = UNSET
        self.session = session
        self.empresa_id = resolve_empresa_id(empresa_id)

    async def get_or_create_conversation(
        self,
        *,
        channel: str,
        phone_e164: str | None = None,
        customer_id: UUID | None = None,
        user_id: UUID | None = None,
    ) -> Conversation:
        """Find existing conversation or create a new one (tenant-scoped)."""
        if channel == "whatsapp" and not phone_e164:
            raise ValueError("phone_e164 is required for WhatsApp conversations")
        if channel == "in_app" and not user_id:
            raise ValueError("user_id is required for in_app conversations")

        stmt = select(Conversation).where(
            Conversation.empresa_id == self.empresa_id,
            Conversation.channel == channel,
            Conversation.status.in_(["ativa", "pausada"]),
        )

        if channel == "whatsapp":
            stmt = stmt.where(Conversation.phone_e164 == phone_e164)
        elif channel == "in_app":
            stmt = stmt.where(Conversation.user_id == user_id)

        stmt = stmt.order_by(Conversation.created_at.desc()).limit(1)
        result = await self.session.execute(stmt)
        conv = result.scalar_one_or_none()

        if conv is not None:
            return conv

        conv = Conversation(
            empresa_id=self.empresa_id,
            channel=channel,
            phone_e164=phone_e164,
            customer_id=customer_id,
            user_id=user_id,
            status="ativa",
        )
        self.session.add(conv)
        await self.session.flush()
        return conv

    async def append_message(
        self,
        conversation_id: UUID,
        *,
        role: str,
        content_text: str | None = None,
        media_url: str | None = None,
        media_mime: str | None = None,
        external_id: str | None = None,
        tool_call_id: str | None = None,
        tool_name: str | None = None,
        sent_by: str | None = None,
        metadata_extra: dict | None = None,
        numero_origem_id: UUID | None = None,
    ) -> ConversationMessage:
        """Append a message to a conversation.

        Story 13.21: `numero_origem_id` indica qual número de WhatsApp (credencial
        Evolution Go) processou a mensagem. Permite timeline unificada multi-número.
        """
        now = datetime.now(timezone.utc)
        msg = ConversationMessage(
            conversation_id=conversation_id,
            role=role,
            content_text=content_text,
            media_url=media_url,
            media_mime=media_mime,
            external_id=external_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            sent_by=sent_by,
            status="sent",
            metadata_extra=metadata_extra,
            sent_at=now,
            numero_origem_id=numero_origem_id,
        )
        self.session.add(msg)

        # Update conversation
        await self.session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(
                last_message_at=now,
                unread_count=Conversation.unread_count + (1 if role == "user" else 0),
                updated_at=now,
            )
        )

        await self.session.flush()

        # Publish to Redis for real-time updates
        await self._publish_message(conversation_id, msg)

        return msg

    async def list_conversations(
        self,
        *,
        channel: str | None = None,
        search: str | None = None,
        unread_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Conversation], int]:
        """List conversations with pagination (tenant-scoped)."""
        stmt = select(Conversation).where(
            Conversation.empresa_id == self.empresa_id,
            Conversation.is_archived.is_(False),
        )

        if channel:
            stmt = stmt.where(Conversation.channel == channel)
        if unread_only:
            stmt = stmt.where(Conversation.unread_count > 0)

        # Count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        # Paginate
        stmt = stmt.order_by(Conversation.last_message_at.desc().nullslast())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await self.session.execute(stmt)
        conversations = list(result.scalars().all())

        return conversations, total

    async def get_messages(
        self,
        conversation_id: UUID,
        *,
        before: UUID | None = None,
        limit: int = 50,
    ) -> list[ConversationMessage]:
        """Get messages for a conversation with cursor pagination (tenant-scoped)."""
        stmt = select(ConversationMessage).where(
            ConversationMessage.conversation_id == conversation_id,
            ConversationMessage.empresa_id == self.empresa_id,
        )

        if before:
            # Get the sent_at of the cursor message
            cursor_stmt = select(ConversationMessage.sent_at).where(
                ConversationMessage.id == before
            )
            cursor_result = await self.session.execute(cursor_stmt)
            cursor_at = cursor_result.scalar_one_or_none()
            if cursor_at:
                stmt = stmt.where(ConversationMessage.sent_at < cursor_at)

        stmt = stmt.order_by(ConversationMessage.sent_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def mark_read(self, conversation_id: UUID) -> None:
        """Mark all messages in a conversation as read (tenant-scoped)."""
        await self.session.execute(
            update(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.empresa_id == self.empresa_id,
            )
            .values(unread_count=0)
        )
        await self.session.flush()

    async def set_status(self, conversation_id: UUID, status: str) -> None:
        """Update conversation status (tenant-scoped)."""
        await self.session.execute(
            update(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.empresa_id == self.empresa_id,
            )
            .values(status=status, updated_at=datetime.now(timezone.utc))
        )
        await self.session.flush()

    async def set_agent_active(self, conversation_id: UUID, active: bool) -> None:
        """Toggle agent activity on a conversation (tenant-scoped)."""
        await self.session.execute(
            update(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.empresa_id == self.empresa_id,
            )
            .values(agent_active=active, updated_at=datetime.now(timezone.utc))
        )
        await self.session.flush()

    async def _publish_message(
        self, conversation_id: UUID, msg: ConversationMessage
    ) -> None:
        """Publish a new message event to Redis Pub/Sub."""
        try:
            settings = get_settings()
            redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
            try:
                channel = f"conversations:{conversation_id}"
                payload = json.dumps(
                    {
                        "type": "new_message",
                        "conversation_id": str(conversation_id),
                        "message_id": str(msg.id),
                        "role": msg.role,
                        "content_text": msg.content_text,
                        "sent_by": msg.sent_by,
                        "sent_at": msg.sent_at.isoformat() if msg.sent_at else None,
                    }
                )
                await redis.publish(channel, payload)
            finally:
                await redis.aclose()
        except Exception:
            log.warning("redis_publish_failed", exc_info=True)
