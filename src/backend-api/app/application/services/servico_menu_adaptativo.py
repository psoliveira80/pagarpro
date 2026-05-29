"""ServicoMenuAdaptativo — calcula o menu visível para o cliente conforme
estado (adimplência, score, blacklist, limites usados, configs do tenant).

Story 13.22.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.servico_configuracao import ServicoConfiguracao
from app.domain.comunicacao.maquina_numero_rigido import (
    ID_MENU_ADIAR,
    ID_MENU_ATENDENTE,
    ID_MENU_COMPROVANTE,
    ID_MENU_DESBLOQUEIO,
    ID_MENU_EXTRATO,
    ID_MENU_PAGAR,
    ID_MENU_PARCIAL,
)
from app.infrastructure.db.models.cadastro import Cliente
from app.infrastructure.db.models.financeiro import TituloReceber


log = structlog.get_logger()


@dataclass(frozen=True)
class OpcaoMenu:
    id: str
    titulo: str  # máximo 20 chars para botão / 24 para list row


@dataclass(frozen=True)
class Menu:
    descricao: str
    opcoes: list[OpcaoMenu]
    # Quando True, o caller deve enviar como list (>3 itens); senão buttons.
    eh_lista: bool


def _periodo_para_dias(periodo: str) -> int:
    """Converte 'semanal'/'quinzenal'/'mensal'/'5d'/'Nd' em dias."""
    p = periodo.strip().lower()
    if p == "semanal":
        return 7
    if p == "quinzenal":
        return 15
    if p == "mensal":
        return 30
    if p.endswith("d"):
        try:
            return max(1, int(p[:-1]))
        except ValueError:
            pass
    return 30  # fallback conservador


class ServicoMenuAdaptativo:
    def __init__(self, session: AsyncSession, empresa_id: UUID) -> None:
        self.session = session
        self.empresa_id = empresa_id

    async def montar_menu(self, cliente_id: UUID) -> Menu:
        """Devolve o menu apropriado para o cliente naquele momento."""
        cliente = await self._carregar_cliente(cliente_id)
        config = ServicoConfiguracao(self.session, self.empresa_id, redis=None)

        # Reset de período (preguiçoso, na hora de montar o menu)
        await self._reset_contador_se_necessario(cliente, config)

        # Status de adimplência
        eh_inadimplente = await self._cliente_tem_titulo_em_atraso(cliente_id)

        # Configurações
        score_min_adiar = await config.obter_decimal(
            "score_minimo_adiar_vencimento", "cobranca", padrao=Decimal("80")
        )
        score_min_desbloq = await config.obter_decimal(
            "score_minimo_desbloqueio_confianca", "cobranca", padrao=Decimal("65")
        )
        score_min_parcial = await config.obter_decimal(
            "score_minimo_pagamento_parcial", "cobranca", padrao=Decimal("50")
        )
        limite_adiar = await config.obter_inteiro(
            "limite_usos_periodo_adiar", "cobranca", padrao=1
        )
        limite_desbloq = await config.obter_inteiro(
            "limite_usos_periodo_desbloqueio_confianca", "cobranca", padrao=1
        )
        ia_ativa = await config.obter_booleano(
            "ia_atendente_ativa", "comunicacao", padrao=False
        )

        score = Decimal(cliente.score or 0)
        bl = cliente.na_blacklist_comprovantes

        opcoes: list[OpcaoMenu] = []

        # Opções base (sempre presentes)
        opcoes.append(OpcaoMenu(id=ID_MENU_EXTRATO, titulo="📋 Meu extrato"))
        opcoes.append(OpcaoMenu(id=ID_MENU_PAGAR, titulo="💰 Gerar QR Code"))
        opcoes.append(OpcaoMenu(id=ID_MENU_COMPROVANTE, titulo="📎 Enviar comprovante"))

        # Opções condicionais — só para inadimplentes não-blacklist com score suficiente
        if eh_inadimplente and not bl:
            if (
                score >= score_min_adiar
                and cliente.adiamentos_usados_no_periodo < limite_adiar
            ):
                opcoes.append(OpcaoMenu(id=ID_MENU_ADIAR, titulo="⏰ Adiar vencimento"))
            if (
                score >= score_min_desbloq
                and cliente.desbloqueios_confianca_usados_no_periodo < limite_desbloq
            ):
                opcoes.append(
                    OpcaoMenu(id=ID_MENU_DESBLOQUEIO, titulo="🔓 Desbloqueio em confiança")
                )
            if score >= score_min_parcial:
                opcoes.append(OpcaoMenu(id=ID_MENU_PARCIAL, titulo="💸 Pagar parcial"))

        # IA atendente (opcional, Story 13.26)
        if ia_ativa:
            opcoes.append(OpcaoMenu(id=ID_MENU_ATENDENTE, titulo="💬 Falar com atendente"))

        if eh_inadimplente:
            descricao = (
                f"Olá {cliente.nome_completo.split(' ')[0]}! "
                f"Você tem pendência. Como posso ajudar?"
            )
        else:
            descricao = f"Olá {cliente.nome_completo.split(' ')[0]}! O que precisa?"

        return Menu(
            descricao=descricao,
            opcoes=opcoes,
            eh_lista=len(opcoes) > 3,
        )

    # ── helpers ──────────────────────────────────────────────────────

    async def _carregar_cliente(self, cliente_id: UUID) -> Cliente:
        cliente = (await self.session.execute(
            select(Cliente).where(
                Cliente.id == cliente_id,
                Cliente.empresa_id == self.empresa_id,
            )
        )).scalar_one_or_none()
        if cliente is None:
            raise ValueError(f"Cliente {cliente_id} não encontrado")
        return cliente

    async def _cliente_tem_titulo_em_atraso(self, cliente_id: UUID) -> bool:
        """Cliente é inadimplente se tem ao menos 1 título em atraso."""
        from app.infrastructure.db.models.contrato import Contrato

        stmt = (
            select(func.count(TituloReceber.id))
            .join(Contrato, Contrato.id == TituloReceber.contrato_id)
            .where(
                Contrato.cliente_id == cliente_id,
                TituloReceber.empresa_id == self.empresa_id,
                TituloReceber.status == "em_atraso",
            )
        )
        total = (await self.session.execute(stmt)).scalar() or 0
        return int(total) > 0

    async def _reset_contador_se_necessario(
        self, cliente: Cliente, config: ServicoConfiguracao
    ) -> None:
        """Se passou um período completo desde `inicio_periodo_acoes`,
        zera contadores e atualiza o início. Idempotente."""
        if (
            cliente.adiamentos_usados_no_periodo == 0
            and cliente.desbloqueios_confianca_usados_no_periodo == 0
        ):
            # Nada pra resetar; só garante que `inicio_periodo_acoes` está
            # marcado pra começar o próximo ciclo.
            if cliente.inicio_periodo_acoes is None:
                cliente.inicio_periodo_acoes = date.today()
            return

        periodo = await config.obter_string(
            "periodo_limite_acoes_cliente", "cobranca", padrao="mensal"
        )
        dias = _periodo_para_dias(periodo)
        inicio = cliente.inicio_periodo_acoes or date.today()
        if (date.today() - inicio).days >= dias:
            log.info(
                "reset_periodo_cliente",
                cliente_id=str(cliente.id),
                periodo=periodo,
                dias=dias,
            )
            cliente.adiamentos_usados_no_periodo = 0
            cliente.desbloqueios_confianca_usados_no_periodo = 0
            cliente.inicio_periodo_acoes = date.today()
