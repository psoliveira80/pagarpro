"""Payables, Suppliers, Expense Categories, and Recurring Payables API routes (Epic 5)."""

import math
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import structlog
from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentUserDep, SessionDep
from app.api.v1.schemas.payables import (
    CategoriaDespesaCreate,
    CategoriaDespesaResponse,
    CategoriaDespesaUpdate,
    DespesaRecorrenteCreate,
    DespesaRecorrenteResponse,
    DespesaRecorrenteUpdate,
    FornecedorCreate,
    FornecedorListResponse,
    FornecedorResponse,
    FornecedorUpdate,
    PagamentoRapidoRequest,
    PagamentoTituloPagarRequest,
    TituloPagarCreate,
    TituloPagarListResponse,
    TituloPagarResponse,
    TituloPagarUpdate,
)
from app.application.shared.audit_logger import AuditLogger
from app.core.correlation import get_correlation_id
from app.infrastructure.db.models.payable import (
    ExpenseCategory,
    Payable,
    RecurringPayableTemplate,
    Supplier,
)
from app.infrastructure.db.repositories.payable_repo import (
    ExpenseCategoryRepository,
    PayableRepository,
    RecurringPayableTemplateRepository,
    SupplierRepository,
)

log = structlog.get_logger()

router = APIRouter(tags=["payables"])


# ══════════════════════════════════════════════════════════════
# Expense Categories
# ══════════════════════════════════════════════════════════════

