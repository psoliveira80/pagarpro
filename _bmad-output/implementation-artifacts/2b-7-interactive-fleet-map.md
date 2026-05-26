---
epic: 2B
story: 7
title: "Interactive Fleet Map"
type: "Vehicle Module"
status: done
---

# Story 2B.7: Interactive Fleet Map

## User Story

As a Manager,
I want to see all vehicles on an interactive map,
So that I can monitor the operation geographically.

## Acceptance Criteria

1. `FleetMapComponent` in `features/modules/vehicles/fleet-map/`.
2. Leaflet with OSM tiles, custom markers (vehicle-type icon + status color).
3. Auto-cluster on zoom-out.
4. **Given** marker click, **Then** popup: photo, model, plate, driver, status, "View Details" + "Block" (with double confirmation).
5. Positions refresh every 30 s via SSE (`/sse/module/vehicles`).
6. Side filters: status, driver, tag.
7. Optional "operating region" polygon highlighting out-of-zone vehicles.

## Technical Context

### Architecture References

- **FR-VH-5**: Interactive fleet map (Leaflet+OSM, swappable Google Maps) with live positions, popups, block/unblock actions
- **Frontend Structure** (Section 10.1):
  - `frontend/src/app/features/system/fleet-map/fleet-map.component.ts`
  - `frontend/src/app/features/system/fleet-map/fleet-map.component.html`
  - `frontend/src/app/features/system/fleet-map/fleet-map.component.css`
- **Shared Components**: `shared/components/leaflet-map/` (base map), `shared/components/confirm-dialog/`
- **SSE**: `GET /sse/module/vehicles` — server-sent events for position updates (Section 5.2 Real-time)
- **Backend SSE**: `backend-api/app/api/sse.py` — SSE endpoint handler
- **API Endpoints**:
  - `GET /api/v1/modules/vehicles/{id}/position` — single vehicle position
  - `POST /api/v1/modules/vehicles/{id}/block` — block with double confirmation

### Files to Create/Modify

**Create:**
- `frontend/src/app/features/system/fleet-map/fleet-map.component.ts`
- `frontend/src/app/features/system/fleet-map/fleet-map.component.html`
- `frontend/src/app/features/system/fleet-map/fleet-map.component.css`
- `frontend/src/app/features/system/fleet-map/components/vehicle-popup/vehicle-popup.component.ts`
- `frontend/src/app/features/system/fleet-map/components/vehicle-popup/vehicle-popup.component.html`
- `frontend/src/app/features/system/fleet-map/components/map-sidebar-filters/map-sidebar-filters.component.ts`
- `frontend/src/app/features/system/fleet-map/components/map-sidebar-filters/map-sidebar-filters.component.html`
- `frontend/src/app/features/system/vehicles/services/tracker.service.ts` — frontend service for position SSE and tracker API

**Modify:**
- `frontend/src/app/features/system/system.routes.ts` — add route for fleet-map (`/fleet-map`)
- `backend-api/app/api/sse.py` — add `/sse/module/vehicles` endpoint that streams vehicle position updates
- `backend-api/app/modules/vehicles/routes.py` — ensure position endpoints are available

### Dependencies

- Story 2B.3 (Vehicle model with position data)
- Story 2B.6 (GPS Tracker Adapter — position and block endpoints)
- Shared Leaflet map component (from shared components)

### Technical Notes

- **Leaflet setup**: use `leaflet` npm package with `@types/leaflet`. OSM tiles: `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`.
- **Custom markers**: create SVG markers with vehicle-type icon (car/truck/motorcycle) and status-based color (green=alugado, blue=disponivel, orange=manutencao, red=blocked).
- **Marker clustering**: use `leaflet.markercluster` plugin. On zoom-out, nearby markers cluster into a circle with count.
- **Popup on click**: Angular component rendered inside Leaflet popup. Shows: vehicle photo (thumbnail), model+plate, current driver name, status badge, "Ver Detalhes" link (navigates to vehicle detail), "Bloquear" button (opens confirm-dialog with password re-entry).
- **SSE refresh**: `core/services/sse.service.ts` connects to `/sse/module/vehicles`. Events contain `{vehicle_id, lat, lng, speed, ignition, timestamp}`. On each event, update the corresponding marker's position with smooth animation (`marker.setLatLng()`).
- **Backend SSE**: Celery task or scheduled job polls tracker for all active vehicles every 30s, publishes position updates to Redis Pub/Sub. SSE endpoint subscribes to Redis channel and streams to connected clients.
- **Side filters**: filter panel on the left with checkboxes for status, driver dropdown, tag chips. Filtering is client-side (hide/show markers) since all positions are loaded.
- **Operating region polygon**: optional GeoJSON polygon stored in module config. Vehicles outside the polygon get a red border highlight on their marker.

## Dev Checklist

- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
