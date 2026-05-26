---
epic: 11
story: 5
title: "Deduplicação de Comprovantes + Fila de Validação Manual"
type: "Core"
status: ready-for-dev
---

# Story 11.5: Deduplicação de Comprovantes + Fila de Validação Manual

## História de Usuário
Como Sistema,
quero detectar comprovantes duplicados e enfileirar elegantemente resultados de OCR de baixa confiança para validação humana,
para que nunca creditemos um pagamento em dobro e a operação continue mesmo quando o fallback de IA Vision estiver desabilitado (ia-eco/ia-zero).

## Critérios de Aceite

1. Nova tabela `receipt_fingerprints`: `id`, `tenant_id`, `customer_id`, `installment_id` (nullable), `phash` BIGINT (perceptual hash 64-bit), `txn_id` (text, nullable — extraído pelo OCR), `bank_code` (text, nullable), `amount` NUMERIC, `txn_date` DATE, `media_url` (referência ao MinIO), `confidence` NUMERIC (0-100, do OCR), `status` ('auto_processed' | 'manual_pending' | 'manual_approved' | 'manual_rejected' | 'duplicate_rejected'), `created_at`. Index em `(tenant_id, txn_id)` (onde `txn_id` não é nulo) e em `(tenant_id, phash)`.
2. `ReceiptDedupeService`:
   - `compute_phash(image_bytes) -> int` — usa `imagehash` (lib Python) — pHash 8x8 default
   - `find_duplicate(tenant_id, phash, txn_id) -> Optional[ReceiptFingerprint]` — 2 estratégias:
     a. Match exato de `txn_id` (mais forte)
     b. Distância de Hamming do pHash ≤ 5 (configurável em `system_settings.dedupe_phash_threshold`) — pega imagens visualmente quase iguais mesmo se renomeadas/recortadas
3. Pipeline atualizado de mídia de entrada (estende Story 6.9):
   ```
   recebe mídia → MinIO → compute_phash → checa duplicata
     se duplicado → status='duplicate_rejected'
       → envia template "Este comprovante já foi processado em DD/MM/YYYY"
       → não chama OCR (economia)
     senão → Tesseract OCR
       se OperationMode.is_allowed('llm_vision_fallback') AND confidence < 70:
         → LlmVisionAdapter (já existe na Story 6.9)
       insere em receipt_fingerprints com confidence final
       se confidence ≥ 70 AND match único encontrado → baixa automática (status='auto_processed')
       senão → status='manual_pending'
   ```
4. Em **ia-zero** ou **ia-eco**: fallback LLM Vision DESABILITADO. Comprovantes com confidence < 70 caem direto em `manual_pending`. Cliente recebe template "Recebemos seu comprovante. Validação manual em até 24h." (template configurável).
5. Endpoints do backend:
   - `GET /api/v1/receipts/pending` — fila de validação manual (filtros: cliente, intervalo de datas, intervalo de valor)
   - `GET /api/v1/receipts/{id}` — detalhe (preview da imagem, dados extraídos pelo OCR, parcelas candidatas)
   - `POST /api/v1/receipts/{id}/approve` — body `{installment_id, amount_override?}` → executa a baixa
   - `POST /api/v1/receipts/{id}/reject` — body `{reason: 'duplicate' | 'invalid' | 'other', notes?}`
   - `POST /api/v1/receipts/{id}/reassign` — body `{customer_id}` → quando o OCR deu match no cliente errado
6. Evento SSE `receipt_pending_review` quando novo item entra na fila — notifica gestores online.
7. Página de frontend **/system/receipts/pending** (nova rota):
   - Lista paginada com badges por status, thumbnail da foto, valor extraído, cliente sugerido, idade do item
   - Clique abre modal de detalhe (usar `<app-modal>` da Story 10.8) com:
     - Preview da imagem (pronto para lightbox)
     - Side panel: dados extraídos editáveis (`txn_id`, `amount`, `date`, `bank`)
     - Lista de parcelas candidatas rankeadas por probabilidade (match de cliente + valor próximo + data próxima)
     - Botões Aprovar/Reatribuir/Rejeitar
   - Filtros: status, intervalo de data, intervalo de valor, cliente
8. Widget no Dashboard: "Comprovantes Aguardando Validação" com contador + link
9. Testes:
    - Detecção de duplicata — `txn_id` exato E phash similar
    - Threshold de confidence respeitado
    - Gate de modo: em ia-zero, LLM Vision nunca é chamado
    - Approve dispara baixa (Epic 4)
    - Reject não movimenta dinheiro
    - SSE disparado ao entrar na fila

## Contexto Técnico

### Referências de Arquitetura
- Construído em cima da Story 6.9 (Detecção de Comprovante e Baixa Primária)
- Reaproveita `IOcrProvider`, `TesseractAdapter`, `LlmVisionAdapter` já existentes
- Fluxos de baixa via Epic 4 (Story 4.3 manual, Story 4.4 parcial)
- Gate de modo via `OperationModeService.is_allowed('llm_vision_fallback')` (Story 11.2)

### Arquivos a Criar/Modificar
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

### Novas dependências
- `imagehash>=4.3` (Python — pHash, dHash, aHash; depende do Pillow já presente)

### Dependências
- Story 6.9 (Detecção de Comprovante — estende, não substitui)
- Story 4.3 / 4.4 (fluxos de baixa)
- Story 10.8 (`<app-modal>` reutilizável)
- Story 11.2 (gate de OperationMode)

### Notas Técnicas
- **Threshold default do pHash = 5**: distância de Hamming ≤ 5 em 64 bits = ~92% de similaridade. Valor calibrado para pegar prints recortados sem falsos positivos.
- **Algoritmo de ranking de candidatos**: score = `customer_match_weight * 0.5 + amount_match_score * 0.3 + date_proximity_score * 0.2`. Threshold de "baixa automática" = score ≥ 0.85 + único candidato.
- **Caso de uso de reassign**: às vezes o telefone do cliente A manda comprovante de pagamento do cliente B (família, contador). Reassign permite isso.
- **Audit log**: aprovação manual grava em `audit_log` com `actor_id` do gestor e `actor='human_validator'`
- **Backfill**: rodar tarefa Celery one-shot para popular pHash de comprovantes antigos do Epic 6 no deploy

## Checklist do Dev
- [ ] Todos os critérios de aceite atendidos
- [ ] Testes escritos e passando
- [ ] Sem regressões
- [ ] Code review (`bmad-code-review`) executado e aprovado
