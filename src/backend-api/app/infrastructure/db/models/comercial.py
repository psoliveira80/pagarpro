from sqlalchemy import Boolean, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin


class Empresa(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "empresas"
    __table_args__ = {"schema": "comercial"}

    razao_social: Mapped[str] = mapped_column(Text, nullable=False)
    nome_fantasia: Mapped[str | None] = mapped_column(Text, nullable=True)
    cnpj: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    telefone: Mapped[str | None] = mapped_column(Text, nullable=True)
    cep: Mapped[str | None] = mapped_column(Text, nullable=True)
    logradouro: Mapped[str | None] = mapped_column(Text, nullable=True)
    numero: Mapped[str | None] = mapped_column(Text, nullable=True)
    complemento: Mapped[str | None] = mapped_column(Text, nullable=True)
    bairro: Mapped[str | None] = mapped_column(Text, nullable=True)
    cidade: Mapped[str | None] = mapped_column(Text, nullable=True)
    estado: Mapped[str | None] = mapped_column(Text, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
