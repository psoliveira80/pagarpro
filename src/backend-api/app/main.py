from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.exception_handlers import register_exception_handlers
from app.api.middleware import (
    CorrelationIdMiddleware,
    PathAliasMiddleware,
    TenantContextResetMiddleware,
)
from app.infrastructure.db.session import get_engine, dispose_engine
from app.infrastructure.observability.logging import configure_logging
from app.infrastructure.settings import get_settings

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    # Eagerly create engine to validate DB connection on startup
    get_engine()

    # Register asset modules
    from app.core.assets.registry import register_module
    from app.modules.vehicles.module import VehicleModule

    register_module(VehicleModule())

    # Register agent tools
    from app.core.agent.tools.registration import register_all_tools

    register_all_tools()

    log.info("application_startup", product=get_settings().PRODUCT_NAME)
    yield
    await dispose_engine()
    log.info("application_shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=f"{settings.PRODUCT_NAME} API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Middleware (order matters — outermost first)
    app.add_middleware(CorrelationIdMiddleware)
    # Path alias deve rodar ANTES do roteamento mas depois do logging.
    # Reescreve `/api/v1/titulos-receber` (e amigos) → `/api/v1/receivables`.
    app.add_middleware(PathAliasMiddleware)
    # Tenant context reset DEVE ficar antes (mais externo) do roteamento para
    # garantir que o contexto começa limpo a cada request, independente de
    # vazamentos de tasks asyncio anteriores.
    app.add_middleware(TenantContextResetMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    # API v1 routes
    from app.api.v1.auth_routes import router as auth_router

    app.include_router(auth_router, prefix="/api/v1")

    # API v1 — customer routes
    from app.api.v1.customer_routes import router as customer_router

    app.include_router(customer_router, prefix="/api/v1")

    # API v1 — vehicle routes
    from app.modules.vehicles.routes import router as vehicle_router

    app.include_router(vehicle_router, prefix="/api/v1")

    # API v1 — contract routes
    from app.api.v1.contract_routes import router as contract_router

    app.include_router(contract_router, prefix="/api/v1")

    # API v1 — receivable routes
    from app.api.v1.receivable_routes import router as receivable_router

    app.include_router(receivable_router, prefix="/api/v1")

    # API v1 — payable routes (suppliers, expense categories, payables, recurring)
    from app.api.v1.payable_routes import router as payable_router

    app.include_router(payable_router, prefix="/api/v1")

    # API v1 — webhook routes
    from app.api.v1.webhook_routes import router as webhook_router

    app.include_router(webhook_router, prefix="/api/v1")

    # API v1 — report routes
    from app.api.v1.report_routes import router as report_router

    app.include_router(report_router, prefix="/api/v1")

    # API v1 — dashboard routes
    from app.api.v1.dashboard_routes import router as dashboard_router

    app.include_router(dashboard_router, prefix="/api/v1")

    # API v1 — conversation routes
    from app.api.v1.conversation_routes import router as conversation_router

    app.include_router(conversation_router, prefix="/api/v1")

    # API v1 — agent routes
    from app.api.v1.agent_routes import router as agent_router

    app.include_router(agent_router, prefix="/api/v1")

    # API v1 — WhatsApp webhook routes
    from app.api.v1.webhook_whatsapp_routes import router as wa_webhook_router

    app.include_router(wa_webhook_router, prefix="/api/v1")

    # API v1 — broadcast routes
    from app.api.v1.broadcast_routes import router as broadcast_router

    app.include_router(broadcast_router, prefix="/api/v1")

    # API v1 — bank account routes (Epic 7)
    from app.api.v1.bank_account_routes import router as bank_account_router

    app.include_router(bank_account_router, prefix="/api/v1")

    # API v1 — reconciliation routes (Epic 7)
    from app.api.v1.reconciliation_routes import router as reconciliation_router

    app.include_router(reconciliation_router, prefix="/api/v1")

    # API v1 — admin routes (Epic 9: integrations, audit, modules, settings, backup, metrics)
    from app.api.v1.admin_routes import router as admin_router

    app.include_router(admin_router, prefix="/api/v1")

    # API v1 — global search (Epic 9: command palette)
    from app.api.v1.search_routes import router as search_router

    app.include_router(search_router, prefix="/api/v1")

    # API v1 — LGPD customer data routes (Epic 9)
    from app.api.v1.customer_data_routes import router as customer_data_router

    app.include_router(customer_data_router, prefix="/api/v1")

    # API v1 — configurações tipadas (Epic 13, Story 13.4)
    from app.api.v1.configuracoes_routes import router as configuracoes_router

    app.include_router(configuracoes_router, prefix="/api/v1")

    # API v1 — templates de mensagem (Epic 13, Story 13.10)
    from app.api.v1.templates_mensagem_routes import router as templates_mensagem_router

    app.include_router(templates_mensagem_router, prefix="/api/v1")

    # API v1 — observabilidade do motor (Epic 13, Story 13.5)
    from app.api.v1.motor_routes import router as motor_router

    app.include_router(motor_router, prefix="/api/v1")

    # SSE routes
    from app.api.sse import router as sse_router

    app.include_router(sse_router)

    # Health endpoint
    @app.get("/health", tags=["system"])
    async def health() -> dict:
        import asyncio

        from redis.asyncio import Redis
        import boto3
        from botocore.config import Config as BotoConfig
        from sqlalchemy import text

        checks: dict[str, str] = {}

        # Postgres
        try:
            engine = get_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            checks["db"] = "ok"
        except Exception:
            log.warning("health_check_db_failed", exc_info=True)
            checks["db"] = "error"

        # Redis (with guaranteed close)
        redis: Redis | None = None
        try:
            redis = Redis.from_url(settings.REDIS_URL)
            await redis.ping()
            checks["redis"] = "ok"
        except Exception:
            log.warning("health_check_redis_failed", exc_info=True)
            checks["redis"] = "error"
        finally:
            if redis is not None:
                await redis.aclose()

        # MinIO / S3 (run sync boto3 in thread to avoid blocking event loop)
        def _check_s3() -> str:
            try:
                s3 = boto3.client(
                    "s3",
                    endpoint_url=settings.S3_ENDPOINT_URL,
                    aws_access_key_id=settings.S3_ACCESS_KEY,
                    aws_secret_access_key=settings.S3_SECRET_KEY,
                    region_name=settings.S3_REGION,
                    config=BotoConfig(
                        signature_version="s3v4",
                        connect_timeout=3,
                        read_timeout=3,
                    ),
                )
                s3.list_buckets()
                s3.close()
                return "ok"
            except Exception:
                return "error"

        checks["storage"] = await asyncio.to_thread(_check_s3)
        if checks["storage"] == "error":
            log.warning("health_check_storage_failed")

        all_ok = all(v == "ok" for v in checks.values())
        return {"status": "ok" if all_ok else "degraded", **checks}

    return app


app = create_app()
