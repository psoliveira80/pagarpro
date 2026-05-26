from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, SmallInteger, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.infrastructure.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.infrastructure.db.models.financeiro import TituloReceber


class Contrato(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "contratos"
    __table_args__ = (
        UniqueConstraint("empresa_id", "numero", name="uq_contratos_empresa_numero"),
        {"schema": "contrato"},
    )

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    numero: Mapped[str] = mapped_column(Text, nullable=False)
    cliente_id: Mapped[UUID] = mapped_column(
        ForeignKey("cadastro.clientes.id"), nullable=False
    )
    veiculo_id: Mapped[UUID] = mapped_column(
        ForeignKey("veiculos.veiculos.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'rascunho'")
    )
    data_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    data_fim: Mapped[date | None] = mapped_column(Date, nullable=True)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    periodicidade: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'mensal'")
    )
    dia_vencimento: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    juros_mora_dia_pct: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False, server_default=text("0")
    )
    multa_mora_pct: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False, server_default=text("0")
    )
    dias_carencia: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    modo_geracao: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'antecipado'")
    )
    indice_correcao: Mapped[str | None] = mapped_column(Text, nullable=True)
    dia_geracao: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    proxima_geracao_em: Mapped[date | None] = mapped_column(Date, nullable=True)
    valor_base_mensal: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    tem_opcao_compra: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    valor_residual: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    clausulas_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)  # restored in 0019
    pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    versao: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("1"))
    assinado_em: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    encerrado_em: Mapped[date | None] = mapped_column(Date, nullable=True)
    motivo_encerramento: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_por_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("acesso.usuarios.id"), nullable=True
    )

    titulos: Mapped[list["TituloReceber"]] = relationship(
        back_populates="contrato",
        lazy="selectin",
        order_by="TituloReceber.sequencia",
        foreign_keys="TituloReceber.contrato_id",
    )
    eventos: Mapped[list["EventoContrato"]] = relationship(
        back_populates="contrato",
        lazy="selectin",
        order_by="EventoContrato.criado_em.desc()",
    )
    lotes: Mapped[list["LoteGeracao"]] = relationship(
        back_populates="contrato", lazy="selectin"
    )

    # --- Compat aliases (Story 12.3 transition) ---
    customer_id = synonym("cliente_id")
    asset_id = synonym("veiculo_id")
    contract_number = synonym("numero")
    start_date = synonym("data_inicio")
    end_date = synonym("data_fim")
    total_value = synonym("valor_total")
    total_amount = synonym("valor_total")
    due_day = synonym("dia_vencimento")
    periodicity = synonym("periodicidade")
    late_interest_pct_per_day = synonym("juros_mora_dia_pct")
    late_fine_pct = synonym("multa_mora_pct")
    grace_days = synonym("dias_carencia")
    generation_mode = synonym("modo_geracao")
    correction_index = synonym("indice_correcao")
    generation_day = synonym("dia_geracao")
    next_generation_date = synonym("proxima_geracao_em")
    monthly_base_value = synonym("valor_base_mensal")
    has_purchase_option = synonym("tem_opcao_compra")
    residual_value = synonym("valor_residual")
    terms_md = synonym("clausulas_md")
    notes = synonym("observacoes")
    version = synonym("versao")
    signed_at = synonym("assinado_em")
    terminated_at = synonym("encerrado_em")
    termination_reason = synonym("motivo_encerramento")
    created_by_user_id = synonym("criado_por_id")


class EventoContrato(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "eventos_contrato"
    __table_args__ = {"schema": "contrato"}

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    contrato_id: Mapped[UUID] = mapped_column(
        ForeignKey("contrato.contratos.id"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    criado_por_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("acesso.usuarios.id"), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    contrato: Mapped["Contrato"] = relationship(back_populates="eventos")

    # --- Compat aliases (Story 12.3 transition) ---
    contract_id = synonym("contrato_id")
    event_type = synonym("tipo")
    kind = synonym("tipo")
    created_by_user_id = synonym("criado_por_id")
    created_at = synonym("criado_em")


class LoteGeracao(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "lotes_geracao"
    __table_args__ = {"schema": "contrato"}

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    contrato_id: Mapped[UUID] = mapped_column(
        ForeignKey("contrato.contratos.id", ondelete="CASCADE"), nullable=False
    )
    rotulo: Mapped[str] = mapped_column(Text, nullable=False)
    qtd_titulos: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    valor_total: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, server_default=text("0")
    )
    tem_movimento_financeiro: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    criado_por_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("acesso.usuarios.id"), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    revertido_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    revertido_por_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("acesso.usuarios.id"), nullable=True
    )

    contrato: Mapped["Contrato"] = relationship(back_populates="lotes")
