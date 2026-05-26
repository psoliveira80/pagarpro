import hmac
import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.audit_log import AuditLog
from app.infrastructure.settings import get_settings


class AuditLogger:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record(
        self,
        *,
        action: str,
        user_id: str | None = None,
        entity: str | None = None,
        entity_id: str | None = None,
        payload_before: dict | None = None,
        payload_after: dict | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
        correlation_id: str | None = None,
        module: str = "core",
        category: str = "info",
        severity: str = "info",
    ) -> AuditLog:
        # Use explicit timestamp so HMAC can be verified later
        now = datetime.now(timezone.utc)
        signature = self._sign(
            action=action,
            user_id=user_id,
            entity=entity,
            entity_id=entity_id,
            payload_before=payload_before,
            payload_after=payload_after,
            module=module,
            category=category,
            severity=severity,
            ts=now,
        )

        entry = AuditLog(
            user_id=user_id,
            action=action,
            entidade=entity,
            entidade_id=entity_id,
            payload_before=payload_before,
            payload_after=payload_after,
            ip=ip,
            user_agent=user_agent,
            correlation_id=correlation_id,
            module=module,
            category=category,
            severity=severity,
            hmac_assinatura=signature,
            criado_em=now,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    @staticmethod
    def _sign(
        *,
        action: str,
        user_id: str | None,
        entity: str | None,
        entity_id: str | None,
        payload_before: dict | None,
        payload_after: dict | None,
        module: str,
        category: str,
        severity: str,
        ts: datetime,
    ) -> bytes:
        settings = get_settings()
        msg = "|".join([
            action,
            user_id or "",
            entity or "",
            entity_id or "",
            json.dumps(payload_before, sort_keys=True, default=str) if payload_before else "",
            json.dumps(payload_after, sort_keys=True, default=str) if payload_after else "",
            module,
            category,
            severity,
            ts.isoformat(),
        ])
        return hmac.new(
            settings.SECRET_KEY.encode(),
            msg.encode(),
            hashlib.sha256,
        ).digest()
