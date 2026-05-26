from datetime import date, datetime
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, SmallInteger, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.infrastructure.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin


class CategoriaDespesa(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "categorias_despesa"
    __table_args__ = {"schema": "cadastro"}

    empresa_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=True
    )
    categoria_pai_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cadastro.categorias_despesa.id"), nullable=True
    )
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    cor: Mapped[str | None] = mapped_column(Text, nullable=True)
    icone: Mapped[str | None] = mapped_column(Text, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    ordem: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("0"))

    filhos: Mapped[list["CategoriaDespesa"]] = relationship(
        back_populates="pai", lazy="selectin",
    )
    pai: Mapped["CategoriaDespesa | None"] = relationship(
        back_populates="filhos", remote_side="CategoriaDespesa.id", lazy="selectin",
    )

    # --- Compat aliases (Story 12.3 transition) ---
    parent_id = synonym("categoria_pai_id")
    name = synonym("nome")
    color = synonym("cor")
    icon = synonym("icone")
    is_active = synonym("ativo")
    sort_order = synonym("ordem")
    children = synonym("filhos")
    parent = synonym("pai")


class Cliente(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "clientes"
    __table_args__ = (
        UniqueConstraint("empresa_id", "cpf_cnpj", name="uq_clientes_empresa_cpf_cnpj"),
        {"schema": "cadastro"},
    )

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    nome_completo: Mapped[str] = mapped_column(Text, nullable=False)
    cpf_cnpj: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    telefone: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_nascimento: Mapped[date | None] = mapped_column(nullable=True)
    cep: Mapped[str | None] = mapped_column(Text, nullable=True)
    logradouro: Mapped[str | None] = mapped_column(Text, nullable=True)
    numero: Mapped[str | None] = mapped_column(Text, nullable=True)
    complemento: Mapped[str | None] = mapped_column(Text, nullable=True)
    bairro: Mapped[str | None] = mapped_column(Text, nullable=True)
    cidade: Mapped[str | None] = mapped_column(Text, nullable=True)
    estado: Mapped[str | None] = mapped_column(Text, nullable=True)
    foto_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("100"))
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'ativo'")
    )
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True, server_default=text("'[]'"))
    metadata_extensoes: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, server_default=text("'{}'")
    )
    criado_por_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("acesso.usuarios.id"), nullable=True
    )

    # --- Compat aliases (Story 12.3 transition) ---
    full_name = synonym("nome_completo")
    name = synonym("nome_completo")
    phone = synonym("telefone")
    birth_date = synonym("data_nascimento")
    zip_code = synonym("cep")
    street = synonym("logradouro")
    number_addr = synonym("numero")
    complement = synonym("complemento")
    neighborhood = synonym("bairro")
    city = synonym("cidade")
    state = synonym("estado")
    photo_url = synonym("foto_url")
    notes = synonym("observacoes")
    metadata_extensions = synonym("metadata_extensoes")
    created_by_user_id = synonym("criado_por_id")


class AnexoCliente(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "anexos_cliente"
    __table_args__ = {"schema": "cadastro"}

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    cliente_id: Mapped[UUID] = mapped_column(
        ForeignKey("cadastro.clientes.id", ondelete="CASCADE"), nullable=False
    )
    nome_arquivo: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    tamanho_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_por_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("acesso.usuarios.id"), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )


class Fornecedor(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "fornecedores"
    __table_args__ = {"schema": "cadastro"}

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    documento: Mapped[str | None] = mapped_column(Text, nullable=True)
    contato: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)  # restored in migration 0018
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)  # restored in migration 0018
    dados_bancarios: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'")
    )
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    # --- Compat aliases (Story 12.3 transition) ---
    name = synonym("nome")
    document = synonym("documento")
    cpf_cnpj = synonym("documento")
    contact = synonym("contato")
    phone = synonym("contato")
    notes = synonym("observacoes")
    bank_data = synonym("dados_bancarios")
    is_active = synonym("ativo")
