from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func, text
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
    # Story 13.20 — cross-reference com comprovante PIX já analisado (13.19),
    # quando o pagamento foi homologado antes do extrato chegar.
    comprovante_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("financeiro.comprovantes_pagamento.id", ondelete="SET NULL"),
        nullable=True,
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
    # Story 13.20 — origem do arquivo importado
    nome_arquivo_origem: Mapped[str | None] = mapped_column(Text, nullable=True)
    hash_arquivo: Mapped[str | None] = mapped_column(String(64), nullable=True)
    formato_origem: Mapped[str | None] = mapped_column(String(10), nullable=True)


class MatchConciliacao(UUIDPrimaryKeyMixin, Base):
    """Story 13.20 — vínculo entre transação bancária e título.

    Permite desfazer em até 30 dias. Auditoria completa de quem aplicou,
    quem desfez, e cross-check com comprovante (13.19).

    Índice único parcial `(transacao_id) WHERE desfeito_em IS NULL`:
    apenas 1 match vigente por transação; após desfazer, libera para
    novo match.
    """

    __tablename__ = "matches_conciliacao"
    __table_args__ = {"schema": "conta_bancaria"}

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id", ondelete="CASCADE"), nullable=False
    )
    sessao_id: Mapped[UUID] = mapped_column(
        ForeignKey("conta_bancaria.sessoes_conciliacao.id", ondelete="CASCADE"),
        nullable=False,
    )
    transacao_id: Mapped[UUID] = mapped_column(
        ForeignKey("conta_bancaria.transacoes_bancarias.id", ondelete="CASCADE"),
        nullable=False,
    )
    titulo_id: Mapped[UUID] = mapped_column(
        ForeignKey("financeiro.titulos_receber.id", ondelete="CASCADE"),
        nullable=False,
    )
    score_match: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    motivo_match: Mapped[str | None] = mapped_column(Text, nullable=True)
    aplicado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False,
    )
    aplicado_por_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("acesso.usuarios.id", ondelete="SET NULL"), nullable=True,
    )
    desfeito_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True,
    )
    desfeito_por_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("acesso.usuarios.id", ondelete="SET NULL"), nullable=True,
    )
    motivo_desfazer: Mapped[str | None] = mapped_column(Text, nullable=True)
    ja_existia_via_comprovante: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
    )
