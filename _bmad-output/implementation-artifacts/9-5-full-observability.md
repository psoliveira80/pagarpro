---
epic: 9
story: 5
title: "Full Observability"
type: "Core"
status: done
---

# Story 9.5: Full Observability

## User Story
As an Operator,
I want Grafana dashboards and alerts,
So that I run the system with confidence.

## Acceptance Criteria

1. Prometheus metrics at `/metrics`: per-route request counts, latency histograms, queue depth, errors, DB connections.
2. OpenTelemetry tracing; traces in Jaeger or Tempo.
3. Structured JSON logs with `correlation_id` propagation.
4. Grafana dashboards (API Overview, DB, Workers, Business, Agent IA) in `infra/observability/grafana/`.
5. Alertmanager rules: API 5xx > 1% (5m), P95 > 1s (10m), Celery queue > 1000 (5m), DB conn pool > 90% (5m), disk > 85%, webhook failures > 5% (10m), agent daily LLM spend over threshold.

## Technical Context

### Architecture References
- **Architecture Section 3.1 (Tech Stack)**: Prometheus + Grafana + Loki + Tempo for metrics/logs/traces.
- **Architecture Section 6 (Infrastructure/Observability)**: `backend-api/app/infrastructure/observability/logging.py`, `tracing.py`, `metrics.py`.
- **Architecture Section 6 (Core)**: `backend-api/app/core/correlation.py` for correlation_id context vars.
- **Architecture Section 16 (Performance)**: P50 <= 80ms, P95 <= 300ms targets.

### Files to Create/Modify
```
backend-api/
├── app/
│   ├── infrastructure/observability/
│   │   ├── logging.py                                  # Modify: ensure structlog JSON with correlation_id
│   │   ├── tracing.py                                  # Modify: OTel tracer setup, export to Tempo/Jaeger
│   │   └── metrics.py                                  # Modify: Prometheus metrics registry, per-route counters/histograms
│   ├── api/middleware.py                               # Modify: inject correlation_id, record request metrics
│   └── core/correlation.py                             # Modify: ensure correlation_id propagation across async boundaries

infra/
├── observability/
│   ├── docker-compose.observability.yml                # Prometheus, Grafana, Loki, Tempo, Alertmanager
│   ├── prometheus/
│   │   ├── prometheus.yml                              # Scrape config: API /metrics, node-exporter, postgres-exporter
│   │   └── rules/
│   │       └── alerts.yml                              # Alertmanager rules (5xx, P95, queue depth, DB, disk, webhooks, LLM spend)
│   ├── grafana/
│   │   ├── provisioning/
│   │   │   ├── datasources/
│   │   │   │   └── datasources.yml                     # Prometheus, Loki, Tempo datasources
│   │   │   └── dashboards/
│   │   │       └── dashboards.yml                      # Dashboard provisioning config
│   │   └── dashboards/
│   │       ├── api-overview.json                       # Dashboard: request rate, latency, error rate, status codes
│   │       ├── database.json                           # Dashboard: connection pool, query latency, locks, size
│   │       ├── workers.json                            # Dashboard: queue depth, task success/failure, latency
│   │       ├── business.json                           # Dashboard: revenue, delinquency, active contracts
│   │       └── agent-ia.json                           # Dashboard: LLM calls, tokens, cost, latency, tool usage
│   ├── loki/
│   │   └── loki-config.yml                             # Loki configuration for log aggregation
│   ├── tempo/
│   │   └── tempo-config.yml                            # Tempo configuration for trace storage
│   └── alertmanager/
│       └── alertmanager.yml                            # Alert routing: email, Slack/webhook notifications
```

### Dependencies
- Epic 1 (Base infrastructure: structlog, middleware, correlation_id)
- Docker Compose infrastructure for local development

### Technical Notes
- Prometheus metrics endpoint at `/metrics` uses `prometheus-fastapi-instrumentator` or manual `prometheus_client` collectors. Metrics include: `http_requests_total{method, path, status}`, `http_request_duration_seconds{method, path}` (histogram), `celery_queue_depth{queue}`, `db_connection_pool_size`, `db_connection_pool_used`.
- OpenTelemetry setup in `tracing.py`: configure `TracerProvider` with `OTLPSpanExporter` pointing to Tempo. Instrument FastAPI, SQLAlchemy, httpx, and Celery with OTel auto-instrumentation.
- Structured logs: `structlog` configured with `JSONRenderer`, processors for `correlation_id` injection, PII masking, and timestamp formatting. Logs shipped to Loki via Docker log driver or Promtail.
- `correlation_id` is generated in middleware (or extracted from `X-Correlation-ID` header), stored in `contextvars`, and propagated through async calls, Celery tasks (via task headers), and log entries.
- Grafana dashboards are provisioned as JSON files. Each dashboard targets specific operational concerns: API health, database performance, worker throughput, business metrics, and AI agent costs.
- Alertmanager rules define thresholds and notification channels. Alert severity levels: `critical` (pages), `warning` (Slack/email).
- The `agent-ia` dashboard tracks: daily LLM API calls, total tokens (prompt + completion), estimated cost, average latency, tool call distribution, and error rate.

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Lint/type-check passing
- [ ] Audit log entries for mutations
- [ ] No regressions
