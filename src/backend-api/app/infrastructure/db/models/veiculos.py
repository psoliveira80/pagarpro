from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Integer, Numeric, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.infrastructure.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin


class Veiculo(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "veiculos"
    __table_args__ = (
        UniqueConstraint("empresa_id", "placa", name="uq_veiculos_empresa_placa"),
        {"schema": "veiculos"},
    )

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    placa: Mapped[str] = mapped_column(Text, nullable=False)
    renavam: Mapped[str | None] = mapped_column(Text, nullable=True)
    chassi: Mapped[str | None] = mapped_column(Text, nullable=True)
    cor: Mapped[str | None] = mapped_column(Text, nullable=True)
    ano_fabricacao: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ano_modelo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fipe_codigo: Mapped[str | None] = mapped_column(Text, nullable=True)
    fipe_marca: Mapped[str | None] = mapped_column(Text, nullable=True)
    fipe_modelo: Mapped[str | None] = mapped_column(Text, nullable=True)
    fipe_valor_atual: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    fipe_atualizado_em: Mapped[date | None] = mapped_column(Date, nullable=True)
    rastreador_codigo: Mapped[str | None] = mapped_column(Text, nullable=True)
    rastreador_imei: Mapped[str | None] = mapped_column(Text, nullable=True)
    chip_operadora: Mapped[str | None] = mapped_column(Text, nullable=True)
    chip_numero: Mapped[str | None] = mapped_column(Text, nullable=True)
    seguro_vencimento: Mapped[date | None] = mapped_column(Date, nullable=True)
    ipva_vencimento: Mapped[date | None] = mapped_column(Date, nullable=True)
    licenciamento_vencimento: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'disponivel'")
    )
    foto_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Denormalized — circular FK with contrato.contratos.veiculo_id. use_alter=True
    # lets SQLAlchemy create the constraint via ALTER TABLE after both tables exist
    # (needed for Base.metadata.create_all() in tests; Alembic migration 0015 also
    # creates this constraint via ALTER post-hoc).
    contrato_ativo_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "contrato.contratos.id",
            use_alter=True,
            name="fk_veiculos_contrato_ativo",
        ),
        nullable=True,
    )
    cliente_atual_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cadastro.clientes.id"), nullable=True
    )
    # Story 13.3 — proprietário após opção de compra exercida (status='alienado')
    proprietario_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cadastro.clientes.id"), nullable=True
    )
    criado_por_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("acesso.usuarios.id"), nullable=True
    )

    aquisicao: Mapped["AquisicaoVeiculo | None"] = relationship(
        back_populates="veiculo", uselist=False, lazy="selectin"
    )
    dispositivos_rastreamento: Mapped[list["DispositivoRastreamento"]] = relationship(
        back_populates="veiculo", lazy="selectin"
    )

    # --- Compat aliases (Story 12.3 transition) ---
    plate = synonym("placa")
    color = synonym("cor")
    year_of_manufacture = synonym("ano_fabricacao")
    fab_year = synonym("ano_fabricacao")
    model_year = synonym("ano_modelo")
    fipe_code = synonym("fipe_codigo")
    fipe_brand = synonym("fipe_marca")
    brand = synonym("fipe_marca")  # old separate field; now derived from FIPE
    fipe_model = synonym("fipe_modelo")
    model_name = synonym("fipe_modelo")  # old separate field; now derived from FIPE
    fipe_current_value = synonym("fipe_valor_atual")
    fipe_value = synonym("fipe_valor_atual")
    fipe_updated_at = synonym("fipe_atualizado_em")
    customer_id = synonym("cliente_atual_id")
    tracker_code = synonym("rastreador_codigo")
    tracker_imei = synonym("rastreador_imei")
    insurance_expiry = synonym("seguro_vencimento")
    ipva_expiry = synonym("ipva_vencimento")
    licensing_expiry = synonym("licenciamento_vencimento")
    photo_url = synonym("foto_url")
    notes = synonym("observacoes")
    current_contract_id = synonym("contrato_ativo_id")
    current_customer_id = synonym("cliente_atual_id")
    created_by_user_id = synonym("criado_por_id")
    acquisition = synonym("aquisicao")


class AquisicaoVeiculo(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "aquisicoes_veiculo"
    __table_args__ = {"schema": "veiculos"}

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    veiculo_id: Mapped[UUID] = mapped_column(
        ForeignKey("veiculos.veiculos.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    data_aquisicao: Mapped[date] = mapped_column(Date, nullable=False)
    valor_aquisicao: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    entrada: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, server_default=text("0")
    )
    parcelas: Mapped[list | None] = mapped_column(
        JSONB, nullable=True, server_default=text("'[]'")
    )
    taxa_juros: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    sistema_amortizacao: Mapped[str | None] = mapped_column(Text, nullable=True)

    veiculo: Mapped["Veiculo"] = relationship(back_populates="aquisicao")

    # --- Compat aliases (Story 12.3 transition) ---
    vehicle_id = synonym("veiculo_id")
    kind = synonym("tipo")
    acquisition_type = synonym("tipo")
    acquisition_date = synonym("data_aquisicao")
    purchase_date = synonym("data_aquisicao")
    acquisition_value = synonym("valor_aquisicao")
    purchase_price = synonym("valor_aquisicao")
    down_payment = synonym("entrada")
    installments = synonym("parcelas")
    interest_rate = synonym("taxa_juros")
    amortization_system = synonym("sistema_amortizacao")
    vehicle = synonym("veiculo")


class DispositivoRastreamento(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "dispositivos_rastreamento"
    __table_args__ = (
        UniqueConstraint("empresa_id", "serial", name="uq_dispositivos_empresa_serial"),
        {"schema": "veiculos"},
    )

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    veiculo_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("veiculos.veiculos.id"), nullable=True
    )
    serial: Mapped[str] = mapped_column(Text, nullable=False)
    modelo: Mapped[str | None] = mapped_column(Text, nullable=True)
    fabricante: Mapped[str | None] = mapped_column(Text, nullable=True)
    imei: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'ativo'")
    )
    ultima_posicao_lat: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    ultima_posicao_lng: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    ultima_comunicacao_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    veiculo: Mapped["Veiculo | None"] = relationship(back_populates="dispositivos_rastreamento")

    # --- Sinônimos de transição (rename PT-BR, story 12.3) ---
    vehicle_id = synonym("veiculo_id")
    device_id = synonym("serial")
    provider = synonym("fabricante")
    vehicle = synonym("veiculo")
