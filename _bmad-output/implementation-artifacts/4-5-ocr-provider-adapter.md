---
epic: 4
story: 5
title: "OCR Provider Adapter"
type: "Core"
status: done
---

# Story 4.5: OCR Provider Adapter

## User Story
As the System,
I want an `IOcrProvider` Port with a default Tesseract implementation,
So that OCR works at zero external cost.

## Acceptance Criteria

1. `IOcrProvider` Protocol: `extract_text(file_bytes, mime)`, `extract_pix_receipt(file_bytes, mime)`.
2. `TesseractOcrAdapter` with OpenCV preprocessing (deskew, denoise, threshold), language `por+eng`.
3. `LlmVisionOcrAdapter` (optional fallback) calling GPT-4o Vision or Claude when confidence is low.
4. Pix receipt regexes: value (`R\$\s*[\d.,]+`), date (`\d{2}/\d{2}/\d{4}`), transaction ID, beneficiary, bank.
5. Results cached in Redis by SHA-256 of file bytes (TTL 7 days).

## Technical Context

### Architecture References
- **Architecture Section 3.1 (Tech Stack)**: `pytesseract + opencv-python` for OCR, latest versions.
- **Architecture Section 6 (Backend Modules)**: `app/domain/ports/ocr_provider.py` — `IOcrProvider` protocol.
- **Architecture Section 6 (Infrastructure)**: `app/infrastructure/integrations/ocr/tesseract_adapter.py` and `llm_vision_adapter.py`.
- **Architecture Section 2.1 (Ports & Adapters)**: All external providers abstracted behind protocol interfaces.

### Files to Create/Modify
```
backend-api/
├── app/domain/ports/ocr_provider.py           # IOcrProvider Protocol definition
├── app/infrastructure/integrations/ocr/
│   ├── __init__.py
│   ├── tesseract_adapter.py                   # TesseractOcrAdapter: OpenCV preprocessing + pytesseract
│   └── llm_vision_adapter.py                  # LlmVisionOcrAdapter: fallback via LLM vision API
├── app/domain/finance/pix_receipt_parser.py    # Pure regex extraction for Pix receipt fields
├── app/application/finance/process_receipt_ocr.py  # Celery task: run OCR, parse, cache, notify
├── app/tests/unit/domain/finance/
│   └── test_pix_receipt_parser.py             # regex extraction tests
├── app/tests/integration/
│   └── test_tesseract_adapter.py              # integration test with sample receipt images
```

### Dependencies
- `pytesseract` and `opencv-python` packages in `pyproject.toml`.
- Redis for caching OCR results.
- `ILlmProvider` port (for `LlmVisionOcrAdapter` fallback).
- Story 4.3 (Write-Off Modal triggers OCR on Pix receipt upload).

### Technical Notes
- `IOcrProvider` protocol has two methods: `extract_text(file_bytes: bytes, mime: str) -> OcrResult` and `extract_pix_receipt(file_bytes: bytes, mime: str) -> PixReceiptData`.
- `TesseractOcrAdapter` preprocessing pipeline: grayscale -> denoise (fastNlMeansDenoising) -> deskew (minAreaRect rotation) -> adaptive threshold -> pytesseract with `lang='por+eng'`.
- `PixReceiptData` dataclass: `value: Decimal | None`, `date: date | None`, `transaction_id: str | None`, `beneficiary: str | None`, `bank: str | None`, `confidence: float` (0.0-1.0).
- Cache key: `ocr:{sha256(file_bytes)}` in Redis with TTL 7 days. Check cache before processing.
- `LlmVisionOcrAdapter` is activated only when Tesseract confidence < 70% and an LLM provider is configured. Uses structured prompt to extract the same `PixReceiptData` fields.
- The OCR processing runs as a Celery background task (`process_receipt_ocr`) triggered by the write-off use case.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
