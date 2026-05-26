# ── Stage 1: Build ──
FROM python:3.12-slim AS builder
WORKDIR /build
RUN pip install --no-cache-dir uv
COPY pyproject.toml ./
COPY app ./app
RUN uv venv /opt/venv && \
    . /opt/venv/bin/activate && \
    uv pip install --no-cache ".[dev]"

# ── Stage 2: Runtime ──
FROM python:3.12-slim AS runtime

# System deps for WeasyPrint, Tesseract OCR, and general health
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpangocairo-1.0-0 libpango-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
    tesseract-ocr tesseract-ocr-por libtesseract-dev libleptonica-dev \
    libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN useradd -m -s /bin/bash appuser

WORKDIR /app
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
