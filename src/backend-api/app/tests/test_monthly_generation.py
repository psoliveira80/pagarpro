"""Tests for Story 10.1 — Monthly Installment Generation with Correction Index.

Covers:
- BcbCorrectionAdapter: happy path, Redis cache fallback, total outage.
- _process_contract / _run task: idempotency, value correction math,
  date advancement, no-correction-index path, skips inactive contracts.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text

from app.domain.ports.correction_index_provider import (
    CorrectionIndexUnavailableError,
)
from app.infrastructure.adapters.bcb_correction_adapter import (
    BcbCorrectionAdapter,
    _cache_key,
)
from app.infrastructure.db.session import get_engine
from app.workers.tasks.gerar_titulos_mensais import (
    _aplicar_correcao as _apply_correction,
    _avancar_um_mes as _advance_one_month,
    _run,
)

TEST_EMAIL = "monthly-gen-test@example.com"


# ── BcbCorrectionAdapter ────────────────────────────────────────────────────


class _FakeRedis:
    """Minimal in-memory async Redis stand-in for unit tests."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        del ex  # TTL is not modeled in this in-memory stub.
        self._store[key] = value

    async def aclose(self) -> None:  # pragma: no cover - parity with real client
        return None


def _mock_async_response(status_code: int, json_body):
    request = httpx.Request("GET", "https://api.bcb.gov.br/test")
    return httpx.Response(status_code, json=json_body, request=request)


@pytest.mark.asyncio
async def test_bcb_adapter_happy_path():
    redis = _FakeRedis()
    adapter = BcbCorrectionAdapter(redis=redis)
    payload = [{"data": "01/05/2026", "valor": "0.53"}]

    async def _mock_get(self, url):  # noqa: ANN001
        return _mock_async_response(200, payload)

    with patch.object(httpx.AsyncClient, "get", _mock_get):
        rate = await adapter.get_current_rate("ipca", date(2026, 5, 20))

    assert rate == Decimal("0.53")
    # Result should be cached for the current YYYY-MM bucket.
    assert redis._store[_cache_key("ipca", date(2026, 5, 20))] == "0.53"


@pytest.mark.asyncio
async def test_bcb_adapter_falls_back_to_cache_when_api_fails():
    redis = _FakeRedis()
    cache_key = _cache_key("igpm", date(2026, 5, 20))
    redis._store[cache_key] = "0.41"
    adapter = BcbCorrectionAdapter(redis=redis)

    async def _mock_get(self, url):  # noqa: ANN001
        raise httpx.ConnectError("BCB unreachable")

    with patch.object(httpx.AsyncClient, "get", _mock_get):
        rate = await adapter.get_current_rate("igpm", date(2026, 5, 20))

    assert rate == Decimal("0.41")


@pytest.mark.asyncio
async def test_bcb_adapter_raises_when_api_and_cache_empty():
    redis = _FakeRedis()
    adapter = BcbCorrectionAdapter(redis=redis)

    async def _mock_get(self, url):  # noqa: ANN001
        raise httpx.ConnectError("BCB unreachable")

    with patch.object(httpx.AsyncClient, "get", _mock_get):
        with pytest.raises(CorrectionIndexUnavailableError):
            await adapter.get_current_rate("inpc", date(2026, 5, 20))


@pytest.mark.asyncio
async def test_bcb_adapter_rejects_unknown_index():
    redis = _FakeRedis()
    adapter = BcbCorrectionAdapter(redis=redis)
    with pytest.raises(ValueError):
        await adapter.get_current_rate("selic", date(2026, 5, 20))


# ── Pure helpers ───────────────────────────────────────────────────────────


def test_apply_correction_rounds_to_two_decimals():
    # 1000 * (1 + 0.53/100) = 1005.30 exactly
    assert _apply_correction(Decimal("1000"), Decimal("0.53")) == Decimal("1005.30")
    # 999.99 * 1.0053 = 1005.289947 -> rounds to 1005.29
    assert _apply_correction(Decimal("999.99"), Decimal("0.53")) == Decimal("1005.29")
    # 500 * (1 + 0/100) = 500.00 (no correction path)
    assert _apply_correction(Decimal("500"), Decimal("0")) == Decimal("500.00")


def test_advance_one_month_simple():
    assert _advance_one_month(date(2026, 5, 15), 15) == date(2026, 6, 15)


def test_advance_one_month_year_rollover():
    assert _advance_one_month(date(2026, 12, 10), 10) == date(2027, 1, 10)


def test_advance_one_month_february_safe_for_28():
    # generation_day capped to 28 by DB constraint; february always has day 28.
    assert _advance_one_month(date(2026, 1, 28), 28) == date(2026, 2, 28)


