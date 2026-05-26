"""Bank Account CRUD API routes (Epic 7 — Story 7.0)."""

import uuid

import structlog
from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentUserDep, SessionDep
from app.api.v1.schemas.bank import (
    ContaBancariaCreate,
    ContaBancariaResponse,
    ContaBancariaUpdate,
)
from app.application.shared.audit_logger import AuditLogger
from app.core.correlation import get_correlation_id
from app.infrastructure.db.models.bank import BankAccount
from app.infrastructure.db.repositories.bank_repo import BankAccountRepository

log = structlog.get_logger()

router = APIRouter(tags=["bank-accounts"])


@router.post("/bank-accounts", response_model=ContaBancariaResponse, status_code=201)
async def create_bank_account(
    body: ContaBancariaCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ContaBancariaResponse:
    repo = BankAccountRepository(session)
    account = BankAccount(
        empresa_id=current_user.empresa_id,
        nome=body.nome,
        codigo_banco=body.codigo_banco,
        agencia=body.agencia,
        numero_conta=body.numero_conta,
        tipo=body.tipo,
    )
    await repo.create(account)

    audit = AuditLogger(session)
    await audit.record(
        action="bank_account.created",
        user_id=str(current_user.id),
        entity="bank_account",
        entity_id=str(account.id),
        payload_after={"nome": body.nome, "nome_banco": body.nome_banco},
        correlation_id=get_correlation_id(),
        module="reconciliation",
        category="financial",
        severity="info",
    )

    await session.commit()
    await session.refresh(account)
    return ContaBancariaResponse.from_model(account)


@router.get("/bank-accounts", response_model=list[ContaBancariaResponse])
async def list_bank_accounts(
    session: SessionDep,
    current_user: CurrentUserDep,
    active_only: bool = Query(True),
) -> list[ContaBancariaResponse]:
    repo = BankAccountRepository(session)
    items = await repo.list_all(active_only=active_only)
    return [ContaBancariaResponse.from_model(a) for a in items]


@router.get("/bank-accounts/{account_id}", response_model=ContaBancariaResponse)
async def get_bank_account(
    account_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ContaBancariaResponse:
    repo = BankAccountRepository(session)
    account = await repo.get_by_id(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Bank account not found")
    return ContaBancariaResponse.from_model(account)


@router.patch("/bank-accounts/{account_id}", response_model=ContaBancariaResponse)
async def update_bank_account(
    account_id: uuid.UUID,
    body: ContaBancariaUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ContaBancariaResponse:
    repo = BankAccountRepository(session)
    account = await repo.get_by_id(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Bank account not found")
    # API agora usa nomes PT-BR; mapeamento 1:1 com colunas do model
    data = {k: v for k, v in body.model_dump(exclude_unset=True).items()
            if k != "nome_banco"}
    await repo.update(account, data)

    audit = AuditLogger(session)
    await audit.record(
        action="bank_account.updated",
        user_id=str(current_user.id),
        entity="bank_account",
        entity_id=str(account.id),
        payload_after=data,
        correlation_id=get_correlation_id(),
        module="reconciliation",
        category="financial",
        severity="info",
    )

    await session.commit()
    await session.refresh(account)
    return ContaBancariaResponse.from_model(account)


@router.delete("/bank-accounts/{account_id}", status_code=204)
async def delete_bank_account(
    account_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> None:
    repo = BankAccountRepository(session)
    account = await repo.get_by_id(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Bank account not found")
    account.ativo = False
    await session.commit()
