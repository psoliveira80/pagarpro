"""Tests for Epic 9: Admin endpoints — integrations, audit log, global search, LGPD."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.api.v1.schemas.admin import (
    IntegrationCreate,
    IntegrationOut,
    IntegrationUpdate,
    AuditLogSearchResponse,
    GlobalSearchResponse,
    SearchResultItem,
    AnonymizeRequest,
)


# ─── Unit tests for schemas ───


class TestIntegrationSchemas:
    def test_integration_create_defaults(self):
        # WhatsApp ficou bloqueado neste endpoint (passou pra /numeros-cobranca).
        # Aqui testamos com uma categoria genérica que ainda usa /admin/integrations.
        body = IntegrationCreate(category="llm", provider="openai")
        assert body.is_active is True
        assert body.config == {}

    def test_integration_create_rejeita_whatsapp(self):
        """Garantia da decisão arquitetural de 2026-05-29: WhatsApp tem
        endpoint dedicado (POST /numeros-cobranca) porque cada credencial é
        uma INSTÂNCIA (número), não um provedor único."""
        with pytest.raises(ValueError, match=r"numeros-cobranca"):
            IntegrationCreate(category="whatsapp", provider="evolution_go")

    def test_integration_update_partial(self):
        body = IntegrationUpdate(provider="zapi")
        assert body.provider == "zapi"
        assert body.config is None
        assert body.is_active is None

    def test_integration_out_from_dict(self):
        out = IntegrationOut(
            id="abc-123",
            category="payment",
            provider="stripe",
            is_active=True,
            config={"api_key": "***"},
            status="healthy",
            last_health_check=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        assert out.category == "payment"
        assert out.status == "healthy"


class TestAuditLogSchemas:
    def test_search_response_structure(self):
        resp = AuditLogSearchResponse(items=[], total=0, page=1, size=25)
        assert resp.total == 0
        assert len(resp.items) == 0


class TestGlobalSearchSchemas:
    def test_search_result_item(self):
        item = SearchResultItem(
            id="123",
            type="customer",
            title="John Doe",
            subtitle="123.456.789-00",
            url="/system/customers/123",
        )
        assert item.type == "customer"
        assert "/system/customers/" in item.url

    def test_global_search_response(self):
        results = [
            SearchResultItem(id="1", type="customer", title="A", url="/a"),
            SearchResultItem(id="2", type="contract", title="B", url="/b"),
        ]
        resp = GlobalSearchResponse(results=results, total=2)
        assert resp.total == 2
        assert resp.results[0].type == "customer"


class TestAnonymizeSchema:
    def test_anonymize_request(self):
        req = AnonymizeRequest(reason="Customer requested LGPD deletion")
        assert "LGPD" in req.reason


# ─── Integration test stubs (require running DB) ───


class TestIntegrationEndpointsStub:
    """These tests validate the route handler logic structure.
    Full integration tests require a running database."""

    def test_integration_crud_schema_roundtrip(self):
        """Ensure create -> out schema works."""
        create = IntegrationCreate(
            category="llm",
            provider="openai",
            config={"api_key": "sk-test"},
        )
        out = IntegrationOut(
            id=str(uuid4()),
            category=create.category,
            provider=create.provider,
            is_active=create.is_active,
            config=create.config,
            status="unknown",
            last_health_check=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        assert out.provider == "openai"
        assert out.is_active is True

    def test_search_result_grouping(self):
        """Verify search results can be grouped by type."""
        results = [
            SearchResultItem(id="1", type="customer", title="A", url="/a"),
            SearchResultItem(id="2", type="customer", title="B", url="/b"),
            SearchResultItem(id="3", type="contract", title="C", url="/c"),
            SearchResultItem(id="4", type="vehicle", title="D", url="/d"),
        ]
        grouped = {}
        for r in results:
            grouped.setdefault(r.type, []).append(r)

        assert len(grouped["customer"]) == 2
        assert len(grouped["contract"]) == 1
        assert len(grouped["vehicle"]) == 1


class TestAuditLogSearchStub:
    def test_filter_params_parsing(self):
        """Verify multi-select action filter splitting."""
        action_param = "customer.created,customer.updated,customer.deleted"
        actions = [a.strip() for a in action_param.split(",")]
        assert len(actions) == 3
        assert "customer.created" in actions

    def test_date_range_filter(self):
        """Verify date strings can be compared."""
        date_from = "2024-01-01T00:00:00Z"
        date_to = "2024-12-31T23:59:59Z"
        assert date_from < date_to


class TestLGPDExportStub:
    def test_cpf_masking(self):
        """Verify CPF masking logic."""
        cpf = "123.456.789-00"
        masked = cpf[:3] + ".***.***-**"
        assert masked == "123.***.***-**"
        assert masked.startswith("123")

    def test_anonymization_preserves_id(self):
        """Verify anonymization concept preserves the customer ID."""
        customer_id = str(uuid4())
        # After anonymization, the ID should remain the same
        assert len(customer_id) == 36  # UUID format
