---
epic: 6
story: 9
title: "Receipt Detection and Primary Write-Off via Agent"
type: "Core"
status: done
---

# Story 6.9: Receipt Detection and Primary Write-Off via Agent

## User Story
As a Customer,
I want my title considered paid as soon as I send a receipt over WhatsApp,
So that I get instant confirmation.

## Acceptance Criteria
1. Inbound media classified via heuristic (image/PDF + OCR detects Pix receipt patterns such as transaction ID, amount, date, bank identifiers).
2. **Given** a receipt is detected, **Then** the agent extracts amount + date + transaction ID via OCR, finds the most likely matching title (by customer + value + date window), and calls `registrar_baixa_primaria`.
3. **Given** paid amount < title amount, **Then** agent executes partial write-off (Epic 4 Story 4.4 logic): partial payment recorded, new title for the difference generated. Agent informs the customer of the partial payment and remaining balance.
4. **Given** full write-off succeeds, **Then** agent replies with a confirmation template. The installment is added to the human validation queue (Epic 4 Story 4.6).
5. **Given** an ambiguous match (multiple candidate titles or low OCR confidence), **Then** the agent asks the customer in natural language to clarify which title, or escalates to the manager.

## Technical Context

### Architecture References
- OCR Port: `IOcrProvider` with `TesseractAdapter` (default) and `LlmVisionAdapter` (fallback) in `backend-api/app/infrastructure/integrations/ocr/`.
- Receipt classification: `backend-api/app/infrastructure/parsing/pix_receipt_classifier.py` — regex heuristics for Pix patterns.
- Default payment flow: Pix via WhatsApp -> screenshot -> OCR -> validation -> write-off. Zero cost.
- Agent tool: `registrar_baixa_primaria` creates write-off with status `pago_aguardando_verificacao`, enqueues for human validation.
- Partial payment logic from Epic 4: if paid < title, partial write-off on original + new title for difference with new collection cycle.

### Files to Create/Modify
**Backend:**
- `backend-api/app/domain/ports/ocr_provider.py` — `IOcrProvider` Protocol (if not already created in Epic 4)
- `backend-api/app/infrastructure/integrations/ocr/tesseract_adapter.py` — Tesseract OCR adapter
- `backend-api/app/infrastructure/integrations/ocr/llm_vision_adapter.py` — LLM vision fallback adapter
- `backend-api/app/infrastructure/parsing/pix_receipt_classifier.py` — enhance with extraction logic (amount, date, txn ID)
- `backend-api/app/application/collections/handle_inbound_message.py` — extend to detect receipt media and trigger OCR pipeline
- `backend-api/app/application/collections/run_agent_turn.py` — implement `registrar_baixa_primaria` tool: OCR extraction, title matching, write-off or partial write-off
- `backend-api/app/workers/tasks/ocr_receipt.py` — Celery task for OCR processing
- `backend-api/app/domain/collections/events.py` — add `ReceiptDetected` event

**Tests:**
- `backend-api/tests/unit/infrastructure/test_pix_receipt_classifier.py` — test classification and extraction accuracy
- `backend-api/tests/unit/infrastructure/test_tesseract_adapter.py`
- `backend-api/tests/unit/application/test_receipt_write_off.py` — test full, partial, and ambiguous scenarios
- `backend-api/tests/integration/test_receipt_pipeline_e2e.py`

### Dependencies
- Story 6.3 (Webhook inbound pipeline — media download to MinIO).
- Story 6.4 (AI Agent Engine — agent tool execution framework).
- Epic 4, Story 4.4 (Partial write-off logic — reused for partial payment handling).
- Epic 4, Story 4.6 (Validation queue — write-offs enqueued for human approval).
- Epic 4, Story 4.7 (OCR infrastructure — may already be partially built).

### Technical Notes
- OCR extraction pipeline: 1) Classify media as receipt vs non-receipt via regex heuristics on OCR text. 2) Extract structured fields: `amount` (R$ value), `date`, `transaction_id` (E2E key or NSU). 3) Match to candidate title by customer_id + value proximity (tolerance +/- R$0.50) + date window (7 days).
- Pix receipt patterns to detect: "Comprovante de Pagamento", "Pix", "Transferencia", bank-specific layouts. Use regex on OCR text output.
- Title matching algorithm: filter customer's open/overdue titles, score by `abs(title_amount - ocr_amount)` + `abs(title_due_date - ocr_date)`, select best match if score above threshold.
- If OCR confidence is below threshold (configurable, default 70%) or multiple titles match equally, the agent asks the customer to confirm.
- The `registrar_baixa_primaria` tool creates the write-off with `pago_aguardando_verificacao` status — it does NOT finalize payment. Final confirmation comes from the validation queue (human) and reconciliation (bank).
- Media files are stored in MinIO with path `receipts/{customer_id}/{message_id}.{ext}` and linked to the write-off record.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
