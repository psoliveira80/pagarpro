"""Admin routes for Epic 9: Integrations, Audit, Modules, Settings, Backup, Metrics."""

import json
import math
import time
from datetime import datetime, timezone
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select, update, delete, and_, or_, text

from app.api.deps import CurrentUserDep, SessionDep
from app.api.v1.schemas.admin import (
    AuditLogEntryOut,
    AuditLogSearchResponse,
    BackupOut,
    BackupTriggerResponse,
    IntegrationCreate,
    IntegrationOut,
    IntegrationTestResult,
    IntegrationUpdate,
    ModuleHookOut,
    ModuleOut,
    ModuleUpdate,
    SystemMetricsOut,
    SystemSettingOut,
    SystemSettingUpdate,
)
from app.application.shared.audit_logger import AuditLogger
from app.core.correlation import get_correlation_id
from app.infrastructure.db.models.active_module import ActiveModule
from app.infrastructure.db.models.audit_log import AuditLog
from app.infrastructure.db.models.integration_credential import IntegrationCredential
from app.infrastructure.db.models.module_hooks_config import ModuleHooksConfig
from app.infrastructure.db.models.system_setting import SystemSetting

log = structlog.get_logger()

router = APIRouter(prefix="/admin", tags=["admin"])


# ──────────────────────────────────────────────────────────────────
# 9-1: Integrations CRUD + test
# ──────────────────────────────────────────────────────────────────


@router.get("/integrations", response_model=list[IntegrationOut])
async def list_integrations(session: SessionDep, current_user: CurrentUserDep) -> list[IntegrationOut]:
    result = await session.execute(
        select(IntegrationCredential)
        .where(IntegrationCredential.empresa_id == current_user.empresa_id)
        .order_by(IntegrationCredential.categoria)
    )
    rows = result.scalars().all()
    return [IntegrationOut(
        id=str(r.id),
        category=r.categoria,
        provider=r.provedor,
        is_active=r.ativo,
        config=r.config,
        status=r.status,
        last_health_check=r.ultimo_health_check,
        created_at=r.criado_em,
        updated_at=r.atualizado_em,
    ) for r in rows]


