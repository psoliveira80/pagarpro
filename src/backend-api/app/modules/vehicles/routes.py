"""Vehicle module HTTP routes — CRUD, financials, FIPE lookups, tracker block/unblock."""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Query
from redis.asyncio import Redis
from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUserDep, SessionDep
from app.application.shared.audit_logger import AuditLogger
from app.core.correlation import get_correlation_id
from app.infrastructure.db.models.asset import Asset
from app.infrastructure.settings import get_settings
from app.modules.vehicles.adapters.fipe_api_adapter import ApiFipeAdapter
from app.modules.vehicles.adapters.generic_rest_tracker import GenericRestTrackerAdapter
from app.modules.vehicles.models import TrackerDevice, Vehicle, VehicleAcquisition
from app.modules.vehicles.schemas import (
    AquisicaoResponse,
    BloqueioDesbloqueioRequest,
    DispositivoRastreamentoCreate,
    DispositivoRastreamentoResponse,
    FipeAnoResponse,
    FipeMarcaResponse,
    FipeModeloResponse,
    FipePrecoResponse,
    VeiculoCreate,
    VeiculoFinanceiroResponse,
    VeiculoPaginatedResponse,
    VeiculoResponse,
    VeiculoUpdate,
)
from app.modules.vehicles.services.fipe_service import FipeService

log = structlog.get_logger()

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_query(empresa_id: UUID):  # type: ignore[no-untyped-def]
    return select(Vehicle).where(
        Vehicle.excluido_em.is_(None),
        Vehicle.empresa_id == empresa_id,
    )


