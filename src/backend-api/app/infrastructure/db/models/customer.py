# Backward-compat shim — story 12.3 will update all direct imports.
from app.infrastructure.db.models.cadastro import (
    Cliente as Customer,
    AnexoCliente as CustomerAttachment,
)

__all__ = ["Customer", "CustomerAttachment"]
