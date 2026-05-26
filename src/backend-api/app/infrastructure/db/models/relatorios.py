from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class RelatorioSalvo(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "relatorios_salvos"
    __table_args__ = {"schema": "relatorios"}

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    filtros: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'")
    )
    colunas: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'")
    )
    criado_por_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("acesso.usuarios.id"), nullable=True
    )
