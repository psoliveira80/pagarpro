# New canonical exports (post migration 0015 — Portuguese names, schema-qualified)
from app.infrastructure.db.models.comercial import Empresa
from app.infrastructure.db.models.acesso import (
    Usuario,
    Perfil,
    Permissao,
    PerfilPermissao,
    UsuarioPerfil,
    RefreshToken,
)
from app.infrastructure.db.models.cadastro import (
    Cliente,
    AnexoCliente,
    Fornecedor,
    CategoriaDespesa,
)
from app.infrastructure.db.models.veiculos import (
    Veiculo,
    AquisicaoVeiculo,
    DispositivoRastreamento,
)
from app.infrastructure.db.models.contrato import (
    Contrato,
    EventoContrato,
    LoteGeracao,
)
from app.infrastructure.db.models.financeiro import (
    TituloReceber,
    MovimentoTituloReceber,
    DespesaRecorrente,
    TituloPagar,
)
from app.infrastructure.db.models.conta_bancaria import (
    ContaBancaria,
    TransacaoBancaria,
    SessaoConciliacao,
)
from app.infrastructure.db.models.cobranca import (
    Conversa,
    Mensagem,
    ConfiguracaoAgente,
    ExecucaoAgente,
    ScoreCliente,
    CampanhaDisparo,
)
from app.infrastructure.db.models.config import (
    ConfiguracaoSistema,
    PoliticaEventoModulo,
    CredencialIntegracao,
)
from app.infrastructure.db.models.relatorios import RelatorioSalvo
from app.infrastructure.db.models.notificacoes import WebhookBruto
from app.infrastructure.db.models.logs import LogAuditoria, LogEvento

# Backward-compat aliases — story 12.3 will replace all usages with new names
User = Usuario
Role = Perfil
Permission = Permissao
UserRole = UsuarioPerfil
RolePermission = PerfilPermissao
AuditLog = LogAuditoria
Customer = Cliente
CustomerAttachment = AnexoCliente
Contract = Contrato
ContractEvent = EventoContrato
InstallmentGeneration = LoteGeracao
Installment = TituloReceber
InstallmentAdjustment = MovimentoTituloReceber
Payable = TituloPagar
RecurringPayableTemplate = DespesaRecorrente
ExpenseCategory = CategoriaDespesa
Supplier = Fornecedor
Vehicle = Veiculo
VehicleAcquisition = AquisicaoVeiculo
TrackerDevice = DispositivoRastreamento
BankAccount = ContaBancaria
BankTransaction = TransacaoBancaria
ReconciliationSession = SessaoConciliacao
Conversation = Conversa
ConversationMessage = Mensagem
AgentConfig = ConfiguracaoAgente
AgentRun = ExecucaoAgente
CustomerScore = ScoreCliente
BroadcastCampaign = CampanhaDisparo
WebhookEventRaw = WebhookBruto
EventLog = LogEvento

__all__ = [
    # New names
    "Empresa",
    "Usuario", "Perfil", "Permissao", "PerfilPermissao", "UsuarioPerfil", "RefreshToken",
    "Cliente", "AnexoCliente", "Fornecedor", "CategoriaDespesa",
    "Veiculo", "AquisicaoVeiculo", "DispositivoRastreamento",
    "Contrato", "EventoContrato", "LoteGeracao",
    "TituloReceber", "MovimentoTituloReceber", "DespesaRecorrente", "TituloPagar",
    "ContaBancaria", "TransacaoBancaria", "SessaoConciliacao",
    "Conversa", "Mensagem", "ConfiguracaoAgente", "ExecucaoAgente",
    "ScoreCliente", "CampanhaDisparo",
    "ConfiguracaoSistema", "PoliticaEventoModulo", "CredencialIntegracao",
    "RelatorioSalvo",
    "WebhookBruto",
    "LogAuditoria", "LogEvento",
    # Backward-compat aliases
    "User", "Role", "Permission", "UserRole", "RolePermission",
    "AuditLog", "Customer", "CustomerAttachment",
    "Contract", "ContractEvent", "InstallmentGeneration",
    "Installment", "InstallmentAdjustment",
    "Payable", "RecurringPayableTemplate", "ExpenseCategory", "Supplier",
    "Vehicle", "VehicleAcquisition", "TrackerDevice",
    "BankAccount", "BankTransaction", "ReconciliationSession",
    "Conversation", "ConversationMessage",
    "AgentConfig", "AgentRun", "CustomerScore", "BroadcastCampaign",
    "WebhookEventRaw", "EventLog",
]
