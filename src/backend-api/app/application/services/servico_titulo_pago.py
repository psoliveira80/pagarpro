"""ServicoTituloPago — hook central de pagamento confirmado (Story 13.9).

Chamado quando:
- Motor de conciliação 13.9 verifica pagamento bancário.
- Validador humano aprova comprovante (Story 4.5).
- Webhook de gateway de pagamento dispara.

Responsabilidades:
1. Atualiza status do título (`pago` ou `pago_parcial`).
2. Em caso de pagamento parcial, decide fusão vs separação via
   `domain/finance/conciliacao.py`.
3. Se título é `opcao_compra` pago → delega para `ServicoOpcaoCompra`.
4. Publica `EventoContrato` apropriado (`titulo_pago`,
   `pagamento_parcial_recebido`).
5. Audit log com `category='financeiro'`.

NÃO reativa contrato suspenso automaticamente — Story 13.13 (desbloqueio
em confiança) avalia separadamente. Aqui só sinaliza via evento.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.servico_configuracao import ServicoConfiguracao
from app.application.services.servico_opcao_compra import ServicoOpcaoCompra
from app.application.shared.audit_logger import AuditLogger
from app.domain.finance.conciliacao import (
    DecisaoConciliacao,
    decidir_conciliacao,
)
from app.domain.finance.tipo_titulo import TipoTitulo
from app.infrastructure.db.models.contrato import EventoContrato
from app.infrastructure.db.models.financeiro import (
    MovimentoTituloReceber,
    TituloReceber,
)


log = structlog.get_logger()


class TituloPagoInvalidoError(Exception):
    pass


class ServicoTituloPago:
    def __init__(self, session: AsyncSession, empresa_id: UUID) -> None:
        self.session = session
        self.empresa_id = empresa_id

    async def registrar_pagamento(
        self,
        titulo_id: UUID,
        valor_pago: Decimal,
        data_pagamento: date | None = None,
        forma_pagamento: str | None = None,
        ator_id: UUID | None = None,
    ) -> dict:
        """Registra pagamento de um título e aplica regras.

        Retorna dict com a decisão tomada (campo `decisao`) e IDs afetados.
        Idempotente: se título já está `pago`, retorna decisao='ja_pago'
        sem alterar estado.
        """
        result = await self.session.execute(
            select(TituloReceber).where(
                TituloReceber.id == titulo_id,
                TituloReceber.empresa_id == self.empresa_id,
            )
        )
        titulo = result.scalar_one_or_none()
        if titulo is None:
            raise TituloPagoInvalidoError(
                f"Título {titulo_id} não encontrado para empresa {self.empresa_id}"
            )

        if titulo.status == "pago":
            return {"decisao": "ja_pago", "titulo_id": str(titulo.id)}

        # Carrega configuração (limite_fusao_parcial_pct)
        # Cria ServicoConfiguracao SEM Redis (caller pode passar instância
        # cacheada via attribute injection se quiser otimizar)
        servico_config = ServicoConfiguracao(self.session, self.empresa_id, redis=None)
        limite_fusao = await servico_config.obter_decimal(
            "limite_fusao_parcial_pct", "financeiro", padrao=Decimal("20.00")
        )

        decisao = decidir_conciliacao(valor_pago, titulo.valor, limite_fusao)
        hoje = data_pagamento or date.today()

        # ── Caso integral ou excedente ──
        if decisao.decisao in (DecisaoConciliacao.INTEGRAL, DecisaoConciliacao.EXCEDENTE):
            titulo.status = "pago"
            titulo.pago_em = hoje
            titulo.valor_pago = valor_pago
            if forma_pagamento:
                titulo.forma_pagamento = forma_pagamento

            self.session.add(MovimentoTituloReceber(
                empresa_id=self.empresa_id,
                titulo_id=titulo.id,
                tipo="pagamento",
                motivo=f"Pagamento {decisao.decisao.value} de R$ {valor_pago}",
                delta_valor=valor_pago,
                snapshot_antes={"status": "em_aberto", "valor_pago": "0"},
                snapshot_depois={"status": "pago", "valor_pago": str(valor_pago)},
            ))

            # Trata opção de compra (alienação)
            opcao_compra_result = None
            if titulo.tipo == TipoTitulo.OPCAO_COMPRA.value:
                servico_oc = ServicoOpcaoCompra(self.session, self.empresa_id)
                opcao_compra_result = await servico_oc.processar_pagamento(
                    titulo.id, ator_id=ator_id
                )

            self.session.add(EventoContrato(
                empresa_id=self.empresa_id,
                contrato_id=titulo.contrato_id,
                tipo="titulo_pago",
                payload={
                    "titulo_id": str(titulo.id),
                    "tipo_titulo": titulo.tipo,
                    "valor_pago": str(valor_pago),
                    "valor_titulo": str(titulo.valor),
                    "decisao": decisao.decisao.value,
                    "data_pagamento": hoje.isoformat(),
                },
                criado_por_id=ator_id,
            ))

            await self._audit(titulo, decisao, hoje, ator_id)
            await self.session.flush()
            return {
                "decisao": decisao.decisao.value,
                "titulo_id": str(titulo.id),
                "opcao_compra": opcao_compra_result,
            }

        # ── Pagamento parcial — FUSÃO ──
        if decisao.decisao == DecisaoConciliacao.FUNDIDO:
            # Acha o próximo título em aberto do mesmo contrato
            proximo_stmt = select(TituloReceber).where(
                TituloReceber.contrato_id == titulo.contrato_id,
                TituloReceber.id != titulo.id,
                TituloReceber.status == "em_aberto",
                TituloReceber.tipo == TipoTitulo.PARCELA.value,
            ).order_by(TituloReceber.data_vencimento).limit(1)
            proximo = (await self.session.execute(proximo_stmt)).scalar_one_or_none()

            if proximo is None:
                # Não há próximo — força separação
                return await self._aplicar_separacao(titulo, valor_pago, decisao.restante, hoje, ator_id)

            valor_anterior_proximo = proximo.valor
            proximo.valor = proximo.valor + decisao.restante
            proximo.observacoes = (
                (proximo.observacoes or "")
                + f"\nFusão de R$ {decisao.restante} do título {titulo.id} (Story 13.9)."
            ).strip()

            titulo.status = "pago_parcial"
            titulo.pago_em = hoje
            titulo.valor_pago = valor_pago
            if forma_pagamento:
                titulo.forma_pagamento = forma_pagamento

            self.session.add(MovimentoTituloReceber(
                empresa_id=self.empresa_id,
                titulo_id=titulo.id,
                tipo="pagamento_parcial_fundido",
                motivo=f"Pagamento parcial de R$ {valor_pago}; restante R$ {decisao.restante} fundido no título {proximo.id}",
                delta_valor=valor_pago,
                snapshot_antes={"valor": str(titulo.valor), "restante": "0"},
                snapshot_depois={
                    "valor_pago": str(valor_pago),
                    "restante_fundido": str(decisao.restante),
                    "fundido_em_titulo": str(proximo.id),
                    "proximo_valor_anterior": str(valor_anterior_proximo),
                    "proximo_valor_novo": str(proximo.valor),
                },
            ))

            self.session.add(EventoContrato(
                empresa_id=self.empresa_id,
                contrato_id=titulo.contrato_id,
                tipo="pagamento_parcial_recebido",
                payload={
                    "titulo_id": str(titulo.id),
                    "valor_pago": str(valor_pago),
                    "restante": str(decisao.restante),
                    "fundido_em": str(proximo.id),
                    "decisao": "fundido",
                },
                criado_por_id=ator_id,
            ))

            await self._audit(titulo, decisao, hoje, ator_id)
            await self.session.flush()
            return {
                "decisao": "fundido",
                "titulo_id": str(titulo.id),
                "fundido_em": str(proximo.id),
            }

        # ── Pagamento parcial — SEPARAÇÃO ──
        return await self._aplicar_separacao(titulo, valor_pago, decisao.restante, hoje, ator_id)

    async def _aplicar_separacao(
        self,
        titulo: TituloReceber,
        valor_pago: Decimal,
        restante: Decimal,
        hoje: date,
        ator_id: UUID | None,
    ) -> dict:
        """Cria um título novo com o valor restante (parent = titulo original)."""
        servico_config = ServicoConfiguracao(self.session, self.empresa_id, redis=None)
        dias_carencia = await servico_config.obter_inteiro(
            "dias_carencia", "financeiro", padrao=5
        )

        # Próxima sequência
        from sqlalchemy import func, select as sa_select
        seq_stmt = sa_select(func.coalesce(func.max(TituloReceber.sequencia), 0)).where(
            TituloReceber.contrato_id == titulo.contrato_id
        )
        prox_seq = int((await self.session.execute(seq_stmt)).scalar_one()) + 1

        novo = TituloReceber(
            empresa_id=self.empresa_id,
            contrato_id=titulo.contrato_id,
            sequencia=prox_seq,
            tipo=TipoTitulo.PARCELA.value,
            data_vencimento=hoje + timedelta(days=max(dias_carencia, 5)),
            valor=restante,
            valor_pago=Decimal("0"),
            status="em_aberto",
            titulo_origem_id=titulo.id,
            observacoes=f"Título gerado por separação de pagamento parcial do título {titulo.id} (Story 13.9).",
        )
        self.session.add(novo)
        await self.session.flush()

        titulo.status = "pago_parcial"
        titulo.pago_em = hoje
        titulo.valor_pago = valor_pago

        self.session.add(MovimentoTituloReceber(
            empresa_id=self.empresa_id,
            titulo_id=titulo.id,
            tipo="pagamento_parcial_separado",
            motivo=f"Pagamento parcial de R$ {valor_pago}; restante R$ {restante} virou título novo {novo.id}",
            delta_valor=valor_pago,
            snapshot_antes={"valor": str(titulo.valor), "status": "em_aberto"},
            snapshot_depois={
                "valor_pago": str(valor_pago),
                "restante_separado": str(restante),
                "titulo_novo": str(novo.id),
            },
        ))

        self.session.add(EventoContrato(
            empresa_id=self.empresa_id,
            contrato_id=titulo.contrato_id,
            tipo="pagamento_parcial_recebido",
            payload={
                "titulo_id": str(titulo.id),
                "valor_pago": str(valor_pago),
                "restante": str(restante),
                "titulo_novo": str(novo.id),
                "decisao": "separado",
            },
            criado_por_id=ator_id,
        ))

        audit = AuditLogger(self.session)
        await audit.record(
            action="titulo.pagamento_parcial_separado",
            user_id=str(ator_id) if ator_id else None,
            entity="titulos_receber",
            entity_id=str(titulo.id),
            payload_before={"valor": str(titulo.valor), "status": "em_aberto"},
            payload_after={
                "valor_pago": str(valor_pago),
                "restante": str(restante),
                "titulo_novo": str(novo.id),
            },
            module="financeiro",
            category="financeiro",
        )
        await self.session.flush()
        return {
            "decisao": "separado",
            "titulo_id": str(titulo.id),
            "titulo_novo": str(novo.id),
        }

    async def _audit(
        self,
        titulo: TituloReceber,
        decisao,
        hoje: date,
        ator_id: UUID | None,
    ) -> None:
        audit = AuditLogger(self.session)
        await audit.record(
            action=f"titulo.pagamento_{decisao.decisao.value}",
            user_id=str(ator_id) if ator_id else None,
            entity="titulos_receber",
            entity_id=str(titulo.id),
            payload_before={"status": "em_aberto"},
            payload_after={
                "status": titulo.status,
                "valor_pago": str(titulo.valor_pago) if titulo.valor_pago else None,
                "data_pagamento": hoje.isoformat(),
                "decisao": decisao.decisao.value,
            },
            module="financeiro",
            category="financeiro",
        )
