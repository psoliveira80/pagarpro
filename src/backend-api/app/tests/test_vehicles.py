"""Tests for the Vehicle module — CRUD, module registration, hooks, value objects."""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.assets.registry import clear_registry, get_module, list_modules, register_module
from app.core.assets.module_interface import IAssetModule
from app.core.events.domain_events import InstallmentOverdueEvent, InstallmentPaidEvent
from app.domain.shared.value_objects import Cnh
from app.infrastructure.db.session import get_engine
from app.infrastructure.security.password_hasher import hash_password
from app.infrastructure.security.jwt_service import create_access_token
from app.main import app
from app.modules.vehicles.hooks import VehicleHooks
from app.modules.vehicles.module import VehicleModule
from app.modules.vehicles.schemas import validate_plate

BASE_URL = "http://test"
VEHICLES_URL = "/api/v1/vehicles"
TEST_EMAIL = "vehicle-test@example.com"
TEST_PASSWORD = "VehicleTest@123"

_user_id: str = ""
_token: str = ""


async def _setup_test_user() -> tuple[str, str]:
    global _user_id, _token
    user_id = str(uuid4())
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM acesso.usuarios WHERE email = :e"), {"e": TEST_EMAIL})
        empresa_row = (await conn.execute(text("SELECT id FROM comercial.empresas LIMIT 1"))).first()
        assert empresa_row is not None, "No empresa found — run seed first"
        empresa_id = str(empresa_row[0])
        await conn.execute(text(
            "INSERT INTO acesso.usuarios (id, email, senha_hash, nome_completo, ativo, mfa_ativo, empresa_id) "
            "VALUES (:id, :email, :pw, :name, true, false, :eid)"
        ), {"id": user_id, "email": TEST_EMAIL, "pw": hash_password(TEST_PASSWORD), "name": "Vehicle Tester", "eid": empresa_id})

    token = create_access_token(sub=user_id, email=TEST_EMAIL, roles=["Admin"], empresa_id=empresa_id)
    _user_id = user_id
    _token = token
    return user_id, token


async def _cleanup() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        # Clean up vehicles and related data created during tests
        await conn.execute(text("DELETE FROM veiculos.dispositivos_rastreamento WHERE veiculo_id IN (SELECT id FROM veiculos.veiculos)"))
        await conn.execute(text("DELETE FROM veiculos.aquisicoes_veiculo WHERE veiculo_id IN (SELECT id FROM veiculos.veiculos)"))
        await conn.execute(text("DELETE FROM veiculos.veiculos"))
        await conn.execute(text(
            "ALTER TABLE logs.log_auditoria DISABLE TRIGGER trg_log_auditoria_immutable"
        ))
        await conn.execute(text(
            "UPDATE logs.log_auditoria SET user_id = NULL WHERE user_id = :uid"
        ), {"uid": _user_id})
        await conn.execute(text(
            "ALTER TABLE logs.log_auditoria ENABLE TRIGGER trg_log_auditoria_immutable"
        ))
        await conn.execute(text("DELETE FROM acesso.usuarios WHERE id = :uid"), {"uid": _user_id})


@pytest.fixture(autouse=True)
async def setup_teardown():
    await _setup_test_user()
    yield
    await _cleanup()


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {_token}"}


def _vehicle_payload(**overrides: object) -> dict:
    base = {
        "placa": "ABC1D23",
        "marca": "Fiat",
        "modelo": "Uno",
        "ano_modelo": 2023,
        "ano_fabricacao": 2022,
        "cor": "Branco",
    }
    # Permite overrides EN antigos pelo nome PT-BR (compat de teste).
    _MAP_EN_PT = {
        "plate": "placa", "brand": "marca", "model_name": "modelo",
        "model_year": "ano_modelo", "fab_year": "ano_fabricacao", "color": "cor",
        "fipe_code": "codigo_fipe", "fipe_value": "valor_fipe",
        "customer_id": "cliente_id", "acquisition": "aquisicao",
    }
    for k, v in list(overrides.items()):
        if k in _MAP_EN_PT:
            overrides[_MAP_EN_PT[k]] = v
            del overrides[k]
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Module registration
# ---------------------------------------------------------------------------

