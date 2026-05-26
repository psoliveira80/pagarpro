---
epic: 2A
story: 5
title: "Generic Assets List"
type: "Core"
status: done
---

# Story 2A.5: Generic Assets List

## User Story
As a Manager,
I want to see all assets registered in the platform,
So that I have a consolidated view regardless of module.

## Acceptance Criteria

1. Route `/system/assets` lists records from the `assets` table with columns: name, module (badge), status, last update, actions.
2. Filters: module type (multi-select), status, text search.
3. Click redirects to the detail page rendered by the corresponding vertical module.
4. If no vertical module is active, empty state: "Activate a vertical module in Settings > Modules to start registering assets."

## Technical Context

### Architecture References
- **Architecture Section 4.2 — Asset Registry**: Asset entity — `id`, `asset_type`, `name`, `status` (`disponivel`/`em_contrato`/`manutencao`/`inativo`), `metadata` (JSONB), `module_data` (JSONB).
- **Architecture Section 5.2 — Assets endpoints**: `GET /assets` (filterable by asset_type), `GET /assets/{id}`, `PATCH /assets/{id}`, `GET /assets/{id}/financials`.
- **Architecture Section 7.2**: ModuleRegistry — `all()` returns registered modules for filter options.
- **Architecture Section 6**: Routes in `app/api/v1/asset_routes.py`, models in `app/infrastructure/db/models/asset.py`.

### Files to Create/Modify
```
backend-api/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── asset_routes.py              # GET /assets (list), GET /assets/{id}
│   │       └── schemas/
│   │           └── assets.py                # AssetResponse, AssetListResponse DTOs
│   ├── application/
│   │   └── assets/
│   │       ├── __init__.py
│   │       ├── list_assets.py               # ListAssets use case
│   │       └── get_asset.py                 # GetAsset use case
│   ├── infrastructure/
│   │   └── db/
│   │       └── repositories/
│   │           └── asset_repo.py            # IAssetRepo implementation
│   └── domain/
│       └── ports/
│           └── repositories.py              # add IAssetRepo interface

frontend/
├── src/app/
│   ├── features/
│   │   └── system/
│   │       └── assets/
│   │           ├── assets.routes.ts                  # lazy route config
│   │           └── assets-list/
│   │               ├── assets-list.component.ts      # standalone component
│   │               ├── assets-list.component.html
│   │               └── assets-list.component.css
│   ├── core/
│   │   └── services/
│   │       └── assets.service.ts                     # API calls: list assets
│   └── app.routes.ts                                 # add /system/assets route
```

### Dependencies
- **Story 1.1** (Backend skeleton, DB session).
- **Story 1.2** (Frontend skeleton, AppShell with sidebar nav).
- **Story 1.8** (assets table, active_modules table, ModuleRegistry).
- **Story 2A.2** (Reuse shared components: data-table, badge, empty-state, skeleton-loader).

### Technical Notes
- **Backend — Asset list endpoint**: `GET /api/v1/assets?asset_type=&status=&search=&page=&size=`. Filter by `asset_type` (matches `module_id` in assets table). Search across `display_name` and `metadata` JSONB fields. Return paginated response.
- **Module badge**: Show the `display_name` of the module (e.g., "Veiculos") as a colored badge. Fetch available module types from `GET /api/v1/admin/modules` or embed in the assets list response.
- **Click behavior**: Each asset row's click should navigate to the module-specific detail page. The URL pattern is `/system/modules/{asset_type}/{asset_external_ref}` (e.g., `/system/modules/vehicles/123`). This requires knowing the `asset_type` and `external_ref` from the asset record.
- **Empty state**: When the `assets` table is empty AND no modules are active, show a friendly message: "Ative um modulo vertical em Configuracoes > Modulos para comecar a cadastrar ativos." with a link to settings (placeholder).
- **Frontend — Filters**: 
  - Module type multi-select: populated from the list of active modules.
  - Status multi-select: `disponivel`, `em_contrato`, `manutencao`, `inativo`.
  - Text search: debounced 300ms, searches `display_name`.
- **Data table**: Reuse the `DataTableComponent` from Story 2A.2. Columns: Name (display_name), Module (badge), Status (badge), Last Update (formatted date), Actions (View button).
- **Sidebar nav**: Add "Ativos" link in the AppShell sidebar under a "Cadastros" section, alongside "Clientes".

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
