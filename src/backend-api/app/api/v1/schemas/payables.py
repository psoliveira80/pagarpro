"""Pydantic schemas for payables, suppliers, expense categories, and reports (story 12-3c PT-BR puro)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# --- Categorias de Despesa ---

class CategoriaDespesaCreate(BaseModel):
    nome: str
    categoria_pai_id: str | None = None
    ativo: bool = True


class CategoriaDespesaUpdate(BaseModel):
    nome: str | None = None
    categoria_pai_id: str | None = None
    ativo: bool | None = None


class CategoriaDespesaResponse(BaseModel):
    id: str
    nome: str
    categoria_pai_id: str | None
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime

    @classmethod
    def from_model(cls, m: object) -> "CategoriaDespesaResponse":
        return cls(
            id=str(m.id),  # type: ignore[union-attr]
            nome=m.nome,  # type: ignore[union-attr]
            categoria_pai_id=str(m.categoria_pai_id) if m.categoria_pai_id else None,  # type: ignore[union-attr]
            ativo=m.ativo,  # type: ignore[union-attr]
            criado_em=m.created_at,  # type: ignore[union-attr]
            atualizado_em=m.updated_at,  # type: ignore[union-attr]
        )


# --- Fornecedores ---

class FornecedorCreate(BaseModel):
    nome: str
    cpf_cnpj: str | None = None
    contato: str | None = None  # ORM column é `contato` — manter alinhado
    email: str | None = None
    observacoes: str | None = None
    ativo: bool = True


class FornecedorUpdate(BaseModel):
    nome: str | None = None
    cpf_cnpj: str | None = None
    contato: str | None = None
    email: str | None = None
    observacoes: str | None = None
    ativo: bool | None = None


class FornecedorResponse(BaseModel):
    id: str
    nome: str
    cpf_cnpj: str | None
    contato: str | None
    email: str | None
    observacoes: str | None
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime

    @classmethod
    def from_model(cls, m: object) -> "FornecedorResponse":
        return cls(
            id=str(m.id),  # type: ignore[union-attr]
            nome=m.nome,  # type: ignore[union-attr]
            cpf_cnpj=m.documento,  # type: ignore[union-attr]
            contato=m.contato,  # type: ignore[union-attr]
            email=m.email,  # type: ignore[union-attr] — restored in migration 0018
            observacoes=m.observacoes,  # type: ignore[union-attr] — restored in migration 0018
            ativo=m.ativo,  # type: ignore[union-attr]
            criado_em=m.created_at,  # type: ignore[union-attr]
            atualizado_em=m.updated_at,  # type: ignore[union-attr]
        )


class FornecedorListResponse(BaseModel):
    items: list[FornecedorResponse]
    total: int
    page: int
    size: int
    pages: int


# --- Títulos a Pagar ---

class TituloPagarCreate(BaseModel):
    fornecedor_id: str | None = None
    categoria_id: str | None = None
    descricao: str
    valor: Decimal = Field(gt=0)
    data_vencimento: date
    observacoes: str | None = None


class TituloPagarUpdate(BaseModel):
    fornecedor_id: str | None = None
    categoria_id: str | None = None
    descricao: str | None = None
    valor: Decimal | None = None
    data_vencimento: date | None = None
    observacoes: str | None = None


class PagamentoTituloPagarRequest(BaseModel):
    data_pagamento: date
    forma_pagamento: str


class PagamentoRapidoRequest(BaseModel):
    fornecedor_id: str | None = None
    categoria_id: str | None = None
    descricao: str
    valor: Decimal = Field(gt=0)
    data_vencimento: date
    data_pagamento: date
    forma_pagamento: str
    observacoes: str | None = None


class TituloPagarResponse(BaseModel):
    id: str
    fornecedor_id: str | None
    categoria_id: str | None
    descricao: str
    valor: Decimal
    data_vencimento: date
    data_pagamento: date | None
    forma_pagamento: str | None
    status: str
    titulo_receber_origem_id: str | None
    observacoes: str | None
    comprovante_url: str | None
    template_id: str | None
    criado_por_id: str
    criado_em: datetime
    atualizado_em: datetime

    @classmethod
    def from_model(cls, m: object) -> "TituloPagarResponse":
        return cls(
            id=str(m.id),  # type: ignore[union-attr]
            fornecedor_id=str(m.fornecedor_id) if m.fornecedor_id else None,  # type: ignore[union-attr]
            categoria_id=str(m.category_id) if m.category_id else None,  # type: ignore[union-attr]
            descricao=m.descricao,  # type: ignore[union-attr]
            valor=m.valor,  # type: ignore[union-attr]
            data_vencimento=m.data_vencimento,  # type: ignore[union-attr]
            data_pagamento=m.data_pagamento,  # type: ignore[union-attr]
            forma_pagamento=m.forma_pagamento,  # type: ignore[union-attr]
            status=m.status,  # type: ignore[union-attr]
            titulo_receber_origem_id=str(m.titulo_receber_origem_id) if m.titulo_receber_origem_id else None,  # type: ignore[union-attr]
            observacoes=m.observacoes,  # type: ignore[union-attr]
            comprovante_url=m.comprovante_url,  # type: ignore[union-attr]
            template_id=str(m.template_id) if m.template_id else None,  # type: ignore[union-attr]
            criado_por_id=str(m.criado_por_id),  # type: ignore[union-attr]
            criado_em=m.created_at,  # type: ignore[union-attr]
            atualizado_em=m.updated_at,  # type: ignore[union-attr]
        )


class TituloPagarListResponse(BaseModel):
    items: list[TituloPagarResponse]
    total: int
    page: int
    size: int
    pages: int


# --- Despesas Recorrentes ---

class DespesaRecorrenteCreate(BaseModel):
    fornecedor_id: str | None = None
    categoria_id: str | None = None
    descricao: str
    valor: Decimal = Field(gt=0)
    periodicidade: str  # mensal/quinzenal/semanal
    dia_do_mes: int | None = None
    proxima_geracao_em: date
    ativo: bool = True


class DespesaRecorrenteUpdate(BaseModel):
    fornecedor_id: str | None = None
    categoria_id: str | None = None
    descricao: str | None = None
    valor: Decimal | None = None
    periodicidade: str | None = None
    dia_do_mes: int | None = None
    proxima_geracao_em: date | None = None
    ativo: bool | None = None


class DespesaRecorrenteResponse(BaseModel):
    id: str
    fornecedor_id: str | None
    categoria_id: str | None
    descricao: str
    valor: Decimal
    periodicidade: str
    dia_do_mes: int | None
    ativo: bool
    proxima_geracao_em: date
    criado_por_id: str
    criado_em: datetime
    atualizado_em: datetime

    @classmethod
    def from_model(cls, m: object) -> "DespesaRecorrenteResponse":
        return cls(
            id=str(m.id),  # type: ignore[union-attr]
            fornecedor_id=str(m.fornecedor_id) if m.fornecedor_id else None,  # type: ignore[union-attr]
            categoria_id=str(m.category_id) if m.category_id else None,  # type: ignore[union-attr]
            descricao=m.descricao,  # type: ignore[union-attr]
            valor=m.valor,  # type: ignore[union-attr]
            periodicidade=m.periodicidade,  # type: ignore[union-attr]
            dia_do_mes=m.dia_do_mes,  # type: ignore[union-attr]
            ativo=m.ativo,  # type: ignore[union-attr]
            proxima_geracao_em=m.proxima_geracao_em,  # type: ignore[union-attr]
            criado_por_id=str(m.criado_por_id),  # type: ignore[union-attr]
            criado_em=m.created_at,  # type: ignore[union-attr]
            atualizado_em=m.updated_at,  # type: ignore[union-attr]
        )


# --- Relatório DRE ---

class DreDetalhamentoCategoria(BaseModel):
    categoria_id: str | None
    categoria_nome: str | None
    total: Decimal


class DreSecao(BaseModel):
    total: Decimal
    por_categoria: list[DreDetalhamentoCategoria]


class DreResponse(BaseModel):
    periodo_inicio: date
    periodo_fim: date
    receitas: DreSecao
    despesas: DreSecao
    resultado_liquido: Decimal
