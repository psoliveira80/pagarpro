"""ServicoSituacaoContrato — única porta para mudar `Contrato.status` (Story 13.2).

Toda mudança passa por aqui para garantir:
1. Validação contra o grafo `ALLOWED_TRANSITIONS`.
2. Persistência atômica + audit log com `category='financeiro'`.
3. Atualização de colunas auxiliares (`suspenso_em`, `motivo_suspensao`,
   `encerrado_em`, `motivo_encerramento`).
4. Emissão de evento de domínio para os hooks de veículo (bloqueio/desbloqueio).

Após esta story, qualquer código que faça `contrato.status = "..."` direto
está fora do contrato — deve passar pelo `transicionar()`.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.shared.audit_logger import AuditLogger
from app.domain.contracts.state_machine import (
    ALLOWED_TRANSITIONS,
    SituacaoContrato,
    TransicaoInvalidaError,
)
from app.infrastructure.db.models.contrato import Contrato, EventoContrato


class ContratoNaoEncontradoError(Exception):
    pass


class ServicoSituacaoContrato:
    def __init__(self, session: AsyncSession, empresa_id: UUID) -> None:
        self.session = session
        self.empresa_id = empresa_id

    async def transicionar(
        self,
        contrato_id: UUID,
        nova_situacao: SituacaoContrato | str,
        motivo: str | None = None,
        ator_id: UUID | None = None,
    ) -> Contrato:
        """Transiciona o contrato para `nova_situacao`.

        Levanta:
        - `ContratoNaoEncontradoError` se o contrato não pertence ao tenant.
        - `TransicaoInvalidaError` se a transição não é permitida pelo grafo.
        """
        nova = (
            nova_situacao
            if isinstance(nova_situacao, SituacaoContrato)
            else SituacaoContrato(nova_situacao)
        )

        result = await self.session.execute(
            select(Contrato).where(
                Contrato.id == contrato_id,
                Contrato.empresa_id == self.empresa_id,
            )
        )
        contrato = result.scalar_one_or_none()
        if contrato is None:
            raise ContratoNaoEncontradoError(
                f"Contrato {contrato_id} não encontrado para empresa {self.empresa_id}"
            )

        origem = contrato.status
        try:
            origem_enum = SituacaoContrato(origem)
        except ValueError:
            # Contrato com status legado fora do enum — força para rascunho-like:
            # se for "encerrado" antigo, tratamos como ENCERRADO_SEM_PENDENCIA (migração 0023).
            raise TransicaoInvalidaError(origem, nova.value)

        if nova not in ALLOWED_TRANSITIONS.get(origem_enum, frozenset()):
            raise TransicaoInvalidaError(origem, nova.value)

        # Mutação atômica
        contrato.status = nova.value
        now = datetime.now(timezone.utc)
        if nova == SituacaoContrato.SUSPENSO:
            contrato.suspenso_em = now
            contrato.motivo_suspensao = motivo
        elif nova == SituacaoContrato.VIGENTE and origem_enum == SituacaoContrato.SUSPENSO:
            # Reativação — limpa suspenso_em
            contrato.suspenso_em = None
            contrato.motivo_suspensao = None
        elif nova in {
            SituacaoContrato.ENCERRADO_SEM_PENDENCIA,
            SituacaoContrato.ENCERRADO_COM_PENDENCIA,
            SituacaoContrato.ENCERRADO_COMPRA,
            SituacaoContrato.RESCINDIDO,
            SituacaoContrato.CANCELADO,
        }:
            contrato.encerrado_em = date.today()
            if motivo:
                contrato.motivo_encerramento = motivo

        # Evento de domínio persistido (consumido por hooks de veículo etc.)
        tipo_evento = self._tipo_evento(origem_enum, nova)
        self.session.add(
            EventoContrato(
                empresa_id=self.empresa_id,
                contrato_id=contrato.id,
                tipo=tipo_evento,
                payload={
                    "situacao_anterior": origem,
                    "situacao_nova": nova.value,
                    "motivo": motivo,
                    "transicao_em": now.isoformat(),
                },
                criado_por_id=ator_id,
            )
        )

        # Audit log (category='financeiro' para auditoria de motor + ações)
        audit = AuditLogger(self.session)
        await audit.record(
            action="contrato.situacao_transicionada",
            user_id=str(ator_id) if ator_id else None,
            entity="contratos",
            entity_id=str(contrato.id),
            payload_before={"status": origem},
            payload_after={"status": nova.value, "motivo": motivo},
            module="contrato",
            category="financeiro",
        )

        await self.session.flush()
        return contrato

    @staticmethod
    def _tipo_evento(origem: SituacaoContrato, destino: SituacaoContrato) -> str:
        """Mapeia transição para nome de evento (consumido pelos hooks)."""
        if destino == SituacaoContrato.SUSPENSO:
            return "contrato_suspenso"
        if origem == SituacaoContrato.SUSPENSO and destino == SituacaoContrato.VIGENTE:
            return "contrato_reativado"
        if destino == SituacaoContrato.VIGENTE:
            return "contrato_ativado"
        if destino == SituacaoContrato.ENCERRADO_COMPRA:
            return "contrato_encerrado_compra"
        if destino in {
            SituacaoContrato.ENCERRADO_SEM_PENDENCIA,
            SituacaoContrato.ENCERRADO_COM_PENDENCIA,
        }:
            return "contrato_encerrado"
        if destino == SituacaoContrato.RESCINDIDO:
            return "contrato_rescindido"
        if destino == SituacaoContrato.CANCELADO:
            return "contrato_cancelado"
        return f"contrato_transicionado_{destino.value}"
