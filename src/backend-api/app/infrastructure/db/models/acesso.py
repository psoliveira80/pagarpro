from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, LargeBinary, Text, func, text
from sqlalchemy.dialects.postgresql import CITEXT, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin


class Perfil(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "perfis"
    __table_args__ = {"schema": "acesso"}

    nome: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)

    usuarios: Mapped[list["Usuario"]] = relationship(
        secondary="acesso.usuario_perfis",
        primaryjoin="Perfil.id == UsuarioPerfil.perfil_id",
        secondaryjoin="UsuarioPerfil.usuario_id == Usuario.id",
        back_populates="perfis",
        lazy="selectin",
        viewonly=True,
    )
    permissoes: Mapped[list["Permissao"]] = relationship(
        secondary="acesso.perfil_permissoes",
        primaryjoin="Perfil.id == PerfilPermissao.perfil_id",
        secondaryjoin="PerfilPermissao.permissao_id == Permissao.id",
        back_populates="perfis",
        lazy="selectin",
        viewonly=True,
    )


class Permissao(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "permissoes"
    __table_args__ = {"schema": "acesso"}

    codigo: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)

    perfis: Mapped[list["Perfil"]] = relationship(
        secondary="acesso.perfil_permissoes",
        primaryjoin="Permissao.id == PerfilPermissao.permissao_id",
        secondaryjoin="PerfilPermissao.perfil_id == Perfil.id",
        back_populates="permissoes",
        lazy="selectin",
        viewonly=True,
    )


class PerfilPermissao(Base):
    __tablename__ = "perfil_permissoes"
    __table_args__ = {"schema": "acesso"}

    perfil_id: Mapped[UUID] = mapped_column(
        ForeignKey("acesso.perfis.id", ondelete="CASCADE"), primary_key=True
    )
    permissao_id: Mapped[UUID] = mapped_column(
        ForeignKey("acesso.permissoes.id", ondelete="CASCADE"), primary_key=True
    )


class Usuario(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "usuarios"
    __table_args__ = {"schema": "acesso"}

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    senha_hash: Mapped[str] = mapped_column(Text, nullable=False)
    nome_completo: Mapped[str] = mapped_column(Text, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    mfa_ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    mfa_secret_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    ultimo_login_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    perfis: Mapped[list["Perfil"]] = relationship(
        secondary="acesso.usuario_perfis",
        primaryjoin="Usuario.id == UsuarioPerfil.usuario_id",
        secondaryjoin="UsuarioPerfil.perfil_id == Perfil.id",
        back_populates="usuarios",
        lazy="selectin",
        viewonly=True,
    )


class UsuarioPerfil(Base):
    """Vínculo usuário ↔ perfil no contexto de uma empresa."""
    __tablename__ = "usuario_perfis"
    __table_args__ = {"schema": "acesso"}

    usuario_id: Mapped[UUID] = mapped_column(
        ForeignKey("acesso.usuarios.id", ondelete="CASCADE"), primary_key=True
    )
    perfil_id: Mapped[UUID] = mapped_column(
        ForeignKey("acesso.perfis.id"), primary_key=True
    )
    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )


class RefreshToken(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = {"schema": "acesso"}

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    usuario_id: Mapped[UUID] = mapped_column(
        ForeignKey("acesso.usuarios.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    expira_em: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    revogado_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
