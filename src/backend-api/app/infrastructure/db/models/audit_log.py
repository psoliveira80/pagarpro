# Backward-compat shim — story 12.3 will update all direct imports.
from app.infrastructure.db.models.logs import LogAuditoria as AuditLog

__all__ = ["AuditLog"]
