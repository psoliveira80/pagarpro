# Backward-compat shim — story 12.3 will update all direct imports.
from app.infrastructure.db.models.cobranca import (
    Conversa as Conversation,
    Mensagem as ConversationMessage,
)

__all__ = ["Conversation", "ConversationMessage"]
