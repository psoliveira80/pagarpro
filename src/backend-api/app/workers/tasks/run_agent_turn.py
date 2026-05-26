"""Celery task: run an agent turn for a conversation."""

from __future__ import annotations

import asyncio

import structlog

from app.workers import celery_app

log = structlog.get_logger()


@celery_app.task(
    name="app.workers.tasks.run_agent_turn.run_agent_turn",
    bind=True,
    max_retries=2,
    default_retry_delay=5,
    queue="agent",
)
def run_agent_turn(self, conversation_id: str, user_message: str) -> dict:
    """Run an agent turn and send the response via the appropriate channel."""
    return asyncio.run(_run(conversation_id, user_message))


async def _run(conversation_id: str, user_message: str) -> dict:
    from uuid import UUID

    from sqlalchemy import select

    from app.core.agent.conversation_store import ConversationStore
    from app.core.agent.orchestrator import AgentOrchestrator
    from app.core.agent.tool_registry import get_tool_registry
    from app.infrastructure.adapters.llm.llm_factory import get_llm_provider
    from app.infrastructure.adapters.whatsapp.whatsapp_factory import get_whatsapp_gateway
    from app.infrastructure.db.models.agent import AgentConfig
    from app.infrastructure.db.models.conversation import Conversation
    from app.infrastructure.db.session import get_sessionmaker

    conv_id = UUID(conversation_id)

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        # Load conversation
        stmt = select(Conversation).where(Conversation.id == conv_id)
        result = await session.execute(stmt)
        conv = result.scalar_one_or_none()

        if conv is None:
            log.error("conversation_not_found", conversation_id=conversation_id)
            return {"status": "error", "reason": "conversation_not_found"}

        if not conv.agent_active:
            return {"status": "skipped", "reason": "agent_paused"}

        # Get agent config
        config_stmt = select(AgentConfig).where(
            AgentConfig.channel == conv.channel,
            AgentConfig.ativo.is_(True),
        ).limit(1)
        config_result = await session.execute(config_stmt)
        agent_config = config_result.scalar_one_or_none()

        # Get LLM provider
        llm = await get_llm_provider(session)

        # Run orchestrator
        registry = get_tool_registry()
        orchestrator = AgentOrchestrator(
            llm=llm,
            tool_registry=registry,
            session=session,
            empresa_id=conv.empresa_id,
            agent_config=agent_config,
        )

        # For WhatsApp, customer gets restricted permissions
        permissions = ["agent.tools.billing"] if conv.channel == "whatsapp" else None

        reply = await orchestrator.run_turn(
            conv_id,
            user_message,
            user_permissions=permissions,
            context={"session": session, "empresa_id": conv.empresa_id},
        )

        await session.commit()

        # Send reply via WhatsApp if applicable
        if conv.channel == "whatsapp" and conv.phone_e164 and reply:
            try:
                gateway = await get_whatsapp_gateway(session)
                if gateway:
                    await gateway.send_text(conv.phone_e164, reply)
            except Exception:
                log.warning("whatsapp_send_failed", exc_info=True)

        return {"status": "completed", "reply_length": len(reply)}
