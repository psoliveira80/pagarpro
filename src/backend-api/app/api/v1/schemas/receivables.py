"""Pydantic schemas for receivables endpoints (story 12-3c rename PT-BR)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# --- Listagem ---

class TituloReceberItem(BaseModel):
    id: str
    empresa_id: str
    contrato_id: str
    sequencia: int
    data_vencimento: date
    valor: Decimal
    valor_pago: Decimal
    status: str
    pago_em: date | None = None
    forma_pagamento: str | None = None
    comprovante_url: str | None = None
    observacoes: str | None = None
    criado_em: datetime
    atualizado_em: datetime

    @classmethod
    def from_model(cls, m: object) -> "TituloReceberItem":
        return cls(
            id=str(m.id),  # type: ignore[union-attr]
            empresa_id=str(m.empresa_id),  # type: ignore[union-attr]
            contrato_id=str(m.contrato_id),  # type: ignore[union-attr]
            sequencia=m.sequencia,  # type: ignore[union-attr]
            data_vencimento=m.data_vencimento,  # type: ignore[union-attr]
            valor=m.valor,  # type: ignore[union-attr]
            valor_pago=m.valor_pago or Decimal("0"),  # type: ignore[union-attr]
            status=m.status,  # type: ignore[union-attr]
            pago_em=m.pago_em,  # type: ignore[union-attr]
            forma_pagamento=m.forma_pagamento,  # type: ignore[union-attr]
            comprovante_url=m.comprovante_url,  # type: ignore[union-attr]
            observacoes=m.observacoes,  # type: ignore[union-attr]
            criado_em=m.created_at,  # type: ignore[union-attr]
            atualizado_em=m.updated_at,  # type: ignore[union-attr]
        )


class TituloReceberAgregados(BaseModel):
    total_em_aberto: Decimal
    total_vencido: Decimal
    total_pago: Decimal


class TituloReceberListResponse(BaseModel):
    items: list[TituloReceberItem]
    total: int
    page: int
    size: int
    pages: int
    agregados: TituloReceberAgregados


# --- Valor Atualizado ---

class ValorAtualizadoResponse(BaseModel):
    original: Decimal
    juros: Decimal
    multa: Decimal
    desconto: Decimal
    total: Decimal


# --- Baixa (Write-Off) ---

class BaixaRequest(BaseModel):
    valor: Decimal = Field(gt=0)
    pago_em: date
    forma_pagamento: str
    comprovante_arquivo: str | None = None  # base64 ou URL


class BaixaResponse(BaseModel):
    id: str
    status: str
    valor_pago: Decimal
    mensagem: str


# --- Baixa Parcial ---

class BaixaParcialRequest(BaseModel):
    valor: Decimal = Field(gt=0)
    pago_em: date
    forma_pagamento: str


class BaixaParcialResponse(BaseModel):
    id: str
    status: str
    valor_pago: Decimal
    titulo_remanescente_id: str
    valor_remanescente: Decimal
    mensagem: str


# --- Validação de Comprovante ---

class ValidacaoComprovanteRequest(BaseModel):
    aprovado: bool
    observacoes: str = ""


class ValidacaoComprovanteResponse(BaseModel):
    id: str
    status: str
    mensagem: str


class ReenvioComprovanteRequest(BaseModel):
    observacoes: str = ""


# --- Pix QR ---

class PixQrResponse(BaseModel):
    brcode: str
    qr_imagem_base64: str


# --- Renegociação ---

class NovaPlanilhaParams(BaseModel):
    valor_total: Decimal = Field(gt=0)
    quantidade_parcelas: int = Field(gt=0)
    data_inicio: date
    periodicidade: str = "mensal"
    metodo: str = "fixo"


class RenegociarRequest(BaseModel):
    titulos_ids: list[str]
    nova_planilha: NovaPlanilhaParams


class RenegociarResponse(BaseModel):
    quantidade_original: int
    novos_titulos: list[TituloReceberItem]
    mensagem: str


# --- Estorno ---

class EstornoRequest(BaseModel):
    valor: Decimal | None = None  # None = estorno total
    motivo: str


class EstornoResponse(BaseModel):
    id: str
    tipo_movimento: str
    valor_estornado: Decimal
    titulo_pagar_id: str | None = None
    mensagem: str


# --- Baixa em Lote ---

class BaixaLoteRequest(BaseModel):
    titulos_ids: list[str]
    valor_total: Decimal = Field(gt=0)
    pago_em: date
    forma_pagamento: str


class BaixaLoteResultado(BaseModel):
    titulo_id: str
    valor_aplicado: Decimal
    status: str


class BaixaLoteResponse(BaseModel):
    resultados: list[BaixaLoteResultado]
    total_aplicado: Decimal
    restante: Decimal
    mensagem: str
