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

    from app.application.services.servico_roteamento_numeros import (
        NenhumNumeroAtivoError,
        ServicoRoteamentoNumeros,
    )
    from app.infrastructure.adapters.whatsapp.whatsapp_factory import (
        _build_adapter,
        get_whatsapp_gateway,
    )
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

            empresa_id = campaign.empresa_id
            roteador = ServicoRoteamentoNumeros(session, empresa_id)

            # Multi-tenant: só clientes da empresa dona da campanha.
            cust_stmt = select(
                Customer.id, Customer.telefone, Customer.nome_completo
            ).where(
                Customer.empresa_id == empresa_id,
                Customer.telefone.isnot(None),
                Customer.telefone != "",
                Customer.status == "ativo",
                Customer.excluido_em.is_(None),
            )
            cust_result = await session.execute(cust_stmt)
            recipients = cust_result.all()

            campaign.total_destinatarios = len(recipients)
            sent = 0
            # Cache de adapter por credencial — durante UMA campanha, número
            # fica igual pra cada cliente (atribuição estável).
            adapter_por_cred: dict = {}
            fallback_legacy_pendente = True
            adapter_legacy = None

            for cliente_id, phone, name in recipients:
                try:
                    # Atribuição estável: cliente já fica no número fixo dele.
                    try:
                        cred = await roteador.credencial_para_outbound(cliente_id)
                    except NenhumNumeroAtivoError:
                        # Fallback legacy: providers zapi/uazapi/evolution_api
                        # ainda no modelo "1 por empresa". Carrega 1x.
                        if fallback_legacy_pendente:
                            adapter_legacy = await get_whatsapp_gateway(session, empresa_id)
                            fallback_legacy_pendente = False
                        if adapter_legacy is None:
                            log.warning(
                                "broadcast_sem_numero",
                                cliente_id=str(cliente_id),
                                campaign_id=campaign_id,
                            )
                            continue
                        gateway = adapter_legacy
                    else:
                        gateway = adapter_por_cred.get(cred.id)
                        if gateway is None:
                            gateway = _build_adapter(cred.provedor, cred.config or {})
                            if gateway is None:
                                log.warning(
                                    "broadcast_adapter_falhou",
                                    cliente_id=str(cliente_id),
                                    credencial_id=str(cred.id),
                                )
                                continue
                            adapter_por_cred[cred.id] = gateway

                    text = campaign.mensagem.replace("{nome}", name or "Cliente")
                    log.info(
                        "broadcast_sending",
                        phone=phone,
                        campaign_id=campaign_id,
                        cliente_id=str(cliente_id),
                    )
                    await gateway.send_text(phone, text)
                    sent += 1
                    campaign.enviadas = sent
                    # Stagger (1s entre mensagens)
                    await asyncio.sleep(1.0)
                except Exception:
                    log.warning("broadcast_send_failed", phone=phone, exc_info=True)

            campaign.status = "completed" if sent == len(recipients) else "partial"
            await session.commit()

        return {"status": campaign.status, "sent": sent, "total": len(recipients)}
    finally:
        await engine.dispose()
