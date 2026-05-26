from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.infrastructure.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.infrastructure.db.models.contrato import Contrato


class TituloReceber(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "titulos_receber"
    __table_args__ = (
        UniqueConstraint(
            "empresa_id", "contrato_id", "sequencia",
            name="uq_titulos_receber_empresa_contrato_seq",
        ),
        {"schema": "financeiro"},
    )

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    contrato_id: Mapped[UUID] = mapped_column(
        ForeignKey("contrato.contratos.id"), nullable=False
    )
    lote_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("contrato.lotes_geracao.id"), nullable=True
    )
    sequencia: Mapped[int] = mapped_column(nullable=False)
    data_vencimento: Mapped[date] = mapped_column(Date, nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'em_aberto'")
    )
    tipo: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'regular'")
    )
    pago_em: Mapped[date | None] = mapped_column(Date, nullable=True)
    valor_pago: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    forma_pagamento: Mapped[str | None] = mapped_column(Text, nullable=True)
    comprovante_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    titulo_origem_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("financeiro.titulos_receber.id"), nullable=True
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_por_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("acesso.usuarios.id"), nullable=True
    )

    contrato: Mapped["Contrato"] = relationship(
        back_populates="titulos",
        foreign_keys=[contrato_id],
    )
    movimentos: Mapped[list["MovimentoTituloReceber"]] = relationship(
        back_populates="titulo", lazy="selectin"
    )

    # --- Compat aliases for pre-rename consumer code (Story 12.3 transition) ---
    contract_id = synonym("contrato_id")
    due_date = synonym("data_vencimento")
    amount = synonym("valor")
    original_value = synonym("valor")
    current_value = synonym("valor")  # interest/fine computed at query-time, not stored
    paid_amount = synonym("valor_pago")
    paid_value = synonym("valor_pago")
    sequence = synonym("sequencia")
    payment_date = synonym("pago_em")
    paid_at = synonym("pago_em")
    payment_method = synonym("forma_pagamento")
    receipt_url = synonym("comprovante_url")
    notes = synonym("observacoes")
    parent_installment_id = synonym("titulo_origem_id")
    generation_id = synonym("lote_id")
    number = synonym("sequencia")
    kind = synonym("tipo")
    adjustments = synonym("movimentos")


class MovimentoTituloReceber(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "movimentos_titulo_receber"
    __table_args__ = {"schema": "financeiro"}

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    titulo_id: Mapped[UUID] = mapped_column(
        ForeignKey("financeiro.titulos_receber.id"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    delta_valor: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    snapshot_antes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    snapshot_depois: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    aplicado_por_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("acesso.usuarios.id"), nullable=True
    )
    aplicado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    # Restored in migration 0018 (flat columns instead of JSONB snapshots)
    valor_anterior: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    valor_posterior: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    criado_por_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("acesso.usuarios.id"), nullable=True
    )

    titulo: Mapped["TituloReceber"] = relationship(back_populates="movimentos")

    # --- Compat aliases (Story 12.3 transition) ---
    installment_id = synonym("titulo_id")
    kind = synonym("tipo")
    amount_delta = synonym("delta_valor")
    snapshot_before = synonym("snapshot_antes")
    snapshot_after = synonym("snapshot_depois")
    reason = synonym("motivo")
    applied_by = synonym("aplicado_por_id")
    applied_at = synonym("aplicado_em")
    old_value = synonym("valor_anterior")
    new_value = synonym("valor_posterior")
    created_by_user_id = synonym("criado_por_id")


class DespesaRecorrente(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "despesas_recorrentes"
    __table_args__ = {"schema": "financeiro"}

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    fornecedor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cadastro.fornecedores.id"), nullable=True
    )
    categoria_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cadastro.categorias_despesa.id"), nullable=True
    )
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    periodicidade: Mapped[str] = mapped_column(Text, nullable=False)
    dia_do_mes: Mapped[int] = mapped_column(nullable=False)
    data_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    data_fim: Mapped[date | None] = mapped_column(Date, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    proxima_geracao_em: Mapped[date | None] = mapped_column(Date, nullable=True)
    criado_por_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("acesso.usuarios.id"), nullable=True
    )

    # --- Compat aliases (Story 12.3 transition) ---
    supplier_id = synonym("fornecedor_id")
    category_id = synonym("categoria_id")
    description = synonym("descricao")
    amount = synonym("valor")
    periodicity = synonym("periodicidade")
    frequency = synonym("periodicidade")
    day_of_month = synonym("dia_do_mes")
    start_date = synonym("data_inicio")
    end_date = synonym("data_fim")
    is_active = synonym("ativo")
    next_generation_date = synonym("proxima_geracao_em")
    created_by_user_id = synonym("criado_por_id")


class TituloPagar(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "titulos_pagar"
    __table_args__ = {"schema": "financeiro"}

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    fornecedor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cadastro.fornecedores.id"), nullable=True
    )
    categoria_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cadastro.categorias_despesa.id"), nullable=True
    )
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    data_vencimento: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'rascunho'")
    )
    data_pagamento: Mapped[date | None] = mapped_column(Date, nullable=True)
    forma_pagamento: Mapped[str | None] = mapped_column(Text, nullable=True)
    comprovante_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    titulo_receber_origem_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("financeiro.titulos_receber.id"), nullable=True
    )
    template_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("financeiro.despesas_recorrentes.id"), nullable=True
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_por_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("acesso.usuarios.id"), nullable=True
    )

    # --- Compat aliases (Story 12.3 transition) ---
    supplier_id = synonym("fornecedor_id")
    category_id = synonym("categoria_id")
    description = synonym("descricao")
    amount = synonym("valor")
    due_date = synonym("data_vencimento")
    payment_date = synonym("data_pagamento")
    paid_at = synonym("data_pagamento")
    payment_method = synonym("forma_pagamento")
    receipt_url = synonym("comprovante_url")
    linked_installment_id = synonym("titulo_receber_origem_id")
    recurring_template_id = synonym("template_id")
    notes = synonym("observacoes")
    created_by_user_id = synonym("criado_por_id")
