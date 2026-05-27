from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, UUIDPrimaryKeyMixin


class ComprovantePagamento(UUIDPrimaryKeyMixin, Base):
    """Comprovante de pagamento PIX analisado pelo pipeline da Story 13.19.

    Idempotência por SHA-256 do arquivo (`arquivo_hash`) — enviar 2x o mesmo
    arquivo dentro da empresa retorna o registro existente.
    """

    __tablename__ = "comprovantes_pagamento"
    __table_args__ = (
        UniqueConstraint("empresa_id", "arquivo_hash", name="uniq_comprovante_empresa_hash"),
        {"schema": "financeiro"},
    )

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id", ondelete="CASCADE"), nullable=False
    )
    titulo_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("financeiro.titulos_receber.id", ondelete="SET NULL"), nullable=True
    )
    cliente_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cadastro.clientes.id", ondelete="SET NULL"), nullable=True
    )

    arquivo_url: Mapped[str] = mapped_column(Text, nullable=False)
    arquivo_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    tipo_arquivo: Mapped[str] = mapped_column(String(20), nullable=False)
    tamanho_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    metodo_analise: Mapped[str | None] = mapped_column(String(20), nullable=True)
    score_confianca: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, default=Decimal("0.00")
    )
    valor_detectado: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    data_detectada: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    pix_txid: Mapped[str | None] = mapped_column(Text, nullable=True)
    pix_e2e_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    banco_emissor: Mapped[str | None] = mapped_column(String(50), nullable=True)
    beneficiario_cnpj: Mapped[str | None] = mapped_column(String(20), nullable=True)
    beneficiario_nome: Mapped[str | None] = mapped_column(Text, nullable=True)
    pagador_nome: Mapped[str | None] = mapped_column(Text, nullable=True)
    pagador_documento: Mapped[str | None] = mapped_column(String(20), nullable=True)
    chave_pix_usada: Mapped[str | None] = mapped_column(Text, nullable=True)
    texto_bruto_ocr: Mapped[str | None] = mapped_column(Text, nullable=True)
    avisos: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="analisado")
    homologado_por_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("acesso.usuarios.id"), nullable=True
    )
    homologado_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    rejeitado_por_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("acesso.usuarios.id"), nullable=True
    )
    rejeitado_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    motivo_rejeicao: Mapped[str | None] = mapped_column(Text, nullable=True)

    origem: Mapped[str] = mapped_column(String(30), nullable=False, default="upload")
    telefone_remetente: Mapped[str | None] = mapped_column(String(20), nullable=True)

    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
