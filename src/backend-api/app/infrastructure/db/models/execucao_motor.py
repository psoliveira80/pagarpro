from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, UUIDPrimaryKeyMixin


class ExecucaoMotor(UUIDPrimaryKeyMixin, Base):
    """Observabilidade: 1 linha por execução de motor (Story 13.5).

    `empresa_id` NULL = execução system-wide (ex.: backup). Não NULL =
    execução por tenant (motores de cobrança).
    """

    __tablename__ = "execucoes_motor"
    __table_args__ = {"schema": "motor"}

    nome_tarefa: Mapped[str] = mapped_column(String(100), nullable=False)
    empresa_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("comercial.empresas.id", ondelete="SET NULL"), nullable=True
    )
    iniciado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    finalizado_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    total_registros: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_erros: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    situacao: Mapped[str] = mapped_column(String(20), nullable=False, default="executando")
    detalhes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