@router.post("/integrations", response_model=IntegrationOut, status_code=201)
async def create_integration(
    body: IntegrationCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> IntegrationOut:
    cred = IntegrationCredential(
        empresa_id=current_user.empresa_id,
        categoria=body.category,
        provedor=body.provider,
        config=body.config,
        ativo=body.is_active,
        status="unknown",
    )
    session.add(cred)
    await session.flush()

    audit = AuditLogger(session)
    await audit.record(
        action="integration.created",
        user_id=str(current_user.id),
        entity="integration_credentials",
        entity_id=str(cred.id),
        payload_after={"category": body.category, "provider": body.provider, "config": "***"},
        ip=None,
        correlation_id=get_correlation_id(),
    )
    await session.commit()

    return IntegrationOut(id=str(cred.id), category=cred.categoria, provider=cred.provedor, is_active=cred.ativo, config=cred.config, status=cred.status, last_health_check=cred.ultimo_health_check, created_at=cred.criado_em, updated_at=cred.atualizado_em)


@router.put("/integrations/{integration_id}", response_model=IntegrationOut)
async def update_integration(
    integration_id: UUID,
    body: IntegrationUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> IntegrationOut:
    result = await session.execute(
        select(IntegrationCredential).where(IntegrationCredential.id == integration_id)
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Integration not found")

    before = {"provider": cred.provedor, "is_active": cred.ativo, "config": "***"}
    if body.provider is not None:
        cred.provedor = body.provider
    if body.config is not None:
        cred.config = body.config
    if body.is_active is not None:
        cred.ativo = body.is_active
    cred.atualizado_em = datetime.now(timezone.utc)

    audit = AuditLogger(session)
    await audit.record(
        action="integration.updated",
        user_id=str(current_user.id),
        entity="integration_credentials",
        entity_id=str(cred.id),
        payload_before=before,
        payload_after={"provider": cred.provedor, "is_active": cred.ativo, "config": "***"},
        ip=None,
        correlation_id=get_correlation_id(),
    )
    await session.commit()
    await session.refresh(cred)

    return IntegrationOut(id=str(cred.id), category=cred.categoria, provider=cred.provedor, is_active=cred.ativo, config=cred.config, status=cred.status, last_health_check=cred.ultimo_health_check, created_at=cred.criado_em, updated_at=cred.atualizado_em)


@router.delete("/integrations/{integration_id}", status_code=204)
async def delete_integration(
    integration_id: UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> None:
    result = await session.execute(
        select(IntegrationCredential).where(IntegrationCredential.id == integration_id)
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Integration not found")

    audit = AuditLogger(session)
    await audit.record(
        action="integration.deleted",
        user_id=str(current_user.id),
        entity="integration_credentials",
        entity_id=str(cred.id),
        payload_before={"category": cred.categoria, "provider": cred.provedor},
        ip=None,
        correlation_id=get_correlation_id(),
    )

    await session.delete(cred)
    await session.commit()


@router.post("/integrations/{integration_id}/test", response_model=IntegrationTestResult)
async def test_integration(
    integration_id: UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> IntegrationTestResult:
    result = await session.execute(
        select(IntegrationCredential).where(IntegrationCredential.id == integration_id)
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Integration not found")

    start = time.monotonic()
    try:
        # Simulate connectivity test - in production this would call the adapter
        cred.status = "healthy"
        cred.ultimo_health_check = datetime.now(timezone.utc)
        latency = (time.monotonic() - start) * 1000
        await session.commit()
        return IntegrationTestResult(
            integration_id=str(cred.id),
            status="healthy",
            latency_ms=round(latency, 2),
        )
    except Exception as e:
        cred.status = "error"
        cred.ultimo_health_check = datetime.now(timezone.utc)
        latency = (time.monotonic() - start) * 1000
        await session.commit()
        return IntegrationTestResult(
            integration_id=str(cred.id),
            status="error",
            latency_ms=round(latency, 2),
            error=str(e),
        )


# ──────────────────────────────────────────────────────────────────
# 9-2: Audit Log search
# ──────────────────────────────────────────────────────────────────


@router.get("/audit-log", response_model=AuditLogSearchResponse)
async def search_audit_log(
    session: SessionDep,
    current_user: CurrentUserDep,
    action: str | None = Query(None),
    user_id: str | None = Query(None),
    entity: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
) -> AuditLogSearchResponse:
    conditions = []
    if action:
        actions = [a.strip() for a in action.split(",")]
        conditions.append(AuditLog.action.in_(actions))
    if user_id:
        conditions.append(AuditLog.user_id == user_id)
    if entity:
        conditions.append(AuditLog.entidade == entity)
    if date_from:
        conditions.append(AuditLog.criado_em >= date_from)
    if date_to:
        conditions.append(AuditLog.criado_em <= date_to)

    where_clause = and_(*conditions) if conditions else True

    # Count
    count_q = select(func.count()).select_from(AuditLog).where(where_clause)
    total = (await session.execute(count_q)).scalar() or 0

    # Data
    q = (
        select(AuditLog)
        .where(where_clause)
        .order_by(AuditLog.criado_em.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    result = await session.execute(q)
    rows = result.scalars().all()

    items = []
    for r in rows:
        # Verify HMAC
        try:
            expected = AuditLogger._sign(
                action=r.action,
                user_id=str(r.user_id) if r.user_id else None,
                entity=r.entidade,
                entity_id=r.entidade_id,
                payload_before=r.payload_before,
                payload_after=r.payload_after,
                module=r.module or "core",
                category=r.category,
                severity=r.severity,
                ts=r.criado_em,
            )
            hmac_valid = expected == r.hmac_assinatura
        except Exception:
            hmac_valid = False

        items.append(
            AuditLogEntryOut(
                id=r.id,
                user_id=str(r.user_id) if r.user_id else None,
                action=r.action,
                entity=r.entidade,
                entity_id=r.entidade_id,
                payload_before=r.payload_before,
                payload_after=r.payload_after,
                ip=r.ip,
                user_agent=r.user_agent,
                correlation_id=r.correlation_id,
                module=r.module,
                category=r.category,
                severity=r.severity,
                hmac_valid=hmac_valid,
                created_at=r.criado_em,
            )
        )

    return AuditLogSearchResponse(items=items, total=total, page=page, size=size)


# ──────────────────────────────────────────────────────────────────
# 9-3: Module management
# ──────────────────────────────────────────────────────────────────


@router.get("/modules", response_model=list[ModuleOut])
async def list_modules(session: SessionDep, current_user: CurrentUserDep) -> list[ModuleOut]:
    result = await session.execute(
        select(ActiveModule).order_by(ActiveModule.module_id)
    )
    return [ModuleOut.model_validate(r) for r in result.scalars().all()]


@router.put("/modules/{module_id}", response_model=ModuleOut)
async def update_module(
    module_id: str,
    body: ModuleUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ModuleOut:
    result = await session.execute(
        select(ActiveModule).where(ActiveModule.module_id == module_id)
    )
    mod = result.scalar_one_or_none()
    if not mod:
        raise HTTPException(status_code=404, detail="Module not found")

    before = {"is_active": mod.ativo, "config": mod.config}
    if body.is_active is not None:
        mod.ativo = body.is_active
    if body.config is not None:
        mod.config = body.config

    audit = AuditLogger(session)
    await audit.record(
        action="module.updated",
        user_id=str(current_user.id),
        entity="active_modules",
        entity_id=module_id,
        payload_before=before,
        payload_after={"is_active": mod.ativo, "config": mod.config},
        ip=None,
        correlation_id=get_correlation_id(),
    )
    await session.commit()
    await session.refresh(mod)
    return ModuleOut.model_validate(mod)


@router.get("/modules/{module_id}/hooks", response_model=list[ModuleHookOut])
async def list_module_hooks(
    module_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> list[ModuleHookOut]:
    result = await session.execute(
        select(ModuleHooksConfig).where(ModuleHooksConfig.module_id == module_id)
    )
    rows = result.scalars().all()
    return [
        ModuleHookOut(
            id=str(r.id), module_id=r.module_id, event_type=r.tipo_evento,
            policy=r.policy, is_active=r.ativo,
        )
        for r in rows
    ]


# ──────────────────────────────────────────────────────────────────
# 9-4: Backup
# ──────────────────────────────────────────────────────────────────


@router.post("/backup", response_model=BackupTriggerResponse)
async def trigger_backup(
    session: SessionDep,
    current_user: CurrentUserDep,
) -> BackupTriggerResponse:
    from app.workers.tasks.backup import run_backup

    task = run_backup.delay()

    audit = AuditLogger(session)
    await audit.record(
        action="backup.triggered",
        user_id=str(current_user.id),
        entity="backup",
        ip=None,
        correlation_id=get_correlation_id(),
    )
    await session.commit()

    return BackupTriggerResponse(task_id=task.id, message="Backup task queued")


@router.get("/backups", response_model=list[BackupOut])
async def list_backups(
    current_user: CurrentUserDep,
) -> list[BackupOut]:
    import boto3
    from botocore.config import Config as BotoConfig
    from app.infrastructure.settings import get_settings

    settings = get_settings()
    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            config=BotoConfig(signature_version="s3v4", connect_timeout=5, read_timeout=5),
        )
        response = s3.list_objects_v2(Bucket=settings.S3_BUCKET, Prefix="backups/")
        objects = response.get("Contents", [])
        backups = [
            BackupOut(
                name=obj["Key"].replace("backups/", ""),
                size=obj.get("Size"),
                created_at=obj.get("LastModified", "").isoformat() if obj.get("LastModified") else None,
            )
            for obj in sorted(objects, key=lambda x: x.get("LastModified", ""), reverse=True)
        ]
        s3.close()
        return backups
    except Exception as e:
        log.warning("list_backups_failed", error=str(e))
        return []


# ──────────────────────────────────────────────────────────────────
# 9-5: Metrics
# ──────────────────────────────────────────────────────────────────


@router.get("/metrics", response_model=SystemMetricsOut)
async def get_system_metrics(current_user: CurrentUserDep) -> SystemMetricsOut:
    from redis.asyncio import Redis
    from app.infrastructure.db.session import get_engine
    from app.infrastructure.settings import get_settings

    metrics = SystemMetricsOut()

    # DB pool info
    try:
        engine = get_engine()
        pool = engine.pool
        metrics.db_pool_size = pool.size()  # type: ignore[union-attr]
        metrics.db_pool_checked_out = pool.checkedout()  # type: ignore[union-attr]
    except Exception:
        pass

    # Redis info
    settings = get_settings()
    redis: Redis | None = None
    try:
        redis = Redis.from_url(settings.REDIS_URL)
        info = await redis.info("clients")
        metrics.redis_connected_clients = info.get("connected_clients", 0)
        mem_info = await redis.info("memory")
        metrics.redis_used_memory_mb = round(mem_info.get("used_memory", 0) / 1024 / 1024, 2)
    except Exception:
        pass
    finally:
        if redis:
            await redis.aclose()

    return metrics


# ──────────────────────────────────────────────────────────────────
# 9-9: Settings CRUD
# ──────────────────────────────────────────────────────────────────


@router.get("/settings", response_model=list[SystemSettingOut])
async def get_settings_all(
    session: SessionDep,
    current_user: CurrentUserDep,
) -> list[SystemSettingOut]:
    result = await session.execute(
        select(SystemSetting)
        .where(SystemSetting.empresa_id == current_user.empresa_id)
        .order_by(SystemSetting.chave)
    )
    return [
        SystemSettingOut(key=r.chave, value=r.valor, updated_at=r.atualizado_em)
        for r in result.scalars().all()
    ]


@router.put("/settings", response_model=list[SystemSettingOut])
async def update_settings(
    body: SystemSettingUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> list[SystemSettingOut]:
    for key, value in body.settings.items():
        result = await session.execute(
            select(SystemSetting).where(
                SystemSetting.empresa_id == current_user.empresa_id,
                SystemSetting.chave == key,
            )
        )
        existing = result.scalar_one_or_none()

        before_val = existing.valor if existing else None

        if existing:
            existing.valor = value
            existing.atualizado_em = datetime.now(timezone.utc)
            existing.atualizado_por_id = current_user.id
        else:
            setting = SystemSetting(
                empresa_id=current_user.empresa_id,
                chave=key,
                valor=value,
                atualizado_em=datetime.now(timezone.utc),
                atualizado_por_id=current_user.id,
            )
            session.add(setting)

        audit = AuditLogger(session)
        await audit.record(
            action="settings.updated",
            user_id=str(current_user.id),
            entity="system_settings",
            entity_id=key,
            payload_before={"value": before_val} if before_val else None,
            payload_after={"value": value},
            ip=None,
            correlation_id=get_correlation_id(),
        )

    await session.commit()

    result = await session.execute(
        select(SystemSetting)
        .where(SystemSetting.empresa_id == current_user.empresa_id)
        .order_by(SystemSetting.chave)
    )
    return [
        SystemSettingOut(key=r.chave, value=r.valor, updated_at=r.atualizado_em)
        for r in result.scalars().all()
    ]
