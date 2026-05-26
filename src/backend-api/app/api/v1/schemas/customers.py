"""Pydantic schemas for customers (story 12-3c rename PT-BR puro)."""

from datetime import date, datetime
from pydantic import BaseModel, EmailStr, field_validator


class EnderecoSchema(BaseModel):
    logradouro: str | None = None
    numero: str | None = None
    complemento: str | None = None
    bairro: str | None = None
    cidade: str | None = None
    estado: str | None = None
    cep: str | None = None


class ClienteCreate(BaseModel):
    nome_completo: str
    cpf_cnpj: str
    telefone: str | None = None
    email: EmailStr | None = None
    data_nascimento: date | None = None
    observacoes: str | None = None
    status: str = "ativo"
    endereco: EnderecoSchema | None = None
    tags: list[str] | None = None
    metadata_extensoes: dict | None = None

    @field_validator("cpf_cnpj")
    @classmethod
    def validate_cpf_cnpj(cls, v: str) -> str:
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) not in (11, 14):
            raise ValueError("CPF deve ter 11 dígitos ou CNPJ 14 dígitos")
        return digits

    @field_validator("telefone")
    @classmethod
    def normalize_phone(cls, v: str | None) -> str | None:
        if v is None:
            return None
        digits = "".join(c for c in v if c.isdigit())
        if not digits:
            return None
        if not digits.startswith("55") and len(digits) <= 11:
            digits = "55" + digits
        return f"+{digits}"


class ClienteUpdate(BaseModel):
    nome_completo: str | None = None
    cpf_cnpj: str | None = None
    telefone: str | None = None
    email: EmailStr | None = None
    data_nascimento: date | None = None
    observacoes: str | None = None
    status: str | None = None
    score: int | None = None
    endereco: EnderecoSchema | None = None
    tags: list[str] | None = None
    metadata_extensoes: dict | None = None

    @field_validator("cpf_cnpj")
    @classmethod
    def validate_cpf_cnpj(cls, v: str | None) -> str | None:
        if v is None:
            return None
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) not in (11, 14):
            raise ValueError("CPF deve ter 11 dígitos ou CNPJ 14 dígitos")
        return digits

    @field_validator("telefone")
    @classmethod
    def normalize_phone(cls, v: str | None) -> str | None:
        if v is None:
            return None
        digits = "".join(c for c in v if c.isdigit())
        if not digits:
            return None
        if not digits.startswith("55") and len(digits) <= 11:
            digits = "55" + digits
        return f"+{digits}"


class ClienteResponse(BaseModel):
    id: str
    nome_completo: str
    cpf_cnpj: str
    telefone: str | None
    email: str | None
    data_nascimento: date | None
    foto_url: str | None
    observacoes: str | None
    score: int
    status: str
    endereco: EnderecoSchema | None
    tags: list[str] | None
    metadata_extensoes: dict | None
    criado_em: datetime
    atualizado_em: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, m: object) -> "ClienteResponse":
        return cls(
            id=str(m.id),  # type: ignore[union-attr]
            nome_completo=m.nome_completo,  # type: ignore[union-attr]
            cpf_cnpj=m.cpf_cnpj,  # type: ignore[union-attr]
            telefone=m.telefone,  # type: ignore[union-attr]
            email=m.email,  # type: ignore[union-attr]
            data_nascimento=m.data_nascimento,  # type: ignore[union-attr]
            foto_url=m.foto_url,  # type: ignore[union-attr]
            observacoes=m.observacoes,  # type: ignore[union-attr]
            score=m.score,  # type: ignore[union-attr]
            status=m.status,  # type: ignore[union-attr]
            endereco=EnderecoSchema(
                logradouro=m.logradouro,  # type: ignore[union-attr]
                numero=m.numero,  # type: ignore[union-attr]
                complemento=m.complemento,  # type: ignore[union-attr]
                bairro=m.bairro,  # type: ignore[union-attr]
                cidade=m.cidade,  # type: ignore[union-attr]
                estado=m.estado,  # type: ignore[union-attr]
                cep=m.cep,  # type: ignore[union-attr]
            ),
            tags=m.tags,  # type: ignore[union-attr]
            metadata_extensoes=m.metadata_extensoes,  # type: ignore[union-attr]
            criado_em=m.criado_em,  # type: ignore[union-attr]
            atualizado_em=m.atualizado_em,  # type: ignore[union-attr]
        )


class PaginatedResponse(BaseModel):
    items: list[ClienteResponse]
    total: int
    page: int
    size: int
    pages: int


class AnexoClienteResponse(BaseModel):
    id: str
    cliente_id: str
    tipo: str
    url: str
    mime: str | None
    tamanho_bytes: int | None
    criado_em: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, m: object) -> "AnexoClienteResponse":
        return cls(
            id=str(m.id),  # type: ignore[union-attr]
            cliente_id=str(m.customer_id),  # type: ignore[union-attr]
            tipo=m.tipo,  # type: ignore[union-attr]
            url=m.url,  # type: ignore[union-attr]
            mime=m.mime_type,  # type: ignore[union-attr]
            tamanho_bytes=m.tamanho_bytes,  # type: ignore[union-attr]
            criado_em=m.criado_em,  # type: ignore[union-attr]
        )
