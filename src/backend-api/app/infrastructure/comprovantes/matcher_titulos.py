"""Match de entidades extraídas contra títulos em aberto (Story 13.19).

Heurística em ordem decrescente de peso:

- Valor exato + CNPJ destinatário = empresa + data ±2 dias → score 0.95 (+0.20 boost)
- Valor exato + data ±2 dias → score 0.85 (+0.10)
- Valor ±R$ 0,01 + CNPJ → score 0.80 (+0.05)
- Valor exato sem outros campos → score base

Retorna o melhor match disponível (maior score). Se nenhum título bate,
retorna `None` e o orquestrador marca o comprovante como "não vinculado".

Multi-tenant safe: query sempre filtra por `empresa_id`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.finance.comprovante import EntidadesExtraidas
from app.infrastructure.db.models.financeiro import TituloReceber


log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResultadoMatch:
    titulo_id: UUID
    score_match: float           # 0.0 a 1.0 — força do match
    score_boost: float           # incremento a aplicar no score do comprovante
    motivo: str                  # descrição auditável


async def encontrar_titulo_match(
    session: AsyncSession,
    empresa_id: UUID,
    entidades: EntidadesExtraidas,
    cnpj_da_empresa: str | None = None,
) -> ResultadoMatch | None:
    """Tenta casar as entidades extraídas com 1 título em aberto.

    Args:
        session: sessão Postgres com `app.empresa_id` setado.
        empresa_id: tenant atual.
        entidades: o que foi extraído do comprovante (valor, data, etc.).
        cnpj_da_empresa: CNPJ da empresa tenant. Se as entidades indicam
            esse CNPJ como beneficiário, ganha bonus.

    Returns:
        `ResultadoMatch` com o melhor candidato OU `None` se nada bate.
    """
    if entidades.valor is None:
        return None

    # Janela de busca: títulos em aberto/em atraso com valor próximo ±1¢
    valor_min = entidades.valor - Decimal("0.01")
    valor_max = entidades.valor + Decimal("0.01")

    # Filtro por data: ±5 dias (janela mais generosa que vai estreitar pelo score)
    if entidades.data is not None:
        data_ref = entidades.data.date()
        data_min = data_ref - timedelta(days=5)
        data_max = data_ref + timedelta(days=5)
        filtro_data = and_(
            TituloReceber.data_vencimento >= data_min,
            TituloReceber.data_vencimento <= data_max,
        )
    else:
        filtro_data = None

    stmt = select(TituloReceber).where(
        TituloReceber.empresa_id == empresa_id,
        TituloReceber.status.in_(("em_aberto", "em_atraso")),
        TituloReceber.valor >= valor_min,
        TituloReceber.valor <= valor_max,
    )
    if filtro_data is not None:
        stmt = stmt.where(filtro_data)
    stmt = stmt.order_by(TituloReceber.data_vencimento)

    candidatos = list((await session.execute(stmt)).scalars().all())
    if not candidatos:
        return None

    # Calcula score para cada candidato e retorna o melhor
    melhor: ResultadoMatch | None = None
    for titulo in candidatos:
        resultado = _calcular_score_match(titulo, entidades, cnpj_da_empresa)
        if melhor is None or resultado.score_match > melhor.score_match:
            melhor = resultado

    return melhor


def _calcular_score_match(
    titulo: TituloReceber,
    entidades: EntidadesExtraidas,
    cnpj_da_empresa: str | None,
) -> ResultadoMatch:
    """Calcula score e boost a aplicar."""
    score = 0.6  # base por valor próximo
    boost = 0.0
    motivos: list[str] = []

    # Valor exato (sem ±1¢)
    if entidades.valor == titulo.valor:
        score = 0.75
        motivos.append("valor exato")
    elif abs(entidades.valor - titulo.valor) <= Decimal("0.01"):
        score = 0.60
        motivos.append("valor ±R$ 0,01")

    # Data próxima
    if entidades.data is not None:
        delta_dias = abs((entidades.data.date() - titulo.data_vencimento).days)
        if delta_dias == 0:
            score += 0.15
            motivos.append("data exata")
        elif delta_dias <= 2:
            score += 0.10
            motivos.append(f"data ±{delta_dias}d")
        elif delta_dias <= 5:
            score += 0.05
            motivos.append(f"data ±{delta_dias}d")

    # CNPJ beneficiário bate com empresa do tenant
    if (
        entidades.beneficiario_cnpj is not None
        and cnpj_da_empresa is not None
        and _normalizar_cnpj(entidades.beneficiario_cnpj) == _normalizar_cnpj(cnpj_da_empresa)
    ):
        score += 0.10
        boost += 0.05  # mais confiança no documento como um todo
        motivos.append("CNPJ beneficiário = empresa")

    return ResultadoMatch(
        titulo_id=titulo.id,
        score_match=min(score, 1.0),
        score_boost=boost,
        motivo=" + ".join(motivos) if motivos else "valor próximo",
    )


def _normalizar_cnpj(cnpj: str) -> str:
    """Remove formatação para comparar."""
    return "".join(c for c in cnpj if c.isdigit())
