---
epic: 2B
story: 2
title: "FIPE Provider Adapter"
type: "Vehicle Module"
status: done
---

# Story 2B.2: FIPE Provider Adapter

## User Story

As the System,
I want an `IFipeProvider` Port with concrete adapters,
So that the FIPE supplier is swappable.

## Acceptance Criteria

1. `IFipeProvider` Protocol in `app/modules/vehicles/ports/fipe.py` with `list_brands`, `list_models`, `list_years`, `get_price`.
2. `ApiFipeBrAdapter` (default) in `app/modules/vehicles/adapters/fipe/apifipe_br.py`.
3. `FipeApiBrAdapter` (alternative) in `app/modules/vehicles/adapters/fipe/fipeapi_br.py`.
4. Fallback adapter: primary -> secondary on error.
5. Redis cache with 30-day TTL per key `fipe:{type}:{brand}:{model}:{year}`.
6. Endpoints: `GET /api/v1/modules/vehicles/fipe/{brands|models|years|price}`.
7. Active adapter selected via `FIPE_PROVIDER` env var.

## Technical Context

### Architecture References

- **FR-VH-12**: `IFipeProvider` with default `ApiFipeBrAdapter`, alternative `FipeApiBrAdapter`, fallback, 30-day Redis cache
- **API Endpoints** (Section 5.2 — Module: Vehicles / FIPE):
  - `GET /api/v1/modules/vehicles/fipe/brands?type=car`
  - `GET /api/v1/modules/vehicles/fipe/models?type=car&brand=XX`
  - `GET /api/v1/modules/vehicles/fipe/years?...`
  - `GET /api/v1/modules/vehicles/fipe/price?...`
- **Hexagonal pattern**: Port in `ports/`, Adapters in `adapters/fipe/`, service in `services/`
- **Settings**: `backend-api/app/infrastructure/settings.py` — add `FIPE_PROVIDER` config

### Files to Create/Modify

**Create:**
- `backend-api/app/modules/vehicles/ports/fipe.py` — `IFipeProvider` Protocol with methods: `list_brands(type)`, `list_models(type, brand_code)`, `list_years(type, brand_code, model_code)`, `get_price(type, brand_code, model_code, year_code)`
- `backend-api/app/modules/vehicles/adapters/fipe/__init__.py`
- `backend-api/app/modules/vehicles/adapters/fipe/apifipe_br.py` — `ApiFipeBrAdapter(IFipeProvider)` hitting `https://brasilapi.com.br/api/fipe/` or similar
- `backend-api/app/modules/vehicles/adapters/fipe/fipeapi_br.py` — `FipeApiBrAdapter(IFipeProvider)` hitting alternative FIPE API
- `backend-api/app/modules/vehicles/adapters/fipe/fallback_adapter.py` — `FallbackFipeAdapter` that tries primary then secondary
- `backend-api/app/modules/vehicles/services/fipe_service.py` — orchestrates adapter + Redis cache
- `backend-api/tests/unit/modules/vehicles/test_fipe_provider.py`
- `backend-api/tests/integration/modules/vehicles/test_fipe_endpoints.py`

**Modify:**
- `backend-api/app/modules/vehicles/routes.py` — add FIPE endpoints
- `backend-api/app/infrastructure/settings.py` — add `FIPE_PROVIDER: str = "apifipe_br"` setting
- `backend-api/app/core/di.py` — wire FIPE provider based on `FIPE_PROVIDER` env var

### Dependencies

- Story 2B.1 (Vehicle Module structure and registration)
- Redis infrastructure (from Epic 1 foundation)

### Technical Notes

- Cache key format: `fipe:{type}:{brand}:{model}:{year}` with 30-day (2592000s) TTL.
- `FallbackFipeAdapter` wraps primary + secondary: on primary failure (HTTP error, timeout), automatically retries with secondary. Log warning on fallback.
- All adapters use `httpx.AsyncClient` for async HTTP calls.
- `FipeService` checks Redis cache first; on miss, calls active adapter, stores result, returns.
- FIPE endpoints are mounted on the Vehicle Module's router, so they appear under `/api/v1/modules/vehicles/fipe/`.
- Permission: any authenticated user can query FIPE data (read-only, no sensitive data).

## Dev Checklist

- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
