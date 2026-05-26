"""Pydantic schemas for bank accounts and reconciliation (story 12-3c rename PT-BR puro)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


# --- Contas Bancárias ---

class ContaBancariaCreate(BaseModel):
    nome: str
    codigo_banco: str | None = None
    nome_banco: str | None = None
    agencia: str | None = None
    numero_conta: str | None = None
    tipo: str = "corrente"


class ContaBancariaUpdate(BaseModel):
    nome: str | None = None
    codigo_banco: str | None = None
    nome_banco: str | None = None
    agencia: str | None = None
    numero_conta: str | None = None
    tipo: str | None = None
    ativo: bool | None = None


class ContaBancariaResponse(BaseModel):
    id: str
    nome: str
    codigo_banco: str | None
    nome_banco: str | None
    agencia: str | None
    numero_conta: str | None
    tipo: str
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime

    @classmethod
    def from_model(cls, m: object) -> "ContaBancariaResponse":
        return cls(
            id=str(m.id),  # type: ignore[union-attr]
            nome=m.nome,  # type: ignore[union-attr]
            codigo_banco=m.codigo_banco,  # type: ignore[union-attr]
            nome_banco=None,  # dropped in migration 0015
            agencia=m.agencia,  # type: ignore[union-attr]
            numero_conta=m.numero_conta,  # type: ignore[union-attr]
            tipo=m.tipo or "corrente",  # type: ignore[union-attr]
            ativo=m.ativo,  # type: ignore[union-attr]
            criado_em=m.criado_em,  # type: ignore[union-attr]
            atualizado_em=m.atualizado_em,  # type: ignore[union-attr]
        )


# --- Transações Bancárias ---

class TransacaoBancariaResponse(BaseModel):
    id: str
    conta_id: str
    fitid: str
    lancado_em: date
    valor: Decimal
    descricao_bruta: str | None
    descricao_limpa: str | None
    tipo: str | None
    status: str
    conciliado_com_tipo: str | None
    conciliado_com_id: str | None
    importado_de: str
    importado_em: datetime

    @classmethod
    def from_model(cls, m: object) -> "TransacaoBancariaResponse":
        return cls(
            id=str(m.id),  # type: ignore[union-attr]
            conta_id=str(m.conta_id),  # type: ignore[union-attr]
            fitid=m.fitid,  # type: ignore[union-attr]
            lancado_em=m.lancado_em,  # type: ignore[union-attr]
            valor=m.valor,  # type: ignore[union-attr]
            descricao_bruta=m.descricao_bruta,  # type: ignore[union-attr]
            descricao_limpa=m.descricao_limpa,  # type: ignore[union-attr]
            tipo=m.tipo,  # type: ignore[union-attr]
            status=m.status,  # type: ignore[union-attr]
            conciliado_com_tipo=m.conciliado_com_tipo,  # type: ignore[union-attr]
            conciliado_com_id=str(m.conciliado_com_id) if m.conciliado_com_id else None,  # type: ignore[union-attr]
            importado_de=m.importado_de or "",  # type: ignore[union-attr]
            importado_em=m.importado_em,  # type: ignore[union-attr]
        )


class TransacaoBancariaListResponse(BaseModel):
    items: list[TransacaoBancariaResponse]
    total: int
    page: int
    size: int


# --- Resumo de Importação ---

class ResumoImportacao(BaseModel):
    # Aliases EN aceitos para compat com routes que ainda não migraram.
    model_config = ConfigDict(populate_by_name=True)
    total_parseado: int = Field(validation_alias="total_parsed")
    novos_inseridos: int = Field(validation_alias="new_inserted")
    duplicatas_puladas: int = Field(validation_alias="duplicates_skipped")


# --- Conciliação ---

class ConciliarRequest(BaseModel):
    transacao_ids: list[str]
    tipo_destino: str  # titulo_receber | titulo_pagar
    destino_id: str


class SugestaoConciliacao(BaseModel):
    transacao_id: str
    tipo_destino: str
    destino_id: str
    pontuacao: float
    diferenca_valor: Decimal
    diferenca_dias: int
    similaridade_descricao: float


class AutoConciliacaoResponse(BaseModel):
    sugestoes: list[SugestaoConciliacao]


class ConfirmarConciliacaoResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    quantidade_conciliada: int = Field(validation_alias="matched_count")


# --- Divergências ---

class DivergenciaItem(BaseModel):
    categoria: str  # orfa | suspeita_paga | divergencia_valor
    tipo_entidade: str
    entidade_id: str
    descricao: str
    valor: Decimal | None = None
    lancado_em: date | None = None
    detalhes: str | None = None


class DivergenciasResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    transacoes_orfas: list[DivergenciaItem] = Field(validation_alias="orphan_transactions")
    titulos_suspeitos_pagos: list[DivergenciaItem] = Field(validation_alias="suspect_paid_titles")
    divergencias_valor: list[DivergenciaItem] = Field(validation_alias="value_mismatches")
    total_orfas: int = Field(validation_alias="total_orphan")
    total_suspeitos: int = Field(validation_alias="total_suspect")
    total_divergencias: int = Field(validation_alias="total_mismatch")


# --- Importação PDF ---

class LinhaPdfParseada(BaseModel):
    fitid: str
    lancado_em: date
    valor: Decimal
    descricao_bruta: str
    descricao_limpa: str
    tipo: str
    selecionada: bool = True


class PdfParseResponse(BaseModel):
    linhas: list[LinhaPdfParseada]
    confianca: float
    total_linhas: int


class ConfirmarPdfRequest(BaseModel):
    conta_id: str
    linhas: list[LinhaPdfParseada]


# Aliases retroativos (transição) — remover quando route migrar 100%.
ImportSummary = ResumoImportacao
PdfParsedRow = LinhaPdfParseada
PdfConfirmRequest = ConfirmarPdfRequest
DivergenceItem = DivergenciaItem
DivergencesResponse = DivergenciasResponse
MatchConfirmResponse = ConfirmarConciliacaoResponse
