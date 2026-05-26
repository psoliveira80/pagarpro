from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import select

from app.core.assets import registry
from app.core.events.domain_events import (
    ContractCreatedEvent,
    ContractTerminatedEvent,
    DomainEvent,
    InstallmentOverdueEvent,
    InstallmentPaidEvent,
    PaymentPartiallyReceivedEvent,
    ReconciliationCompletedEvent,
)
from app.infrastructure.db.models.active_module import ActiveModule
from app.infrastructure.db.models.event_log import EventLog
from app.infrastructure.db.models.module_hooks_config import ModuleHooksConfig
from app.infrastructure.db.session import get_sessionmaker
from app.workers import celery_app

log = structlog.get_logger()

_EVENT_HANDLER_MAP = {
    ContractCreatedEvent: "on_contract_created",
    ContractTerminatedEvent: "on_contract_terminated",
    InstallmentOverdueEvent: "on_installment_overdue",
    InstallmentPaidEvent: "on_installment_paid",
    PaymentPartiallyReceivedEvent: "on_partial_payment",
    ReconciliationCompletedEvent: "on_reconciliation_completed",
}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def handle_domain_event(self, event_dict: dict) -> dict:  # type: ignore[no-untyped-def]
    import asyncio

    return asyncio.get_event_loop().run_until_complete(_process_event(self, event_dict))


async def _process_event(task: object, event_dict: dict) -> dict:
    event = DomainEvent.from_dict(event_dict.copy())
    event_type_name = type(event).__name__

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        # Idempotency check
        existing = await session.execute(
            select(EventLog).where(EventLog.event_id == event.event_id)
        )
        if existing.scalar_one_or_none():
            return {"status": "duplicate", "event_id": str(event.event_id)}

        # Log event
        event_log = EventLog(
            event_id=event.event_id,
            event_type=event_type_name,
            asset_type=event.asset_type,
            payload=event_dict,
            processing_status="processing",
        )
        session.add(event_log)
        await session.flush()

        try:
            modules = registry.get_modules_for_asset_type(event.asset_type)
            for module in modules:
                if not module.handles_event(type(event)):
                    continue

                # Check active_modules
                active_row = await session.execute(
                    select(ActiveModule).where(
                        ActiveModule.module_id == module.asset_type,
                        ActiveModule.ativo.is_(True),
                    )
                )
                if not active_row.scalar_one_or_none():
                    continue

                # Check module_hooks_config
                hook_row = await session.execute(
                    select(ModuleHooksConfig).where(
                        ModuleHooksConfig.module_id == module.asset_type,
                        ModuleHooksConfig.event_type == event_type_name,
                        ModuleHooksConfig.ativo.is_(True),
                    )
                )
                hook_config = hook_row.scalar_one_or_none()
                policy = hook_config.policy if hook_config else {}

                # Dispatch to handler
                handler_name = _EVENT_HANDLER_MAP.get(type(event))
                if handler_name:
                    handler = getattr(module, handler_name, None)
                    if handler:
                        if handler_name == "on_installment_overdue":
                            handler(event, policy or {})
                        else:
                            handler(event)

            event_log.processing_status = "completed"
            event_log.processed_at = datetime.now(timezone.utc)

        except Exception as exc:
            event_log.processing_status = "failed"
            event_log.processed_at = datetime.now(timezone.utc)
            event_log.error = str(exc)
            log.error("event_processing_failed", event_id=str(event.event_id), error=str(exc))

        await session.commit()

    return {"status": event_log.processing_status, "event_id": str(event.event_id)}
