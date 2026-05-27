from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, UUIDPrimaryKeyMixin


class TemplateMensagem(UUIDPrimaryKeyMixin, Base):
    """Template Jinja2 para mensagens automatizadas (cobrança, lembretes, etc).

    empresa_id NULL  → template padrão global (fallback de fábrica).
    empresa_id !NULL → versão customizada do tenant.

    Resolução: tenant procura por empresa_id próprio + nome + canal; se não
    achar, cai pro padrão (empresa_id IS NULL).
    """

    __tablename__ = "templates_mensagem"
    __table_args__ = (
        UniqueConstraint(
            "empresa_id", "nome", "canal",
            name="uniq_template_empresa_nome_canal",
        ),
        {"schema": "comunicacao"},
    )

    empresa_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("comercial.empresas.id", ondelete="CASCADE"), nullable=True
    )
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    canal: Mapped[str] = mapped_column(String(30), nullable=False, default="whatsapp")
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
