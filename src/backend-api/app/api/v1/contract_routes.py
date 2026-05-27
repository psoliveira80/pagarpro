import math
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import structlog
from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentUserDep, SessionDep
from app.api.v1.schemas.contracts import (
    AcaoEdicaoLote,
    AtivarContratoResponse,
    ContratoCreate,
    ContratoListResponse,
    ContratoResponse,
    ContratoUpdate,
    DiffEdicaoLote,
    EdicaoLoteRequest,
    EdicaoLoteResponse,
    EventoContratoResponse,
    LoteGeracaoResponse,
    PdfUrlResponse,
    PreviewPlanilhaRequest,
    PreviewPlanilhaResponse,
    PreviewTituloResponse,
    RescindirContratoRequest,
    ResumoRescisaoResponse,
    ResumoSimulacao,
    SimulacaoRequest,
    SimulacaoResponse,
)
from app.application.shared.audit_logger import AuditLogger
from app.core.correlation import get_correlation_id
from app.core.events.domain_events import ContractCreatedEvent, ContractTerminatedEvent
from app.core.events.event_bus import CeleryEventBus
from app.domain.finance.schedule_calculator import calculate_schedule
from app.domain.finance.termination_calculator import compute_termination
from app.infrastructure.db.models.contract import (
    Contract,
    ContractEvent,
    Installment,
    InstallmentAdjustment,
    InstallmentGeneration,
)
from app.infrastructure.db.repositories.contract_repo import ContractRepository
from app.workers import celery_app

log = structlog.get_logger()

router = APIRouter(prefix="/contracts", tags=["contracts"])


# ── helpers ──────────────────────────────────────────────────────

def _event_bus() -> CeleryEventBus:
    return CeleryEventBus(celery_app)


# Helpers PT-BR → EN para `calculate_schedule` (helper interno permanece em EN).
_PERIODICIDADE_PARA_EN = {"mensal": "monthly", "quinzenal": "biweekly", "semanal": "weekly"}
_METODO_PARA_EN = {"fixo": "fixed", "frances": "french", "price": "price"}


def _freq_en(p: str) -> str:
    return _PERIODICIDADE_PARA_EN.get(p, p)


def _met_en(m: str) -> str:
    return _METODO_PARA_EN.get(m, m)


# ── 3-9: Simulation (no DB) ─────────────────────────────────────

@router.post("/simulate", response_model=SimulacaoResponse)
async def simulate_contract(body: SimulacaoRequest) -> SimulacaoResponse:
    previews = calculate_schedule(
        total_value=body.valor_total,
        num_installments=body.quantidade_parcelas,
        start_date=body.data_inicio,
        frequency=_freq_en(body.periodicidade),
        interest_rate=body.taxa_juros,
        method=_met_en(body.metodo),
        custom_dates=body.datas_customizadas,
    )
    items = [
        PreviewTituloResponse(
            sequencia=p.number, data_vencimento=p.due_date,
            principal=p.principal, juros=p.interest, valor=p.value,
        )
        for p in previews
    ]
    total_paid = sum(p.value for p in previews)
    total_interest = sum(p.interest for p in previews)
    total_principal = sum(p.principal for p in previews)
    effective_rate = (
        (total_interest / total_principal * 100).quantize(Decimal("0.0001"))
        if total_principal > 0 else Decimal("0")
    )
    return SimulacaoResponse(
        titulos=items,
        resumo=ResumoSimulacao(
            total_pago=total_paid,
            total_juros=total_interest,
            total_principal=total_principal,
            taxa_efetiva=effective_rate,
        ),
    )


# ── 3-2: Preview Schedule ───────────────────────────────────────

@router.post("/preview-schedule", response_model=PreviewPlanilhaResponse)
async def preview_schedule(
    body: PreviewPlanilhaRequest,
    _current_user: CurrentUserDep,
) -> PreviewPlanilhaResponse:
    previews = calculate_schedule(
        total_value=body.valor_total,
        num_installments=body.quantidade_parcelas,
        start_date=body.data_inicio,
        frequency=_freq_en(body.periodicidade),
        interest_rate=body.taxa_juros,
        method=_met_en(body.metodo),
        custom_dates=body.datas_customizadas,
    )
    items = [
        PreviewTituloResponse(
            sequencia=p.number, data_vencimento=p.due_date,
            principal=p.principal, juros=p.interest, valor=p.value,
        )
        for p in previews
    ]
    total = sum(p.value for p in previews)
    total_interest = sum(p.interest for p in previews)
    return PreviewPlanilhaResponse(titulos=items, total=total, total_juros=total_interest)


