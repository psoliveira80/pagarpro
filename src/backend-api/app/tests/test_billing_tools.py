"""Tests for billing BI tools."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.agent.tool_interface import ToolResult


class TestBillingTools:
    """Test billing tool functions with mocked sessions."""

    @pytest.mark.asyncio
    async def test_get_overdue_installments_returns_data(self):
        """get_overdue_installments returns structured data."""
        from app.core.agent.tools.billing_tools import get_overdue_installments

        mock_row = (
            uuid4(),          # id
            uuid4(),          # contrato_id
            3,                # sequencia
            date.today() - timedelta(days=10),  # data_vencimento
            Decimal("1500.00"),  # valor
            Decimal("0.00"),     # valor_pago
            "vencido",           # status
        )

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        result = await get_overdue_installments(session, days_min=1, days_max=30)

        assert isinstance(result, ToolResult)
        assert result.error is None
        assert len(result.data) == 1
        assert result.data[0]["status"] == "vencido"
        assert result.data[0]["days_overdue"] == 10

    @pytest.mark.asyncio
    async def test_get_overdue_installments_empty(self):
        """get_overdue_installments returns empty when no overdue."""
        from app.core.agent.tools.billing_tools import get_overdue_installments

        mock_result = MagicMock()
        mock_result.all.return_value = []

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        result = await get_overdue_installments(session)

        assert result.data == []
        assert result.error is None

    @pytest.mark.asyncio
    async def test_get_collection_summary_returns_summary(self):
        """get_collection_summary returns aggregated data."""
        from app.core.agent.tools.billing_tools import get_collection_summary

        session = AsyncMock()
        # Mock three queries: total, collected, overdue count
        session.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar=MagicMock(return_value=Decimal("10000.00"))),
                MagicMock(scalar=MagicMock(return_value=Decimal("7500.00"))),
                MagicMock(scalar=MagicMock(return_value=5)),
            ]
        )

        result = await get_collection_summary(session)

        assert result.error is None
        assert result.data["total_receivable"] == 10000.0
        assert result.data["total_collected"] == 7500.0
        assert result.data["collection_rate_pct"] == 75.0

    @pytest.mark.asyncio
    async def test_get_revenue_by_period(self):
        """get_revenue_by_period returns bucketed revenue."""
        from app.core.agent.tools.billing_tools import get_revenue_by_period
        from datetime import datetime

        mock_rows = [
            (datetime(2026, 1, 1), Decimal("5000.00"), 10),
            (datetime(2026, 2, 1), Decimal("7000.00"), 15),
        ]
        mock_result = MagicMock()
        mock_result.all.return_value = mock_rows

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        result = await get_revenue_by_period(
            session, start_date="2026-01-01", end_date="2026-03-01"
        )

        assert result.error is None
        assert len(result.data) == 2
        assert result.data[0]["revenue"] == 5000.0

    @pytest.mark.asyncio
    async def test_generate_pix_qr_not_found(self):
        """generate_pix_qr returns error for nonexistent installment."""
        from app.core.agent.tools.billing_tools import generate_pix_qr

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        result = await generate_pix_qr(session, installment_id=str(uuid4()))

        assert result.error == "Installment not found"
        assert result.confidence == "low"

    @pytest.mark.asyncio
    async def test_list_defaulters_returns_list(self):
        """list_defaulters returns customer debt summaries."""
        from app.core.agent.tools.billing_tools import list_defaulters

        today = date.today()
        mock_rows = [
            (uuid4(), "John Doe", "5511999999999", 3, Decimal("4500.00"), today - timedelta(days=30)),
        ]
        mock_result = MagicMock()
        mock_result.all.return_value = mock_rows

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        result = await list_defaulters(session, min_days_overdue=1, limit=10)

        assert result.error is None
        assert len(result.data) == 1
        assert result.data[0]["nome_completo"] == "John Doe"
        assert result.data[0]["total_debt"] == 4500.0

    @pytest.mark.asyncio
    async def test_register_writeoff_not_found(self):
        """register_writeoff returns error for nonexistent installment."""
        from app.core.agent.tools.billing_tools import register_writeoff

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        result = await register_writeoff(session, installment_id=str(uuid4()))

        assert result.error == "Installment not found"
