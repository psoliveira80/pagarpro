# Backward-compat shim — story 12.3 will update all direct imports.
from app.infrastructure.db.models.conta_bancaria import (
    ContaBancaria as BankAccount,
    TransacaoBancaria as BankTransaction,
    SessaoConciliacao as ReconciliationSession,
)

__all__ = ["BankAccount", "BankTransaction", "ReconciliationSession"]
