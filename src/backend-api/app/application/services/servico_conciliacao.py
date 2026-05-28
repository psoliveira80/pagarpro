"""ServicoConciliacao — orquestrador da conciliação bancária (Story 13.20).

Fluxo:

1. Recebe arquivo (OFX/PDF/CSV) + conta bancária.
2. Importa transações via importador apropriado.
3. Idempotência: se mesmo hash de arquivo já tem sessão, retorna a existente.
4. Persiste transações em `conta_bancaria.transacoes_bancarias` (skip duplicadas
   por unique `(empresa_id, conta_id, fitid)`).
5. Para cada transação de crédito, busca match em `titulos_receber` em aberto.
6. Calcula score do match e retorna lista de sugestões pra UI confirmar.
7. Quando gestor aplica match: cria `MatchConciliacao` + chama
   `ServicoTituloPago.registrar_pagamento` (reusa fluxo da 13.9).
8. Desfazer match (em até 30 dias): marca `desfeito_em`, reabre o título
   manualmente (transição precisa ser feita pelo gestor — ServicoSituacaoContrato
   não cobre "reabrir título pago" automaticamente).

Cross-check com comprovantes (13.19): se uma transação tem valor + data que
casam com um comprovante já homologado, marcamos `ja_existia_via_comprovante=True`
e bloqueamos o match (evita dupla contagem).
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.servico_titulo_pago import ServicoTituloPago
from app.application.shared.audit_logger import AuditLogger
from app.infrastructure.conciliacao.dto import (
    FormatoOrigem,
    ResultadoImportacao,
    TransacaoImportada,
)
from app.infrastructure.conciliacao.importador_csv import importar_csv
from app.infrastructure.conciliacao.importador_ofx import importar_ofx
from app.infrastructure.conciliacao.importador_pdf import importar_pdf
from app.infrastructure.db.models.comprovante_pagamento import ComprovantePagamento
from app.infrastructure.db.models.conta_bancaria import (
    ContaBancaria,
    MatchConciliacao,
    SessaoConciliacao,
    TransacaoBancaria,
)
from app.infrastructure.db.models.financeiro import TituloReceber


log = logging.getLogger(__name__)

# Tolerância em dias para um match automático
TOLERANCIA_DIAS_MATCH = 5
# Janela para desfazer um match
JANELA_DESFAZER_DIAS = 30


@dataclass(frozen=True)
class SugestaoMatch:
    transacao_id: UUID
    titulo_id: UUID | None
    score: float  # 0.0 a 1.0
    motivo: str
    ja_existia_via_comprovante: bool = False
    comprovante_id: UUID | None = None  # se ja_existia, qual comprovante


class ConciliacaoInvalidaError(Exception):
    pass


class SessaoJaExistenteError(Exception):
    """Levantada quando idempotência detecta que extrato já foi importado."""

    def __init__(self, sessao_existente: SessaoConciliacao):
        self.sessao_existente = sessao_existente
        super().__init__(f"Sessão já existente: {sessao_existente.id}")


class ServicoConciliacao:
    def __init__(self, session: AsyncSession, empresa_id: UUID) -> None:
        self.session = session
        self.empresa_id = empresa_id

    # ──────────────────────────────────────────────────────────────
    # Importação
    # ──────────────────────────────────────────────────────────────

    async def importar(
        self,
        conta_id: UUID,
        bytes_arquivo: bytes,
        nome_arquivo: str,
        formato: FormatoOrigem,
        criado_por_id: UUID | None = None,
        mapeamento_csv: dict[str, str] | None = None,
    ) -> SessaoConciliacao:
        """Importa um arquivo bancário e cria sessão de conciliação."""

        # Valida conta pertence ao tenant
        conta = (await self.session.execute(
            select(ContaBancaria).where(
                ContaBancaria.id == conta_id,
                ContaBancaria.empresa_id == self.empresa_id,
            )
        )).scalar_one_or_none()
        if conta is None:
            raise ConciliacaoInvalidaError(
                f"Conta bancária {conta_id} não encontrada"
            )

        # Idempotência por hash
        hash_arquivo = hashlib.sha256(bytes_arquivo).hexdigest()
        existente = (await self.session.execute(
            select(SessaoConciliacao).where(
                SessaoConciliacao.empresa_id == self.empresa_id,
                SessaoConciliacao.conta_id == conta_id,
                SessaoConciliacao.hash_arquivo == hash_arquivo,
            )
        )).scalar_one_or_none()
        if existente is not None:
            raise SessaoJaExistenteError(existente)

        # Dispatch para importador
        if formato == FormatoOrigem.OFX:
            resultado = importar_ofx(bytes_arquivo)
        elif formato == FormatoOrigem.PDF:
            resultado = importar_pdf(bytes_arquivo)
        elif formato == FormatoOrigem.CSV:
            if not mapeamento_csv:
                raise ConciliacaoInvalidaError(
                    "Importação CSV exige mapeamento de colunas"
                )
            resultado = importar_csv(bytes_arquivo, mapeamento_csv)
        else:
            raise ConciliacaoInvalidaError(f"Formato não suportado: {formato}")

        if not resultado.transacoes:
            raise ConciliacaoInvalidaError(
                "Nenhuma transação importada. "
                + (" ".join(resultado.erros) if resultado.erros else "")
            )

        # Cria sessão
        sessao = SessaoConciliacao(
            empresa_id=self.empresa_id,
            conta_id=conta_id,
            periodo_inicio=resultado.periodo_inicio or resultado.transacoes[0].data,
            periodo_fim=resultado.periodo_fim or resultado.transacoes[-1].data,
            status="em_andamento",
            total_transacoes=len(resultado.transacoes),
            total_conciliadas=0,
            criado_por_id=criado_por_id,
            nome_arquivo_origem=nome_arquivo,
            hash_arquivo=hash_arquivo,
            formato_origem=formato.value,
        )
        self.session.add(sessao)
        await self.session.flush()

        # Persiste transações (skip duplicatas por fitid)
        await self._persistir_transacoes(conta_id, resultado.transacoes, formato.value)

        return sessao

    async def _persistir_transacoes(
        self,
        conta_id: UUID,
        transacoes: list[TransacaoImportada],
        origem: str,
    ) -> None:
        """Persiste cada transação; duplicatas por fitid são ignoradas."""
        for tx in transacoes:
            transacao = TransacaoBancaria(
                empresa_id=self.empresa_id,
                conta_id=conta_id,
                fitid=tx.fitid,
                lancado_em=tx.data,
                valor=tx.valor,
                descricao_bruta=tx.descricao,
                tipo=tx.tipo,
                status="pendente",
                importado_de=origem,
            )
            self.session.add(transacao)
            try:
                await self.session.flush()
            except IntegrityError:
                await self.session.rollback()
                # transação já existia para essa conta — segue
                continue

    # ──────────────────────────────────────────────────────────────
    # Sugestões de match
    # ──────────────────────────────────────────────────────────────

    async def listar_sugestoes(
        self, sessao_id: UUID
    ) -> list[SugestaoMatch]:
        """Para cada transação de crédito pendente da sessão, retorna
        a melhor sugestão de match com título em aberto."""

        sessao = await self._carregar_sessao(sessao_id)

        # Transações pendentes (sem match vigente) na conta da sessão
        from sqlalchemy import not_, exists
        stmt = select(TransacaoBancaria).where(
            TransacaoBancaria.empresa_id == self.empresa_id,
            TransacaoBancaria.conta_id == sessao.conta_id,
            TransacaoBancaria.lancado_em >= sessao.periodo_inicio,
            TransacaoBancaria.lancado_em <= sessao.periodo_fim,
            TransacaoBancaria.valor > 0,  # só créditos (recebimentos)
            ~exists(
                select(MatchConciliacao.id).where(
                    MatchConciliacao.transacao_id == TransacaoBancaria.id,
                    MatchConciliacao.desfeito_em.is_(None),
                )
            ),
        ).order_by(TransacaoBancaria.lancado_em)
        transacoes = list((await self.session.execute(stmt)).scalars().all())

        sugestoes: list[SugestaoMatch] = []
        for tx in transacoes:
            sugestao = await self._calcular_melhor_sugestao(tx)
            sugestoes.append(sugestao)
        return sugestoes

    async def _calcular_melhor_sugestao(
        self, tx: TransacaoBancaria
    ) -> SugestaoMatch:
        """Heurística de score:
        - valor exato + data exata + descrição contém nome → 1.00
        - valor exato + data ±2 dias → 0.95
        - valor exato sem data próxima → 0.80
        - valor ±R$ 1 + data ±5 dias → 0.70
        """
        # Primeiro, cross-check com comprovantes homologados (13.19)
        comprov = await self._buscar_comprovante_ja_homologado(tx)
        if comprov is not None:
            return SugestaoMatch(
                transacao_id=tx.id,
                titulo_id=comprov.titulo_id,
                score=1.0,
                motivo="Pagamento já conciliado via comprovante PIX",
                ja_existia_via_comprovante=True,
                comprovante_id=comprov.id,
            )

        # Busca títulos candidatos: valor próximo + data dentro da janela
        valor_min = tx.valor - Decimal("1.00")
        valor_max = tx.valor + Decimal("1.00")
        data_min = tx.lancado_em - timedelta(days=TOLERANCIA_DIAS_MATCH)
        data_max = tx.lancado_em + timedelta(days=TOLERANCIA_DIAS_MATCH)

        candidatos = list((await self.session.execute(
            select(TituloReceber).where(
                TituloReceber.empresa_id == self.empresa_id,
                TituloReceber.status.in_(("em_aberto", "em_atraso")),
                TituloReceber.valor >= valor_min,
                TituloReceber.valor <= valor_max,
                and_(
                    TituloReceber.data_vencimento >= data_min,
                    TituloReceber.data_vencimento <= data_max,
                ),
            ).order_by(TituloReceber.data_vencimento)
        )).scalars().all())

        if not candidatos:
            return SugestaoMatch(
                transacao_id=tx.id,
                titulo_id=None,
                score=0.0,
                motivo="Nenhum título compatível",
            )

        # Calcula score para cada candidato
        melhor: SugestaoMatch | None = None
        for titulo in candidatos:
            score, motivo = _scorear(tx, titulo)
            if melhor is None or score > melhor.score:
                melhor = SugestaoMatch(
                    transacao_id=tx.id,
                    titulo_id=titulo.id,
                    score=score,
                    motivo=motivo,
                )
        return melhor or SugestaoMatch(
            transacao_id=tx.id, titulo_id=None, score=0.0, motivo="Nenhum match",
        )

    async def _buscar_comprovante_ja_homologado(
        self, tx: TransacaoBancaria
    ) -> ComprovantePagamento | None:
        """Cross-check com 13.19: pagamento que veio antes pelo comprovante."""
        if tx.valor <= 0:
            return None
        # Mesmo valor + data ±2 dias + status homologado
        data_min = tx.lancado_em - timedelta(days=2)
        data_max = tx.lancado_em + timedelta(days=2)
        result = await self.session.execute(
            select(ComprovantePagamento).where(
                ComprovantePagamento.empresa_id == self.empresa_id,
                ComprovantePagamento.status == "homologado",
                ComprovantePagamento.valor_detectado == tx.valor,
                ComprovantePagamento.data_detectada.isnot(None),
            ).limit(10)
        )
        candidatos = list(result.scalars().all())
        for comp in candidatos:
            if comp.data_detectada is None:
                continue
            d = comp.data_detectada.date()
            if data_min <= d <= data_max:
                return comp
        return None

    # ──────────────────────────────────────────────────────────────
    # Aplicar / desfazer match
    # ──────────────────────────────────────────────────────────────

    async def aplicar_match(
        self,
        sessao_id: UUID,
        transacao_id: UUID,
        titulo_id: UUID,
        score: float,
        motivo: str,
        aplicado_por_id: UUID,
        ja_existia_via_comprovante: bool = False,
    ) -> MatchConciliacao:
        """Confirma o vínculo transação × título.

        Se `ja_existia_via_comprovante=True`, NÃO chama `ServicoTituloPago`
        (já foi feito quando o comprovante foi homologado). Só registra o
        match para audit.
        """
        sessao = await self._carregar_sessao(sessao_id)
        tx = await self._carregar_transacao(transacao_id, sessao.conta_id)

        # Match já vigente nessa transação?
        ja_match = (await self.session.execute(
            select(MatchConciliacao).where(
                MatchConciliacao.transacao_id == transacao_id,
                MatchConciliacao.desfeito_em.is_(None),
            )
        )).scalar_one_or_none()
        if ja_match is not None:
            raise ConciliacaoInvalidaError(
                f"Transação {transacao_id} já tem match vigente ({ja_match.id})"
            )

        titulo = (await self.session.execute(
            select(TituloReceber).where(
                TituloReceber.id == titulo_id,
                TituloReceber.empresa_id == self.empresa_id,
            )
        )).scalar_one_or_none()
        if titulo is None:
            raise ConciliacaoInvalidaError(
                f"Título {titulo_id} não encontrado"
            )

        # Quando não veio via comprovante, dispara o registrar_pagamento da 13.9
        if not ja_existia_via_comprovante:
            servico_pago = ServicoTituloPago(self.session, self.empresa_id)
            await servico_pago.registrar_pagamento(
                titulo_id=titulo_id,
                valor_pago=tx.valor,
                data_pagamento=tx.lancado_em,
                forma_pagamento=tx.tipo or "pix",
                ator_id=aplicado_por_id,
            )

        match = MatchConciliacao(
            empresa_id=self.empresa_id,
            sessao_id=sessao_id,
            transacao_id=transacao_id,
            titulo_id=titulo_id,
            score_match=Decimal(str(round(score, 2))),
            motivo_match=motivo,
            aplicado_por_id=aplicado_por_id,
            ja_existia_via_comprovante=ja_existia_via_comprovante,
        )
        self.session.add(match)

        # Atualiza estado da transação
        tx.status = "conciliada"
        tx.conciliado_com_tipo = "titulo_receber"
        tx.conciliado_com_id = titulo_id

        # Atualiza contagem da sessão
        sessao.total_conciliadas = (sessao.total_conciliadas or 0) + 1

        # Audit
        audit = AuditLogger(self.session)
        await audit.record(
            action="conciliacao.match_aplicado",
            user_id=str(aplicado_por_id),
            entity="matches_conciliacao",
            entity_id=str(transacao_id),
            payload_after={
                "transacao_id": str(transacao_id),
                "titulo_id": str(titulo_id),
                "score": str(score),
                "motivo": motivo,
                "via_comprovante": ja_existia_via_comprovante,
            },
            module="conciliacao",
            category="financeiro",
        )

        await self.session.flush()
        return match

    async def desfazer_match(
        self,
        match_id: UUID,
        motivo: str,
        desfeito_por_id: UUID,
    ) -> MatchConciliacao:
        """Desfaz match em até 30 dias.

        **Não reabre o título automaticamente.** O título permanece `pago` —
        decisão deliberada porque reverter um `pagamento` envolve estorno
        contábil (`MovimentoTituloReceber` tipo='estorno') que tem
        implicações fiscais. O gestor faz a reversão via endpoint dedicado
        (`POST /receivables/{id}/estornar`) quando confirmar que o
        pagamento de fato não aconteceu.

        Esta operação:
        1. Marca `match.desfeito_em` (audit).
        2. Libera a transação bancária para novo match.
        3. NÃO altera o título nem o `valor_pago` do título.
        """
        match = (await self.session.execute(
            select(MatchConciliacao).where(
                MatchConciliacao.id == match_id,
                MatchConciliacao.empresa_id == self.empresa_id,
            )
        )).scalar_one_or_none()
        if match is None:
            raise ConciliacaoInvalidaError("Match não encontrado")
        if match.desfeito_em is not None:
            raise ConciliacaoInvalidaError("Match já está desfeito")

        agora = datetime.now(timezone.utc)
        limite = match.aplicado_em + timedelta(days=JANELA_DESFAZER_DIAS)
        # `aplicado_em` é tz-aware; comparar com `agora` (tz-aware UTC)
        if agora > limite:
            raise ConciliacaoInvalidaError(
                f"Match aplicado há mais de {JANELA_DESFAZER_DIAS} dias — "
                "não pode ser desfeito automaticamente"
            )

        match.desfeito_em = agora
        match.desfeito_por_id = desfeito_por_id
        match.motivo_desfazer = motivo

        # Libera a transação para novo match
        tx = (await self.session.execute(
            select(TransacaoBancaria).where(
                TransacaoBancaria.id == match.transacao_id
            )
        )).scalar_one()
        tx.status = "pendente"
        tx.conciliado_com_tipo = None
        tx.conciliado_com_id = None

        audit = AuditLogger(self.session)
        await audit.record(
            action="conciliacao.match_desfeito",
            user_id=str(desfeito_por_id),
            entity="matches_conciliacao",
            entity_id=str(match_id),
            payload_before={
                "transacao_id": str(match.transacao_id),
                "titulo_id": str(match.titulo_id),
            },
            payload_after={"motivo": motivo, "desfeito_em": agora.isoformat()},
            module="conciliacao",
            category="financeiro",
        )

        await self.session.flush()
        return match

    # ──────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────

    async def _carregar_sessao(self, sessao_id: UUID) -> SessaoConciliacao:
        sessao = (await self.session.execute(
            select(SessaoConciliacao).where(
                SessaoConciliacao.id == sessao_id,
                SessaoConciliacao.empresa_id == self.empresa_id,
            )
        )).scalar_one_or_none()
        if sessao is None:
            raise ConciliacaoInvalidaError(f"Sessão {sessao_id} não encontrada")
        return sessao

    async def _carregar_transacao(
        self, transacao_id: UUID, conta_id_esperada: UUID
    ) -> TransacaoBancaria:
        tx = (await self.session.execute(
            select(TransacaoBancaria).where(
                TransacaoBancaria.id == transacao_id,
                TransacaoBancaria.empresa_id == self.empresa_id,
                TransacaoBancaria.conta_id == conta_id_esperada,
            )
        )).scalar_one_or_none()
        if tx is None:
            raise ConciliacaoInvalidaError(
                f"Transação {transacao_id} não encontrada nesta conta"
            )
        return tx


def _scorear(tx: TransacaoBancaria, titulo: TituloReceber) -> tuple[float, str]:
    """Score do match transação × título. Função pura, testável."""
    score = 0.0
    motivos: list[str] = []

    # Valor
    diff_valor = abs(tx.valor - titulo.valor)
    if diff_valor == Decimal("0"):
        score += 0.60
        motivos.append("valor exato")
    elif diff_valor <= Decimal("0.01"):
        score += 0.55
        motivos.append("valor ±R$ 0,01")
    elif diff_valor <= Decimal("1.00"):
        score += 0.30
        motivos.append(f"valor ±R$ {diff_valor:.2f}")

    # Data
    delta = abs((tx.lancado_em - titulo.data_vencimento).days)
    if delta == 0:
        score += 0.30
        motivos.append("data exata")
    elif delta <= 2:
        score += 0.25
        motivos.append(f"data ±{delta}d")
    elif delta <= 5:
        score += 0.15
        motivos.append(f"data ±{delta}d")

    # Pequeno boost se descrição contém pista do título (sequência, contrato)
    if tx.descricao_bruta:
        desc_low = tx.descricao_bruta.lower()
        if "pix" in desc_low or "transferencia" in desc_low or "transferência" in desc_low:
            score += 0.05
            motivos.append("descrição PIX/transferência")

    return min(score, 1.0), " + ".join(motivos) if motivos else "sem detalhes"
