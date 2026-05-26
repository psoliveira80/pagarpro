from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, synonym

from app.infrastructure.db.base import Base, UUIDPrimaryKeyMixin


class WebhookBruto(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "webhooks_brutos"
    __table_args__ = (
        # Multi-tenant unique: include empresa_id to allow different tenants to share
        # legitimate external_id values from upstream providers. See migration 0016.
        UniqueConstraint(
            "empresa_id", "provedor", "external_id",
            name="uq_webhooks_empresa_provedor_external",
        ),
        {"schema": "notificacoes"},
    )

    empresa_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=True
    )
    provedor: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    processado: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    processado_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    erro: Mapped[str | None] = mapped_column(Text, nullable=True)
    recebido_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    # --- Sinônimos de transição (rename PT-BR, story 12.3) ---
    processed = synonym("processado")
    provider = synonym("provedor")
    received_at = synonym("recebido_em")
