"""ServicoValidacaoAutomatica — Story 13.23 AC 3 (refactor hexagonal).

Encapsula a regra de "este comprovante pode ser auto-homologado?" em
um serviço de aplicação puro. Antes estava inlined dentro da task Celery
`analisar_e_validar_comprovante_whatsapp`, violando hexagonal e impedindo
reuso pela Story 13.26 (IA atendente).

Regra de decisão (todas precisam ser verdadeiras):
1. Cliente NÃO está em blacklist.
2. `comprovante.score_confianca >= score_minimo_auto_homologar` (config).
3. Comprovante tem `titulo_id` matched + `valor_detectado`.
4. O título matched ainda é homologável: status em (em_aberto, em_atraso),
   contrato status em (vigente, suspenso), sem soft-delete.

Quando rejeita, o serviço explica o motivo (string curta — vai pra audit
e potencialmente pra mensagem do cliente).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.servico_configuracao import ServicoConfiguracao


log = structlog.get_logger()


@dataclass(frozen=True)
class DecisaoValidacao:
    """Resultado puro da avaliação. Caller (task) decide o que fazer."""
    pode_auto: bool
    motivo: str  # explicação humana — vai pra audit/template
    blacklist: bool = False  # quando True, mensagem ao cliente esconde o motivo real


class ServicoValidacaoAutomatica:
    def __init__(self, session: AsyncSession, empresa_id: UUID) -> None:
        self.session = session
        self.empresa_id = empresa_id

    async def avaliar(self, comprovante_id: UUID) -> DecisaoValidacao:
        """Avalia se o comprovante pode ser auto-homologado.

        Idempotente — pode ser chamado quantas vezes for, mesma decisão.
        """
        from app.infrastructure.db.models.cadastro import Cliente
        from app.infrastructure.db.models.comprovante_pagamento import (
            ComprovantePagamento,
        )
        from app.infrastructure.db.models.contrato import Contrato
        from app.infrastructure.db.models.financeiro import TituloReceber

        comprovante = (await self.session.execute(
            select(ComprovantePagamento).where(
                ComprovantePagamento.id == comprovante_id,
                ComprovantePagamento.empresa_id == self.empresa_id,
            )
        )).scalar_one_or_none()
        if comprovante is None:
            return DecisaoValidacao(
                pode_auto=False, motivo="comprovante não encontrado"
            )
        if comprovante.cliente_id is None:
            return DecisaoValidacao(
                pode_auto=False, motivo="comprovante sem cliente vinculado"
            )

        cliente = (await self.session.execute(
            select(Cliente).where(
                Cliente.id == comprovante.cliente_id,
                Cliente.empresa_id == self.empresa_id,
            )
        )).scalar_one_or_none()
        if cliente is None:
            return DecisaoValidacao(
                pode_auto=False, motivo="cliente não encontrado"
            )

        if cliente.na_blacklist_comprovantes:
            return DecisaoValidacao(
                pode_auto=False, motivo="cliente em blacklist", blacklist=True
            )

        config = ServicoConfiguracao(self.session, self.empresa_id, redis=None)
        score_min = await config.obter_decimal(
            "score_minimo_auto_homologar", "comprovantes",
            padrao=Decimal("0.80"),
        )

        if comprovante.score_confianca is None:
            return DecisaoValidacao(
                pode_auto=False, motivo="score não calculado"
            )
        if Decimal(comprovante.score_confianca) < score_min:
            return DecisaoValidacao(
                pode_auto=False,
                motivo=(
                    f"score baixo ({Decimal(comprovante.score_confianca):.2f} "
                    f"< {score_min})"
                ),
            )
        if comprovante.titulo_id is None:
            return DecisaoValidacao(
                pode_auto=False, motivo="sem título compatível"
            )
        if comprovante.valor_detectado is None:
            return DecisaoValidacao(
                pode_auto=False, motivo="valor não detectado"
            )

        # Título válido + contrato ativo?
        row = (await self.session.execute(
            select(TituloReceber.status, Contrato.status.label("contrato_status"))
            .join(Contrato, Contrato.id == TituloReceber.contrato_id)
            .where(
                TituloReceber.id == comprovante.titulo_id,
                TituloReceber.empresa_id == self.empresa_id,
            )
        )).first()
        if row is None:
            return DecisaoValidacao(
                pode_auto=False, motivo="título não encontrado"
            )
        if row[0] not in ("em_aberto", "em_atraso"):
            return DecisaoValidacao(
                pode_auto=False,
                motivo=f"título em status '{row[0]}' não aceita pagamento",
            )
        if row[1] not in ("vigente", "suspenso"):
            return DecisaoValidacao(
                pode_auto=False,
                motivo=f"contrato em status '{row[1]}' não aceita pagamento",
            )

        return DecisaoValidacao(pode_auto=True, motivo="ok")