class TestVehicleModuleRegistration:
    def test_vehicle_module_satisfies_protocol(self):
        mod = VehicleModule()
        assert isinstance(mod, IAssetModule)

    def test_vehicle_module_identity(self):
        mod = VehicleModule()
        assert mod.asset_type == "vehicle"
        assert mod.display_name == "Veículos"
        assert mod.icon == "heroTruck"

    def test_register_vehicle_module(self):
        clear_registry()
        mod = VehicleModule()
        register_module(mod)
        assert get_module("vehicle") is mod
        assert len(list_modules()) >= 1
        clear_registry()

    def test_vehicle_module_agent_tools(self):
        mod = VehicleModule()
        tools = mod.get_agent_tools()
        tool_ids = [t.tool_id for t in tools]
        assert "check_vehicle_status" in tool_ids
        assert "block_vehicle_gps" in tool_ids
        assert "unblock_vehicle_gps" in tool_ids

    def test_vehicle_module_asset_schema_includes_cnh(self):
        mod = VehicleModule()
        schema = mod.get_asset_schema()
        field_names = [f.name for f in schema]
        assert "cnh_number" in field_names
        assert "cnh_category" in field_names
        assert "cnh_expiry" in field_names


# ---------------------------------------------------------------------------
# Plate validation
# ---------------------------------------------------------------------------

class TestPlateValidation:
    def test_valid_mercosul_plate(self):
        assert validate_plate("ABC1D23") == "ABC1D23"
        assert validate_plate("abc1d23") == "ABC1D23"
        assert validate_plate("ABC-1D23") == "ABC1D23"

    def test_valid_legacy_plate(self):
        assert validate_plate("ABC1234") == "ABC1234"
        assert validate_plate("abc-1234") == "ABC1234"

    def test_invalid_plate(self):
        with pytest.raises(ValueError):
            validate_plate("AB12345")
        with pytest.raises(ValueError):
            validate_plate("ABCD123")
        with pytest.raises(ValueError):
            validate_plate("123")


# ---------------------------------------------------------------------------
# CNH value object
# ---------------------------------------------------------------------------

class TestCnhValueObject:
    def test_valid_cnh(self):
        cnh = Cnh.parse("12345678901", "B")
        assert cnh.number == "12345678901"
        assert cnh.category == "B"

    def test_valid_cnh_categories(self):
        for cat in ["A", "B", "C", "D", "E", "AB", "AC", "AD", "AE"]:
            cnh = Cnh.parse("12345678901", cat)
            assert cnh.category == cat

    def test_invalid_cnh_digits(self):
        with pytest.raises(ValueError, match="11 digits"):
            Cnh.parse("1234", "B")

    def test_invalid_cnh_category(self):
        with pytest.raises(ValueError, match="category"):
            Cnh.parse("12345678901", "X")


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------

class TestVehicleHooks:
    def test_overdue_triggers_block(self):
        hooks = VehicleHooks()
        event = InstallmentOverdueEvent(
            asset_type="vehicle",
            installment_id="inst-1",
            contract_id="c-1",
            customer_id="cust-1",
            days_overdue=10,
            amount_due=500.0,
        )
        actions = hooks.on_installment_overdue(event, {"min_days_overdue": 5})
        assert len(actions) == 1
        assert actions[0].name == "block_vehicle"

    def test_overdue_below_threshold_no_block(self):
        hooks = VehicleHooks()
        event = InstallmentOverdueEvent(
            asset_type="vehicle",
            installment_id="inst-1",
            contract_id="c-1",
            customer_id="cust-1",
            days_overdue=3,
            amount_due=500.0,
        )
        actions = hooks.on_installment_overdue(event, {"min_days_overdue": 5})
        assert len(actions) == 0

    def test_overdue_score_above_threshold_no_block(self):
        hooks = VehicleHooks()
        event = InstallmentOverdueEvent(
            asset_type="vehicle",
            installment_id="inst-1",
            contract_id="c-1",
            customer_id="cust-1",
            days_overdue=10,
            amount_due=500.0,
        )
        actions = hooks.on_installment_overdue(
            event,
            {"min_days_overdue": 5, "min_score": 50, "customer_score": 80},
        )
        assert len(actions) == 0

    def test_paid_triggers_unblock(self):
        hooks = VehicleHooks()
        event = InstallmentPaidEvent(
            asset_type="vehicle",
            installment_id="inst-1",
            contract_id="c-1",
            customer_id="cust-1",
            amount_paid=500.0,
        )
        actions = hooks.on_installment_paid(event)
        assert len(actions) == 1
        assert actions[0].name == "unblock_vehicle"


