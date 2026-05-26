from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey, LargeBinary, Text, func, text
from sqlalchemy.dialects.postgresql import INET, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class LogAuditoria(Base):
    __tablename__ = "log_auditoria"
    __table_args__ = {"schema": "logs"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    empresa_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=True
    )
    # Columns kept with original English names — migration 0015 did not rename them
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("acesso.usuarios.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    entidade: Mapped[str | None] = mapped_column(Text, nullable=True)
    entidade_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_before: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    payload_after: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    hmac_assinatura: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    module: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'info'")
    )
    severity: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'info'")
    )
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )


class LogEvento(Base):
    __tablename__ = "log_eventos"
    __table_args__ = {"schema": "logs"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    empresa_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=True
    )
    event_id: Mapped[UUID] = mapped_column(unique=True, nullable=False)
    tipo_evento: Mapped[str] = mapped_column(Text, nullable=False)
    tipo_ativo: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'")
    )
    despachado_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    processado_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    status_processamento: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'pendente'")
    )
    erro: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
