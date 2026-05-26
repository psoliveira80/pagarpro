---
epic: 11
story: 5
title: "Receipt Dedupe + Manual Validation Queue"
type: "Core"
status: ready-for-dev
---

# Story 11.5: Receipt Dedupe + Manual Validation Queue

## User Story
As a System,
I want to detect duplicate receipts and gracefully queue low-confidence OCR results for human validation,
So that we never double-credit a payment and the operation continues even when IA Vision fallback is disabled (ia-eco/ia-zero).

## Acceptance Criteria

1. New table `receipt_fingerprints`: `id`, `tenant_id`, `customer_id`, `installment_id` (nullable), `phash` BIGINT (perceptual hash 64-bit), `txn_id` (text, nullable — extracted by OCR), `bank_code` (text, nullable), `amount` NUMERIC, `txn_date` DATE, `media_url` (MinIO ref), `confidence` NUMERIC (0-100, from OCR), `status` ('auto_processed' | 'manual_pending' | 'manual_approved' | 'manual_rejected' | 'duplicate_rejected'), `created_at`. Index in `(tenant_id, txn_id)` (where txn_id is not null) and `(tenant_id, phash)`.
2. `ReceiptDedupeService`:
   - `compute_phash(image_bytes) -> int` — usa `imagehash` (Python lib) — pHash 8x8 default
   - `find_duplicate(tenant_id, phash, txn_id) -> Optional[ReceiptFingerprint]` — 2 estratégias:
     a. Exact txn_id match (mais forte)
     b. Hamming distance pHash ≤ 5 (configurável em `system_settings.dedupe_phash_threshold`) — pega imagens visualmente quase iguais mesmo se renomeadas/recortadas
3. Updated inbound media pipeline (extends Story 6.9):
   ```
   recebe mídia → MinIO → compute_phash → check duplicate
     se duplicado → status='duplicate_rejected'
       → envia template "Este comprovante já foi processado em DD/MM/YYYY"
       → não chama OCR (economia)
     senão → Tesseract OCR
       se OperationMode.is_allowed('llm_vision_fallback') AND confidence < 70:
         → LlmVisionAdapter (já existe em Story 6.9)
       insert receipt_fingerprints com confidence final
       se confidence ≥ 70 AND match único achado → auto write-off (status='auto_processed')
       senão → status='manual_pending'
   ```
4. Em **ia-zero** ou **ia-eco**: LLM Vision fallback DESABILITADO. Comprovantes com confidence < 70 caem direto em `manual_pending`. Cliente recebe template "Recebemos seu comprovante. Validação manual em até 24h." (template configurável).
5. Backend endpoints:
   - `GET /api/v1/receipts/pending` — fila de validação manual (filtros: customer, date_range, amount_range)
   - `GET /api/v1/receipts/{id}` — detalhe (preview da imagem, dados extraídos pelo OCR, candidate installments)
   - `POST /api/v1/receipts/{id}/approve` — body `{installment_id, amount_override?}` → executa write-off
   - `POST /api/v1/receipts/{id}/reject` — body `{reason: 'duplicate' | 'invalid' | 'other', notes?}`
   - `POST /api/v1/receipts/{id}/reassign` — body `{customer_id}` → quando OCR matchou cliente errado
6. SSE event `receipt_pending_review` quando novo item entra na fila — notifica gestores online.
7. Frontend page **/system/receipts/pending** (nova rota):
   - Lista paginada com badges por status, foto thumbnail, valor extraído, cliente sugerido, idade do item
   - Click abre detail modal (usar `<app-modal>` da Story 10.8) com:
     - Preview da imagem (lightbox-ready)
     - Side panel: dados extraídos editáveis (txn_id, amount, date, bank)
     - Lista de candidate installments rankeados por likelihood (customer match + valor próximo + data próxima)
     - Botões Aprovar/Reatribuir/Rejeitar
   - Filtros: status, range de data, range de valor, cliente
8. Frontend widget no Dashboard: "Comprovantes Aguardando Validação" com contador + link
9. Tests:
    - Duplicate detection — exact txn_id E phash similar
    - Confidence threshold respeitado
    - Mode gate: em ia-zero, LLM Vision nunca é chamado
    - Approve dispara write-off (Epic 4)
    - Reject não move dinheiro
    - SSE fired ao entrar na fila

## Technical Context

### Architecture References
- Builds on Story 6.9 (Receipt Detection & Primary Write-Off)
- Reusa `IOcrProvider`, `TesseractAdapter`, `LlmVisionAdapter` já existentes
- Write-off paths via Epic 4 (Story 4.3 manual, Story 4.4 partial)
- Mode gate via `OperationModeService.is_allowed('llm_vision_fallback')` (Story 11.2)

### Files to Create/Modify
```
backend-api/
├── app/domain/receipts/
│   ├── entities.py                      # ReceiptFingerprint
│   ├── dedupe_service.py                # ReceiptDedupeService
│   └── matcher.py                       # candidate installment matcher
├── app/application/receipts/
│   ├── process_inbound_receipt.py       # orquestra: dedupe → OCR → fingerprint → write-off ou fila
│   ├── approve_receipt.py
│   ├── reject_receipt.py
│   └── reassign_receipt.py
├── app/api/v1/receipts_routes.py
├── alembic/versions/xxxx_receipt_fingerprints.py
frontend/
├── src/app/features/receipts/receipts-pending-list.component.ts/.html/.css
├── src/app/features/receipts/receipt-detail-modal.component.ts/.html/.css
├── src/app/features/receipts/receipt-candidate-list.component.ts/.html/.css
├── src/app/features/dashboard/widgets/pending-receipts-widget.component.ts/.html/.css
└── src/app/core/services/receipts.service.ts
```

### New dependencies
- `imagehash>=4.3` (Python — pHash, dHash, aHash; depende de Pillow já presente)

### Dependencies
- Story 6.9 (Receipt Detection — extends, not replaces)
- Story 4.3 / 4.4 (write-off flows)
- Story 10.8 (`<app-modal>` reusable)
- Story 11.2 (OperationMode gate)

### Technical Notes
- **pHash threshold default 5**: Hamming distance ≤ 5 em 64 bits = ~92% similaridade. Valor calibrado pra pegar prints recortados sem falsos positivos.
- **Candidate ranking algorithm**: score = `customer_match_weight * 0.5 + amount_match_score * 0.3 + date_proximity_score * 0.2`. Threshold de "auto write-off" = score ≥ 0.85 + único candidato.
- **Reassign use case**: às vezes o telefone do cliente A manda comprovante de pagamento do cliente B (família, contador). Reassign permite isso.
- **Audit log**: aprovação manual grava em audit_log com `actor_id` do gestor, `actor='human_validator'`
- **Backfill**: rodar Celery one-shot para popular pHash de receipts antigos do Epic 6 quando deploy

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] No regressions
- [ ] Code review (`bmad-code-review`) executed and approved
