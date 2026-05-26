"""Tests for Epic 8: Dashboard & Reports endpoints."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_headers():
    """Placeholder auth headers — in real tests, create a user + JWT."""
    return {"Authorization": "Bearer test-token"}


class TestDashboardSummary:
    """Tests for GET /api/v1/dashboard/summary."""

    @pytest.mark.anyio
    async def test_summary_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/dashboard/summary")
        assert resp.status_code in (401, 403)

    @pytest.mark.anyio
    async def test_summary_response_shape(self, client: AsyncClient):
        """Verify the endpoint exists and returns expected shape (when auth works)."""
        resp = await client.get("/api/v1/dashboard/summary")
        # Without valid auth, we just confirm the route is mounted (not 404)
        assert resp.status_code != 404


class TestReceivablesTrend:
    """Tests for GET /api/v1/dashboard/charts/receivables-trend."""

    @pytest.mark.anyio
    async def test_trend_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/dashboard/charts/receivables-trend")
        assert resp.status_code in (401, 403)

    @pytest.mark.anyio
    async def test_trend_route_exists(self, client: AsyncClient):
        resp = await client.get("/api/v1/dashboard/charts/receivables-trend")
        assert resp.status_code != 404


class TestOverdueAging:
    """Tests for GET /api/v1/dashboard/charts/overdue-aging."""

    @pytest.mark.anyio
    async def test_aging_route_exists(self, client: AsyncClient):
        resp = await client.get("/api/v1/dashboard/charts/overdue-aging")
        assert resp.status_code != 404


class TestTopDefaulters:
    """Tests for GET /api/v1/dashboard/charts/top-defaulters."""

    @pytest.mark.anyio
    async def test_defaulters_route_exists(self, client: AsyncClient):
        resp = await client.get("/api/v1/dashboard/charts/top-defaulters")
        assert resp.status_code != 404


class TestReportsReceivables:
    """Tests for GET /api/v1/reports/receivables."""

    @pytest.mark.anyio
    async def test_receivables_report_route_exists(self, client: AsyncClient):
        resp = await client.get("/api/v1/reports/receivables")
        assert resp.status_code != 404


class TestReportsCustom:
    """Tests for POST /api/v1/reports/custom."""

    @pytest.mark.anyio
    async def test_custom_report_route_exists(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/reports/custom",
            json={"dimensions": ["customer_name"], "measures": ["count"]},
        )
        assert resp.status_code != 404


class TestCustomerDashboard:
    """Tests for GET /api/v1/dashboard/customer/{id}."""

    @pytest.mark.anyio
    async def test_customer_dashboard_route_exists(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/dashboard/customer/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code != 404


class TestVehicleDashboard:
    """Tests for GET /api/v1/dashboard/vehicle/{id}."""

    @pytest.mark.anyio
    async def test_vehicle_dashboard_route_exists(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/dashboard/vehicle/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code != 404