@router.post("/expense-categories", response_model=CategoriaDespesaResponse, status_code=201)
async def create_expense_category(
    body: CategoriaDespesaCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> CategoriaDespesaResponse:
    repo = ExpenseCategoryRepository(session, current_user.empresa_id)
    cat = ExpenseCategory(
        empresa_id=current_user.empresa_id,
        nome=body.nome,
        categoria_pai_id=uuid.UUID(body.categoria_pai_id) if body.categoria_pai_id else None,
        ativo=body.ativo,
    )
    await repo.create(cat)
    await session.commit()
    await session.refresh(cat)
    return CategoriaDespesaResponse.from_model(cat)


@router.get("/expense-categories", response_model=list[CategoriaDespesaResponse])
async def list_expense_categories(
    session: SessionDep,
    current_user: CurrentUserDep,
    active_only: bool = Query(True),
) -> list[CategoriaDespesaResponse]:
    repo = ExpenseCategoryRepository(session, current_user.empresa_id)
    items = await repo.list_all(active_only=active_only)
    return [CategoriaDespesaResponse.from_model(c) for c in items]


@router.get("/expense-categories/{category_id}", response_model=CategoriaDespesaResponse)
async def get_expense_category(
    category_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> CategoriaDespesaResponse:
    repo = ExpenseCategoryRepository(session, current_user.empresa_id)
    cat = await repo.get_by_id(category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return CategoriaDespesaResponse.from_model(cat)


@router.patch("/expense-categories/{category_id}", response_model=CategoriaDespesaResponse)
async def update_expense_category(
    category_id: uuid.UUID,
    body: CategoriaDespesaUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> CategoriaDespesaResponse:
    repo = ExpenseCategoryRepository(session, current_user.empresa_id)
    cat = await repo.get_by_id(category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    data = body.model_dump(exclude_unset=True)
    if "categoria_pai_id" in data and data["categoria_pai_id"] is not None:
        data["categoria_pai_id"] = uuid.UUID(data["categoria_pai_id"])
    await repo.update(cat, data)
    await session.commit()
    await session.refresh(cat)
    return CategoriaDespesaResponse.from_model(cat)


# ══════════════════════════════════════════════════════════════
# Suppliers
# ══════════════════════════════════════════════════════════════

@router.post("/suppliers", response_model=FornecedorResponse, status_code=201)
async def create_supplier(
    body: FornecedorCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> FornecedorResponse:
    repo = SupplierRepository(session, current_user.empresa_id)
    if body.cpf_cnpj:
        existing = await repo.get_by_cpf_cnpj(body.cpf_cnpj)
        if existing:
            raise HTTPException(status_code=409, detail="Supplier with this CPF/CNPJ already exists")

    supplier = Supplier(
        empresa_id=current_user.empresa_id,
        nome=body.nome,
        documento=body.cpf_cnpj,
        contato=body.contato,
        email=body.email,
        observacoes=body.observacoes,
        ativo=body.ativo,
    )
    await repo.create(supplier)
    await session.commit()
    await session.refresh(supplier)
    return FornecedorResponse.from_model(supplier)


@router.get("/suppliers", response_model=FornecedorListResponse)
async def list_suppliers(
    session: SessionDep,
    current_user: CurrentUserDep,
    search: str | None = Query(None),
    active_only: bool = Query(True),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> FornecedorListResponse:
    repo = SupplierRepository(session, current_user.empresa_id)
    items, total = await repo.list_paginated(
        search=search, active_only=active_only, page=page, size=size,
    )
    pages = math.ceil(total / size) if total > 0 else 0
    return FornecedorListResponse(
        items=[FornecedorResponse.from_model(s) for s in items],
        total=total, page=page, size=size, pages=pages,
    )


@router.get("/suppliers/{supplier_id}", response_model=FornecedorResponse)
async def get_supplier(
    supplier_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> FornecedorResponse:
    repo = SupplierRepository(session, current_user.empresa_id)
    supplier = await repo.get_by_id(supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return FornecedorResponse.from_model(supplier)


@router.patch("/suppliers/{supplier_id}", response_model=FornecedorResponse)
async def update_supplier(
    supplier_id: uuid.UUID,
    body: FornecedorUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> FornecedorResponse:
    repo = SupplierRepository(session, current_user.empresa_id)
    supplier = await repo.get_by_id(supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    data = body.model_dump(exclude_unset=True)
    await repo.update(supplier, data)
    await session.commit()
    await session.refresh(supplier)
    return FornecedorResponse.from_model(supplier)


@router.delete("/suppliers/{supplier_id}", status_code=204)
async def delete_supplier(
    supplier_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> None:
    repo = SupplierRepository(session, current_user.empresa_id)
    supplier = await repo.get_by_id(supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    await repo.soft_delete(supplier)
    await session.commit()


# ══════════════════════════════════════════════════════════════
# Payables
# ══════════════════════════════════════════════════════════════

@router.post("/payables", response_model=TituloPagarResponse, status_code=201)
async def create_payable(
    body: TituloPagarCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> TituloPagarResponse:
    repo = PayableRepository(session, current_user.empresa_id)
    payable = Payable(
        empresa_id=current_user.empresa_id,
        fornecedor_id=uuid.UUID(body.fornecedor_id) if body.fornecedor_id else None,
        categoria_id=uuid.UUID(body.categoria_id) if body.categoria_id else None,
        descricao=body.descricao,
        valor=body.valor,
        data_vencimento=body.data_vencimento,
        observacoes=body.observacoes,
        status="pendente",
        criado_por_id=current_user.id,
    )
    await repo.create(payable)

    audit = AuditLogger(session)
    await audit.record(
        action="payable.created",
        user_id=str(current_user.id),
        entity="payable",
        entity_id=str(payable.id),
        payload_after={"descricao": body.descricao, "valor": str(body.valor)},
        correlation_id=get_correlation_id(),
        module="payables",
        category="financial",
        severity="info",
    )

    await session.commit()
    await session.refresh(payable)
    return TituloPagarResponse.from_model(payable)


@router.get("/payables", response_model=TituloPagarListResponse)
async def list_payables(
    session: SessionDep,
    current_user: CurrentUserDep,
    status: str | None = Query(None),
    supplier_id: str | None = Query(None),
    category_id: str | None = Query(None),
    due_from: date | None = Query(None),
    due_to: date | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> TituloPagarListResponse:
    repo = PayableRepository(session, current_user.empresa_id)
    sid = uuid.UUID(supplier_id) if supplier_id else None
    cid = uuid.UUID(category_id) if category_id else None
    items, total = await repo.list_paginated(
        status=status, supplier_id=sid, category_id=cid,
        due_from=due_from, due_to=due_to, search=search,
        page=page, size=size,
    )
    pages = math.ceil(total / size) if total > 0 else 0
    return TituloPagarListResponse(
        items=[TituloPagarResponse.from_model(p) for p in items],
        total=total, page=page, size=size, pages=pages,
    )


@router.get("/payables/{payable_id}", response_model=TituloPagarResponse)
async def get_payable(
    payable_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> TituloPagarResponse:
    repo = PayableRepository(session, current_user.empresa_id)
    payable = await repo.get_by_id(payable_id)
    if not payable:
        raise HTTPException(status_code=404, detail="Payable not found")
    return TituloPagarResponse.from_model(payable)


@router.patch("/payables/{payable_id}", response_model=TituloPagarResponse)
async def update_payable(
    payable_id: uuid.UUID,
    body: TituloPagarUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> TituloPagarResponse:
    repo = PayableRepository(session, current_user.empresa_id)
    payable = await repo.get_by_id(payable_id)
    if not payable:
        raise HTTPException(status_code=404, detail="Payable not found")
    if payable.status == "pago":
        raise HTTPException(status_code=400, detail="Cannot update a paid payable")

    data = body.model_dump(exclude_unset=True)
    if "fornecedor_id" in data and data["fornecedor_id"] is not None:
        data["fornecedor_id"] = uuid.UUID(data["fornecedor_id"])
    if "categoria_id" in data and data["categoria_id"] is not None:
        data["categoria_id"] = uuid.UUID(data["categoria_id"])
    await repo.update(payable, data)
    await session.commit()
    await session.refresh(payable)
    return TituloPagarResponse.from_model(payable)


@router.delete("/payables/{payable_id}", status_code=204)
async def delete_payable(
    payable_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> None:
    repo = PayableRepository(session, current_user.empresa_id)
    payable = await repo.get_by_id(payable_id)
    if not payable:
        raise HTTPException(status_code=404, detail="Payable not found")
    if payable.status == "pago":
        raise HTTPException(status_code=400, detail="Cannot delete a paid payable")
    await repo.soft_delete(payable)
    await session.commit()


@router.post("/payables/{payable_id}/pay", response_model=TituloPagarResponse)
async def pay_payable(
    payable_id: uuid.UUID,
    body: PagamentoTituloPagarRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> TituloPagarResponse:
    repo = PayableRepository(session, current_user.empresa_id)
    payable = await repo.get_by_id(payable_id)
    if not payable:
        raise HTTPException(status_code=404, detail="Payable not found")
    if payable.status == "pago":
        raise HTTPException(status_code=400, detail="Payable is already paid")
    if payable.status == "cancelado":
        raise HTTPException(status_code=400, detail="Cannot pay a cancelled payable")

    payable.status = "pago"
    payable.payment_date = body.data_pagamento
    payable.payment_method = body.forma_pagamento

    audit = AuditLogger(session)
    await audit.record(
        action="payable.paid",
        user_id=str(current_user.id),
        entity="payable",
        entity_id=str(payable.id),
        payload_after={"data_pagamento": str(body.data_pagamento), "forma_pagamento": body.forma_pagamento},
        correlation_id=get_correlation_id(),
        module="payables",
        category="financial",
        severity="info",
    )

    await session.commit()
    await session.refresh(payable)
    return TituloPagarResponse.from_model(payable)


@router.post("/payables/quick-pay", response_model=TituloPagarResponse, status_code=201)
async def quick_pay(
    body: PagamentoRapidoRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> TituloPagarResponse:
    repo = PayableRepository(session, current_user.empresa_id)
    payable = Payable(
        empresa_id=current_user.empresa_id,
        fornecedor_id=uuid.UUID(body.fornecedor_id) if body.fornecedor_id else None,
        categoria_id=uuid.UUID(body.categoria_id) if body.categoria_id else None,
        descricao=body.descricao,
        valor=body.valor,
        data_vencimento=body.data_vencimento,
        data_pagamento=body.data_pagamento,
        forma_pagamento=body.forma_pagamento,
        observacoes=body.observacoes,
        status="pago",
        criado_por_id=current_user.id,
    )
    await repo.create(payable)

    audit = AuditLogger(session)
    await audit.record(
        action="payable.quick_pay",
        user_id=str(current_user.id),
        entity="payable",
        entity_id=str(payable.id),
        payload_after={"descricao": body.descricao, "valor": str(body.valor)},
        correlation_id=get_correlation_id(),
        module="payables",
        category="financial",
        severity="info",
    )

    await session.commit()
    await session.refresh(payable)
    return TituloPagarResponse.from_model(payable)


# ══════════════════════════════════════════════════════════════
# Recurring Payables
# ══════════════════════════════════════════════════════════════

@router.post("/recurring-payables", response_model=DespesaRecorrenteResponse, status_code=201)
async def create_recurring_payable(
    body: DespesaRecorrenteCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> DespesaRecorrenteResponse:
    repo = RecurringPayableTemplateRepository(session, current_user.empresa_id)
    template = RecurringPayableTemplate(
        empresa_id=current_user.empresa_id,
        fornecedor_id=uuid.UUID(body.fornecedor_id) if body.fornecedor_id else None,
        categoria_id=uuid.UUID(body.categoria_id) if body.categoria_id else None,
        descricao=body.descricao,
        valor=body.valor,
        periodicidade=body.periodicidade,
        dia_do_mes=body.dia_do_mes,
        ativo=body.ativo,
        proxima_geracao_em=body.proxima_geracao_em,
        # data_inicio é NOT NULL no novo schema; usa proxima_geracao_em como padrão
        data_inicio=body.proxima_geracao_em,
        criado_por_id=current_user.id,
    )
    await repo.create(template)
    await session.commit()
    await session.refresh(template)
    return DespesaRecorrenteResponse.from_model(template)


@router.get("/recurring-payables", response_model=list[DespesaRecorrenteResponse])
async def list_recurring_payables(
    session: SessionDep,
    current_user: CurrentUserDep,
    active_only: bool = Query(True),
) -> list[DespesaRecorrenteResponse]:
    repo = RecurringPayableTemplateRepository(session, current_user.empresa_id)
    items = await repo.list_all(active_only=active_only)
    return [DespesaRecorrenteResponse.from_model(t) for t in items]


@router.get("/recurring-payables/{template_id}", response_model=DespesaRecorrenteResponse)
async def get_recurring_payable(
    template_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> DespesaRecorrenteResponse:
    repo = RecurringPayableTemplateRepository(session, current_user.empresa_id)
    template = await repo.get_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Recurring payable template not found")
    return DespesaRecorrenteResponse.from_model(template)


@router.patch("/recurring-payables/{template_id}", response_model=DespesaRecorrenteResponse)
async def update_recurring_payable(
    template_id: uuid.UUID,
    body: DespesaRecorrenteUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> DespesaRecorrenteResponse:
    repo = RecurringPayableTemplateRepository(session, current_user.empresa_id)
    template = await repo.get_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Recurring payable template not found")
    data = body.model_dump(exclude_unset=True)
    if "fornecedor_id" in data and data["fornecedor_id"] is not None:
        data["fornecedor_id"] = uuid.UUID(data["fornecedor_id"])
    if "categoria_id" in data and data["categoria_id"] is not None:
        data["categoria_id"] = uuid.UUID(data["categoria_id"])
    await repo.update(template, data)
    await session.commit()
    await session.refresh(template)
    return DespesaRecorrenteResponse.from_model(template)


@router.delete("/recurring-payables/{template_id}", status_code=204)
async def delete_recurring_payable(
    template_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> None:
    repo = RecurringPayableTemplateRepository(session, current_user.empresa_id)
    template = await repo.get_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Recurring payable template not found")
    template.ativo = False
    await session.commit()
