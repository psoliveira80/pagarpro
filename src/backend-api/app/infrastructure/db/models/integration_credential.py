# Backward-compat shim — story 12.3 will update all direct imports.
from app.infrastructure.db.models.config import CredencialIntegracao as IntegrationCredential

__all__ = ["IntegrationCredential"]
