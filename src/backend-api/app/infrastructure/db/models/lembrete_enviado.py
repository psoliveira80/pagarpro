from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, UUIDPrimaryKeyMixin


class LembreteEnviado(UUIDPrimaryKeyMixin, Base):
    """Idempotência de envio de mensagem (Story 13.5).

    Índice único `(titulo_id, tipo, DATE(enviado_em))` impede reenvio do
    mesmo tipo de lembrete pro mesmo título no mesmo dia (definido em UTC).
    """

    __tablename__ = "lembretes_enviados"
    __table_args__ = {"schema": "financeiro"}

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id", ondelete="CASCADE"), nullable=False
    )
    titulo_id: Mapped[UUID] = mapped_column(
        ForeignKey("financeiro.titulos_receber.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    canal: Mapped[str] = mapped_column(String(30), nullable=False)
    enviado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    sucesso: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    erro: Mapped[str | None] = mapped_column(Text, nullable=True)
