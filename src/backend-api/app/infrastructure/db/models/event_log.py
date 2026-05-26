# Backward-compat shim — story 12.3 will update all direct imports.
from app.infrastructure.db.models.logs import LogEvento as EventLog

__all__ = ["EventLog"]
