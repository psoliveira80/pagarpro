# Backward-compat shim — story 12.3 will update all direct imports.
from app.infrastructure.db.models.cobranca import (
    ConfiguracaoAgente as AgentConfig,
    ExecucaoAgente as AgentRun,
    ScoreCliente as CustomerScore,
    CampanhaDisparo as BroadcastCampaign,
)

__all__ = ["AgentConfig", "AgentRun", "CustomerScore", "BroadcastCampaign"]
