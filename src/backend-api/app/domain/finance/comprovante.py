"""Domain types do pipeline de análise de comprovante (Story 13.19).

Dataclasses puros, sem dependência de I/O. Usados por todas as camadas
do pipeline (BR Code, PDF texto, OCR) e pelo service orquestrador.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class MetodoAnalise(StrEnum):
    BR_CODE = "br_code"
    PDF_TEXTO = "pdf_texto"
    OCR = "ocr"
    IA = "ia"


@dataclass(frozen=True)
class EntidadesExtraidas:
    """Entidades brutas extraídas de uma camada (sem score de match ainda).

    Cada camada do pipeline produz isto. O service compõe + atribui score.
    """
    valor: Decimal | None = None
    data: datetime | None = None
    pix_txid: str | None = None
    pix_e2e_id: str | None = None
    chave_pix: str | None = None
    beneficiario_cnpj: str | None = None
    beneficiario_nome: str | None = None
    pagador_documento: str | None = None
    pagador_nome: str | None = None
    banco_emissor: str | None = None
    textos_brutos: list[str] = field(default_factory=list)


@dataclass
class ResultadoAnaliseComprovante:
    """Resultado consolidado da análise. Persistido em `comprovantes_pagamento`.

    Mutable porque o service preenche em fases: primeiro extração, depois
    matching com títulos, depois (opcional) IA de reforço.
    """
    metodo: MetodoAnalise
    score_confianca: float  # 0.0 a 1.0
    entidades: EntidadesExtraidas
    titulo_match_id: str | None = None
    titulo_match_score: float = 0.0
    avisos: list[str] = field(default_factory=list)

    def adicionar_aviso(self, aviso: str) -> None:
        if aviso not in self.avisos:
            self.avisos.append(aviso)

    def clamp_score(self) -> None:
        """Garante que score fique no intervalo [0, 1] após múltiplos ajustes."""
        self.score_confianca = max(0.0, min(1.0, self.score_confianca))
