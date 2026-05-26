# Backward-compat shim — story 12.3 will update all direct imports.
from app.infrastructure.db.models.financeiro import (
    TituloPagar as Payable,
    DespesaRecorrente as RecurringPayableTemplate,
)
from app.infrastructure.db.models.cadastro import (
    CategoriaDespesa as ExpenseCategory,
    Fornecedor as Supplier,
)
from app.infrastructure.db.models.config import CredencialIntegracao as IntegrationCredential
from app.infrastructure.db.models.notificacoes import WebhookBruto as WebhookEventRaw

__all__ = [
    "Payable",
    "RecurringPayableTemplate",
    "ExpenseCategory",
    "Supplier",
    "IntegrationCredential",
    "WebhookEventRaw",
]
