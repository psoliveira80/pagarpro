"""ServicoAcoesCliente — executa cada ação do menu do número rígido.

Story 13.22.

Cobre:
- `montar_extrato_saldo(cliente_id)` → texto pronto pra enviar.
- `gerar_pix_para_proximo_titulo(cliente_id)` → dados de PIX para botão nativo.
- `aplicar_adiamento(cliente_id, dias)` → adia data_vencimento do próximo
  título, incrementa contador.
- `aplicar_desbloqueio_confianca(cliente_id, dias)` → reativa contrato,
  agenda re-bloqueio, incrementa contador.
- `aplicar_pagamento_parcial(cliente_id, valor)` → gera PIX com valor
  parcial (após validar % mínimo).

Cada método retorna um DTO ou levanta erro se a ação não é permitida
(score baixo, blacklist, limite atingido).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.servico_configuracao import ServicoConfiguracao
from app.application.shared.audit_logger import AuditLogger
from app.infrastructure.db.models.cadastro import Cliente
from app.infrastructure.db.models.contrato import Contrato
from app.infrastructure.db.models.financeiro import TituloReceber


log = structlog.get_logger()


class AcaoNaoPermitidaError(Exception):
    """Cliente tentou ação para a qual não tem direito (score baixo,
    blacklist, limite atingido). Caller decide como responder."""


@dataclass(frozen=True)
class DadosPix:
    """Tudo que o adapter Evolution Go precisa pra enviar botão PIX nativo."""
    descricao: str
    valor: Decimal
    chave_pix: str
    tipo_chave: str  # cnpj | cpf | email | phone | random
    nome_recebedor: str


class ServicoAcoesCliente:
    def __init__(self, session: AsyncSession, empresa_id: UUID) -> None:
        self.session = session
        self.empresa_id = empresa_id

    # ── Extrato e saldo ──────────────────────────────────────────

    async def montar_extrato_saldo(self, cliente_id: UUID) -> str:
        """Retorna texto pronto com extrato simplificado do cliente."""
        cliente = await self._carregar_cliente(cliente_id)

        # Pega títulos abertos + em atraso
        titulos = list((await self.session.execute(
            select(TituloReceber)
            .join(Contrato, Contrato.id == TituloReceber.contrato_id)
            .where(
                Contrato.cliente_id == cliente_id,
                TituloReceber.empresa_id == self.empresa_id,
                TituloReceber.status.in_(("em_aberto", "em_atraso")),
            )
            .order_by(asc(TituloReceber.data_vencimento))
        )).scalars().all())

        if not titulos:
            return (
                f"Olá {cliente.nome_completo.split(' ')[0]}!\n\n"
                f"✅ Você não tem pendências.\n"
                f"Continue assim! 🙂"
            )

        em_atraso = [t for t in titulos if t.status == "em_atraso"]
        em_aberto = [t for t in titulos if t.status == "em_aberto"]

        linhas: list[str] = [
            f"📋 *Extrato — {cliente.nome_completo.split(' ')[0]}*",
            "",
        ]

        if em_atraso:
            linhas.append("⚠️ *Em atraso:*")
            for t in em_atraso[:5]:
                dias = (date.today() - t.data_vencimento).days
                linhas.append(
                    f"• Parcela {t.sequencia}: R$ {t.valor:.2f} "
                    f"— venceu há {dias}d (em {t.data_vencimento.strftime('%d/%m/%Y')})"
                )
            linhas.append("")

        if em_aberto:
            linhas.append("📅 *Em aberto:*")
            for t in em_aberto[:5]:
                linhas.append(
                    f"• Parcela {t.sequencia}: R$ {t.valor:.2f} "
                    f"— vence em {t.data_vencimento.strftime('%d/%m/%Y')}"
                )

        total = sum(t.valor for t in titulos)
        linhas.append("")
        linhas.append(f"💰 *Total em aberto: R$ {total:.2f}*")
        return "\n".join(linhas)

    # ── PIX ──────────────────────────────────────────────────────

    async def gerar_pix_para_proximo_titulo(self, cliente_id: UUID) -> DadosPix:
        """Gera dados de PIX para o título mais antigo em aberto/atraso."""
        from app.infrastructure.db.models.comercial import Empresa

        titulo = (await self.session.execute(
            select(TituloReceber)
            .join(Contrato, Contrato.id == TituloReceber.contrato_id)
            .where(
                Contrato.cliente_id == cliente_id,
                TituloReceber.empresa_id == self.empresa_id,
                TituloReceber.status.in_(("em_aberto", "em_atraso")),
            )
            .order_by(asc(TituloReceber.data_vencimento))
            .limit(1)
        )).scalar_one_or_none()
        if titulo is None:
            raise AcaoNaoPermitidaError("Nenhum título em aberto")

        empresa = (await self.session.execute(
            select(Empresa).where(Empresa.id == self.empresa_id)
        )).scalar_one_or_none()
        if empresa is None:
            raise AcaoNaoPermitidaError("Empresa não encontrada")

        # V1: usa CNPJ da empresa como chave PIX.
        # V2: ler chave PIX preferida das configurações da empresa.
        chave = (empresa.cnpj or "").strip()
        return DadosPix(
            descricao=(
                f"Parcela {titulo.sequencia} — vencimento "
                f"{titulo.data_vencimento.strftime('%d/%m/%Y')}"
            ),
            valor=titulo.valor,
            chave_pix=chave,
            tipo_chave="cnpj",
            nome_recebedor=empresa.razao_social,
        )

    # ── Adiamento ────────────────────────────────────────────────

    async def aplicar_adiamento(
        self, cliente_id: UUID, ator_id: UUID | None = None
    ) -> dict:
        """Adia data_vencimento do próximo título pelo número de dias
        configurado em `dias_maximos_adiamento`. Incrementa contador.

        Levanta `AcaoNaoPermitidaError` se cliente não tem direito.
        """
        cliente = await self._carregar_cliente(cliente_id)
        config = ServicoConfiguracao(self.session, self.empresa_id, redis=None)

        if cliente.na_blacklist_comprovantes:
            raise AcaoNaoPermitidaError("Cliente em blacklist")

        score_min = await config.obter_decimal(
            "score_minimo_adiar_vencimento", "cobranca", padrao=Decimal("80")
        )
        if Decimal(cliente.score or 0) < score_min:
            raise AcaoNaoPermitidaError(
                f"Score insuficiente para adiar (precisa {score_min})"
            )

        limite = await config.obter_inteiro(
            "limite_usos_periodo_adiar", "cobranca", padrao=1
        )
        if cliente.adiamentos_usados_no_periodo >= limite:
            raise AcaoNaoPermitidaError(
                f"Limite de adiamentos no período atingido ({limite})"
            )

        dias = await config.obter_inteiro(
            "dias_maximos_adiamento", "cobranca", padrao=5
        )

        # Pega próximo título a vencer (em_aberto)
        proximo = (await self.session.execute(
            select(TituloReceber)
            .join(Contrato, Contrato.id == TituloReceber.contrato_id)
            .where(
                Contrato.cliente_id == cliente_id,
                TituloReceber.empresa_id == self.empresa_id,
                TituloReceber.status == "em_aberto",
            )
            .order_by(asc(TituloReceber.data_vencimento))
            .limit(1)
        )).scalar_one_or_none()
        if proximo is None:
            raise AcaoNaoPermitidaError("Nenhum título em aberto para adiar")

        venc_anterior = proximo.data_vencimento
        proximo.data_vencimento = venc_anterior + timedelta(days=dias)
        cliente.adiamentos_usados_no_periodo += 1

        audit = AuditLogger(self.session)
        await audit.record(
            action="cliente.adiamento_aplicado",
            user_id=str(ator_id) if ator_id else None,
            entity="titulos_receber",
            entity_id=str(proximo.id),
            payload_after={
                "venc_anterior": venc_anterior.isoformat(),
                "venc_novo": proximo.data_vencimento.isoformat(),
                "dias": dias,
                "cliente_id": str(cliente_id),
            },
            module="cobranca",
            category="financeiro",
        )
        await self.session.flush()
        return {
            "titulo_id": str(proximo.id),
            "dias_adiados": dias,
            "vencimento_novo": proximo.data_vencimento.isoformat(),
        }

    # ── Desbloqueio em confiança ────────────────────────────────

    async def aplicar_desbloqueio_confianca(
        self, cliente_id: UUID, ator_id: UUID | None = None
    ) -> dict:
        """Libera veículo por N dias. Reativa contrato suspenso (se for o caso)
        via `ServicoSituacaoContrato`. Incrementa contador."""
        from app.application.services.servico_situacao_contrato import (
            ServicoSituacaoContrato,
        )
        from app.domain.contracts.state_machine import SituacaoContrato

        cliente = await self._carregar_cliente(cliente_id)
        config = ServicoConfiguracao(self.session, self.empresa_id, redis=None)

        if cliente.na_blacklist_comprovantes:
            raise AcaoNaoPermitidaError("Cliente em blacklist")

        score_min = await config.obter_decimal(
            "score_minimo_desbloqueio_confianca", "cobranca", padrao=Decimal("65")
        )
        if Decimal(cliente.score or 0) < score_min:
            raise AcaoNaoPermitidaError("Score insuficiente para desbloqueio")

        limite = await config.obter_inteiro(
            "limite_usos_periodo_desbloqueio_confianca", "cobranca", padrao=1
        )
        if cliente.desbloqueios_confianca_usados_no_periodo >= limite:
            raise AcaoNaoPermitidaError("Limite de desbloqueios no período atingido")

        dias = await config.obter_inteiro(
            "desbloqueio_confianca_dias", "frota", padrao=3
        )

        # Pega contrato vigente do cliente — desbloqueio só faz sentido se o
        # contrato está suspenso.
        contrato = (await self.session.execute(
            select(Contrato).where(
                Contrato.cliente_id == cliente_id,
                Contrato.empresa_id == self.empresa_id,
                Contrato.status.in_(("suspenso", "vigente")),
            )
            .order_by(Contrato.data_inicio.desc())
            .limit(1)
        )).scalar_one_or_none()
        if contrato is None:
            raise AcaoNaoPermitidaError("Cliente sem contrato vigente/suspenso")

        if contrato.status == "suspenso":
            servico = ServicoSituacaoContrato(self.session, self.empresa_id)
            await servico.transicionar(
                contrato.id,
                SituacaoContrato.VIGENTE,
                motivo=f"Desbloqueio em confiança por {dias} dias (via menu WhatsApp)",
                ator_id=ator_id,
            )

        cliente.desbloqueios_confianca_usados_no_periodo += 1
        await self.session.flush()
        return {
            "contrato_id": str(contrato.id),
            "dias_desbloqueio": dias,
            "validade_ate": (date.today() + timedelta(days=dias)).isoformat(),
        }

    # ── Pagamento parcial ───────────────────────────────────────

    async def gerar_pix_parcial(
        self,
        cliente_id: UUID,
        texto_valor: str,
    ) -> DadosPix:
        """Parse texto digitado pelo cliente como valor e gera PIX parcial.

        Valida que o valor é >= % mínimo do título.
        """
        from app.infrastructure.db.models.comercial import Empresa

        cliente = await self._carregar_cliente(cliente_id)
        config = ServicoConfiguracao(self.session, self.empresa_id, redis=None)

        if cliente.na_blacklist_comprovantes:
            raise AcaoNaoPermitidaError("Cliente em blacklist")

        score_min = await config.obter_decimal(
            "score_minimo_pagamento_parcial", "cobranca", padrao=Decimal("50")
        )
        if Decimal(cliente.score or 0) < score_min:
            raise AcaoNaoPermitidaError("Score insuficiente para parcial")

        # Parse valor BR
        valor_str = (
            texto_valor.replace("R$", "")
            .replace(" ", "")
            .replace(".", "")
            .replace(",", ".")
            .strip()
        )
        try:
            valor = Decimal(valor_str)
        except Exception:
            raise AcaoNaoPermitidaError(f"Valor inválido: {texto_valor}")
        if valor <= 0:
            raise AcaoNaoPermitidaError("Valor precisa ser positivo")

        titulo = (await self.session.execute(
            select(TituloReceber)
            .join(Contrato, Contrato.id == TituloReceber.contrato_id)
            .where(
                Contrato.cliente_id == cliente_id,
                TituloReceber.empresa_id == self.empresa_id,
                TituloReceber.status.in_(("em_aberto", "em_atraso")),
            )
            .order_by(asc(TituloReceber.data_vencimento))
            .limit(1)
        )).scalar_one_or_none()
        if titulo is None:
            raise AcaoNaoPermitidaError("Nenhum título em aberto")

        pct_min = await config.obter_decimal(
            "valor_minimo_pagamento_parcial_pct", "cobranca", padrao=Decimal("40.0")
        )
        minimo = (titulo.valor * pct_min / Decimal(100)).quantize(Decimal("0.01"))
        if valor < minimo:
            raise AcaoNaoPermitidaError(
                f"Valor mínimo do parcial é R$ {minimo} ({pct_min}% da parcela)"
            )
        if valor > titulo.valor:
            valor = titulo.valor  # cliente não paga mais do que deve

        empresa = (await self.session.execute(
            select(Empresa).where(Empresa.id == self.empresa_id)
        )).scalar_one()

        return DadosPix(
            descricao=f"Pagamento parcial — parcela {titulo.sequencia}",
            valor=valor,
            chave_pix=(empresa.cnpj or "").strip(),
            tipo_chave="cnpj",
            nome_recebedor=empresa.razao_social,
        )

    # ── Helpers ──────────────────────────────────────────────────

    async def _carregar_cliente(self, cliente_id: UUID) -> Cliente:
        cliente = (await self.session.execute(
            select(Cliente).where(
                Cliente.id == cliente_id,
                Cliente.empresa_id == self.empresa_id,
            )
        )).scalar_one_or_none()
        if cliente is None:
            raise AcaoNaoPermitidaError(f"Cliente {cliente_id} não encontrado")
        return cliente
