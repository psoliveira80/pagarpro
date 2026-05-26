from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class ContaBancaria(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "contas_bancarias"
    __table_args__ = {"schema": "conta_bancaria"}

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    codigo_banco: Mapped[str | None] = mapped_column(Text, nullable=True)
    agencia: Mapped[str | None] = mapped_column(Text, nullable=True)
    numero_conta: Mapped[str | None] = mapped_column(Text, nullable=True)
    tipo: Mapped[str | None] = mapped_column(Text, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    transacoes: Mapped[list["TransacaoBancaria"]] = relationship(
        back_populates="conta", lazy="selectin",
    )


class TransacaoBancaria(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "transacoes_bancarias"
    __table_args__ = (
        UniqueConstraint(
            "empresa_id", "conta_id", "fitid",
            name="uq_transacoes_bancarias_empresa_conta_fitid",
        ),
        {"schema": "conta_bancaria"},
    )

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    conta_id: Mapped[UUID] = mapped_column(
        ForeignKey("conta_bancaria.contas_bancarias.id", ondelete="CASCADE"), nullable=False
    )
    fitid: Mapped[str] = mapped_column(Text, nullable=False)
    lancado_em: Mapped[date] = mapped_column(Date, nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    descricao_bruta: Mapped[str | None] = mapped_column(Text, nullable=True)
    descricao_limpa: Mapped[str | None] = mapped_column(Text, nullable=True)
    tipo: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'pendente'")
    )
    conciliado_com_tipo: Mapped[str | None] = mapped_column(Text, nullable=True)
    conciliado_com_id: Mapped[UUID | None] = mapped_column(nullable=True)
    importado_de: Mapped[str | None] = mapped_column(Text, nullable=True)
    importado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False,
    )

    conta: Mapped["ContaBancaria"] = relationship(
        back_populates="transacoes", lazy="selectin"
    )


class SessaoConciliacao(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "sessoes_conciliacao"
    __table_args__ = {"schema": "conta_bancaria"}

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    conta_id: Mapped[UUID] = mapped_column(
        ForeignKey("conta_bancaria.contas_bancarias.id", ondelete="CASCADE"), nullable=False,
    )
    periodo_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    periodo_fim: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'em_andamento'")
    )
    total_transacoes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    total_conciliadas: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    criado_por_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("acesso.usuarios.id", ondelete="SET NULL"), nullable=True,
    )
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False,
    )
    concluida_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True,
    )
