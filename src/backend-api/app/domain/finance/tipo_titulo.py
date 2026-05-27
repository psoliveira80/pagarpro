"""Tipos de título a receber (Story 13.3).

`parcela`      — mensalidade regular de locação (entra no cálculo de inadimplência)
`opcao_compra` — parcela final única; se paga, dispara transferência do veículo
`multa`        — multa contratual avulsa
`taxa`         — taxa avulsa (ex.: taxa de cadastro)
`ajuste`       — ajuste manual positivo ou negativo

Apenas `parcela` entra no cálculo de saldo devedor / inadimplência.
"""

from __future__ import annotations

from enum import StrEnum


class TipoTitulo(StrEnum):
    PARCELA = "parcela"
    OPCAO_COMPRA = "opcao_compra"
    MULTA = "multa"
    TAXA = "taxa"
    AJUSTE = "ajuste"


# Tipos que entram no cálculo padrão de saldo devedor / inadimplência
TIPOS_DEVEDORES: frozenset[TipoTitulo] = frozenset({
    TipoTitulo.PARCELA,
    TipoTitulo.MULTA,
    TipoTitulo.TAXA,
})
