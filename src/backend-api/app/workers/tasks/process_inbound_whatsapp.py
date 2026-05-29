"""Celery task: process inbound WhatsApp messages."""

from __future__ import annotations

import asyncio

import structlog

from app.workers import celery_app

log = structlog.get_logger()


@celery_app.task(
    name="app.workers.tasks.process_inbound_whatsapp.process_inbound_whatsapp",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    queue="whatsapp_inbound",
)
def process_inbound_whatsapp(self, event_id: str, provider: str) -> dict:
    """Process an inbound WhatsApp message.

    Steps:
    1. Load raw event from webhook_events_raw
    2. Parse payload via provider adapter
    3. Find or create conversation by phone number
    4. Persist message
    5. Enqueue agent turn (if agent is active on conversation)
    """
    return asyncio.run(_process(event_id, provider))


async def _process(event_id: str, provider: str) -> dict:
    from uuid import UUID

    from sqlalchemy import select

    from app.core.agent.conversation_store import ConversationStore
    from app.infrastructure.adapters.whatsapp.whatsapp_factory import (
        get_evolution_go_por_instance_id,
        get_whatsapp_gateway,
    )
    from app.infrastructure.db.models.customer import Customer
    from app.infrastructure.db.models.payable import WebhookEventRaw
    from app.infrastructure.db.session import get_sessionmaker

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        # Load raw event
        stmt = select(WebhookEventRaw).where(WebhookEventRaw.id == UUID(event_id))
        result = await session.execute(stmt)
        event = result.scalar_one_or_none()

        if event is None:
            log.error("webhook_event_not_found", event_id=event_id)
            return {"status": "error", "reason": "event_not_found"}

        payload = event.payload or {}
        headers = payload.pop("headers", {})

        # Story 13.21 — para Evolution Go, identifica a credencial específica
        # pelo `instanceId` no payload. Isso traz contexto multi-tenant +
        # numero_origem_id pra timeline unificada.
        numero_origem_id = None
        if provider == "evolution_go":
            instance_id = payload.get("instanceId") or payload.get("instance_id")
            if not instance_id:
                log.warning(
                    "evolution_go_webhook_sem_instance_id",
                    event_id=event_id,
                )
                event.processed = True
                await session.commit()
                return {"status": "skipped", "reason": "missing_instance_id"}

            adapter, cred = await get_evolution_go_por_instance_id(session, instance_id)
            if adapter is None or cred is None:
                log.error(
                    "evolution_go_instance_nao_cadastrada",
                    instance_id=instance_id,
                    event_id=event_id,
                )
                event.processed = True
                await session.commit()
                return {"status": "error", "reason": "instance_not_registered"}

            # Tenant context vem da credencial
            if event.empresa_id is None:
                event.empresa_id = cred.empresa_id
            numero_origem_id = cred.id
        else:
            # Fallback: providers legados (zapi/uazapi/evolution_api).
            # `get_whatsapp_gateway` busca o primeiro ativo na tabela.
            adapter = await get_whatsapp_gateway(session)

        if adapter is None:
            log.error("no_whatsapp_adapter", provider=provider)
            event.processed = True
            await session.commit()
            return {"status": "error", "reason": "no_adapter"}

        try:
            parsed = await adapter.parse_webhook(headers, payload)
        except ValueError as exc:
            log.warning("webhook_parse_failed", error=str(exc))
            event.processed = True
            await session.commit()
            return {"status": "error", "reason": "parse_failed"}

        if parsed is None:
            event.processed = True
            await session.commit()
            return {"status": "skipped", "reason": "irrelevant_event"}

        from app.domain.ports.whatsapp_gateway import ReceivedMessage, MessageStatusUpdate

        if isinstance(parsed, MessageStatusUpdate):
            event.processed = True
            await session.commit()
            return {"status": "status_update", "external_id": parsed.external_id}

        # It's a ReceivedMessage
        msg: ReceivedMessage = parsed

        # WhatsApp messages without a sender phone cannot be attributed to a
        # conversation. Skip and mark processed so retries don't pile up.
        if not msg.sender_phone:
            log.warning("inbound_whatsapp_missing_phone", event_id=event_id)
            event.processed = True
            await session.commit()
            return {"status": "skipped", "reason": "missing_sender_phone"}

        # Find customer by phone (only within the same tenant as the webhook).
        # If event.empresa_id is NULL (system-level webhook), there is no tenant
        # context — skip persisting since Conversa requires empresa_id NOT NULL.
        if event.empresa_id is None:
            log.warning("inbound_whatsapp_no_tenant", event_id=event_id)
            event.processed = True
            await session.commit()
            return {"status": "skipped", "reason": "no_tenant_context"}

        empresa_id = event.empresa_id

        # Match exato pelo número normalizado para evitar falsos positivos
        # (dois clientes com sufixos coincidentes). Cobre as variações comuns:
        # +5511987654321, 5511987654321, 11987654321, 987654321.
        customer_id = None
        digits_only = "".join(c for c in msg.sender_phone if c.isdigit())
        candidates = {
            digits_only,
            f"+{digits_only}",
            digits_only[-11:],
            digits_only[-10:],
            digits_only[-9:],
        }
        cust_stmt = (
            select(Customer)
            .where(
                Customer.empresa_id == empresa_id,
                Customer.phone.in_(candidates),
            )
            .limit(2)
        )
        cust_result = await session.execute(cust_stmt)
        matches = cust_result.scalars().all()
        if len(matches) == 1:
            customer_id = matches[0].id
        elif len(matches) > 1:
            log.warning(
                "inbound_whatsapp_ambiguous_customer",
                empresa_id=str(empresa_id),
                phone=msg.sender_phone,
                match_count=len(matches),
            )
            # Conversa fica sem customer_id; operador decide manualmente.

        # Get or create conversation
        store = ConversationStore(session, empresa_id)
        conv = await store.get_or_create_conversation(
            channel="whatsapp",
            phone_e164=msg.sender_phone,
            customer_id=customer_id,
        )

        # Persist message
        content = msg.text
        if msg.is_audio:
            content = "[audio message - pending transcription]"

        await store.append_message(
            conv.id,
            role="user",
            content_text=content,
            media_url=msg.media_url,
            media_mime=msg.media_mime,
            external_id=msg.external_id,
            sent_by="customer",
            numero_origem_id=numero_origem_id,
        )

        # Story 13.21 — atribui o número ao cliente se for o primeiro contato.
        # Idempotente: ServicoRoteamentoNumeros respeita atribuição estável.
        if numero_origem_id is not None and customer_id is not None:
            try:
                from app.application.services.servico_roteamento_numeros import (
                    ServicoRoteamentoNumeros,
                )
                # Carrega cliente atualizado pra checar se já tem número
                from app.infrastructure.db.models.cadastro import Cliente
                cliente = (await session.execute(
                    select(Cliente).where(Cliente.id == customer_id)
                )).scalar_one_or_none()
                if cliente is not None and cliente.numero_origem_id is None:
                    cliente.numero_origem_id = numero_origem_id
                    log.info(
                        "cliente_recebeu_numero_origem",
                        cliente_id=str(customer_id),
                        numero_origem_id=str(numero_origem_id),
                    )
            except Exception:
                log.warning("atribuir_numero_origem_falhou", exc_info=True)

        event.processed = True
        await session.commit()

        # Enqueue agent turn if agent is active
        if conv.agent_active:
            try:
                from app.workers import celery_app as celery

                celery.send_task(
                    "app.workers.tasks.run_agent_turn.run_agent_turn",
                    args=[str(conv.id), content or ""],
                    queue="agent",
                )
            except Exception:
                log.warning("agent_turn_enqueue_failed", exc_info=True)

        return {"status": "processed", "conversation_id": str(conv.id)}