async def _get_vehicle_or_404(session: object, vehicle_id: UUID, empresa_id: UUID) -> Vehicle:
    from sqlalchemy.ext.asyncio import AsyncSession

    assert isinstance(session, AsyncSession)
    result = await session.execute(_base_query(empresa_id).where(Vehicle.id == vehicle_id))
    vehicle = result.scalar_one_or_none()
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.post("", response_model=VeiculoResponse, status_code=201)
async def create_vehicle(
    body: VeiculoCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> VeiculoResponse:
    # Check plate uniqueness
    existing = await session.execute(
        _base_query(current_user.empresa_id).where(Vehicle.plate == body.placa)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Placa já registrada")

    # Note: Asset abstraction layer dropped in migration 0015. Veiculo replaces it directly.
    vehicle = Vehicle(
        empresa_id=current_user.empresa_id,
        plate=body.placa,
        brand=body.marca,
        model_name=body.modelo,
        model_year=body.ano_modelo,
        fab_year=body.ano_fabricacao,
        color=body.cor,
        chassi=body.chassi,
        renavam=body.renavam,
        fipe_code=body.codigo_fipe,
        fipe_value=body.valor_fipe,
        status=body.status,
        customer_id=UUID(body.cliente_id) if body.cliente_id else None,
    )
    session.add(vehicle)
    await session.flush()

    # Aquisição
    if body.aquisicao:
        # Mapeia campos PT-BR da Aquisicao schema → JSONB `parcelas` (chaves mantidas em EN por compat
        # com o storage atual; consumidores leem do JSONB via from_model).
        _FIN_FIELD_MAP = {
            "banco_financiamento": "financing_bank",
            "contrato_financiamento": "financing_contract",
            "parcelas_financiamento": "financing_installments",
            "valor_mensal_financiamento": "financing_monthly_value",
            "observacoes": "notes",
        }
        financing_data = {}
        for pt_field, en_key in _FIN_FIELD_MAP.items():
            val = getattr(body.aquisicao, pt_field, None)
            if val is not None:
                financing_data[en_key] = (
                    str(val) if not isinstance(val, (str, int, float, bool, list, dict)) else val
                )
        acq = VehicleAcquisition(
            empresa_id=current_user.empresa_id,
            vehicle_id=vehicle.id,
            acquisition_type=body.aquisicao.tipo_aquisicao,
            purchase_price=body.aquisicao.preco_compra,
            purchase_date=body.aquisicao.data_compra,
            parcelas=financing_data if financing_data else None,
        )
        session.add(acq)
        await session.flush()

    # Audit
    audit = AuditLogger(session)
    await audit.record(
        action="vehicle.created",
        user_id=str(current_user.id),
        entity="vehicle",
        entity_id=str(vehicle.id),
        payload_after={"placa": vehicle.plate, "marca": vehicle.brand, "modelo": vehicle.model_name},
        correlation_id=get_correlation_id(),
        module="vehicles",
        category="data",
        severity="info",
    )

    await session.commit()
    await session.refresh(vehicle)
    return VeiculoResponse.from_model(vehicle)


@router.get("", response_model=VeiculoPaginatedResponse)
async def list_vehicles(
    session: SessionDep,
    current_user: CurrentUserDep,
    search: str | None = Query(None),
    status: str | None = Query(None),
    customer_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> VeiculoPaginatedResponse:
    query = _base_query(current_user.empresa_id)

    if status:
        query = query.where(Vehicle.status == status)
    if customer_id:
        query = query.where(Vehicle.customer_id == UUID(customer_id))
    # Aliases EN antigos aceitos via query string foram mantidos acima como parâmetros.
    if search:
        term = f"%{search}%"
        query = query.where(
            or_(
                Vehicle.plate.ilike(term),
                Vehicle.brand.ilike(term),
                Vehicle.model_name.ilike(term),
            )
        )

    count_q = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_q)
    total = total_result.scalar_one()

    query = query.order_by(Vehicle.criado_em.desc())
    query = query.offset((page - 1) * size).limit(size)
    result = await session.execute(query)
    items = list(result.scalars().all())

    pages = math.ceil(total / size) if total > 0 else 0
    return VeiculoPaginatedResponse(
        items=[VeiculoResponse.from_model(v) for v in items],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get("/{vehicle_id}", response_model=VeiculoResponse)
async def get_vehicle(
    vehicle_id: UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> VeiculoResponse:
    vehicle = await _get_vehicle_or_404(session, vehicle_id, current_user.empresa_id)
    return VeiculoResponse.from_model(vehicle)


@router.patch("/{vehicle_id}", response_model=VeiculoResponse)
async def update_vehicle(
    vehicle_id: UUID,
    body: VeiculoUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> VeiculoResponse:
    vehicle = await _get_vehicle_or_404(session, vehicle_id, current_user.empresa_id)

    before = {"placa": vehicle.plate, "status": vehicle.status}
    update_data = body.model_dump(exclude_unset=True)

    # `metadados` e `rastreador_id` foram dropados do Veiculo schema; ignora silenciosamente
    update_data.pop("metadados", None)
    update_data.pop("rastreador_id", None)

    if "cliente_id" in update_data:
        cid = update_data.pop("cliente_id")
        vehicle.customer_id = UUID(cid) if cid else None

    # Mapeia nomes PT-BR do schema externo → atributos EN do ORM (synonyms cobrem alguns;
    # outros precisam de tradução explícita).
    _UPDATE_FIELD_MAP = {
        "placa": "plate",
        "marca": "brand",
        "modelo": "model_name",
        "ano_modelo": "model_year",
        "ano_fabricacao": "fab_year",
        "cor": "color",
        "codigo_fipe": "fipe_code",
        "valor_fipe": "fipe_value",
    }
    for field, value in update_data.items():
        setattr(vehicle, _UPDATE_FIELD_MAP.get(field, field), value)

    audit = AuditLogger(session)
    await audit.record(
        action="vehicle.updated",
        user_id=str(current_user.id),
        entity="vehicle",
        entity_id=str(vehicle.id),
        payload_before=before,
        payload_after=update_data,
        correlation_id=get_correlation_id(),
        module="vehicles",
        category="data",
        severity="info",
    )

    await session.commit()
    await session.refresh(vehicle)
    return VeiculoResponse.from_model(vehicle)


@router.delete("/{vehicle_id}", status_code=204)
async def delete_vehicle(
    vehicle_id: UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> None:
    vehicle = await _get_vehicle_or_404(session, vehicle_id, current_user.empresa_id)
    vehicle.excluido_em = datetime.now(timezone.utc)

    audit = AuditLogger(session)
    await audit.record(
        action="vehicle.deleted",
        user_id=str(current_user.id),
        entity="vehicle",
        entity_id=str(vehicle.id),
        correlation_id=get_correlation_id(),
        module="vehicles",
        category="data",
        severity="warning",
    )

    await session.commit()


# ---------------------------------------------------------------------------
# Financials
# ---------------------------------------------------------------------------

@router.get("/{vehicle_id}/financials", response_model=VeiculoFinanceiroResponse)
async def get_vehicle_financials(
    vehicle_id: UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> VeiculoFinanceiroResponse:
    vehicle = await _get_vehicle_or_404(session, vehicle_id, current_user.empresa_id)
    acq = None
    if vehicle.acquisition:
        acq = AquisicaoResponse.from_model(vehicle.acquisition)
    return VeiculoFinanceiroResponse(
        veiculo_id=str(vehicle.id),
        valor_fipe=vehicle.fipe_value,
        aquisicao=acq,
    )


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------

@router.post("/{vehicle_id}/trackers", response_model=DispositivoRastreamentoResponse, status_code=201)
async def add_tracker(
    vehicle_id: UUID,
    body: DispositivoRastreamentoCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> DispositivoRastreamentoResponse:
    await _get_vehicle_or_404(session, vehicle_id, current_user.empresa_id)

    cfg = body.config or {}
    device = TrackerDevice(
        empresa_id=current_user.empresa_id,
        veiculo_id=vehicle_id,
        serial=body.serial,
        fabricante=body.fabricante,
        modelo=cfg.get("modelo"),
        imei=cfg.get("imei"),
    )
    session.add(device)

    audit = AuditLogger(session)
    await audit.record(
        action="tracker.added",
        user_id=str(current_user.id),
        entity="tracker_device",
        entity_id=str(device.id) if hasattr(device, "id") else "",
        payload_after={"veiculo_id": str(vehicle_id), "fabricante": body.fabricante, "serial": body.serial},
        correlation_id=get_correlation_id(),
        module="vehicles",
        category="data",
        severity="info",
    )

    await session.commit()
    await session.refresh(device)
    return DispositivoRastreamentoResponse.from_model(device)


@router.post("/{vehicle_id}/block", status_code=200)
async def block_vehicle(
    vehicle_id: UUID,
    body: BloqueioDesbloqueioRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> dict:
    """Block vehicle via GPS tracker. Requires password re-confirmation."""
    from app.infrastructure.security.password_hasher import verify_password

    if not verify_password(body.senha, current_user.senha_hash):
        raise HTTPException(status_code=403, detail="Invalid password confirmation")

    vehicle = await _get_vehicle_or_404(session, vehicle_id, current_user.empresa_id)

    # Find active tracker
    result = await session.execute(
        select(TrackerDevice).where(
            TrackerDevice.veiculo_id == vehicle_id,
            TrackerDevice.empresa_id == current_user.empresa_id,
            TrackerDevice.status == "ativo",
        )
    )
    tracker = result.scalar_one_or_none()
    if not tracker:
        raise HTTPException(status_code=422, detail="No active tracker for this vehicle")

    # Attempt block via adapter
    adapter = GenericRestTrackerAdapter()
    # `config` foi consolidado em modelo/fabricante/imei no schema novo (migration 0015).
    config = {"modelo": tracker.modelo, "fabricante": tracker.fabricante, "imei": tracker.imei}
    try:
        success = await adapter.block(tracker.serial, config)
    except Exception as exc:
        log.error("tracker_block_failed", serial=tracker.serial, error=str(exc))
        raise HTTPException(status_code=502, detail="Tracker block command failed")

    if success:
        vehicle.status = "bloqueado"

    audit = AuditLogger(session)
    await audit.record(
        action="vehicle.blocked",
        user_id=str(current_user.id),
        entity="vehicle",
        entity_id=str(vehicle.id),
        payload_after={"motivo": body.motivo, "tracker_serial": tracker.serial},
        correlation_id=get_correlation_id(),
        module="vehicles",
        category="security",
        severity="critical",
    )

    await session.commit()
    return {"status": "blocked", "vehicle_id": str(vehicle.id)}


@router.post("/{vehicle_id}/unblock", status_code=200)
async def unblock_vehicle(
    vehicle_id: UUID,
    body: BloqueioDesbloqueioRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> dict:
    """Unblock vehicle via GPS tracker. Requires password re-confirmation."""
    from app.infrastructure.security.password_hasher import verify_password

    if not verify_password(body.senha, current_user.senha_hash):
        raise HTTPException(status_code=403, detail="Invalid password confirmation")

    vehicle = await _get_vehicle_or_404(session, vehicle_id, current_user.empresa_id)

    result = await session.execute(
        select(TrackerDevice).where(
            TrackerDevice.veiculo_id == vehicle_id,
            TrackerDevice.empresa_id == current_user.empresa_id,
            TrackerDevice.status == "ativo",
        )
    )
    tracker = result.scalar_one_or_none()
    if not tracker:
        raise HTTPException(status_code=422, detail="No active tracker for this vehicle")

    adapter = GenericRestTrackerAdapter()
    config = {"modelo": tracker.modelo, "fabricante": tracker.fabricante, "imei": tracker.imei}
    try:
        success = await adapter.unblock(tracker.serial, config)
    except Exception as exc:
        log.error("tracker_unblock_failed", serial=tracker.serial, error=str(exc))
        raise HTTPException(status_code=502, detail="Tracker unblock command failed")

    if success:
        vehicle.status = "disponivel"

    audit = AuditLogger(session)
    await audit.record(
        action="vehicle.unblocked",
        user_id=str(current_user.id),
        entity="vehicle",
        entity_id=str(vehicle.id),
        payload_after={"motivo": body.motivo, "tracker_serial": tracker.serial},
        correlation_id=get_correlation_id(),
        module="vehicles",
        category="security",
        severity="critical",
    )

    await session.commit()
    return {"status": "unblocked", "vehicle_id": str(vehicle.id)}


# ---------------------------------------------------------------------------
# FIPE
# ---------------------------------------------------------------------------

async def _get_fipe_service(session: AsyncSession | None = None) -> FipeService:
    from app.modules.vehicles.adapters.fipe_api_adapter import ApiFipeAdapter
    from app.modules.vehicles.adapters.parallelum_fipe_adapter import ParallelumFipeAdapter

    settings = get_settings()
    redis = Redis.from_url(settings.REDIS_URL)

    # Read active FIPE provider from integration_credentials
    _registry = {
        "brasilapi": lambda cfg: ApiFipeAdapter(base_url=cfg.get("base_url", "https://brasilapi.com.br/api/fipe")),
        "parallelum": lambda cfg: ParallelumFipeAdapter(base_url=cfg.get("base_url", "https://fipe.parallelum.com.br/api/v2")),
    }

    if session:
        from app.infrastructure.db.models.integration_credential import IntegrationCredential

        stmt = select(IntegrationCredential).where(
            IntegrationCredential.categoria == "fipe",
            IntegrationCredential.ativo.is_(True),
        )
        result = await session.execute(stmt)
        cred = result.scalar_one_or_none()
        if cred and cred.provedor in _registry:
            provider = _registry[cred.provedor](cred.config or {})
            return FipeService(provider=provider, redis=redis)

    # Fallback: try parallelum (most reliable public API)
    return FipeService(provider=ParallelumFipeAdapter(), redis=redis)


@router.get("/fipe/brands", response_model=list[FipeMarcaResponse])
async def fipe_brands(
    session: SessionDep,
    current_user: CurrentUserDep,
    vehicle_type: str = Query("carros"),
) -> list[FipeMarcaResponse]:
    svc = await _get_fipe_service(session)
    try:
        data = await svc.list_brands(vehicle_type)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return [FipeMarcaResponse(codigo=str(b.get("valor", b.get("code", ""))), nome=b.get("nome", b.get("name", ""))) for b in data]


@router.get("/fipe/brands/{brand_code}/models", response_model=list[FipeModeloResponse])
async def fipe_models(
    brand_code: str,
    session: SessionDep,
    current_user: CurrentUserDep,
    vehicle_type: str = Query("carros"),
) -> list[FipeModeloResponse]:
    svc = await _get_fipe_service(session)
    data = await svc.list_models(vehicle_type, brand_code)
    return [FipeModeloResponse(codigo=str(m.get("valor", m.get("code", ""))), nome=m.get("nome", m.get("name", ""))) for m in data]


@router.get("/fipe/brands/{brand_code}/models/{model_code}/years", response_model=list[FipeAnoResponse])
async def fipe_years(
    brand_code: str,
    model_code: str,
    session: SessionDep,
    current_user: CurrentUserDep,
    vehicle_type: str = Query("carros"),
) -> list[FipeAnoResponse]:
    svc = await _get_fipe_service(session)
    data = await svc.list_years(vehicle_type, brand_code, model_code)
    return [FipeAnoResponse(codigo=str(y.get("valor", y.get("code", ""))), nome=y.get("nome", y.get("name", ""))) for y in data]


@router.get("/fipe/brands/{brand_code}/models/{model_code}/years/{year_code}/price", response_model=FipePrecoResponse)
async def fipe_price(
    brand_code: str,
    model_code: str,
    year_code: str,
    session: SessionDep,
    current_user: CurrentUserDep,
    vehicle_type: str = Query("carros"),
) -> FipePrecoResponse:
    svc = await _get_fipe_service(session)
    data = await svc.get_price(vehicle_type, brand_code, model_code, year_code)
    return FipePrecoResponse(
        preco=data.get("valor", data.get("price", "")),
        marca=data.get("marca", data.get("brand", "")),
        modelo=data.get("modelo", data.get("model", "")),
        ano_modelo=int(data.get("anoModelo", data.get("model_year", 0))),
        combustivel=data.get("combustivel", data.get("fuel", "")),
        codigo_fipe=data.get("codigoFipe", data.get("fipe_code", "")),
        mes_referencia=data.get("mesReferencia", data.get("reference_month", "")),
        tipo_veiculo=int(data.get("tipoVeiculo", data.get("vehicle_type", 1))),
    )
