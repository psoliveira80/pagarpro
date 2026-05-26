"""Startup registration of all agent tools."""

from __future__ import annotations

from app.core.agent.tool_interface import ToolDefinition
from app.core.agent.tool_registry import get_tool_registry


def register_all_tools() -> None:
    """Register all built-in agent tools at application startup."""
    registry = get_tool_registry()

    # Import tool functions
    from app.core.agent.tools.billing_tools import (
        generate_pix_qr,
        get_collection_summary,
        get_customer_payment_history,
        get_overdue_installments,
        get_revenue_by_period,
        list_defaulters,
        register_writeoff,
    )
    from app.core.agent.tools.fleet_tools import get_contract_status, get_vehicle_position

    # Billing tools
    registry.register(
        ToolDefinition(
            name="get_overdue_installments",
            description="Busca parcelas vencidas de um cliente ou de toda a carteira. Retorna valor atualizado com juros e multa.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "days_min": {
                        "type": "integer",
                        "description": "Dias minimos de atraso",
                        "default": 1,
                    },
                    "days_max": {
                        "type": "integer",
                        "description": "Dias maximos de atraso",
                        "default": 365,
                    },
                    "customer_id": {
                        "type": "string",
                        "description": "UUID do cliente (opcional)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Limite de resultados",
                        "default": 50,
                    },
                },
            },
            required_permissions=["agent.tools.billing"],
            handler=get_overdue_installments,
        )
    )

    registry.register(
        ToolDefinition(
            name="get_collection_summary",
            description="Retorna resumo de cobranca do periodo: total a receber, recebido, inadimplente, taxa de cobranca.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Data inicio (YYYY-MM-DD)"},
                    "end_date": {"type": "string", "description": "Data fim (YYYY-MM-DD)"},
                },
            },
            required_permissions=["agent.tools.billing"],
            handler=get_collection_summary,
        )
    )

    registry.register(
        ToolDefinition(
            name="get_revenue_by_period",
            description="Retorna receita agrupada por periodo (dia, semana ou mes).",
            parameters_schema={
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Data inicio (YYYY-MM-DD)"},
                    "end_date": {"type": "string", "description": "Data fim (YYYY-MM-DD)"},
                    "group_by": {
                        "type": "string",
                        "enum": ["day", "week", "month"],
                        "default": "month",
                    },
                },
            },
            required_permissions=["agent.tools.billing"],
            handler=get_revenue_by_period,
        )
    )

    registry.register(
        ToolDefinition(
            name="get_customer_payment_history",
            description="Retorna historico de pagamentos de um cliente especifico.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "UUID do cliente",
                    },
                    "months_back": {
                        "type": "integer",
                        "description": "Meses para tras",
                        "default": 12,
                    },
                },
                "required": ["customer_id"],
            },
            required_permissions=["agent.tools.billing"],
            handler=get_customer_payment_history,
        )
    )

    registry.register(
        ToolDefinition(
            name="list_defaulters",
            description="Lista clientes inadimplentes ordenados por divida total.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "min_days_overdue": {
                        "type": "integer",
                        "description": "Dias minimos de atraso",
                        "default": 1,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Limite de resultados",
                        "default": 50,
                    },
                },
            },
            required_permissions=["agent.tools.billing"],
            handler=list_defaulters,
        )
    )

    registry.register(
        ToolDefinition(
            name="generate_pix_qr",
            description="Gera QR code Pix para pagamento de uma parcela.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "installment_id": {
                        "type": "string",
                        "description": "UUID da parcela",
                    },
                },
                "required": ["installment_id"],
            },
            required_permissions=["agent.tools.billing"],
            handler=generate_pix_qr,
        )
    )

    registry.register(
        ToolDefinition(
            name="register_writeoff",
            description="Registra baixa primaria de uma parcela (pagamento via comprovante).",
            parameters_schema={
                "type": "object",
                "properties": {
                    "installment_id": {
                        "type": "string",
                        "description": "UUID da parcela",
                    },
                    "amount": {
                        "type": "number",
                        "description": "Valor pago (se omitido, usa valor total)",
                    },
                    "payment_method": {
                        "type": "string",
                        "description": "Metodo de pagamento",
                        "default": "pix",
                    },
                },
                "required": ["installment_id"],
            },
            required_permissions=["agent.tools.billing"],
            handler=register_writeoff,
            requires_confirmation=True,
        )
    )

    # Fleet tools
    registry.register(
        ToolDefinition(
            name="get_vehicle_position",
            description="Retorna posicao GPS mais recente de um veiculo.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "vehicle_id": {
                        "type": "string",
                        "description": "UUID do veiculo",
                    },
                },
                "required": ["vehicle_id"],
            },
            required_permissions=["agent.tools.fleet"],
            handler=get_vehicle_position,
        )
    )

    registry.register(
        ToolDefinition(
            name="get_contract_status",
            description="Retorna detalhes de um contrato com resumo de parcelas.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "contract_id": {
                        "type": "string",
                        "description": "UUID do contrato",
                    },
                },
                "required": ["contract_id"],
            },
            required_permissions=["agent.tools.fleet"],
            handler=get_contract_status,
        )
    )
