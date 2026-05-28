"""DTOs do pipeline de conciliação (Story 13.20).

Estruturas neutras retornadas pelos importadores (OFX, PDF, CSV) e
consumidas pelo service de conciliação.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum


class FormatoOrigem(StrEnum):
    OFX = "ofx"
    PDF = "pdf"
    CSV = "csv"
    MANUAL = "manual"


@dataclass(frozen=True)
class TransacaoImportada:
    """1 transação extraída do extrato bancário, independente do formato."""

    fitid: str  # ID único do banco (Financial Institution Transaction ID)
    data: date
    valor: Decimal  # positivo = crédito, negativo = débito
    descricao: str
    tipo: str | None = None  # 'pix', 'ted', 'doc', 'tarifa', etc., quando identificável

    @property
    def eh_credito(self) -> bool:
        return self.valor > 0


@dataclass(frozen=True)
class ResultadoImportacao:
    """Saída dos importadores."""

    formato: FormatoOrigem
    transacoes: list[TransacaoImportada]
    periodo_inicio: date | None = None
    periodo_fim: date | None = None
    nome_banco: str | None = None
    erros: list[str] = field(default_factory=list)