# ── 3-2: Create Draft ───────────────────────────────────────────

@router.post("", response_model=ContratoResponse, status_code=201)
async def create_contract(
    body: ContratoCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ContratoResponse:
    repo = ContractRepository(session, current_user.empresa_id)

    existing = await repo.get_by_contract_number(body.numero)
    if existing:
        raise HTTPException(status_code=409, detail="Contract number already exists")

    contract = Contract(
        empresa_id=current_user.empresa_id,
        cliente_id=uuid.UUID(body.cliente_id),
        veiculo_id=uuid.UUID(body.veiculo_id) if body.veiculo_id else None,
        numero=body.numero,
        status="rascunho",
        data_inicio=body.data_inicio,
        data_fim=body.data_fim,
        valor_total=body.valor_total,
        modo_geracao="antecipado",
        clausulas_md=body.clausulas_md,
        criado_por_id=current_user.id,
    )
    await repo.create(contract)

    # Generate installments
    generation = InstallmentGeneration(
        empresa_id=current_user.empresa_id,
        contrato_id=contract.id,
        rotulo=f"Geração 1",
        criado_por_id=current_user.id,
        qtd_titulos=body.quantidade_parcelas,
        valor_total=body.valor_total,
    )
    await repo.add_generation(generation)

    previews = calculate_schedule(
        total_value=body.valor_total,
        num_installments=body.quantidade_parcelas,
        start_date=body.data_inicio,
        frequency=_freq_en(body.periodicidade),
        interest_rate=body.taxa_juros,
        method=_met_en(body.metodo),
        custom_dates=body.datas_customizadas,
    )

    installments = [
        Installment(
            empresa_id=current_user.empresa_id,
            contrato_id=contract.id,
            lote_id=generation.id,
            sequencia=p.number,
            data_vencimento=p.due_date,
            valor=p.value,
            valor_pago=Decimal("0"),
            status="em_aberto",
        )
        for p in previews
    ]
    await repo.add_installments(installments)

    # Contract event
    await repo.add_event(ContractEvent(
        empresa_id=current_user.empresa_id,
        contrato_id=contract.id,
        tipo="contrato_criado",
        payload={"numero": body.numero, "description": "Contract draft created"},
        criado_por_id=current_user.id,
    ))

    # Audit
    audit = AuditLogger(session)
    await audit.record(
        action="contract.created",
        user_id=str(current_user.id),
        entity="contract",
        entity_id=str(contract.id),
        payload_after={"numero": body.numero, "valor_total": str(body.valor_total)},
        correlation_id=get_correlation_id(),
        module="contracts",
        category="data",
        severity="info",
    )

    await session.commit()

    # Re-fetch with relationships
    contract = await repo.get_by_id(contract.id)
    return ContratoResponse.from_model(contract)


# ── 3-4: List Contracts ─────────────────────────────────────────

@router.get("", response_model=ContratoListResponse)
async def list_contracts(
    session: SessionDep,
    current_user: CurrentUserDep,
    search: str | None = Query(None),
    status: str | None = Query(None),
    customer_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> ContratoListResponse:
    repo = ContractRepository(session, current_user.empresa_id)
    cid = uuid.UUID(customer_id) if customer_id else None
    items, total = await repo.list_paginated(
        search=search, status=status, customer_id=cid, page=page, size=size,
    )
    pages = math.ceil(total / size) if total > 0 else 0
    return ContratoListResponse(
        items=[ContratoResponse.from_model(c, include_installments=False) for c in items],
        total=total, page=page, size=size, pages=pages,
    )


# ── 3-4: Get Contract Detail ────────────────────────────────────

@router.get("/{contract_id}", response_model=ContratoResponse)
async def get_contract(
    contract_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ContratoResponse:
    repo = ContractRepository(session, current_user.empresa_id)
    contract = await repo.get_by_id(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return ContratoResponse.from_model(contract)


# ── 3-4: Update Draft ───────────────────────────────────────────

@router.patch("/{contract_id}", response_model=ContratoResponse)
async def update_contract(
    contract_id: uuid.UUID,
    body: ContratoUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ContratoResponse:
    repo = ContractRepository(session, current_user.empresa_id)
    contract = await repo.get_by_id(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    if contract.status != "rascunho":
        raise HTTPException(status_code=400, detail="Only draft contracts can be updated")

    update_data = body.model_dump(exclude_unset=True)
    # API agora usa nomes PT-BR; mapeamento direto 1:1 com colunas do model (sem aliases).
    for field, value in update_data.items():
        if field in ("cliente_id", "veiculo_id") and value is not None:
            setattr(contract, field, uuid.UUID(value))
        else:
            setattr(contract, field, value)

    await repo.add_event(ContractEvent(
        empresa_id=current_user.empresa_id,
        contrato_id=contract.id,
        tipo="contrato_atualizado",
        payload={**update_data, "description": "Contract draft updated"},
        criado_por_id=current_user.id,
    ))

    audit = AuditLogger(session)
    await audit.record(
        action="contract.updated",
        user_id=str(current_user.id),
        entity="contract",
        entity_id=str(contract.id),
        payload_after=update_data,
        correlation_id=get_correlation_id(),
        module="contracts",
        category="data",
        severity="info",
    )

    await session.commit()
    contract = await repo.get_by_id(contract.id)
    return ContratoResponse.from_model(contract)


# ── 3-4: Activate ───────────────────────────────────────────────

@router.post("/{contract_id}/activate", response_model=AtivarContratoResponse)
async def activate_contract(
    contract_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> AtivarContratoResponse:
    repo = ContractRepository(session, current_user.empresa_id)
    contract = await repo.get_by_id(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    if contract.status != "rascunho":
        raise HTTPException(status_code=400, detail="Only draft contracts can be activated")

    # Validate required fields
    errors: list[str] = []
    if not contract.cliente_id:
        errors.append("customer_id is required")
    if not contract.data_inicio:
        errors.append("start_date is required")
    if not contract.data_fim:
        errors.append("end_date is required")
    if not contract.valor_total or contract.valor_total <= 0:
        errors.append("total_value must be > 0")
    if not contract.titulos:
        errors.append("Contract must have installments")
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))

    contract.status = "vigente"

    await repo.add_event(ContractEvent(
        empresa_id=current_user.empresa_id,
        contrato_id=contract.id,
        tipo="contrato_ativado",
        payload={"description": "Contract activated"},
        criado_por_id=current_user.id,
    ))

    audit = AuditLogger(session)
    await audit.record(
        action="contract.activated",
        user_id=str(current_user.id),
        entity="contract",
        entity_id=str(contract.id),
        correlation_id=get_correlation_id(),
        module="contracts",
        category="data",
        severity="info",
    )

    await session.commit()

    # Publish domain event (fire-and-forget via Celery)
    try:
        _event_bus().publish(ContractCreatedEvent(
            contract_id=str(contract.id),
            customer_id=str(contract.cliente_id),
        ))
    except Exception:
        log.warning("failed_to_publish_contract_created_event", contract_id=str(contract.id))

    return AtivarContratoResponse(id=str(contract.id), status="vigente", mensagem="Contrato ativado com sucesso")


# ── 3-8: Terminate ──────────────────────────────────────────────

@router.post("/{contract_id}/terminate", response_model=ResumoRescisaoResponse)
async def terminate_contract(
    contract_id: uuid.UUID,
    body: RescindirContratoRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ResumoRescisaoResponse:
    repo = ContractRepository(session, current_user.empresa_id)
    contract = await repo.get_by_id(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    if contract.status not in ("vigente", "suspenso"):
        raise HTTPException(status_code=400, detail="Only active or suspended contracts can be terminated")

    # Compute termination summary
    inst_dicts = [
        {"status": i.status, "current_value": i.valor, "paid_value": i.valor_pago or Decimal("0")}
        for i in contract.titulos
    ]
    summary = compute_termination(inst_dicts, fine_amount=body.valor_multa)

    # Cancela apenas as parcelas com vencimento posterior à data efetiva da rescisão.
    # Parcelas vencidas/em aberto ANTES da data efetiva continuam devidas (entram
    # no saldo final calculado por compute_termination).
    effective_date = body.data_efetiva
    for inst in contract.titulos:
        if inst.status in ("em_aberto", "vencido") and inst.data_vencimento > effective_date:
            old_val = inst.valor
            inst.status = "cancelado"

            adj = InstallmentAdjustment(
                empresa_id=current_user.empresa_id,
                titulo_id=inst.id,
                tipo="cancel",
                delta_valor=old_val,
                motivo=f"Contract terminated: {body.motivo} (effective {effective_date.isoformat()})",
                aplicado_por_id=current_user.id,
            )
            await repo.add_adjustment(adj)

    contract.status = "encerrado_sem_pendencia"

    await repo.add_event(ContractEvent(
        empresa_id=current_user.empresa_id,
        contrato_id=contract.id,
        tipo="contrato_encerrado",
        payload={
            "description": f"Contract terminated: {body.motivo}",
            "motivo": body.motivo,
            "data_efetiva": body.data_efetiva.isoformat(),
            "valor_multa": str(body.valor_multa),
            "saldo_final": str(summary.final_balance),
        },
        criado_por_id=current_user.id,
    ))

    audit = AuditLogger(session)
    await audit.record(
        action="contract.terminated",
        user_id=str(current_user.id),
        entity="contract",
        entity_id=str(contract.id),
        payload_after={"motivo": body.motivo, "valor_multa": str(body.valor_multa)},
        correlation_id=get_correlation_id(),
        module="contracts",
        category="data",
        severity="warning",
    )

    await session.commit()

    try:
        _event_bus().publish(ContractTerminatedEvent(
            contract_id=str(contract.id),
            customer_id=str(contract.cliente_id),
            reason=body.motivo,
        ))
    except Exception:
        log.warning("failed_to_publish_contract_terminated_event", contract_id=str(contract.id))

    return ResumoRescisaoResponse(
        contrato_id=str(contract.id),
        quantidade_titulos_em_aberto=summary.open_installments_count,
        total_titulos_em_aberto=summary.open_installments_total,
        total_pago=summary.paid_total,
        valor_multa=summary.fine_amount,
        saldo_final=summary.final_balance,
        status="encerrado_sem_pendencia",
    )


# ── 3-6: Bulk Edit ──────────────────────────────────────────────

@router.post("/{contract_id}/installments/bulk-edit", response_model=EdicaoLoteResponse)
async def bulk_edit_installments(
    contract_id: uuid.UUID,
    body: EdicaoLoteRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> EdicaoLoteResponse:
    repo = ContractRepository(session, current_user.empresa_id)
    contract = await repo.get_by_id(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    diffs: list[DiffEdicaoLote] = []

    for action_item in body.acoes:
        inst = await repo.get_installment(uuid.UUID(action_item.titulo_id))
        if not inst or inst.contrato_id != contract_id:
            raise HTTPException(
                status_code=404,
                detail=f"Installment {action_item.titulo_id} not found in this contract",
            )
        if inst.status not in ("em_aberto", "vencido"):
            raise HTTPException(
                status_code=400,
                detail=f"Installment {action_item.titulo_id} is not open (status={inst.status})",
            )

        old_value = inst.valor
        old_due_date = inst.data_vencimento
        new_value = old_value
        new_due_date = old_due_date

        if action_item.acao == "postpone":
            new_due_date_str = action_item.params.get("new_due_date")
            if not new_due_date_str:
                raise HTTPException(status_code=400, detail="new_due_date is required for postpone")
            from datetime import date as date_type
            new_due_date = date_type.fromisoformat(new_due_date_str)

        elif action_item.acao == "discount":
            pct = action_item.params.get("percentage")
            fixed = action_item.params.get("fixed")
            if pct is not None:
                discount = (old_value * Decimal(str(pct)) / 100).quantize(Decimal("0.01"))
                new_value = old_value - discount
            elif fixed is not None:
                new_value = old_value - Decimal(str(fixed))
            else:
                raise HTTPException(status_code=400, detail="percentage or fixed is required for discount")
            if new_value < 0:
                new_value = Decimal("0")

        elif action_item.acao == "set_value":
            val = action_item.params.get("value")
            if val is None:
                raise HTTPException(status_code=400, detail="value is required for set_value")
            new_value = Decimal(str(val))

        elif action_item.acao == "cancel":
            new_value = Decimal("0")

        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action_item.acao}")

        diff = DiffEdicaoLote(
            titulo_id=str(inst.id),
            acao=action_item.acao,
            valor_antigo=old_value,
            valor_novo=new_value,
            data_vencimento_antiga=old_due_date if action_item.acao == "postpone" else None,
            data_vencimento_nova=new_due_date if action_item.acao == "postpone" else None,
        )
        diffs.append(diff)

        if not body.dry_run:
            inst.valor = new_value
            if action_item.acao == "postpone":
                inst.data_vencimento = new_due_date
            if action_item.acao == "cancel":
                inst.status = "cancelado"

            adj = InstallmentAdjustment(
                empresa_id=current_user.empresa_id,
                titulo_id=inst.id,
                tipo=action_item.acao,
                delta_valor=new_value - old_value,
                motivo=action_item.params.get("reason", action_item.acao),
                aplicado_por_id=current_user.id,
            )
            await repo.add_adjustment(adj)

            await repo.add_event(ContractEvent(
                empresa_id=current_user.empresa_id,
                contrato_id=contract_id,
                tipo=f"titulo_{action_item.acao}",
                payload={
                    "description": f"Installment #{inst.sequencia} {action_item.acao}: {old_value} -> {new_value}",
                    "installment_id": str(inst.id),
                    "action": action_item.acao,
                    "old_value": str(old_value),
                    "new_value": str(new_value),
                },
                criado_por_id=current_user.id,
            ))

    if not body.dry_run:
        await session.commit()

    return EdicaoLoteResponse(aplicado=not body.dry_run, diffs=diffs)


# ── 3-7: Contract Event Timeline ────────────────────────────────

@router.get("/{contract_id}/events")
async def list_contract_events(
    contract_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> dict:
    repo = ContractRepository(session, current_user.empresa_id)
    contract = await repo.get_by_id(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    items, total = await repo.get_events_paginated(contract_id, page=page, size=size)
    pages = math.ceil(total / size) if total > 0 else 0
    return {
        "items": [EventoContratoResponse.from_model(e) for e in items],
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }


# ── 3-5: PDF ────────────────────────────────────────────────────

@router.get("/{contract_id}/pdf", response_model=PdfUrlResponse)
async def get_contract_pdf(
    contract_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> PdfUrlResponse:
    repo = ContractRepository(session, current_user.empresa_id)
    contract = await repo.get_by_id(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    if not contract.pdf_url:
        # Trigger PDF generation
        try:
            celery_app.send_task(
                "app.workers.tasks.render_contract_pdf.render_contract_pdf",
                args=[str(contract.id)],
                queue="default",
            )
        except Exception:
            log.warning("failed_to_enqueue_pdf_task", contract_id=str(contract.id))
        raise HTTPException(status_code=202, detail="PDF generation enqueued. Try again later.")

    # Return presigned URL
    import boto3
    from botocore.config import Config as BotoConfig
    from app.infrastructure.settings import get_settings

    settings = get_settings()
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        config=BotoConfig(signature_version="s3v4"),
    )

    # Extract key from pdf_url
    key = contract.pdf_url
    if key.startswith("http"):
        # Strip the endpoint + bucket prefix
        prefix = f"{settings.S3_ENDPOINT_URL}/{settings.S3_BUCKET}/"
        if key.startswith(prefix):
            key = key[len(prefix):]

    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET, "Key": key},
        ExpiresIn=3600,
    )
    s3.close()

    return PdfUrlResponse(url=url, version=getattr(contract, "pdf_version", 1))


# ── 3-10: Generation Management ─────────────────────────────────

@router.get("/{contract_id}/generations")
async def list_generations(
    contract_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> list[LoteGeracaoResponse]:
    repo = ContractRepository(session, current_user.empresa_id)
    contract = await repo.get_by_id(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    gens = await repo.get_generations(contract_id)
    return [LoteGeracaoResponse.from_model(g) for g in gens]


@router.post("/{contract_id}/generations/{generation_id}/rollback")
async def rollback_generation(
    contract_id: uuid.UUID,
    generation_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> dict:
    repo = ContractRepository(session, current_user.empresa_id)
    contract = await repo.get_by_id(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    generation = await repo.get_generation(generation_id)
    if not generation or generation.contrato_id != contract_id:
        raise HTTPException(status_code=404, detail="Generation not found in this contract")

    if generation.revertido_em is not None:
        raise HTTPException(status_code=400, detail="Generation already rolled back")

    installments = await repo.get_installments_by_generation(generation_id)
    has_paid = any(i.status in ("pago", "pago_parcial", "pago_aguardando_verificacao") for i in installments)

    if has_paid:
        # Bulk cancel — cannot hard delete paid installments
        for inst in installments:
            if inst.status in ("em_aberto", "vencido"):
                inst.status = "cancelado"
        method = "bulk_cancel"
    else:
        # Hard delete — no paid installments
        await repo.hard_delete_installments([i.id for i in installments])
        method = "hard_delete"

    from datetime import datetime, timezone
    generation.revertido_em = datetime.now(timezone.utc)
    generation.revertido_por_id = current_user.id

    await repo.add_event(ContractEvent(
        empresa_id=current_user.empresa_id,
        contrato_id=contract_id,
        tipo="geracao_revertida",
        payload={
            "description": f"Generation '{generation.rotulo}' rolled back ({method})",
            "generation_id": str(generation_id),
            "method": method,
        },
        criado_por_id=current_user.id,
    ))

    await session.commit()
    return {"generation_id": str(generation_id), "method": method, "status": "rolled_back"}
