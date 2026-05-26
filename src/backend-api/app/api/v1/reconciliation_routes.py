"""Reconciliation API routes (Epic 7 — Stories 7.1-7.5)."""

from __future__ import annotations

import math
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import structlog
from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.api.deps import CurrentUserDep, SessionDep
from app.api.v1.schemas.bank import (
    AutoConciliacaoResponse,
    ConciliarRequest,
    ConfirmarConciliacaoResponse,
    DivergenceItem,  # alias para DivergenciaItem
    DivergencesResponse,  # alias para DivergenciasResponse
    ImportSummary,  # alias para ResumoImportacao
    MatchConfirmResponse,  # alias
    PdfConfirmRequest,  # alias
    PdfParseResponse,
    PdfParsedRow,  # alias para LinhaPdfParseada
    SugestaoConciliacao,
    TransacaoBancariaListResponse,
    TransacaoBancariaResponse,
)
from app.application.shared.audit_logger import AuditLogger
from app.core.correlation import get_correlation_id
from app.infrastructure.db.models.bank import BankTransaction
from app.infrastructure.db.repositories.bank_repo import (
    BankAccountRepository,
    BankTransactionRepository,
)
from app.infrastructure.parsing.ofx_parser import parse_ofx
from app.infrastructure.parsing.pdf_extract_parser import extract_text_from_pdf, parse_pdf_text

log = structlog.get_logger()

router = APIRouter(tags=["reconciliation"])


# ══════════════════════════════════════════════════════════════
# OFX Import  (Story 7.1)
# ══════════════════════════════════════════════════════════════

