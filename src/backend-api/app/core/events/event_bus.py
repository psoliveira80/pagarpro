from __future__ import annotations

import structlog
from celery import Celery

from app.core.events.domain_events import DomainEvent

log = structlog.get_logger()


class CeleryEventBus:
    def __init__(self, celery_app: Celery):
        self.celery = celery_app

    def publish(self, event: DomainEvent) -> str:
        """Enqueue event for async processing. Returns task_id."""
        event_dict = event.to_dict()
        result = self.celery.send_task(
            "app.workers.tasks.handle_domain_event.handle_domain_event",
            args=[event_dict],
            queue="events",
        )
        log.info(
            "event_published",
            event_type=type(event).__name__,
            event_id=str(event.event_id),
            task_id=result.id,
        )
        return result.id
