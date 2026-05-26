# Backward-compat shim — story 12.3 will update all direct imports.
from app.infrastructure.db.models.contrato import (
    Contrato as Contract,
    EventoContrato as ContractEvent,
    LoteGeracao as InstallmentGeneration,
)
from app.infrastructure.db.models.financeiro import (
    TituloReceber as Installment,
    MovimentoTituloReceber as InstallmentAdjustment,
)

__all__ = [
    "Contract",
    "ContractEvent",
    "InstallmentGeneration",
    "Installment",
    "InstallmentAdjustment",
]
