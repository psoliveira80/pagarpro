# Backward-compat shim — story 12.3 will update all direct imports.
from app.infrastructure.db.models.acesso import RefreshToken

__all__ = ["RefreshToken"]
