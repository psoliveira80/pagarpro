"""Pydantic schemas for contracts (story 12-3c rename PT-BR puro)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# --- Schedule Preview ---

class PreviewPlanilhaRequest(BaseModel):
    valor_total: Decimal = Field(gt=0)
    quantidade_parcelas: int = Field(gt=0)
    data_inicio: date
    periodicidade: str = "mensal"
    taxa_juros: Decimal = Decimal("0")
    metodo: str = "fixo"
    datas_customizadas: list[date] | None = None


class PreviewTituloResponse(BaseModel):
    sequencia: int
    data_vencimento: date
    principal: Decimal
    juros: Decimal
    valor: Decimal


class PreviewPlanilhaResponse(BaseModel):
    titulos: list[PreviewTituloResponse]
    total: Decimal
    total_juros: Decimal


# --- Contrato CRUD ---

class ContratoCreate(BaseModel):
    cliente_id: str
    veiculo_id: str | None = None
    numero: str
    data_inicio: date
    data_fim: date
    valor_total: Decimal = Field(gt=0)
    observacoes: str | None = None
    clausulas_md: str | None = None
    termos: dict | None = None
    # Params de planilha — usados para auto-gerar títulos
    quantidade_parcelas: int = Field(gt=0)
    periodicidade: str = "mensal"
    taxa_juros: Decimal = Decimal("0")
    metodo: str = "fixo"
    datas_customizadas: list[date] | None = None


class ContratoUpdate(BaseModel):
    cliente_id: str | None = None
    veiculo_id: str | None = None
    numero: str | None = None
    data_inicio: date | None = None
    data_fim: date | None = None
    valor_total: Decimal | None = None
    observacoes: str | None = None
    clausulas_md: str | None = None
    termos: dict | None = None


class TituloReceberContratoResponse(BaseModel):
    """Título a receber dentro de um contrato (vista parcial — apenas campos do escopo do contrato)."""
    id: str
    contrato_id: str
    lote_id: str | None
    titulo_origem_id: str | None
    sequencia: int
    data_vencimento: date
    valor: Decimal
    valor_pago: Decimal
    status: str
    pago_em: date | None
    forma_pagamento: str | None
    comprovante_url: str | None
    observacoes: str | None
    criado_em: datetime
    atualizado_em: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, m: object) -> "TituloReceberContratoResponse":
        return cls(
            id=str(m.id),  # type: ignore[union-attr]
            contrato_id=str(m.contrato_id),  # type: ignore[union-attr]
            lote_id=str(m.lote_id) if m.lote_id else None,  # type: ignore[union-attr]
            titulo_origem_id=str(m.titulo_origem_id) if m.titulo_origem_id else None,  # type: ignore[union-attr]
            sequencia=m.sequencia,  # type: ignore[union-attr]
            data_vencimento=m.data_vencimento,  # type: ignore[union-attr]
            valor=m.valor,  # type: ignore[union-attr]
            valor_pago=m.valor_pago or Decimal("0"),  # type: ignore[union-attr]
            status=m.status,  # type: ignore[union-attr]
            pago_em=m.pago_em,  # type: ignore[union-attr]
            forma_pagamento=m.forma_pagamento,  # type: ignore[union-attr]
            comprovante_url=m.comprovante_url,  # type: ignore[union-attr]
            observacoes=m.observacoes,  # type: ignore[union-attr]
            criado_em=m.criado_em,  # type: ignore[union-attr]
            atualizado_em=m.atualizado_em,  # type: ignore[union-attr]
        )


class EventoContratoResponse(BaseModel):
    id: str
    contrato_id: str
    tipo: str
    descricao: str
    payload: dict | None
    criado_por_id: str | None
    criado_em: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, m: object) -> "EventoContratoResponse":
        return cls(
            id=str(m.id),  # type: ignore[union-attr]
            contrato_id=str(m.contrato_id),  # type: ignore[union-attr]
            tipo=m.tipo,  # type: ignore[union-attr]
            descricao=m.payload.get("description", "") if m.payload else "",  # type: ignore[union-attr]
            payload=m.payload,  # type: ignore[union-attr]
            criado_por_id=str(m.criado_por_id) if m.criado_por_id else None,  # type: ignore[union-attr]
            criado_em=m.criado_em,  # type: ignore[union-attr]
        )


class LoteGeracaoResponse(BaseModel):
    id: str
    contrato_id: str
    numero_geracao: int
    gerado_em: datetime
    gerado_por_id: str | None
    config: dict
    status: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, m: object) -> "LoteGeracaoResponse":
        return cls(
            id=str(m.id),  # type: ignore[union-attr]
            contrato_id=str(m.contrato_id),  # type: ignore[union-attr]
            numero_geracao=0,  # campo removido; usa rotulo no novo schema
            gerado_em=m.criado_em,  # type: ignore[union-attr]
            gerado_por_id=str(m.criado_por_id) if m.criado_por_id else None,  # type: ignore[union-attr]
            config={},  # campo removido em migration 0015
            status="ativo",  # campo removido em migration 0015
        )


class ContratoResponse(BaseModel):
    id: str
    cliente_id: str
    veiculo_id: str | None
    numero: str
    status: str
    data_inicio: date
    data_fim: date
    valor_total: Decimal
    observacoes: str | None
    pdf_url: str | None
    versao_pdf: int
    clausulas_md: str | None
    termos: dict | None
    criado_por_id: str | None
    criado_em: datetime
    atualizado_em: datetime
    titulos: list[TituloReceberContratoResponse] = []

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, m: object, include_installments: bool = True) -> "ContratoResponse":
        inst_list: list[TituloReceberContratoResponse] = []
        if include_installments:
            try:
                inst_list = [TituloReceberContratoResponse.from_model(i) for i in m.titulos]  # type: ignore[union-attr]
            except Exception:
                inst_list = []

        return cls(
            id=str(m.id),  # type: ignore[union-attr]
            cliente_id=str(m.cliente_id),  # type: ignore[union-attr]
            veiculo_id=str(m.veiculo_id) if m.veiculo_id else None,  # type: ignore[union-attr]
            numero=m.numero,  # type: ignore[union-attr]
            status=m.status,  # type: ignore[union-attr]
            data_inicio=m.data_inicio,  # type: ignore[union-attr]
            data_fim=m.data_fim,  # type: ignore[union-attr]
            valor_total=m.valor_total,  # type: ignore[union-attr]
            observacoes=m.observacoes,  # type: ignore[union-attr]
            pdf_url=m.pdf_url,  # type: ignore[union-attr]
            versao_pdf=m.versao,  # type: ignore[union-attr]
            clausulas_md=m.clausulas_md,  # type: ignore[union-attr]
            termos=None,  # terms removed in migration 0015
            criado_por_id=str(m.criado_por_id) if m.criado_por_id else None,  # type: ignore[union-attr]
            criado_em=m.criado_em,  # type: ignore[union-attr]
            atualizado_em=m.atualizado_em,  # type: ignore[union-attr]
            titulos=inst_list,
        )


class ContratoListResponse(BaseModel):
    items: list[ContratoResponse]
    total: int
    page: int
    size: int
    pages: int


# --- Ativar ---

class AtivarContratoResponse(BaseModel):
    id: str
    status: str
    mensagem: str


# --- Rescindir ---

class RescindirContratoRequest(BaseModel):
    motivo: str
    data_efetiva: date
    valor_multa: Decimal = Decimal("0")


class ResumoRescisaoResponse(BaseModel):
    contrato_id: str
    quantidade_titulos_em_aberto: int
    total_titulos_em_aberto: Decimal
    total_pago: Decimal
    valor_multa: Decimal
    saldo_final: Decimal
    status: str


# --- Edição em Lote ---

class AcaoEdicaoLote(BaseModel):
    titulo_id: str
    acao: str  # postpone | discount | set_value | cancel
    params: dict = {}


class EdicaoLoteRequest(BaseModel):
    acoes: list[AcaoEdicaoLote]
    dry_run: bool = False


class DiffEdicaoLote(BaseModel):
    titulo_id: str
    acao: str
    valor_antigo: Decimal
    valor_novo: Decimal
    data_vencimento_antiga: date | None = None
    data_vencimento_nova: date | None = None


class EdicaoLoteResponse(BaseModel):
    aplicado: bool
    diffs: list[DiffEdicaoLote]


# --- Simular ---

class SimulacaoRequest(BaseModel):
    valor_total: Decimal = Field(gt=0)
    quantidade_parcelas: int = Field(gt=0)
    data_inicio: date
    periodicidade: str = "mensal"
    taxa_juros: Decimal = Decimal("0")
    metodo: str = "fixo"
    datas_customizadas: list[date] | None = None


class ResumoSimulacao(BaseModel):
    total_pago: Decimal
    total_juros: Decimal
    total_principal: Decimal
    taxa_efetiva: Decimal


class SimulacaoResponse(BaseModel):
    titulos: list[PreviewTituloResponse]
    resumo: ResumoSimulacao


# --- PDF ---

class PdfUrlResponse(BaseModel):
    url: str
    versao: int