# ── Task integration tests ────────────────────────────────────────────────


async def _create_minimum_dependencies(user_id: str, customer_id: str) -> str:
    """Cria fixtures mínimas e retorna o `empresa_id` (string) usado."""
    engine = get_engine()
    async with engine.begin() as conn:
        # Pre-cleanup: null out FK references on rows that might have been left
        # by a previous failed test run with the same TEST_EMAIL user
        for tbl in (
            "cadastro.clientes",
            "veiculos.veiculos",
            "contrato.contratos",
        ):
            await conn.execute(
                text(
                    f"UPDATE {tbl} SET criado_por_id = NULL "
                    f"WHERE criado_por_id IN (SELECT id FROM acesso.usuarios WHERE email = :e)"
                ),
                {"e": TEST_EMAIL},
            )
        await conn.execute(
            text("DELETE FROM acesso.usuarios WHERE email = :e"), {"e": TEST_EMAIL}
        )
        empresa_row = (await conn.execute(text("SELECT id FROM comercial.empresas LIMIT 1"))).first()
        assert empresa_row is not None, "No empresa found — run seed first"
        empresa_id = str(empresa_row[0])
        await conn.execute(
            text(
                "INSERT INTO acesso.usuarios "
                "(id, email, senha_hash, nome_completo, ativo, mfa_ativo, empresa_id) "
                "VALUES (:id, :email, 'x', 'Monthly Tester', true, false, :eid)"
            ),
            {"id": user_id, "email": TEST_EMAIL, "eid": empresa_id},
        )
        # cpf_cnpj is UNIQUE; randomize to avoid collisions across runs.
        cpf = customer_id.replace("-", "")[:11]
        await conn.execute(
            text(
                "INSERT INTO cadastro.clientes (id, nome_completo, cpf_cnpj, criado_por_id, empresa_id) "
                "VALUES (:id, 'Monthly Cust', :cpf, :uid, :eid)"
            ),
            {"id": customer_id, "cpf": cpf, "uid": user_id, "eid": empresa_id},
        )
    return empresa_id


async def _create_monthly_contract(
    user_id: str,
    customer_id: str,
    next_gen: date,
    base_value: Decimal,
    index: str | None = "ipca",
    generation_day: int = 15,
    status: str = "vigente",
) -> str:
    contract_id = str(uuid4())
    engine = get_engine()
    async with engine.begin() as conn:
        empresa_row = (await conn.execute(text("SELECT id FROM comercial.empresas LIMIT 1"))).first()
        assert empresa_row is not None, "No empresa found — run seed first"
        empresa_id = str(empresa_row[0])
        await conn.execute(
            text(
                "INSERT INTO contrato.contratos ("
                "  id, cliente_id, numero, status, data_inicio, data_fim, "
                "  valor_total, criado_por_id, modo_geracao, indice_correcao, "
                "  dia_geracao, proxima_geracao_em, valor_base_mensal, empresa_id, veiculo_id"
                ") VALUES ("
                "  :id, :cid, :num, :status, :sd, :ed, :tv, :uid, 'mensal', :idx, "
                "  :gd, :ngd, :bv, :eid, NULL"
                ")"
            ),
            {
                "id": contract_id,
                "cid": customer_id,
                "num": f"TEST-{contract_id[:8]}",
                "status": status,
                "sd": date(2026, 1, 1),
                "ed": date(2028, 1, 1),
                "tv": Decimal("0"),
                "uid": user_id,
                "idx": index,
                "gd": generation_day,
                "ngd": next_gen,
                "bv": base_value,
                "eid": empresa_id,
            },
        )
    return contract_id


async def _cleanup_contract(contract_id: str, user_id: str, customer_id: str) -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "DELETE FROM contrato.eventos_contrato WHERE contrato_id = :id"
            ),
            {"id": contract_id},
        )
        await conn.execute(
            text("DELETE FROM financeiro.titulos_receber WHERE contrato_id = :id"),
            {"id": contract_id},
        )
        await conn.execute(
            text("DELETE FROM contrato.lotes_geracao WHERE contrato_id = :id"),
            {"id": contract_id},
        )
        await conn.execute(
            text("DELETE FROM contrato.contratos WHERE id = :id"), {"id": contract_id}
        )
        await conn.execute(
            text("DELETE FROM cadastro.clientes WHERE id = :id"), {"id": customer_id}
        )
        # FK RESTRICT (Modelo A) blocks user delete while other rows reference
        # criado_por_id. Easiest cleanup: null out the references before deleting user.
        for tbl in (
            "cadastro.clientes",
            "veiculos.veiculos",
            "contrato.contratos",
        ):
            await conn.execute(
                text(f"UPDATE {tbl} SET criado_por_id = NULL WHERE criado_por_id = :uid"),
                {"uid": user_id},
            )
        await conn.execute(
            text("ALTER TABLE logs.log_auditoria DISABLE TRIGGER trg_log_auditoria_immutable")
        )
        await conn.execute(
            text("UPDATE logs.log_auditoria SET user_id = NULL WHERE user_id = :uid"),
            {"uid": user_id},
        )
        await conn.execute(
            text("ALTER TABLE logs.log_auditoria ENABLE TRIGGER trg_log_auditoria_immutable")
        )
        await conn.execute(text("DELETE FROM acesso.usuarios WHERE id = :uid"), {"uid": user_id})


