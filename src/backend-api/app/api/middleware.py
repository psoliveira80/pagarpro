import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.correlation import generate_correlation_id
from app.core.tenant_context import reset_empresa_id

log = structlog.get_logger()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        correlation_id = generate_correlation_id()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        response.headers["X-Request-Id"] = correlation_id

        log.info(
            "request_completed",
            method=request.method,
            path=str(request.url.path),
            status=response.status_code,
            duration_ms=duration_ms,
        )

        structlog.contextvars.unbind_contextvars("correlation_id")
        return response


class TenantContextResetMiddleware(BaseHTTPMiddleware):
    """Limpa o tenant context no início de cada request.

    Defesa em profundidade contra vazamento de `empresa_id` entre requests
    em ambientes que reusam tasks asyncio (testes, workers, SSE de longa
    duração). FastAPI normalmente cria task nova por request, mas este
    middleware garante reset explícito independente do runner.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        reset_empresa_id()
        try:
            return await call_next(request)
        finally:
            reset_empresa_id()


# Story 12-3e — alias de URL paths PT-BR → EN.
# Routers continuam declarando paths em inglês; este middleware reescreve
# o `request.url.path` antes do roteamento para que clientes possam usar
# tanto o nome legado (inglês) quanto o canônico (português). Quando o
# frontend (story 12-8) migrar 100% para PT-BR, removeremos os routers EN.
#
# Mapeamento ordenado do MAIS específico para o MENOS específico para evitar
# matches parciais (ex.: `/conciliacao/transactions` antes de `/conciliacao`).
_PT_TO_EN_PATH_ALIASES: tuple[tuple[str, str], ...] = (
    ("/api/v1/conciliacao/", "/api/v1/reconciliation/"),
    ("/api/v1/titulos-receber/", "/api/v1/receivables/"),
    ("/api/v1/titulos-receber", "/api/v1/receivables"),
    ("/api/v1/titulos-pagar/", "/api/v1/payables/"),
    ("/api/v1/titulos-pagar", "/api/v1/payables"),
    ("/api/v1/despesas-recorrentes/", "/api/v1/recurring-payables/"),
    ("/api/v1/despesas-recorrentes", "/api/v1/recurring-payables"),
    ("/api/v1/fornecedores/", "/api/v1/suppliers/"),
    ("/api/v1/fornecedores", "/api/v1/suppliers"),
    ("/api/v1/categorias-despesa/", "/api/v1/expense-categories/"),
    ("/api/v1/categorias-despesa", "/api/v1/expense-categories"),
    ("/api/v1/contas-bancarias/", "/api/v1/bank-accounts/"),
    ("/api/v1/contas-bancarias", "/api/v1/bank-accounts"),
)


class PathAliasMiddleware(BaseHTTPMiddleware):
    """Reescreve paths PT-BR para EN antes do roteamento (story 12-3e).

    Ambos os caminhos respondem com o mesmo handler — útil para o frontend
    migrar gradualmente de `/receivables` para `/titulos-receber` sem
    backend duplicar lógica. Quando 12-8 fechar e os clientes EN sumirem,
    invertemos: routers em PT-BR + alias EN com `deprecated=True`.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        original_path = request.url.path
        for pt_prefix, en_prefix in _PT_TO_EN_PATH_ALIASES:
            if original_path.startswith(pt_prefix):
                novo_path = en_prefix + original_path[len(pt_prefix):]
                # Mutate scope para o router enxergar o novo path.
                request.scope["path"] = novo_path
                request.scope["raw_path"] = novo_path.encode("latin-1")
                break
        return await call_next(request)
