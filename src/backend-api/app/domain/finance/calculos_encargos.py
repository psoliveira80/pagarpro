"""Cálculo de encargos sobre títulos a receber (Story 13.8).

Funções puras (sem I/O, sem session) — facilita testes unitários e
reuso por outros pontos (preview no frontend, simulação de quitação, etc).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Encargos:
    """Resultado do cálculo de encargos para um título em atraso."""
    valor_base: Decimal
    multa: Decimal
    juros: Decimal
    valor_atualizado: Decimal
    dias_atraso: int
    dentro_da_carencia: bool


def calcular_encargos(
    valor_base: Decimal,
    data_vencimento: date,
    hoje: date,
    dias_carencia: int,
    percentual_multa: Decimal,
    percentual_juros_dia: Decimal,
) -> Encargos:
    """Calcula multa + juros sobre `valor_base`.

    Regra de negócio (FR-CORE-CR-X — políticas configuráveis):
    - Atraso ≤ `dias_carencia`: sem encargos (`valor_atualizado = valor_base`).
    - Atraso > `dias_carencia`: aplica `multa` fixa (D+1 após vencimento)
      + `juros_dia × dias_atraso` (composto linear, não exponencial).

    `juros_dia` é fração do dia. Default 0.0333% ≈ 1%/mês.
    """
    dias_atraso = (hoje - data_vencimento).days
    dentro_da_carencia = dias_atraso <= dias_carencia

    if dentro_da_carencia or dias_atraso <= 0:
        return Encargos(
            valor_base=valor_base,
            multa=Decimal("0.00"),
            juros=Decimal("0.00"),
            valor_atualizado=valor_base,
            dias_atraso=max(dias_atraso, 0),
            dentro_da_carencia=True,
        )

    multa = (valor_base * percentual_multa / Decimal(100)).quantize(Decimal("0.01"))
    juros = (
        valor_base * percentual_juros_dia / Decimal(100) * Decimal(dias_atraso)
    ).quantize(Decimal("0.01"))
    valor_atualizado = (valor_base + multa + juros).quantize(Decimal("0.01"))

    return Encargos(
        valor_base=valor_base,
        multa=multa,
        juros=juros,
        valor_atualizado=valor_atualizado,
        dias_atraso=dias_atraso,
        dentro_da_carencia=False,
    )
