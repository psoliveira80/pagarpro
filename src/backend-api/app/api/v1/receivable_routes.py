"""Receivables API routes (Epic 4)."""

import base64
import io
import math
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import structlog
from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentUserDep, SessionDep
from app.api.v1.schemas.receivables import (
    BaixaLoteRequest,
    BaixaLoteResponse,
    BaixaLoteResultado,
    BaixaParcialRequest,
    BaixaParcialResponse,
    BaixaRequest,
    BaixaResponse,
    EstornoRequest,
    EstornoResponse,
    PixQrResponse,
    ReenvioComprovanteRequest,
    RenegociarRequest,
    RenegociarResponse,
    TituloReceberAgregados,
    TituloReceberItem,
    TituloReceberListResponse,
    ValidacaoComprovanteRequest,
    ValidacaoComprovanteResponse,
    ValorAtualizadoResponse,
)
from app.application.shared.audit_logger import AuditLogger
from app.core.correlation import get_correlation_id
from app.domain.finance.calculations import compute_updated_value
from app.domain.finance.pix_brcode import generate_pix_brcode
from app.domain.finance.schedule_calculator import calculate_schedule
from app.infrastructure.db.models.contract import (
    Installment,
    InstallmentAdjustment,
)
from app.infrastructure.db.models.payable import Payable
from app.infrastructure.db.repositories.receivable_repo import ReceivableRepository

log = structlog.get_logger()

router = APIRouter(prefix="/receivables", tags=["receivables"])


# ── 4-1: Master Receivables List ──────────────────────────────

@router.get("", response_model=TituloReceberListResponse)
async def list_receivables(
    session: SessionDep,
    current_user: CurrentUserDep,
    status: str | None = Query(None),
    customer_id: str | None = Query(None),
    due_from: date | None = Query(None),
    due_to: date | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("due_date"),
    sort_dir: str = Query("asc"),
) -> TituloReceberListResponse:
    repo = ReceivableRepository(session, current_user.empresa_id)
    cid = uuid.UUID(customer_id) if customer_id else None

    items, total = await repo.list_paginated(
        status=status, customer_id=cid,
        due_from=due_from, due_to=due_to,
        search=search, page=page, size=size,
        sort_by=sort_by, sort_dir=sort_dir,
    )
    pages = math.ceil(total / size) if total > 0 else 0

    aggregates_raw = await repo.get_aggregates(
        customer_id=cid, due_from=due_from, due_to=due_to, search=search,
    )
    # Repo retorna chaves EN (total_due/overdue/paid); mapeamos pra PT-BR.
    agregados = TituloReceberAgregados(
        total_em_aberto=aggregates_raw["total_due"],
        total_vencido=aggregates_raw["total_overdue"],
        total_pago=aggregates_raw["total_paid"],
    )

    return TituloReceberListResponse(
        items=[TituloReceberItem.from_model(i) for i in items],
        total=total, page=page, size=size, pages=pages,
        agregados=agregados,
    )


# ── 4-2: Updated Value Calculation ────────────────────────────

