---
epic: 4
story: 9
title: "Optional Pix Payment Gateway Adapter"
type: "Core"
status: done
---

# Story 4.9: Optional Pix Payment Gateway Adapter

## User Story
As an Admin,
I want to optionally connect Asaas/Efi,
So that auto-confirmed Pix collections become available when ROI justifies the per-transaction cost.

## Acceptance Criteria

1. `IPaymentGateway` Port: `create_charge(installment) -> Charge`, `webhook_handler(payload, signature) -> Event`.
2. `AsaasAdapter`, `EfiAdapter` implemented; `NoOpPaymentGateway` is default (off).
3. Settings > Integrations: Admin can enable, store encrypted credentials, define scope.
4. **Given** webhook at `POST /api/v1/webhooks/payment-gateway/{provider}`, **When** signature validates, **Then** idempotent processing moves installment straight to `pago` (skips manual validation).
5. Default: **disabled**, per zero-cost Pix preference.

## Technical Context

### Architecture References
- **Architecture Section 6 (Infrastructure)**: `app/infrastructure/integrations/payment/` — `noop_gateway.py` (default), `asaas_adapter.py`, `efi_adapter.py`.
- **Architecture Section 4.1 (Domain Ports)**: `app/domain/ports/payment_gateway.py` — `IPaymentGateway` protocol.
- **Architecture Section 5 (API Endpoints)**: `POST /api/v1/webhooks/payment-gateway/{provider}` — Pix gateway plugin webhook.
- **Architecture Section 4.1 (Domain Entities)**: `IntegrationCredential` entity for encrypted provider credentials; `WebhookEventRaw` for idempotent webhook processing.
- **Architecture Section 2.1 (Design Decisions)**: Default payment = Pix via WhatsApp (zero cost); gateways are optional plugins, never mandatory.

### Files to Create/Modify
```
backend-api/
├── app/domain/ports/payment_gateway.py        # IPaymentGateway Protocol: create_charge, webhook_handler
├── app/infrastructure/integrations/payment/
│   ├── __init__.py
│   ├── noop_gateway.py                        # NoOpPaymentGateway — default, returns "not configured"
│   ├── asaas_adapter.py                       # AsaasAdapter: create Pix charge, verify webhook signature
│   └── efi_adapter.py                         # EfiAdapter: create Pix charge, verify webhook signature
├── app/api/v1/webhook_routes.py               # POST /webhooks/payment-gateway/{provider}
├── app/application/finance/handle_payment_webhook.py  # idempotent webhook processing use case
├── app/infrastructure/db/models/integration_credential.py  # encrypted credentials storage
├── app/infrastructure/db/models/webhook_event_raw.py       # raw webhook event log

frontend/
├── src/app/features/system/settings/integrations/
│   ├── payment-gateway-config.component.ts    # admin UI: enable/disable, credentials, scope
│   ├── payment-gateway-config.component.html
│   └── payment-gateway-config.component.css
```

### Dependencies
- Story 4.7 (Pix QR Code — static QR is the default; gateway adds dynamic/auto-confirmed Pix).
- `IntegrationCredential` entity with AES-256-GCM encryption for stored credentials.
- `WebhookEventRaw` entity for idempotent webhook processing (deduplicate by `provider` + `external_id`).
- Admin Settings feature (Settings > Integrations UI).

### Technical Notes
- `IPaymentGateway` protocol methods:
  - `create_charge(installment_id, amount, pix_key, description) -> Charge` — creates a Pix charge with the provider.
  - `webhook_handler(payload: bytes, signature: str) -> PaymentEvent` — validates signature and parses the webhook payload.
- `NoOpPaymentGateway` is the **default** injected adapter. It raises a descriptive error if `create_charge` is called ("Payment gateway not configured"). This ensures the system works at zero cost by default.
- Webhook processing must be **idempotent**: check `WebhookEventRaw` for existing `(provider, external_id)` before processing. If already processed, return 200 OK without side effects.
- When a valid payment webhook is received, the installment transitions directly to `pago` status, skipping `pago_aguardando_verificacao` (gateway confirms payment automatically).
- Credentials are encrypted at rest using AES-256-GCM with a master key from environment/KMS. Never log or expose credentials in API responses.
- Provider selection in DI container: read `FeatureFlag` or `IntegrationCredential.is_active` to determine which adapter to inject. Default to `NoOpPaymentGateway` if none active.
- Webhook endpoint validates request signature before any processing (HMAC or provider-specific verification).

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
