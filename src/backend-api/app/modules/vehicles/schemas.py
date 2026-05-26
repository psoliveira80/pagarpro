"""Pydantic DTOs para o módulo Vehicle (story 12-3c rename PT-BR puro)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, field_validator

import re

# Plate patterns
_MERCOSUL_RE = re.compile(r"^[A-Z]{3}[0-9][A-Z][0-9]{2}$")
_LEGACY_RE = re.compile(r"^[A-Z]{3}[0-9]{4}$")


def validar_placa(v: str) -> str:
    """Valida e normaliza uma placa brasileira."""
    normalized = v.upper().replace("-", "").replace(" ", "")
    if not (_MERCOSUL_RE.match(normalized) or _LEGACY_RE.match(normalized)):
        raise ValueError(
            "Placa deve ser Mercosul (AAA0A00) ou modelo antigo (AAA0000)"
        )
    return normalized


# Alias retroativo — test_vehicles ainda importa `validate_plate`.
# Mantido até o teste ser atualizado para usar `validar_placa`.
validate_plate = validar_placa


# ---------------------------------------------------------------------------
# Aquisição
# ---------------------------------------------------------------------------

class AquisicaoCreate(BaseModel):
    tipo_aquisicao: str = "compra"
    preco_compra: Decimal | None = None
    data_compra: date | None = None
    banco_financiamento: str | None = None
    contrato_financiamento: str | None = None
    parcelas_financiamento: int | None = None
    valor_mensal_financiamento: Decimal | None = None
    observacoes: str | None = None


class AquisicaoResponse(BaseModel):
    id: str
    veiculo_id: str
    tipo_aquisicao: str
    preco_compra: Decimal | None
    data_compra: date | None
    banco_financiamento: str | None
    contrato_financiamento: str | None
    parcelas_financiamento: int | None
    valor_mensal_financiamento: Decimal | None
    observacoes: str | None
    criado_em: datetime
    atualizado_em: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, m: Any) -> "AquisicaoResponse":
        # Campos de financiamento ficam no JSONB `parcelas` desde migration 0015
        financing = m.parcelas or {}
        return cls(
            id=str(m.id),
            veiculo_id=str(m.vehicle_id),
            tipo_aquisicao=m.acquisition_type,
            preco_compra=m.purchase_price,
            data_compra=m.purchase_date,
            banco_financiamento=financing.get("financing_bank"),
            contrato_financiamento=financing.get("financing_contract"),
            parcelas_financiamento=financing.get("financing_installments"),
            valor_mensal_financiamento=financing.get("financing_monthly_value"),
            observacoes=financing.get("notes"),
            criado_em=m.created_at,
            atualizado_em=m.updated_at,
        )


# ---------------------------------------------------------------------------
# Veículo
# ---------------------------------------------------------------------------

class VeiculoCreate(BaseModel):
    placa: str
    marca: str
    modelo: str
    ano_modelo: int
    ano_fabricacao: int
    cor: str | None = None
    chassi: str | None = None
    renavam: str | None = None
    codigo_fipe: str | None = None
    valor_fipe: Decimal | None = None
    status: str = "disponivel"
    cliente_id: str | None = None
    rastreador_id: str | None = None
    metadados: dict | None = None
    aquisicao: AquisicaoCreate | None = None

    @field_validator("placa")
    @classmethod
    def _normalize_placa(cls, v: str) -> str:
        return validar_placa(v)


class VeiculoUpdate(BaseModel):
    placa: str | None = None
    marca: str | None = None
    modelo: str | None = None
    ano_modelo: int | None = None
    ano_fabricacao: int | None = None
    cor: str | None = None
    chassi: str | None = None
    renavam: str | None = None
    codigo_fipe: str | None = None
    valor_fipe: Decimal | None = None
    status: str | None = None
    cliente_id: str | None = None
    rastreador_id: str | None = None
    metadados: dict | None = None

    @field_validator("placa")
    @classmethod
    def _normalize_placa(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return validar_placa(v)


class VeiculoResponse(BaseModel):
    id: str
    placa: str
    marca: str
    modelo: str
    ano_modelo: int
    ano_fabricacao: int
    cor: str | None
    chassi: str | None
    renavam: str | None
    codigo_fipe: str | None
    valor_fipe: Decimal | None
    status: str
    cliente_id: str | None
    asset_id: str | None  # depreciated: tabela Asset removida; mantemos por compat externa
    rastreador_id: str | None
    metadados: dict | None
    aquisicao: AquisicaoResponse | None
    criado_em: datetime
    atualizado_em: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, m: Any) -> "VeiculoResponse":
        acq = None
        if m.acquisition:
            acq = AquisicaoResponse.from_model(m.acquisition)
        return cls(
            id=str(m.id),
            placa=m.plate,
            marca=m.brand,
            modelo=m.model_name,
            ano_modelo=m.model_year,
            ano_fabricacao=m.fab_year,
            cor=m.color,
            chassi=m.chassi,
            renavam=m.renavam,
            codigo_fipe=m.fipe_code,
            valor_fipe=m.fipe_value,
            status=m.status,
            cliente_id=str(m.customer_id) if m.customer_id else None,
            asset_id=str(m.id),  # tabela Asset removida em 0015; id do veículo é o asset id
            rastreador_id=None,  # campo dropado do schema Veiculo
            metadados=None,  # campo dropado do schema Veiculo
            aquisicao=acq,
            criado_em=m.created_at,
            atualizado_em=m.updated_at,
        )


class VeiculoPaginatedResponse(BaseModel):
    items: list[VeiculoResponse]
    total: int
    page: int
    size: int
    pages: int


class VeiculoFinanceiroResponse(BaseModel):
    veiculo_id: str
    valor_fipe: Decimal | None
    aquisicao: AquisicaoResponse | None


# ---------------------------------------------------------------------------
# Rastreador (Tracker)
# ---------------------------------------------------------------------------

class DispositivoRastreamentoCreate(BaseModel):
    fabricante: str
    serial: str
    config: dict | None = None


class DispositivoRastreamentoResponse(BaseModel):
    id: str
    veiculo_id: str | None
    fabricante: str | None
    serial: str
    config: dict | None
    ultima_posicao: dict | None
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, m: Any) -> "DispositivoRastreamentoResponse":
        last_pos = None
        if m.ultima_posicao_lat is not None and m.ultima_posicao_lng is not None:
            last_pos = {
                "lat": float(m.ultima_posicao_lat),
                "lng": float(m.ultima_posicao_lng),
                "em": m.ultima_comunicacao_em.isoformat() if m.ultima_comunicacao_em else None,
            }
        return cls(
            id=str(m.id),
            veiculo_id=str(m.veiculo_id) if m.veiculo_id else None,
            fabricante=m.fabricante,
            serial=m.serial,
            config={"modelo": m.modelo, "imei": m.imei} if (m.modelo or m.imei) else None,
            ultima_posicao=last_pos,
            ativo=(m.status == "ativo"),
            criado_em=m.criado_em,
            atualizado_em=m.atualizado_em,
        )


class BloqueioDesbloqueioRequest(BaseModel):
    senha: str
    motivo: str | None = None


# ---------------------------------------------------------------------------
# FIPE
# ---------------------------------------------------------------------------

class FipeMarcaResponse(BaseModel):
    codigo: str
    nome: str


class FipeModeloResponse(BaseModel):
    codigo: str
    nome: str


class FipeAnoResponse(BaseModel):
    codigo: str
    nome: str


class FipePrecoResponse(BaseModel):
    preco: str
    marca: str
    modelo: str
    ano_modelo: int
    combustivel: str
    codigo_fipe: str
    mes_referencia: str
    tipo_veiculo: int
