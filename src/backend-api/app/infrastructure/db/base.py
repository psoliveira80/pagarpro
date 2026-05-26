from datetime import datetime
from uuid import UUID

from sqlalchemy import text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column, synonym


class Base(DeclarativeBase):
    pass


class UUIDPrimaryKeyMixin:
    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


class TimestampMixin:
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Compat aliases (Story 12.3 transition) — declared_attr required on mixins
    @declared_attr
    def created_at(cls):
        return synonym("criado_em")

    @declared_attr
    def updated_at(cls):
        return synonym("atualizado_em")


class SoftDeleteMixin:
    excluido_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        default=None,
    )

    @declared_attr
    def deleted_at(cls):
        return synonym("excluido_em")
