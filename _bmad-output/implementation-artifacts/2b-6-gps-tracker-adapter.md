---
epic: 2B
story: 6
title: "GPS Tracker Adapter"
type: "Vehicle Module"
status: done
---

# Story 2B.6: GPS Tracker Adapter

## User Story

As the System,
I want an `ITrackerGateway` Port with a generic implementation,
So that GPS tracking is plug-and-play.

## Acceptance Criteria

1. `ITrackerGateway` Protocol with `get_position`, `get_positions`, `block_vehicle`, `unblock_vehicle`, `get_history`.
2. `GenericRestTrackerAdapter` parameterizable by base URL, auth, JSONPath mapping — works for most REST trackers without code changes.
3. `MqttRestTrackerAdapter` for MQTT-command / REST-position trackers.
4. Block/unblock requires Admin profile + password re-confirmation (double approval) and writes signed `audit_log` event with reason.

## Technical Context

### Architecture References

- **FR-VH-13**: `ITrackerGateway` with generic REST/MQTT adapters for GPS position, block/unblock. Double approval + audit for block commands.
- **Port/Adapter Pattern**: Port in `backend-api/app/modules/vehicles/ports/tracker_gateway.py`, Adapters in `backend-api/app/modules/vehicles/adapters/tracker/`
- **Adapter implementations** (Section 6 source tree):
  - `backend-api/app/modules/vehicles/adapters/tracker/generic_rest_adapter.py`
  - `backend-api/app/modules/vehicles/adapters/tracker/mqtt_rest_adapter.py`
  - `backend-api/app/modules/vehicles/adapters/tracker/suntech_adapter.py`
- **API Endpoints** (Section 5.2):
  - `GET /api/v1/modules/vehicles/{id}/position` — current position
  - `GET /api/v1/modules/vehicles/{id}/position-history` — history
  - `POST /api/v1/modules/vehicles/{id}/block` — block (gated)
  - `POST /api/v1/modules/vehicles/{id}/unblock` — unblock (gated)
- **Audit**: `audit_log` table with HMAC signature, action `vehicle.block` / `vehicle.unblock`
- **DB Table**: `tracker_devices` — `id`, `external_id`, `vehicle_id`, `provider`, `last_seen_at`, `last_position` (JSONB)
- **Security**: Block/unblock requires Admin role + password re-confirmation

### Files to Create/Modify

**Create:**
- `backend-api/app/modules/vehicles/ports/tracker_gateway.py` — `ITrackerGateway` Protocol
- `backend-api/app/modules/vehicles/adapters/tracker/__init__.py`
- `backend-api/app/modules/vehicles/adapters/tracker/generic_rest_adapter.py` — `GenericRestTrackerAdapter(ITrackerGateway)` parameterizable via config JSONB
- `backend-api/app/modules/vehicles/adapters/tracker/mqtt_rest_adapter.py` — `MqttRestTrackerAdapter(ITrackerGateway)`
- `backend-api/app/modules/vehicles/services/tracker_service.py` — orchestrates tracker operations, enforces double approval for block
- `backend-api/app/modules/vehicles/services/block_vehicle.py` — use case: validate permissions, re-confirm password, call tracker, write audit
- `backend-api/app/modules/vehicles/services/unblock_vehicle.py` — use case: validate, call tracker, write audit
- `backend-api/tests/unit/modules/vehicles/test_tracker_gateway.py`
- `backend-api/tests/unit/modules/vehicles/test_block_vehicle.py`

**Modify:**
- `backend-api/app/modules/vehicles/routes.py` — add position, position-history, block, unblock endpoints
- `backend-api/app/modules/vehicles/models.py` — ensure `TrackerDevice` model is defined
- `backend-api/app/infrastructure/settings.py` — add `TRACKER_PROVIDER`, `TRACKER_BASE_URL`, `TRACKER_AUTH_TOKEN`, `TRACKER_FIELD_MAPPING` settings

### Dependencies

- Story 2B.1 (Vehicle Module structure)
- Story 2B.3 (Vehicle model with `tracker_device_id`)
- Epic 1 (audit_log infrastructure, password hashing service for re-confirmation)

### Technical Notes

- `GenericRestTrackerAdapter` is configured via JSONB config: `base_url`, `auth_type` (bearer/basic/apikey), `auth_value`, `endpoints` mapping (get_position path, block path, etc.), `field_mapping` (JSONPath to extract lat, lng, speed, ignition from response).
- `MqttRestTrackerAdapter` uses REST for reading positions and MQTT for sending commands (block/unblock). MQTT client uses `aiomqtt`.
- **Double approval for block**: endpoint requires `Authorization: Bearer <admin_jwt>` + body field `password_confirmation`. Service re-validates password hash before executing.
- Block/unblock writes to `audit_log` with: `action='vehicle.block'` or `vehicle.unblock`, `entity='vehicle'`, `entity_id=vehicle_id`, `payload_after` includes reason, associated overdue title, customer score, tracker response.
- `tracker_devices.last_position` stores `{lat, lng, speed, ignition, heading, timestamp}`.
- Position data is returned with `Cache-Control: no-store` header (real-time data).

## Dev Checklist

- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
