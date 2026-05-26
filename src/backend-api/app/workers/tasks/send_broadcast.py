"""Celery task: send a broadcast campaign with staggered delivery."""

from __future__ import annotations

import asyncio

import structlog

from app.workers import celery_app

log = structlog.get_logger()


@celery_app.task(
    name="app.workers.tasks.send_broadcast.send_broadcast",
    bind=True,
    max_retries=1,
    queue="default",
)
def send_broadcast(self, campaign_id: str) -> dict:
    """Send a broadcast campaign to matching customers."""
    return asyncio.run(_send(campaign_id))


async def _send(campaign_id: str) -> dict:
    from uuid import UUID

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.infrastructure.adapters.whatsapp.whatsapp_factory import get_whatsapp_gateway, clear_adapter_cache
    from app.infrastructure.db.models.agent import BroadcastCampaign
    from app.infrastructure.db.models.customer import Customer
    from app.infrastructure.settings import get_settings

    # Create fresh engine+session for this task (avoids event loop conflicts)
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, pool_size=2)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_factory() as session:
            stmt = select(BroadcastCampaign).where(
                BroadcastCampaign.id == UUID(campaign_id)
            )
            result = await session.execute(stmt)
            campaign = result.scalar_one_or_none()

            if campaign is None:
                return {"status": "error", "reason": "campaign_not_found"}

            # Get customers with phone numbers
            cust_stmt = select(Customer.telefone, Customer.nome_completo).where(
                Customer.telefone.isnot(None),
                Customer.telefone != "",
                Customer.status == "ativo",
                Customer.excluido_em.is_(None),
            )
            cust_result = await session.execute(cust_stmt)
            recipients = cust_result.all()

            campaign.total_recipients = len(recipients)
            sent = 0

            # Get WhatsApp gateway from DB
            clear_adapter_cache()
            gateway = await get_whatsapp_gateway(session)

            if gateway is None:
                campaign.status = "failed"
                await session.commit()
                log.error("broadcast_no_gateway", campaign_id=campaign_id)
                return {"status": "error", "reason": "no_whatsapp_gateway"}

            for phone, name in recipients:
                try:
                    text = campaign.template.replace("{nome}", name or "Cliente")
                    log.info("broadcast_sending", phone=phone, campaign_id=campaign_id)
                    await gateway.send_text(phone, text)
                    sent += 1
                    campaign.sent_count = sent
                    # Stagger (1s between messages)
                    await asyncio.sleep(1.0)
                except Exception:
                    log.warning("broadcast_send_failed", phone=phone, exc_info=True)

            campaign.status = "completed" if sent == len(recipients) else "partial"
            await session.commit()

        return {"status": campaign.status, "sent": sent, "total": len(recipients)}
    finally:
        await engine.dispose()
