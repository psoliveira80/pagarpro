import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.correlation import get_correlation_id
from app.core.tenant_context import EmpresaContextoAusenteError
from app.domain.shared.exceptions import DomainError

log = structlog.get_logger()


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content={
                "type": f"urn:app:errors:{exc.code.lower().replace('_', '-')}",
                "title": exc.__class__.__name__,
                "status": exc.http_status,
                "detail": str(exc),
                "instance": str(request.url),
                "code": exc.code,
                "request_id": get_correlation_id(),
            },
            media_type="application/problem+json",
        )

    @app.exception_handler(EmpresaContextoAusenteError)
    async def tenant_missing_handler(
        request: Request, exc: EmpresaContextoAusenteError
    ) -> JSONResponse:
        """Repos/stores tenant-scoped construídos sem contexto retornam 403,
        não 500. Detalhe vai pro log (mensagem do exc) — cliente recebe genérico
        para não enumerar superfície interna."""
        log.warning(
            "tenant_context_missing",
            path=str(request.url),
            detail=str(exc),
        )
        return JSONResponse(
            status_code=403,
            content={
                "type": "urn:app:errors:forbidden",
                "title": "Forbidden",
                "status": 403,
                "detail": "Acesso negado",
                "request_id": get_correlation_id(),
            },
            media_type="application/problem+json",
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        log.error(
            "unhandled_exception",
            error=str(exc),
            path=str(request.url),
            exc_info=exc,
        )
        return JSONResponse(
            status_code=500,
            content={
                "type": "urn:app:errors:internal-error",
                "title": "Internal Server Error",
                "status": 500,
                "detail": "An unexpected error occurred.",
                "request_id": get_correlation_id(),
            },
            media_type="application/problem+json",
        )
