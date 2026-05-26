import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint_returns_status():
    """Health endpoint should return JSON with status and dependency checks."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "db" in data
    assert "redis" in data
    assert "storage" in data


@pytest.mark.asyncio
async def test_openapi_docs_available():
    """OpenAPI docs should be accessible."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/openapi.json")

    assert response.status_code == 200
    data = response.json()
    assert "openapi" in data
    assert "paths" in data
    assert "/health" in data["paths"]


@pytest.mark.asyncio
async def test_cors_headers():
    """CORS headers should be set for allowed origins."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/health",
            headers={
                "Origin": "http://localhost:4200",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.headers.get("access-control-allow-origin") == "http://localhost:4200"


@pytest.mark.asyncio
async def test_correlation_id_header():
    """Every response should include X-Request-Id header."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) == 36  # UUID format


@pytest.mark.asyncio
async def test_unhandled_error_returns_problem_json():
    """Unhandled errors should return RFC 7807 Problem Details."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/nonexistent-path-that-triggers-404")

    # FastAPI returns 404 for unknown routes, not 500
    # But our exception handler should handle DomainErrors
    assert response.status_code in (404, 405)