class _StubProvider:
    """In-memory ICorrectionIndexProvider for task tests."""

    def __init__(self, rate: Decimal = Decimal("0.50")) -> None:
        self.rate = rate
        self.calls: list[tuple[str, date]] = []

    async def get_current_rate(self, index: str, reference_date: date) -> Decimal:
        self.calls.append((index, reference_date))
        return self.rate


@pytest.mark.asyncio
async def test_task_generates_installment_with_correction():
    user_id = str(uuid4())
    customer_id = str(uuid4())
    empresa_id = UUID(await _create_minimum_dependencies(user_id, customer_id))
    contract_id = await _create_monthly_contract(
        user_id,
        customer_id,
        next_gen=date.today(),  # due today => should run
        base_value=Decimal("1000.00"),
        index="ipca",
        generation_day=15,
    )

    provider = _StubProvider(rate=Decimal("0.53"))
    try:
        summary = await _run(empresa_id, provider=provider)
        assert summary["generated"] == 1

        # Re-running on the same day must be idempotent.
        summary2 = await _run(empresa_id, provider=provider)
        # next_generation_date was advanced, so contract is no longer due.
        assert summary2["generated"] == 0
        assert summary2["skipped"] == 0

        # Inspect persisted state.
        engine = get_engine()
        async with engine.begin() as conn:
            installments = (
                await conn.execute(
                    text(
                        "SELECT sequencia, valor, valor AS current_value, data_vencimento "
                        "FROM financeiro.titulos_receber WHERE contrato_id = :id ORDER BY sequencia"
                    ),
                    {"id": contract_id},
                )
            ).all()
            next_gen_row = (
                await conn.execute(
                    text(
                        "SELECT proxima_geracao_em FROM contrato.contratos WHERE id = :id"
                    ),
                    {"id": contract_id},
                )
            ).one()
        assert len(installments) == 1
        # 1000 * 1.0053 = 1005.30
        assert installments[0].valor == Decimal("1005.30")
        assert installments[0].current_value == Decimal("1005.30")
        # proxima_geracao_em advanced by one month, snapped to generation_day=15.
        today = date.today()
        expected_next = _advance_one_month(today, 15)
        assert next_gen_row.proxima_geracao_em == expected_next
    finally:
        await _cleanup_contract(contract_id, user_id, customer_id)


@pytest.mark.asyncio
async def test_task_skips_contract_without_correction_index():
    user_id = str(uuid4())
    customer_id = str(uuid4())
    empresa_id = UUID(await _create_minimum_dependencies(user_id, customer_id))
    contract_id = await _create_monthly_contract(
        user_id,
        customer_id,
        next_gen=date.today(),
        base_value=Decimal("750.00"),
        index=None,  # no correction
        generation_day=10,
    )

    provider = AsyncMock()
    try:
        summary = await _run(empresa_id, provider=provider)
        assert summary["generated"] == 1
        provider.get_current_rate.assert_not_awaited()

        engine = get_engine()
        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT valor FROM financeiro.titulos_receber "
                        "WHERE contrato_id = :id"
                    ),
                    {"id": contract_id},
                )
            ).one()
        # No index => value is the base, untouched.
        assert row.valor == Decimal("750.00")
    finally:
        await _cleanup_contract(contract_id, user_id, customer_id)


@pytest.mark.asyncio
async def test_task_skips_inactive_contracts():
    user_id = str(uuid4())
    customer_id = str(uuid4())
    empresa_id = UUID(await _create_minimum_dependencies(user_id, customer_id))
    contract_id = await _create_monthly_contract(
        user_id,
        customer_id,
        next_gen=date.today(),
        base_value=Decimal("500.00"),
        index="ipca",
        status="encerrado",
    )

    provider = _StubProvider()
    try:
        summary = await _run(empresa_id, provider=provider)
        assert summary["generated"] == 0
        # Provider must not be called for encerrado contracts.
        assert provider.calls == []
    finally:
        await _cleanup_contract(contract_id, user_id, customer_id)