# ---------------------------------------------------------------------------
# Vehicle CRUD (integration)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_vehicle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post(
            VEHICLES_URL,
            json=_vehicle_payload(),
            headers=_auth_headers(),
        )

    assert response.status_code == 201
    data = response.json()
    assert data["placa"] == "ABC1D23"
    assert data["marca"] == "Fiat"
    assert data["modelo"] == "Uno"
    assert data["status"] == "disponivel"
    assert data["asset_id"] is not None


@pytest.mark.asyncio
async def test_create_duplicate_plate():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        await client.post(
            VEHICLES_URL,
            json=_vehicle_payload(plate="DUP1A23"),
            headers=_auth_headers(),
        )
        response = await client.post(
            VEHICLES_URL,
            json=_vehicle_payload(plate="DUP1A23"),
            headers=_auth_headers(),
        )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_list_vehicles_with_pagination():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        for i in range(3):
            await client.post(
                VEHICLES_URL,
                json=_vehicle_payload(plate=f"LST{i}A00"),
                headers=_auth_headers(),
            )

        response = await client.get(
            VEHICLES_URL,
            params={"page": 1, "size": 2},
            headers=_auth_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["pages"] == 2


@pytest.mark.asyncio
async def test_get_vehicle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        create_resp = await client.post(
            VEHICLES_URL,
            json=_vehicle_payload(plate="GET1A00"),
            headers=_auth_headers(),
        )
        vid = create_resp.json()["id"]

        response = await client.get(
            f"{VEHICLES_URL}/{vid}",
            headers=_auth_headers(),
        )

    assert response.status_code == 200
    assert response.json()["placa"] == "GET1A00"


@pytest.mark.asyncio
async def test_update_vehicle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        create_resp = await client.post(
            VEHICLES_URL,
            json=_vehicle_payload(plate="UPD1A00"),
            headers=_auth_headers(),
        )
        vid = create_resp.json()["id"]

        response = await client.patch(
            f"{VEHICLES_URL}/{vid}",
            json={"cor": "Preto", "status": "em_uso"},
            headers=_auth_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["cor"] == "Preto"
    assert data["status"] == "em_uso"


@pytest.mark.asyncio
async def test_soft_delete_vehicle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        create_resp = await client.post(
            VEHICLES_URL,
            json=_vehicle_payload(plate="DEL1A00"),
            headers=_auth_headers(),
        )
        vid = create_resp.json()["id"]

        delete_resp = await client.delete(
            f"{VEHICLES_URL}/{vid}",
            headers=_auth_headers(),
        )
        assert delete_resp.status_code == 204

        get_resp = await client.get(
            f"{VEHICLES_URL}/{vid}",
            headers=_auth_headers(),
        )
        assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_get_nonexistent_vehicle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.get(
            f"{VEHICLES_URL}/{uuid4()}",
            headers=_auth_headers(),
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_vehicle_financials():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        create_resp = await client.post(
            VEHICLES_URL,
            json=_vehicle_payload(
                plate="FIN1A00",
                fipe_value="55000.00",
                aquisicao={
                    "tipo_aquisicao": "financiamento",
                    "preco_compra": "50000.00",
                    "banco_financiamento": "Banco X",
                    "parcelas_financiamento": 48,
                    "valor_mensal_financiamento": "1200.00",
                },
            ),
            headers=_auth_headers(),
        )
        vid = create_resp.json()["id"]

        response = await client.get(
            f"{VEHICLES_URL}/{vid}/financials",
            headers=_auth_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["valor_fipe"] is not None
    assert data["aquisicao"] is not None
    assert data["aquisicao"]["tipo_aquisicao"] == "financiamento"
    assert data["aquisicao"]["banco_financiamento"] == "Banco X"


@pytest.mark.asyncio
async def test_search_vehicles():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        await client.post(
            VEHICLES_URL,
            json=_vehicle_payload(plate="SRC1A00", brand="Toyota", model_name="Corolla"),
            headers=_auth_headers(),
        )
        await client.post(
            VEHICLES_URL,
            json=_vehicle_payload(plate="SRC2A00", brand="Honda", model_name="Civic"),
            headers=_auth_headers(),
        )

        response = await client.get(
            VEHICLES_URL,
            params={"search": "Toyota"},
            headers=_auth_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["marca"] == "Toyota"


@pytest.mark.asyncio
async def test_unauthenticated_returns_401():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.get(VEHICLES_URL)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_invalid_plate_returns_422():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post(
            VEHICLES_URL,
            json=_vehicle_payload(plate="INVALID"),
            headers=_auth_headers(),
        )

    assert response.status_code == 422