@router.post(
    "/reconciliation/import-ofx/{account_id}",
    response_model=ImportSummary,
)
async def import_ofx(
    account_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
    file: UploadFile = File(...),
) -> ImportSummary:
    # Validate account exists
    acct_repo = BankAccountRepository(session)
    account = await acct_repo.get_by_id(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Bank account not found")

    content = await file.read()
    parsed = parse_ofx(content)
    total_parsed = len(parsed)

    if total_parsed == 0:
        return ImportSummary(total_parsed=0, new_inserted=0, duplicates_skipped=0)

    rows = [
        {
            "empresa_id": current_user.empresa_id,
            "conta_id": account_id,
            "fitid": tx["fitid"],
            "lancado_em": tx["posted_at"],
            "valor": tx["amount"],
            "descricao_bruta": tx["description_raw"],
            "descricao_limpa": tx["description_clean"],
            "tipo": tx["type"],
            "status": "pendente",
            "importado_de": "ofx",
        }
        for tx in parsed
    ]

    tx_repo = BankTransactionRepository(session)
    inserted = await tx_repo.bulk_upsert_skip(rows)

    audit = AuditLogger(session)
    await audit.record(
        action="reconciliation.ofx_imported",
        user_id=str(current_user.id),
        entity="bank_account",
        entity_id=str(account_id),
        payload_after={"total_parsed": total_parsed, "inserted": inserted},
        correlation_id=get_correlation_id(),
        module="reconciliation",
        category="financial",
        severity="info",
    )

    await session.commit()

    return ImportSummary(
        total_parsed=total_parsed,
        new_inserted=inserted,
        duplicates_skipped=total_parsed - inserted,
    )


# ══════════════════════════════════════════════════════════════
# PDF Import  (Story 7.2)
# ══════════════════════════════════════════════════════════════

@router.post(
    "/reconciliation/import-pdf/{account_id}",
    response_model=PdfParseResponse,
)
async def import_pdf_parse(
    account_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
    file: UploadFile = File(...),
) -> PdfParseResponse:
    acct_repo = BankAccountRepository(session)
    account = await acct_repo.get_by_id(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Bank account not found")

    content = await file.read()
    text_content = extract_text_from_pdf(content)

    if not text_content:
        raise HTTPException(
            status_code=422,
            detail="Could not extract text from PDF. File may be image-only.",
        )

    parsed, confidence = parse_pdf_text(text_content)
    rows = [
        PdfParsedRow(
            fitid=tx["fitid"],
            posted_at=tx["posted_at"],
            amount=tx["amount"],
            description_raw=tx["description_raw"],
            description_clean=tx["description_clean"],
            type=tx["type"],
            selected=True,
        )
        for tx in parsed
    ]

    return PdfParseResponse(
        rows=rows,
        confidence=confidence,
        total_rows=len(rows),
    )


@router.post(
    "/reconciliation/import-pdf/confirm",
    response_model=ImportSummary,
)
async def import_pdf_confirm(
    body: PdfConfirmRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ImportSummary:
    acct_id = uuid.UUID(body.account_id)
    acct_repo = BankAccountRepository(session)
    account = await acct_repo.get_by_id(acct_id)
    if not account:
        raise HTTPException(status_code=404, detail="Bank account not found")

    selected = [r for r in body.rows if r.selected]
    if not selected:
        return ImportSummary(total_parsed=0, new_inserted=0, duplicates_skipped=0)

    rows = [
        {
            "empresa_id": current_user.empresa_id,
            "conta_id": acct_id,
            "fitid": r.fitid,
            "lancado_em": r.posted_at,
            "valor": r.amount,
            "descricao_bruta": r.description_raw,
            "descricao_limpa": r.description_clean,
            "tipo": r.type,
            "status": "pendente",
            "importado_de": "pdf",
        }
        for r in selected
    ]

    tx_repo = BankTransactionRepository(session)
    inserted = await tx_repo.bulk_upsert_skip(rows)
    await session.commit()

    return ImportSummary(
        total_parsed=len(selected),
        new_inserted=inserted,
        duplicates_skipped=len(selected) - inserted,
    )


# ══════════════════════════════════════════════════════════════
# Transactions listing
# ══════════════════════════════════════════════════════════════

@router.get(
    "/reconciliation/transactions",
    response_model=TransacaoBancariaListResponse,
)
async def list_transactions(
    session: SessionDep,
    current_user: CurrentUserDep,
    account_id: str | None = Query(None),
    status: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
) -> TransacaoBancariaListResponse:
    tx_repo = BankTransactionRepository(session)

    if account_id:
        items, total = await tx_repo.list_by_account(
            uuid.UUID(account_id),
            status=status,
            date_from=date_from,
            date_to=date_to,
            page=page,
            size=size,
        )
    else:
        items, total = await tx_repo.list_pending(page=page, size=size)

    return TransacaoBancariaListResponse(
        items=[TransacaoBancariaResponse.from_model(t) for t in items],
        total=total,
        page=page,
        size=size,
    )


# ══════════════════════════════════════════════════════════════
# Match / Reconcile  (Story 7.4)
# ══════════════════════════════════════════════════════════════

@router.post("/reconciliation/match", response_model=MatchConfirmResponse)
async def confirm_match(
    body: ConciliarRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> MatchConfirmResponse:
    tx_repo = BankTransactionRepository(session)
    matched = 0
    target_uuid = uuid.UUID(body.destino_id)

    for tx_id_str in body.transacao_ids:
        tx = await tx_repo.get_by_id(uuid.UUID(tx_id_str))
        if not tx:
            continue
        if tx.status != "pendente":
            continue
        tx.status = "conciliada"
        tx.conciliado_com_tipo = body.tipo_destino
        tx.conciliado_com_id = target_uuid
        matched += 1

    audit = AuditLogger(session)
    await audit.record(
        action="reconciliation.match_confirmed",
        user_id=str(current_user.id),
        entity="reconciliation",
        entity_id=body.destino_id,
        payload_after={
            "transacao_ids": body.transacao_ids,
            "tipo_destino": body.tipo_destino,
            "matched": matched,
        },
        correlation_id=get_correlation_id(),
        module="reconciliation",
        category="financial",
        severity="info",
    )

    await session.commit()
    return MatchConfirmResponse(matched_count=matched)


@router.post("/reconciliation/transactions/{tx_id}/ignore", status_code=200)
async def ignore_transaction(
    tx_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> dict:
    tx_repo = BankTransactionRepository(session)
    tx = await tx_repo.get_by_id(tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    tx.status = "ignorada"
    await session.commit()
    return {"status": "ok"}


# ══════════════════════════════════════════════════════════════
# Auto-match suggestions  (Story 7.4)
# ══════════════════════════════════════════════════════════════

@router.get(
    "/reconciliation/match-suggestions",
    response_model=AutoConciliacaoResponse,
)
async def get_match_suggestions(
    session: SessionDep,
    current_user: CurrentUserDep,
    account_id: str | None = Query(None),
) -> AutoConciliacaoResponse:
    """Compute auto-match suggestions between pending transactions and pending titles."""
    from sqlalchemy import select, or_
    from app.infrastructure.db.models.contract import Installment
    from app.infrastructure.db.models.payable import Payable

    tx_repo = BankTransactionRepository(session)
    if account_id:
        txns, _ = await tx_repo.list_by_account(
            uuid.UUID(account_id), status="pendente", page=1, size=200,
        )
    else:
        txns, _ = await tx_repo.list_pending(page=1, size=200)

    if not txns:
        return AutoConciliacaoResponse(suggestions=[])

    # Fetch pending installments (pago_aguardando_verificacao)
    result = await session.execute(
        select(Installment).where(
            Installment.status == "pago_aguardando_verificacao"
        ).limit(500)
    )
    installments = list(result.scalars().all())

    # Fetch pending payables
    result = await session.execute(
        select(Payable).where(
            Payable.status == "pendente",
            Payable.excluido_em.is_(None),
        ).limit(500)
    )
    payables = list(result.scalars().all())

    suggestions: list[SugestaoConciliacao] = []

    for tx in txns:
        best_score = 0.0
        best_suggestion: SugestaoConciliacao | None = None

        # Try matching against installments (credits)
        if tx.valor > 0:
            for inst in installments:
                score, amount_diff, date_diff = _compute_match_score(
                    tx.valor, tx.lancado_em,
                    inst.valor, inst.data_vencimento,
                    tx.descricao_limpa or "",
                    "",
                )
                if score >= 0.6 and score > best_score:
                    best_score = score
                    best_suggestion = SugestaoConciliacao(
                        transaction_id=str(tx.id),
                        target_kind="installment",
                        target_id=str(inst.id),
                        score=round(score, 3),
                        amount_diff=abs(tx.valor - inst.valor),
                        date_diff_days=date_diff,
                        description_similarity=0.0,
                    )

        # Try matching against payables (debits)
        if tx.valor < 0:
            for pay in payables:
                score, amount_diff, date_diff = _compute_match_score(
                    abs(tx.valor), tx.lancado_em,
                    pay.valor, pay.data_vencimento,
                    tx.descricao_limpa or "",
                    pay.descricao or "",
                )
                if score >= 0.6 and score > best_score:
                    best_score = score
                    best_suggestion = SugestaoConciliacao(
                        transaction_id=str(tx.id),
                        target_kind="payable",
                        target_id=str(pay.id),
                        score=round(score, 3),
                        amount_diff=abs(abs(tx.valor) - pay.valor),
                        date_diff_days=date_diff,
                        description_similarity=0.0,
                    )

        if best_suggestion and best_score >= 0.6:
            suggestions.append(best_suggestion)

    # Sort by score descending
    suggestions.sort(key=lambda s: s.score, reverse=True)
    return AutoConciliacaoResponse(suggestions=suggestions)


def _compute_match_score(
    tx_amount: Decimal,
    tx_date: date,
    title_amount: Decimal,
    title_date: date,
    tx_desc: str,
    title_desc: str,
) -> tuple[float, Decimal, int]:
    """Score = exact_value(60%) + date_window(30%) + description_match(10%)."""
    # Value component (60%)
    if tx_amount == title_amount:
        value_score = 1.0
    else:
        max_val = max(abs(tx_amount), abs(title_amount))
        if max_val == 0:
            value_score = 1.0
        else:
            diff_ratio = float(abs(tx_amount - title_amount)) / float(max_val)
            value_score = max(0.0, 1.0 - diff_ratio)

    # Date component (30%)
    date_diff = abs((tx_date - title_date).days)
    if date_diff == 0:
        date_score = 1.0
    elif date_diff <= 3:
        date_score = 0.8
    elif date_diff <= 7:
        date_score = 0.5
    else:
        date_score = 0.0

    # Description component (10%) — simple overlap
    desc_score = 0.0
    if tx_desc and title_desc:
        tx_words = set(tx_desc.lower().split())
        title_words = set(title_desc.lower().split())
        if tx_words and title_words:
            overlap = len(tx_words & title_words)
            total = len(tx_words | title_words)
            desc_score = overlap / total if total > 0 else 0.0

    score = value_score * 0.6 + date_score * 0.3 + desc_score * 0.1
    return score, abs(tx_amount - title_amount), date_diff


# ══════════════════════════════════════════════════════════════
# Divergences  (Story 7.5)
# ══════════════════════════════════════════════════════════════

@router.get(
    "/reconciliation/divergences",
    response_model=DivergencesResponse,
)
async def get_divergences(
    session: SessionDep,
    current_user: CurrentUserDep,
    tolerance: Decimal = Query(Decimal("0.50")),
) -> DivergencesResponse:
    """Detect divergences: orphan transactions, suspect paid titles, value mismatches."""
    from sqlalchemy import select, and_, not_, exists
    from app.infrastructure.db.models.contract import Installment

    tx_repo = BankTransactionRepository(session)

    # 1) Orphan transactions — pending > 3 days
    orphans = await tx_repo.get_orphan_transactions(days_old=3)
    orphan_items = [
        DivergenceItem(
            category="orphan",
            entity_type="bank_transaction",
            entity_id=str(tx.id),
            description=tx.descricao_limpa or tx.descricao_bruta or "Sem descrição",
            amount=tx.valor,
            posted_at=tx.lancado_em,
            details=f"Importado via {tx.importado_de}",
        )
        for tx in orphans
    ]

    # 2) Suspect paid titles — installments with status=pago but no matching conciliada transaction
    subq = (
        select(BankTransaction.id)
        .where(BankTransaction.conciliado_com_id == Installment.id)
        .where(BankTransaction.status == "conciliada")
        .correlate(Installment)
    )
    result = await session.execute(
        select(Installment)
        .where(Installment.status == "pago")
        .where(~exists(subq))
        .limit(100)
    )
    suspect_installments = list(result.scalars().all())
    suspect_items = [
        DivergenceItem(
            category="suspect_paid",
            entity_type="installment",
            entity_id=str(inst.id),
            description=f"Parcela {inst.data_vencimento}",
            amount=inst.valor,
            posted_at=inst.data_vencimento,
            details="Marcada como paga sem transação bancária conciliada",
        )
        for inst in suspect_installments
    ]

    # 3) Value mismatches — conciliada transactions where amount differs from target
    result = await session.execute(
        select(BankTransaction)
        .where(BankTransaction.status == "conciliada")
        .where(BankTransaction.conciliado_com_tipo == "installment")
        .where(BankTransaction.conciliado_com_id.isnot(None))
        .limit(500)
    )
    conciliated = list(result.scalars().all())

    mismatch_items: list[DivergenceItem] = []
    for tx in conciliated:
        inst_result = await session.execute(
            select(Installment).where(Installment.id == tx.conciliado_com_id)
        )
        inst = inst_result.scalar_one_or_none()
        if inst and abs(abs(tx.valor) - inst.valor) > tolerance:
            mismatch_items.append(
                DivergenceItem(
                    category="value_mismatch",
                    entity_type="bank_transaction",
                    entity_id=str(tx.id),
                    description=tx.descricao_limpa or "Transação",
                    amount=tx.valor,
                    posted_at=tx.lancado_em,
                    details=f"Diferença: R$ {abs(abs(tx.valor) - inst.valor):.2f} (parcela: R$ {inst.valor:.2f})",
                )
            )

    return DivergencesResponse(
        orphan_transactions=orphan_items,
        suspect_paid_titles=suspect_items,
        value_mismatches=mismatch_items,
        total_orphan=len(orphan_items),
        total_suspect=len(suspect_items),
        total_mismatch=len(mismatch_items),
    )
