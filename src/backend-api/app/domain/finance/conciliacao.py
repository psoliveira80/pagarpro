"""Lógica pura de conciliação de pagamentos (Story 13.9).

Sem I/O — funções recebem valores e retornam decisões. Service layer
(`ServicoTituloPago`) aplica essas decisões ao banco.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class DecisaoConciliacao(StrEnum):
    INTEGRAL = "integral"           # valor pago == valor do título
    FUNDIDO = "fundido"             # restante pequeno, funde na próxima parcela
    SEPARADO = "separado"           # restante grande, gera título novo
    EXCEDENTE = "excedente"         # valor pago > valor do título (raro, mas possível)


@dataclass(frozen=True)
class ResultadoConciliacao:
    decisao: DecisaoConciliacao
    valor_pago: Decimal
    valor_titulo: Decimal
    restante: Decimal
    """Valor que falta. Se DecisaoConciliacao.EXCEDENTE, é negativo."""


def decidir_conciliacao(
    valor_pago: Decimal,
    valor_titulo: Decimal,
    limite_fusao_pct: Decimal,
) -> ResultadoConciliacao:
    """Decide o tratamento do pagamento.

    - `INTEGRAL`: `valor_pago == valor_titulo` (com tolerância de 1 centavo).
    - `EXCEDENTE`: `valor_pago > valor_titulo` (cliente pagou a mais — raro).
    - `FUNDIDO`: restante <= `valor_titulo * limite_fusao_pct / 100`.
      Pequena diferença que economicamente não vale título novo — funde
      no próximo título em aberto do mesmo contrato.
    - `SEPARADO`: restante > limite — gera título novo `tipo='parcela'`
      apontando para o original via `titulo_origem_id`.
    """
    restante = (valor_titulo - valor_pago).quantize(Decimal("0.01"))

    # Tolerância: 1 centavo de diferença conta como integral (arredondamento de gateway)
    if abs(restante) <= Decimal("0.01"):
        return ResultadoConciliacao(
            decisao=DecisaoConciliacao.INTEGRAL,
            valor_pago=valor_pago,
            valor_titulo=valor_titulo,
            restante=Decimal("0.00"),
        )

    if restante < Decimal("0"):
        return ResultadoConciliacao(
            decisao=DecisaoConciliacao.EXCEDENTE,
            valor_pago=valor_pago,
            valor_titulo=valor_titulo,
            restante=restante,  # negativo
        )

    limite_valor = (valor_titulo * limite_fusao_pct / Decimal(100)).quantize(Decimal("0.01"))
    if restante <= limite_valor:
        return ResultadoConciliacao(
            decisao=DecisaoConciliacao.FUNDIDO,
            valor_pago=valor_pago,
            valor_titulo=valor_titulo,
            restante=restante,
        )

    return ResultadoConciliacao(
        decisao=DecisaoConciliacao.SEPARADO,
        valor_pago=valor_pago,
        valor_titulo=valor_titulo,
        restante=restante,
    )
