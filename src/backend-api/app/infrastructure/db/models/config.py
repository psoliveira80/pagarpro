from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class ConfiguracaoSistema(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "configuracoes_sistema"
    __table_args__ = (
        UniqueConstraint("empresa_id", "chave", name="uq_configuracoes_empresa_chave"),
        {"schema": "config"},
    )

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    chave: Mapped[str] = mapped_column(Text, nullable=False)
    valor: Mapped[dict] = mapped_column(JSONB, nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    atualizado_por_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("acesso.usuarios.id"), nullable=True
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )


class PoliticaEventoModulo(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "politicas_eventos_modulo"
    __table_args__ = {"schema": "config"}

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    # Column names kept as-is from migration 0015 (module_id, policy not renamed)
    module_id: Mapped[str] = mapped_column(Text, nullable=False)
    tipo_evento: Mapped[str] = mapped_column(Text, nullable=False)
    policy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class CredencialIntegracao(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "credenciais_integracao"
    __table_args__ = (
        UniqueConstraint(
            "empresa_id", "categoria", "provedor",
            name="uq_credenciais_empresa_categoria_provedor",
        ),
        {"schema": "config"},
    )

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    categoria: Mapped[str] = mapped_column(Text, nullable=False)
    provedor: Mapped[str] = mapped_column(Text, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'")
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'inativo'")
    )
    ultimo_health_check: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
