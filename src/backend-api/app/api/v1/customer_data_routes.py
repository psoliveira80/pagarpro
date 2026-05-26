"""LGPD data export and anonymization endpoints (Story 9-10)."""

import json
from datetime import datetime, timezone
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select, update

from app.api.deps import CurrentUserDep, SessionDep
from app.api.v1.schemas.admin import AnonymizeRequest, AnonymizeResponse
from app.application.shared.audit_logger import AuditLogger
from app.core.correlation import get_correlation_id
from app.infrastructure.db.models.contract import Contract, Installment
from app.infrastructure.db.models.customer import Customer, CustomerAttachment

log = structlog.get_logger()

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/{customer_id}/my-data")
async def export_customer_data(
    customer_id: UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> JSONResponse:
    """Export all customer data as JSON (LGPD data portability)."""
    result = await session.execute(
        select(Customer).where(
            Customer.id == customer_id,
            Customer.empresa_id == current_user.empresa_id,
        )
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Personal data
    personal = {
        "id": str(customer.id),
        "full_name": customer.nome_completo,
        "cpf_cnpj": customer.cpf_cnpj,
        "email": customer.email,
        "phone": customer.telefone,
        "birth_date": str(customer.data_nascimento) if customer.data_nascimento else None,
        "address": {
            "street": customer.logradouro,
            "number": customer.numero,
            "complement": customer.complemento,
            "neighborhood": customer.bairro,
            "city": customer.cidade,
            "state": customer.estado,
            "zip": customer.cep,
        },
        "tags": customer.tags,
        "notes": customer.observacoes,
        "status": customer.status,
        "score": customer.score,
        "created_at": customer.criado_em.isoformat(),
    }

    # Contracts
    contracts_result = await session.execute(
        select(Contract).where(
            Contract.cliente_id == customer_id,
            Contract.empresa_id == current_user.empresa_id,
        )
    )
    contracts = contracts_result.scalars().all()
    contracts_data = []
    for c in contracts:
        installments_data = []
        for inst in c.titulos:
            installments_data.append({
                "number": inst.sequencia,
                "due_date": str(inst.data_vencimento),
                "original_value": str(inst.valor),
                "current_value": str(inst.valor),
                "paid_value": str(inst.valor_pago or 0),
                "status": inst.status,
                "payment_date": str(inst.pago_em) if inst.pago_em else None,
            })
        contracts_data.append({
            "contract_number": c.numero,
            "status": c.status,
            "start_date": str(c.data_inicio),
            "end_date": str(c.data_fim),
            "total_value": str(c.valor_total),
            "installments": installments_data,
        })

    # Attachments
    attachments_result = await session.execute(
        select(CustomerAttachment).where(
            CustomerAttachment.cliente_id == customer_id,
            CustomerAttachment.empresa_id == current_user.empresa_id,
        )
    )
    attachments = attachments_result.scalars().all()
    attachments_data = [
        {"kind": a.tipo, "url": a.url, "uploaded_at": a.criado_em.isoformat()}
        for a in attachments
    ]

    export_data = {
        "export_date": datetime.now(timezone.utc).isoformat(),
        "personal_data": personal,
        "contracts": contracts_data,
        "attachments": attachments_data,
    }

    # Audit
    audit = AuditLogger(session)
    await audit.record(
        action="customer.data_exported",
        user_id=str(current_user.id),
        entity="customers",
        entity_id=str(customer_id),
        category="security",
        correlation_id=get_correlation_id(),
    )
    await session.commit()

    return JSONResponse(content=export_data)


@router.delete("/{customer_id}/anonymize", response_model=AnonymizeResponse)
async def anonymize_customer(
    customer_id: UUID,
    body: AnonymizeRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> AnonymizeResponse:
    """Anonymize customer data (LGPD right to be forgotten)."""
    # Check admin role
    roles = [(p.nome or "").lower() for p in (current_user.perfis or [])]
    if "admin" not in roles:
        raise HTTPException(status_code=403, detail="Admin role required for anonymization")

    result = await session.execute(
        select(Customer).where(
            Customer.id == customer_id,
            Customer.empresa_id == current_user.empresa_id,
        )
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Anonymize personal fields
    cpf = customer.cpf_cnpj
    masked_cpf = cpf[:3] + ".***.***-**" if len(cpf) >= 3 else "[redigido]"

    before_data = {
        "full_name": customer.nome_completo,
        "cpf_cnpj": customer.cpf_cnpj,
        "email": customer.email,
        "phone": customer.telefone,
    }

    customer.nome_completo = "[redigido]"
    customer.cpf_cnpj = masked_cpf
    customer.email = None
    customer.telefone = None
    customer.data_nascimento = None
    customer.foto_url = None
    customer.observacoes = None
    customer.logradouro = None
    customer.numero = None
    customer.complemento = None
    customer.bairro = None
    customer.cidade = None
    customer.estado = None
    customer.cep = None
    customer.tags = None
    customer.metadata_extensoes = None
    customer.status = "anonimizado"

    # Audit with security category
    audit = AuditLogger(session)
    await audit.record(
        action="customer.anonymized",
        user_id=str(current_user.id),
        entity="customers",
        entity_id=str(customer_id),
        payload_before=before_data,
        payload_after={"status": "anonimizado", "reason": body.reason},
        category="security",
        severity="critical",
        correlation_id=get_correlation_id(),
    )
    await session.commit()

    return AnonymizeResponse(
        message="Customer data anonymized successfully",
        customer_id=str(customer_id),
    )
