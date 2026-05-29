import math
import uuid

import boto3
import structlog
from botocore.config import Config as BotoConfig
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel, Field

from app.api.deps import CurrentUserDep, SessionDep
from app.api.v1.schemas.customers import (
    AnexoClienteResponse,
    ClienteCreate,
    ClienteResponse,
    ClienteUpdate,
    PaginatedResponse,
)
from app.application.shared.audit_logger import AuditLogger
from app.core.correlation import get_correlation_id
from app.infrastructure.db.models.customer import Customer, CustomerAttachment
from app.infrastructure.db.repositories.customer_repo import CustomerRepository
from app.infrastructure.settings import get_settings

log = structlog.get_logger()

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("", response_model=ClienteResponse, status_code=201)
async def create_customer(
    body: ClienteCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ClienteResponse:
    repo = CustomerRepository(session, current_user.empresa_id)

    # Check uniqueness
    existing = await repo.get_by_cpf_cnpj(body.cpf_cnpj)
    if existing:
        raise HTTPException(status_code=409, detail="CPF/CNPJ already registered")

    customer = Customer(
        empresa_id=current_user.empresa_id,
        nome_completo=body.nome_completo,
        cpf_cnpj=body.cpf_cnpj,
        telefone=body.telefone,
        email=body.email,
        data_nascimento=body.data_nascimento,
        observacoes=body.observacoes,
        status=body.status,
        tags=body.tags,
        metadata_extensoes=body.metadata_extensoes,
        criado_por_id=current_user.id,
    )
    if body.endereco:
        customer.logradouro = body.endereco.logradouro
        customer.numero = body.endereco.numero
        customer.complemento = body.endereco.complemento
        customer.bairro = body.endereco.bairro
        customer.cidade = body.endereco.cidade
        customer.estado = body.endereco.estado
        customer.cep = body.endereco.cep

    await repo.create(customer)

    # Audit
    audit = AuditLogger(session)
    await audit.record(
        action="customer.created",
        user_id=str(current_user.id),
        entity="customer",
        entity_id=str(customer.id),
        payload_after={"nome_completo": customer.nome_completo, "cpf_cnpj": customer.cpf_cnpj},
        correlation_id=get_correlation_id(),
        module="customers",
        category="data",
        severity="info",
    )

    await session.commit()
    await session.refresh(customer)
    return ClienteResponse.from_model(customer)


@router.get("", response_model=PaginatedResponse)
async def list_customers(
    session: SessionDep,
    current_user: CurrentUserDep,
    search: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse:
    repo = CustomerRepository(session, current_user.empresa_id)
    items, total = await repo.list_paginated(
        search=search, status=status, page=page, size=size
    )
    pages = math.ceil(total / size) if total > 0 else 0
    return PaginatedResponse(
        items=[ClienteResponse.from_model(c) for c in items],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get("/{customer_id}", response_model=ClienteResponse)
async def get_customer(
    customer_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ClienteResponse:
    repo = CustomerRepository(session, current_user.empresa_id)
    customer = await repo.get_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return ClienteResponse.from_model(customer)


@router.patch("/{customer_id}", response_model=ClienteResponse)
async def update_customer(
    customer_id: uuid.UUID,
    body: ClienteUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ClienteResponse:
    repo = CustomerRepository(session, current_user.empresa_id)
    customer = await repo.get_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    before = {"nome_completo": customer.nome_completo, "status": customer.status}
    update_data = body.model_dump(exclude_unset=True)

    # API agora usa nomes PT-BR puros que batem 1:1 com colunas do model.
    endereco = update_data.pop("endereco", None)
    if endereco:
        for field, value in endereco.items():
            setattr(customer, field, value)

    for field, value in update_data.items():
        setattr(customer, field, value)

    # Audit
    audit = AuditLogger(session)
    await audit.record(
        action="customer.updated",
        user_id=str(current_user.id),
        entity="customer",
        entity_id=str(customer.id),
        payload_before=before,
        payload_after={k: str(v) if hasattr(v, 'isoformat') else v for k, v in update_data.items()},
        correlation_id=get_correlation_id(),
        module="customers",
        category="data",
        severity="info",
    )

    await session.commit()
    await session.refresh(customer)
    return ClienteResponse.from_model(customer)


@router.delete("/{customer_id}", status_code=204)
async def delete_customer(
    customer_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> None:
    repo = CustomerRepository(session, current_user.empresa_id)
    customer = await repo.get_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    await repo.soft_delete(customer)

    # Audit
    audit = AuditLogger(session)
    await audit.record(
        action="customer.deleted",
        user_id=str(current_user.id),
        entity="customer",
        entity_id=str(customer.id),
        correlation_id=get_correlation_id(),
        module="customers",
        category="data",
        severity="warning",
    )

    await session.commit()


@router.post("/{customer_id}/attachments", response_model=AnexoClienteResponse, status_code=201)
async def upload_attachment(
    customer_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
    file: UploadFile = File(...),
    tipo: str = Form("documento"),
) -> AnexoClienteResponse:
    repo = CustomerRepository(session, current_user.empresa_id)
    customer = await repo.get_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    settings = get_settings()
    file_id = str(uuid.uuid4())
    filename = file.filename or "unknown"
    s3_key = f"customers/{customer_id}/{file_id}-{filename}"

    # Upload to MinIO/S3
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        config=BotoConfig(signature_version="s3v4"),
    )

    content = await file.read()
    s3.put_object(
        Bucket=settings.S3_BUCKET,
        Key=s3_key,
        Body=content,
        ContentType=file.content_type or "application/octet-stream",
    )
    s3.close()

    url = f"{settings.S3_ENDPOINT_URL}/{settings.S3_BUCKET}/{s3_key}"

    attachment = CustomerAttachment(
        empresa_id=current_user.empresa_id,
        cliente_id=customer_id,
        tipo=tipo,
        nome_arquivo=filename,
        url=url,
        mime_type=file.content_type,
        tamanho_bytes=len(content),
        criado_por_id=current_user.id,
    )
    session.add(attachment)

    # Audit
    audit = AuditLogger(session)
    await audit.record(
        action="customer.attachment_uploaded",
        user_id=str(current_user.id),
        entity="customer_attachment",
        entity_id=str(attachment.id),
        payload_after={"cliente_id": str(customer_id), "tipo": tipo, "nome_arquivo": filename},
        correlation_id=get_correlation_id(),
        module="customers",
        category="data",
        severity="info",
    )

    await session.commit()
    return AnexoClienteResponse(
        id=str(attachment.id),
        cliente_id=str(customer_id),
        tipo=tipo,
        url=url,
        mime=file.content_type,
        tamanho_bytes=len(content),
        criado_em=attachment.criado_em,
    )


# ─────────────────── Story 13.22 AC 8 — Blacklist de comprovantes ────────────


class BlacklistComprovantesRequest(BaseModel):
    ativar: bool = Field(..., description="True ativa blacklist, false desativa")
    motivo: str | None = Field(
        default=None,
        max_length=500,
        description="Motivo da inclusão/remoção (registrado em audit log)",
    )


class BlacklistComprovantesResponse(BaseModel):
    cliente_id: str
    na_blacklist_comprovantes: bool
    motivo_blacklist: str | None


@router.put(
    "/{customer_id}/blacklist-comprovantes",
    response_model=BlacklistComprovantesResponse,
)
async def alternar_blacklist_comprovantes(
    customer_id: uuid.UUID,
    body: BlacklistComprovantesRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> BlacklistComprovantesResponse:
    """Ativa/desativa blacklist de validação automática de comprovantes do
    cliente. Cliente em blacklist sempre cai em homologação manual mesmo
    com score 100 (regra de fraude — Story 13.22 AC 8).

    Restrito a roles `admin` e `financeiro` (mutação sensível, exige audit
    com `category='security'`).
    """
    permitidos = {"admin", "financeiro"}
    roles = {(p.nome or "").lower() for p in (current_user.perfis or [])}
    if not (permitidos & roles):
        raise HTTPException(
            status_code=403,
            detail="Apenas admin ou financeiro podem alterar blacklist",
        )

    repo = CustomerRepository(session, current_user.empresa_id)
    cliente = await repo.get_by_id(customer_id)
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    antes = {
        "na_blacklist_comprovantes": cliente.na_blacklist_comprovantes,
        "motivo_blacklist": cliente.motivo_blacklist,
    }
    cliente.na_blacklist_comprovantes = body.ativar
    cliente.motivo_blacklist = body.motivo if body.ativar else None
    depois = {
        "na_blacklist_comprovantes": cliente.na_blacklist_comprovantes,
        "motivo_blacklist": cliente.motivo_blacklist,
    }

    audit = AuditLogger(session)
    await audit.record(
        action=(
            "cliente.blacklist_comprovantes_ativada"
            if body.ativar
            else "cliente.blacklist_comprovantes_desativada"
        ),
        user_id=str(current_user.id),
        entity="clientes",
        entity_id=str(customer_id),
        payload_before=antes,
        payload_after=depois,
        correlation_id=get_correlation_id(),
        module="cobranca",
        category="security",
        severity="warning",
    )
    await session.commit()
    await session.refresh(cliente)
    return BlacklistComprovantesResponse(
        cliente_id=str(customer_id),
        na_blacklist_comprovantes=cliente.na_blacklist_comprovantes,
        motivo_blacklist=cliente.motivo_blacklist,
    )
