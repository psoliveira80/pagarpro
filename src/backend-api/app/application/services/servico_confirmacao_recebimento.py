"""ServicoConfirmacaoRecebimento — Story 13.25 AC 4 (refactor hexagonal).

Cliente clicou no botão "Confirmo recebimento" do lembrete de vencimento.
Encapsula:

- Validação multi-tenant do `titulo_id` (id vem do payload do botão; não
  pode confiar sozinho — pode apontar pra título de outra empresa).
- Atualização de `conversa.confirmacao_recebimento_em` +
  `confirmacao_recebimento_titulo_id`.
- Audit log com category=`comunicacao`.

Worker `alertar_vencimentos_proximos` lê esses campos antes de enviar
lembrete (AC 5) — se cliente confirmou nas últimas N dias, pula o envio.

Antes estava inlined no handler do `process_inbound_whatsapp`. Extrair
permite reuso por endpoint admin (gestor marcar como confirmado em nome
do cliente) ou pela IA atendente (Story 13.26).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.shared.audit_logger import AuditLogger


log = structlog.get_logger()


@dataclass(frozen=True)
class ResultadoConfirmacao:
    registrada: bool
    motivo: str  # ok | titulo_outro_tenant | conversa_nao_encontrada


class ServicoConfirmacaoRecebimento:
    def __init__(self, session: AsyncSession, empresa_id: UUID) -> None:
        self.session = session
        self.empresa_id = empresa_id

    async def registrar(
        self,
        *,
        conversa_id: UUID,
        titulo_id: UUID | None,
        ator: str = "cliente",
        ator_id: UUID | None = None,
    ) -> ResultadoConfirmacao:
        """Marca a conversa como tendo recebido confirmação. `ator='cliente'`
        para clique no botão WhatsApp; `ator='gestor'` para reuso em
        endpoint admin futuro."""
        from app.infrastructure.db.models.cobranca import Conversa
        from app.infrastructure.db.models.financeiro import TituloReceber

        conversa = (await self.session.execute(
            select(Conversa).where(
                Conversa.id == conversa_id,
                Conversa.empresa_id == self.empresa_id,
            )
        )).scalar_one_or_none()
        if conversa is None:
            log.warning(
                "confirmacao_recebimento_conversa_inexistente",
                conversa_id=str(conversa_id),
            )
            return ResultadoConfirmacao(False, "conversa_nao_encontrada")

        titulo_id_validado: UUID | None = None
        if titulo_id is not None:
            existe = (await self.session.execute(
                select(TituloReceber.id).where(
                    TituloReceber.id == titulo_id,
                    TituloReceber.empresa_id == self.empresa_id,
                )
            )).scalar_one_or_none()
            if existe is None:
                log.warning(
                    "confirmacao_recebimento_titulo_de_outro_tenant",
                    titulo_id=str(titulo_id),
                    empresa_id=str(self.empresa_id),
                )
                return ResultadoConfirmacao(False, "titulo_outro_tenant")
            titulo_id_validado = titulo_id

        agora = datetime.now(timezone.utc)
        conversa.confirmacao_recebimento_em = agora
        if titulo_id_validado is not None:
            conversa.confirmacao_recebimento_titulo_id = titulo_id_validado

        audit = AuditLogger(self.session)
        await audit.record(
            action="conversa.confirmacao_recebimento_registrada",
            user_id=str(ator_id) if ator_id else None,
            entity="conversas",
            entity_id=str(conversa_id),
            payload_after={
                "titulo_id": str(titulo_id_validado) if titulo_id_validado else None,
                "ator": ator,
                "registrada_em": agora.isoformat(),
            },
            module="comunicacao",
            category="comunicacao",
        )
        await self.session.flush()
        return ResultadoConfirmacao(True, "ok")
