"""ServicoOpcaoCompra — handler de pagamento de opção de compra (Story 13.3).

Quando um título com `tipo='opcao_compra'` é pago, este serviço:
1. Marca o veículo como `alienado` e preenche `proprietario_id` com o cliente.
2. Transita o contrato para `encerrado_compra` via `ServicoSituacaoContrato`.
3. Grava audit log com `category='transferencia_propriedade'`.

É chamado pelo motor de conciliação (Story 13.9 — `quando_titulo_pago`) ou
pode ser invocado manualmente por uma rota admin.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.servico_situacao_contrato import (
    ServicoSituacaoContrato,
)
from app.application.shared.audit_logger import AuditLogger
from app.domain.contracts.state_machine import SituacaoContrato
from app.domain.finance.tipo_titulo import TipoTitulo
from app.infrastructure.db.models.contrato import Contrato, EventoContrato
from app.infrastructure.db.models.financeiro import TituloReceber
from app.infrastructure.db.models.veiculos import Veiculo


class OpcaoCompraInvalidaError(Exception):
    pass


class ServicoOpcaoCompra:
    def __init__(self, session: AsyncSession, empresa_id: UUID) -> None:
        self.session = session
        self.empresa_id = empresa_id

    async def processar_pagamento(
        self,
        titulo_id: UUID,
        ator_id: UUID | None = None,
    ) -> dict:
        """Processa o pagamento de uma opção de compra.

        Valida que o título é `tipo='opcao_compra'` e está `pago`. Aliena o
        veículo e encerra o contrato com `encerrado_compra`.

        Retorna dict com os IDs afetados (útil para logging/eventos).
        """
        # Carrega título + contrato + veículo no mesmo session
        result = await self.session.execute(
            select(TituloReceber).where(
                TituloReceber.id == titulo_id,
                TituloReceber.empresa_id == self.empresa_id,
            )
        )
        titulo = result.scalar_one_or_none()
        if titulo is None:
            raise OpcaoCompraInvalidaError(
                f"Título {titulo_id} não encontrado para empresa {self.empresa_id}"
            )

        if titulo.tipo != TipoTitulo.OPCAO_COMPRA.value:
            raise OpcaoCompraInvalidaError(
                f"Título {titulo_id} é tipo='{titulo.tipo}', não 'opcao_compra'"
            )

        if titulo.status != "pago":
            raise OpcaoCompraInvalidaError(
                f"Título {titulo_id} status='{titulo.status}' — só processa quando pago"
            )

        # Carrega contrato (com cliente_id) e veículo
        contrato = (await self.session.execute(
            select(Contrato).where(Contrato.id == titulo.contrato_id)
        )).scalar_one_or_none()
        if contrato is None:
            raise OpcaoCompraInvalidaError(
                f"Contrato {titulo.contrato_id} do título {titulo_id} não existe"
            )

        veiculo = (await self.session.execute(
            select(Veiculo).where(Veiculo.id == contrato.veiculo_id)
        )).scalar_one_or_none()
        if veiculo is None:
            raise OpcaoCompraInvalidaError(
                f"Veículo {contrato.veiculo_id} do contrato {contrato.id} não existe"
            )

        # 1) Aliena o veículo
        veiculo.status = "alienado"
        veiculo.proprietario_id = contrato.cliente_id

        # 2) Encerra o contrato
        servico_situacao = ServicoSituacaoContrato(self.session, self.empresa_id)
        await servico_situacao.transicionar(
            contrato.id,
            SituacaoContrato.ENCERRADO_COMPRA,
            motivo="Opção de compra exercida — transferência de propriedade",
            ator_id=ator_id,
        )

        # 3) Evento específico (extra ao gerado pelo servico_situacao)
        self.session.add(
            EventoContrato(
                empresa_id=self.empresa_id,
                contrato_id=contrato.id,
                tipo="opcao_compra_paga",
                payload={
                    "titulo_id": str(titulo.id),
                    "veiculo_id": str(veiculo.id),
                    "cliente_id": str(contrato.cliente_id),
                    "valor_pago": str(titulo.valor_pago) if titulo.valor_pago else None,
                    "data_pagamento": titulo.pago_em.isoformat() if titulo.pago_em else date.today().isoformat(),
                },
                criado_por_id=ator_id,
            )
        )

        # 4) Audit log com categoria específica
        audit = AuditLogger(self.session)
        await audit.record(
            action="veiculo.alienado",
            user_id=str(ator_id) if ator_id else None,
            entity="veiculos",
            entity_id=str(veiculo.id),
            payload_before={"status": "indisponivel", "proprietario_id": None},
            payload_after={
                "status": "alienado",
                "proprietario_id": str(contrato.cliente_id),
                "contrato_id": str(contrato.id),
                "titulo_id": str(titulo.id),
            },
            module="veiculos",
            category="transferencia_propriedade",
        )

        await self.session.flush()
        return {
            "contrato_id": str(contrato.id),
            "veiculo_id": str(veiculo.id),
            "cliente_id": str(contrato.cliente_id),
            "titulo_id": str(titulo.id),
        }