@router.get("/{installment_id}/updated-value", response_model=ValorAtualizadoResponse)
async def get_updated_value(
    installment_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
    on_date: date | None = Query(None),
) -> ValorAtualizadoResponse:
    repo = ReceivableRepository(session, current_user.empresa_id)
    inst = await repo.get_installment(installment_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Installment not found")

    result = compute_updated_value(
        original_value=inst.current_value,
        due_date=inst.due_date,
        payment_date=on_date,
    )
    # Helper interno retorna chaves EN (original/interest/fine/discount/total);
    # convertemos pra PT-BR como contrato externo do schema (story 12-3c).
    return ValorAtualizadoResponse(
        original=result["original"],
        juros=result["interest"],
        multa=result["fine"],
        desconto=result["discount"],
        total=result["total"],
    )


# ── 4-3: Manual Write-Off ─────────────────────────────────────

@router.post("/{installment_id}/write-off", response_model=BaixaResponse)
async def write_off(
    installment_id: uuid.UUID,
    body: BaixaRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> BaixaResponse:
    repo = ReceivableRepository(session, current_user.empresa_id)
    inst = await repo.get_installment(installment_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Installment not found")
    if inst.status not in ("em_aberto", "vencido", "pago_parcial"):
        raise HTTPException(status_code=400, detail=f"Cannot write-off installment with status={inst.status}")

    receipt_url = None
    if body.comprovante_arquivo:
        # Upload receipt to MinIO
        receipt_url = await _upload_receipt(body.comprovante_arquivo, str(installment_id))
        inst.receipt_url = receipt_url
        inst.status = "pago_aguardando_verificacao"
    else:
        inst.status = "pago"

    inst.paid_value = body.valor
    inst.payment_date = body.pago_em
    inst.payment_method = body.forma_pagamento

    # Audit
    audit = AuditLogger(session)
    await audit.record(
        action="receivable.write_off",
        user_id=str(current_user.id),
        entity="installment",
        entity_id=str(inst.id),
        payload_after={"valor": str(body.valor), "status": inst.status},
        correlation_id=get_correlation_id(),
        module="receivables",
        category="financial",
        severity="info",
    )

    await session.commit()

    return BaixaResponse(
        id=str(inst.id),
        status=inst.status,
        valor_pago=inst.paid_value,
        mensagem="Baixa registrada com sucesso",
    )


# ── 4-4: Partial Payment ──────────────────────────────────────

@router.post("/{installment_id}/partial-write-off", response_model=BaixaParcialResponse)
async def partial_write_off(
    installment_id: uuid.UUID,
    body: BaixaParcialRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> BaixaParcialResponse:
    repo = ReceivableRepository(session, current_user.empresa_id)
    inst = await repo.get_installment(installment_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Installment not found")
    if inst.status not in ("em_aberto", "vencido", "pago_parcial"):
        raise HTTPException(status_code=400, detail=f"Cannot partially pay installment with status={inst.status}")
    if body.valor >= inst.current_value - inst.paid_value:
        raise HTTPException(status_code=400, detail="Valor excede ou iguala o saldo. Use baixa total.")

    # Update original installment
    inst.paid_value = inst.paid_value + body.valor
    inst.status = "pago_parcial"
    inst.payment_date = body.pago_em
    inst.payment_method = body.forma_pagamento

    # Create remainder installment
    remainder_value = inst.current_value - inst.paid_value
    # Find max installment number in same contract
    from sqlalchemy import select, func
    from app.infrastructure.db.models.contract import Installment as InstModel
    max_num_result = await session.execute(
        select(func.max(InstModel.number)).where(InstModel.contract_id == inst.contract_id)
    )
    max_num = max_num_result.scalar_one() or 0

    remainder = Installment(
        empresa_id=current_user.empresa_id,
        contract_id=inst.contract_id,
        generation_id=inst.generation_id,
        parent_installment_id=inst.id,
        number=max_num + 1,
        due_date=inst.due_date,
        original_value=remainder_value,
        current_value=remainder_value,
        valor_pago=Decimal("0"),  # NOT NULL on schema
        status="em_aberto",
    )
    await repo.add_installment(remainder)

    # Audit
    audit = AuditLogger(session)
    await audit.record(
        action="receivable.partial_write_off",
        user_id=str(current_user.id),
        entity="installment",
        entity_id=str(inst.id),
        payload_after={
            "valor": str(body.valor),
            "titulo_remanescente_id": str(remainder.id),
            "valor_remanescente": str(remainder_value),
        },
        correlation_id=get_correlation_id(),
        module="receivables",
        category="financial",
        severity="info",
    )

    await session.commit()

    return BaixaParcialResponse(
        id=str(inst.id),
        status=inst.status,
        valor_pago=inst.paid_value,
        titulo_remanescente_id=str(remainder.id),
        valor_remanescente=remainder_value,
        mensagem="Pagamento parcial registrado; título remanescente criado",
    )


# ── 4-6: Receipt Validation Queue ─────────────────────────────

@router.get("/validation-queue")
async def validation_queue(
    session: SessionDep,
    current_user: CurrentUserDep,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> dict:
    repo = ReceivableRepository(session, current_user.empresa_id)
    items, total = await repo.get_validation_queue(page=page, size=size)
    pages = math.ceil(total / size) if total > 0 else 0
    return {
        "items": [TituloReceberItem.from_model(i) for i in items],
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }


@router.post("/{installment_id}/validate", response_model=ValidacaoComprovanteResponse)
async def validate_receipt(
    installment_id: uuid.UUID,
    body: ValidacaoComprovanteRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ValidacaoComprovanteResponse:
    repo = ReceivableRepository(session, current_user.empresa_id)
    inst = await repo.get_installment(installment_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Installment not found")
    if inst.status != "pago_aguardando_verificacao":
        raise HTTPException(status_code=400, detail="Installment is not awaiting validation")

    if body.aprovado:
        inst.status = "pago"
        msg = "Comprovante aprovado; status definido como pago"
    else:
        inst.status = "em_aberto"
        inst.receipt_url = None
        inst.paid_value = Decimal("0")
        inst.payment_date = None
        inst.payment_method = None
        msg = "Comprovante rejeitado; status revertido para em_aberto"

    if body.observacoes:
        inst.notes = body.observacoes

    audit = AuditLogger(session)
    await audit.record(
        action="receivable.validate",
        user_id=str(current_user.id),
        entity="installment",
        entity_id=str(inst.id),
        payload_after={"aprovado": body.aprovado, "observacoes": body.observacoes},
        correlation_id=get_correlation_id(),
        module="receivables",
        category="financial",
        severity="info",
    )

    await session.commit()

    return ValidacaoComprovanteResponse(id=str(inst.id), status=inst.status, mensagem=msg)


@router.post("/{installment_id}/request-resubmission")
async def request_resubmission(
    installment_id: uuid.UUID,
    body: ReenvioComprovanteRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> dict:
    repo = ReceivableRepository(session, current_user.empresa_id)
    inst = await repo.get_installment(installment_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Installment not found")

    # Status stays, but we log the request
    log.info("receipt_resubmission_requested", installment_id=str(installment_id), observacoes=body.observacoes)

    audit = AuditLogger(session)
    await audit.record(
        action="receivable.request_resubmission",
        user_id=str(current_user.id),
        entity="installment",
        entity_id=str(inst.id),
        payload_after={"observacoes": body.observacoes},
        correlation_id=get_correlation_id(),
        module="receivables",
        category="financial",
        severity="info",
    )
    await session.commit()

    return {"id": str(inst.id), "message": "Resubmission notification sent"}


# ── 4-7: Static Pix QR Code ───────────────────────────────────

@router.get("/{installment_id}/pix-qr", response_model=PixQrResponse)
async def get_pix_qr(
    installment_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> PixQrResponse:
    repo = ReceivableRepository(session, current_user.empresa_id)
    inst = await repo.get_installment(installment_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Installment not found")

    from app.infrastructure.settings import get_settings
    settings = get_settings()

    brcode = generate_pix_brcode(
        chave="pix@example.com",  # Would come from settings in production
        nome=settings.PRODUCT_NAME[:25],
        cidade="SaoPaulo",
        valor=inst.current_value - inst.paid_value,
        txid=str(inst.id).replace("-", "")[:25],
    )

    # Generate QR code image
    try:
        import qrcode
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(brcode)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        qr_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    except ImportError:
        # qrcode not installed — return brcode only
        qr_b64 = ""

    return PixQrResponse(brcode=brcode, qr_imagem_base64=qr_b64)


# ── 4-8: Renegotiation ────────────────────────────────────────

@router.post("/renegotiate", response_model=RenegociarResponse)
async def renegotiate(
    body: RenegociarRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> RenegociarResponse:
    repo = ReceivableRepository(session, current_user.empresa_id)

    ids = [uuid.UUID(iid) for iid in body.titulos_ids]
    installments = await repo.get_installments_by_ids(ids)

    if len(installments) != len(ids):
        raise HTTPException(status_code=404, detail="One or more installments not found")

    # Validate all are open/overdue
    for inst in installments:
        if inst.status not in ("em_aberto", "vencido", "pago_parcial"):
            raise HTTPException(
                status_code=400,
                detail=f"Installment {inst.id} has status={inst.status} and cannot be renegotiated",
            )

    # Mark originals as renegociado + create adjustments
    for inst in installments:
        old_val = inst.current_value
        inst.status = "renegociado"
        adj = InstallmentAdjustment(
            empresa_id=current_user.empresa_id,
            installment_id=inst.id,
            kind="renegotiation",
            old_value=old_val,
            new_value=Decimal("0"),
            reason="Renegotiated into new schedule",
            created_by_user_id=current_user.id,
        )
        await repo.add_adjustment(adj)

    # Generate new installments from schedule.
    # Helper interno aceita frequency/method em EN ("monthly"/"fixed");
    # mapeamos a periodicidade/metodo PT-BR do schema externo.
    _PERIODICIDADE_PARA_EN = {
        "mensal": "monthly",
        "quinzenal": "biweekly",
        "semanal": "weekly",
    }
    _METODO_PARA_EN = {"fixo": "fixed", "frances": "french", "price": "fixed"}
    ns = body.nova_planilha
    previews = calculate_schedule(
        total_value=ns.valor_total,
        num_installments=ns.quantidade_parcelas,
        start_date=ns.data_inicio,
        frequency=_PERIODICIDADE_PARA_EN.get(ns.periodicidade, ns.periodicidade),
        method=_METODO_PARA_EN.get(ns.metodo, ns.metodo),
    )

    # Use the contract_id from the first original installment
    contract_id = installments[0].contract_id

    # Find max number in contract
    from sqlalchemy import select, func
    from app.infrastructure.db.models.contract import Installment as InstModel
    max_num_result = await session.execute(
        select(func.max(InstModel.number)).where(InstModel.contract_id == contract_id)
    )
    max_num = max_num_result.scalar_one() or 0

    new_installments: list[Installment] = []
    for p in previews:
        new_inst = Installment(
            empresa_id=current_user.empresa_id,
            contract_id=contract_id,
            generation_id=installments[0].generation_id,
            number=max_num + p.number,
            due_date=p.due_date,
            original_value=p.value,
            current_value=p.value,
            valor_pago=Decimal("0"),
            status="em_aberto",
        )
        new_installments.append(new_inst)

    await repo.add_installments(new_installments)

    # Audit
    audit = AuditLogger(session)
    await audit.record(
        action="receivable.renegotiate",
        user_id=str(current_user.id),
        entity="installment",
        entity_id=",".join(body.titulos_ids),
        payload_after={
            "quantidade_original": len(installments),
            "quantidade_nova": len(new_installments),
            "valor_total": str(ns.valor_total),
        },
        correlation_id=get_correlation_id(),
        module="receivables",
        category="financial",
        severity="warning",
    )

    await session.commit()

    return RenegociarResponse(
        quantidade_original=len(installments),
        novos_titulos=[TituloReceberItem.from_model(i) for i in new_installments],
        mensagem="Renegociação concluída com sucesso",
    )


# ── 4-10: Installment Reversal ────────────────────────────────

@router.post("/{installment_id}/reverse", response_model=EstornoResponse)
async def reverse_installment(
    installment_id: uuid.UUID,
    body: EstornoRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> EstornoResponse:
    repo = ReceivableRepository(session, current_user.empresa_id)
    inst = await repo.get_installment(installment_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Installment not found")
    if inst.status not in ("pago", "pago_parcial", "pago_aguardando_verificacao"):
        raise HTTPException(status_code=400, detail=f"Cannot reverse installment with status={inst.status}")

    is_full = body.valor is None or body.valor >= inst.paid_value
    reversed_amount = inst.paid_value if is_full else body.valor
    kind = "full_reversal" if is_full else "partial_reversal"

    # Create adjustment (original stays pago — immutable)
    adj = InstallmentAdjustment(
        empresa_id=current_user.empresa_id,
        installment_id=inst.id,
        kind=kind,
        old_value=inst.paid_value,
        new_value=inst.paid_value - reversed_amount,
        reason=body.motivo,
        created_by_user_id=current_user.id,
    )
    await repo.add_adjustment(adj)

    # Optionally create a Payable for refund tracking
    payable = Payable(
        empresa_id=current_user.empresa_id,
        description=f"Refund for installment #{inst.number} ({kind})",
        amount=reversed_amount,
        due_date=date.today(),
        status="pendente",
        linked_installment_id=inst.id,
        created_by_user_id=current_user.id,
    )
    session.add(payable)
    await session.flush()

    # Audit
    audit = AuditLogger(session)
    await audit.record(
        action="receivable.reverse",
        user_id=str(current_user.id),
        entity="installment",
        entity_id=str(inst.id),
        payload_after={
            "kind": kind,
            "reversed_amount": str(reversed_amount),
            "payable_id": str(payable.id),
        },
        correlation_id=get_correlation_id(),
        module="receivables",
        category="financial",
        severity="warning",
    )

    await session.commit()

    return EstornoResponse(
        id=str(inst.id),
        tipo_movimento=kind,
        valor_estornado=reversed_amount,
        titulo_pagar_id=str(payable.id),
        mensagem=f"{kind.replace('_', ' ').title()} registrado",
    )


# ── 4-11: Bulk Write-Off ──────────────────────────────────────

@router.post("/bulk-write-off", response_model=BaixaLoteResponse)
async def bulk_write_off(
    body: BaixaLoteRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> BaixaLoteResponse:
    repo = ReceivableRepository(session, current_user.empresa_id)

    ids = [uuid.UUID(iid) for iid in body.titulos_ids]
    installments = await repo.get_installments_by_ids(ids)

    if not installments:
        raise HTTPException(status_code=404, detail="No installments found")

    # Sort by due_date (oldest first) — already ordered by repo
    remaining = body.valor_total
    results: list[BaixaLoteResultado] = []
    total_applied = Decimal("0")

    for inst in installments:
        if remaining <= 0:
            break
        if inst.status not in ("em_aberto", "vencido", "pago_parcial"):
            continue

        owed = inst.current_value - inst.paid_value
        apply_amount = min(remaining, owed)

        inst.paid_value = inst.paid_value + apply_amount
        inst.payment_date = body.pago_em
        inst.payment_method = body.forma_pagamento

        if inst.paid_value >= inst.current_value:
            inst.status = "pago"
        else:
            inst.status = "pago_parcial"

        remaining -= apply_amount
        total_applied += apply_amount

        results.append(BaixaLoteResultado(
            titulo_id=str(inst.id),
            valor_aplicado=apply_amount,
            status=inst.status,
        ))

    # Audit
    audit = AuditLogger(session)
    await audit.record(
        action="receivable.bulk_write_off",
        user_id=str(current_user.id),
        entity="installment",
        entity_id=",".join(body.titulos_ids),
        payload_after={
            "valor_total": str(body.valor_total),
            "total_aplicado": str(total_applied),
            "restante": str(remaining),
        },
        correlation_id=get_correlation_id(),
        module="receivables",
        category="financial",
        severity="info",
    )

    await session.commit()

    return BaixaLoteResponse(
        resultados=results,
        total_aplicado=total_applied,
        restante=remaining,
        mensagem=f"Baixa em lote aplicada a {len(results)} títulos",
    )


# ── Helpers ────────────────────────────────────────────────────

_MAX_RECEIPT_BYTES = 10 * 1024 * 1024  # 10 MiB
_MAX_RECEIPT_B64_LEN = (_MAX_RECEIPT_BYTES * 4) // 3 + 64  # margem para padding


async def _upload_receipt(receipt_data: str, installment_id: str) -> str:
    """Upload receipt file to MinIO. Accepts base64 data (max 10 MiB)."""
    import asyncio
    import boto3
    from botocore.config import Config as BotoConfig
    from app.infrastructure.settings import get_settings

    # Limita o payload base64 ANTES de decodificar para evitar OOM.
    if len(receipt_data) > _MAX_RECEIPT_B64_LEN:
        raise HTTPException(
            status_code=413,
            detail=f"Comprovante excede o limite de {_MAX_RECEIPT_BYTES // (1024 * 1024)} MiB",
        )

    settings = get_settings()
    try:
        file_bytes = base64.b64decode(receipt_data, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Comprovante base64 inválido") from exc

    if len(file_bytes) > _MAX_RECEIPT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Comprovante excede o limite de {_MAX_RECEIPT_BYTES // (1024 * 1024)} MiB",
        )

    key = f"receipts/{installment_id}/{uuid.uuid4().hex}.png"

    def _upload() -> str:
        s3 = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            config=BotoConfig(signature_version="s3v4"),
        )
        s3.put_object(
            Bucket=settings.S3_BUCKET,
            Key=key,
            Body=file_bytes,
            ContentType="image/png",
        )
        s3.close()
        return f"{settings.S3_ENDPOINT_URL}/{settings.S3_BUCKET}/{key}"

    return await asyncio.to_thread(_upload)
