# Lab 3 Report

Team Lab 3 delivery notes. The worker starts from the Lab 2 REST version and
adds structured logs, traces, and metrics.

## Goal

Instrument the Python email worker with the three observability pillars required
by Lab 3:

- structured JSON logs with document and trace correlation;
- OpenTelemetry traces exported to Jaeger;
- Prometheus metrics exposed by the worker.

## Prerequisite

Lab 2 REST worker behavior is the starting point. The worker must be able to:

- authenticate against MZinga through the REST API;
- poll pending `Communications` documents;
- update status through `PATCH /api/communications/:id`;
- send email through the configured SMTP sink.

The MZinga app must be running with the Lab 2/Lab 3 communication flow enabled,
and the infrastructure must expose MongoDB, RabbitMQ, Redis, Jaeger, and an SMTP
sink such as MailHog.

## How to Run

From `lab3-team-delivery/lab3-worker-observable`:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python worker.py
```

The worker reads configuration from `.env`:

```text
MZINGA_API_BASE_URL=http://localhost:3000
MZINGA_ADMIN_EMAIL=admin.lab1@example.com
MZINGA_ADMIN_PASSWORD=Lab1Admin!2026
POLL_INTERVAL_SECONDS=5
SMTP_HOST=localhost
SMTP_PORT=1025
EMAIL_FROM=worker@mzinga.io
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces
OTEL_SERVICE_NAME=email-worker
PROMETHEUS_PORT=8000
```

For another machine, keep the same variable names and change only the endpoint or
credential values needed by that local setup.

## Step 1 - Observability Baseline

The existing MZinga observability baseline was checked before instrumenting the
worker:

- MZinga exposes Prometheus metrics at `http://localhost:3000/metrics`.
- Relevant MZinga metric families include `http_request_duration_seconds`,
  `http_requests_total`, and `up`.
- Jaeger is available at `http://localhost:16686` when the infrastructure is
  started with the `jaeger` service.
- MZinga tracing is configured in `src/tracing.ts`, exporting HTTP, Express,
  MongoDB, and Mongoose spans through OTLP.

Evidence:

- `lab3-team-delivery/logs/metrics.log`
- `lab3-team-delivery/screenshots/step1-jaeger-search.png`
- `lab3-team-delivery/screenshots/step1-jaeger-trace.png`

## Step 2 - Structured Logging

A Lab 3 worker copy was created in:

```text
lab3-team-delivery/lab3-worker-observable/
```

The worker uses `structlog` JSON output instead of plain text logging.
Log fields:

- stable JSON events such as `worker_started`, `authenticated`,
  `starting_processing`, `communication_sent`, and `processing_failed`;
- fixed `service="email-worker"` field;
- `doc_id` bound while processing a Communication;
- `trace_id` and `span_id` added to log entries emitted inside active spans.

Verification:

```sh
python3 -m py_compile lab3-team-delivery/lab3-worker-observable/worker.py
rg "print\(|\[lab2-worker-rest\]" lab3-team-delivery/lab3-worker-observable
```

Evidence:

- `lab3-team-delivery/logs/step2-worker-json.log`
- `lab3-team-delivery/screenshots/step2-mzinga-status-sent.png`

## Step 3 - Distributed Tracing

The worker initializes OpenTelemetry tracing at startup:

- `Resource` uses `service.name` from `OTEL_SERVICE_NAME` with fallback
  `email-worker`;
- `OTLPSpanExporter` sends traces to `OTEL_EXPORTER_OTLP_ENDPOINT`;
- `BatchSpanProcessor` exports spans asynchronously;
- `RequestsInstrumentor().instrument()` creates automatic spans for MZinga REST
  calls;
- manual spans wrap `process_communication`, `serialize_body`, and `send_email`.

Span attributes:

- `process_communication.doc_id`;
- `serialize_body.node_count`;
- `send_email.recipient_count`.

## Step 4 - Custom Prometheus Metrics

The worker exposes Prometheus metrics on `PROMETHEUS_PORT` using
`PrometheusMetricReader` and `prometheus_client.start_http_server`.

Implemented instruments:

| Instrument | Type | Labels |
|---|---|---|
| `emails_processed_total` | Counter | `status`, `recipient_count` |
| `email_processing_duration_seconds` | Histogram | - |
| `smtp_send_duration_seconds` | Histogram | - |
| `worker_poll_total` | Counter | `result` |

Measurements are recorded for success, failure, and recovery paths. SMTP and
processing durations are also recorded when SMTP fails.

Verification:

```sh
curl -s http://localhost:8000/metrics | grep -E \
  'emails_processed_total|email_processing_duration_seconds_bucket|smtp_send_duration_seconds_bucket|worker_poll_total'
```

## Step 5 - Configure the Environment

The worker `.env` contains the Lab 3 observability variables:

```text
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces
OTEL_SERVICE_NAME=email-worker
PROMETHEUS_PORT=8000
```

These values make the worker appear as `email-worker` in Jaeger and expose its
metrics endpoint on `http://localhost:8000/metrics`.

## Step 6 - Verify Logging

Worker logs were verified to be JSON and correlated with both document and trace
context.

Checked:

- log entries include `doc_id` for the same Communication;
- log entries emitted inside spans include `trace_id` and `span_id`;
- the logged `trace_id` matches the trace visible in Jaeger.

Evidence:

- `lab3-team-delivery/logs/step2-worker-json.log`
- `lab3-team-delivery/screenshots/step5_6_worker_output_pure.png`
- `lab3-team-delivery/screenshots/step5_6_worker_output_readable.png`
- `lab3-team-delivery/screenshots/step5_6_jaeger_proof_closelook.png`
- `lab3-team-delivery/screenshots/step5_6_jaeger_proof_JSON.png`

## Step 7 - Verify Traces in Jaeger

Evidence:

- `lab3-team-delivery/logs/step7-team-baseline-check.log`

Checked:

- `email-worker` service appears in Jaeger;
- root span `process_communication` is present;
- root span includes `doc_id`;
- child spans `serialize_body` and `send_email` are present;
- HTTP client spans for `GET /api/communications/:id` and
  `PATCH /api/communications/:id` are present as children;
- MZinga server spans are linked under the worker HTTP client spans;
- worker log `trace_id` matches the Jaeger trace.

Step 7 check: OK.

## Step 8 - Verify Metrics in Prometheus

Evidence:

- `lab3-team-delivery/logs/step8-team-metrics-check.log`

Checked at `http://localhost:8000/metrics`:

- `emails_processed_total` with `status` and `recipient_count` labels;
- `email_processing_duration_seconds_bucket`;
- `smtp_send_duration_seconds_bucket`;
- `worker_poll_total` with `result` label;
- counters increment after success, failure, and recovery runs.

Step 8 check: OK.

## Step 9 - Simulate and Diagnose a Failure

Evidence:

- `lab3-team-delivery/logs/step9-team-baseline-check.log`

Failure path verified:

- stopping MailHog makes SMTP fail;
- worker logs a structured `processing_failed` event with `doc_id`, `trace_id`,
  and exception message;
- Jaeger marks `process_communication` and `send_email` as `ERROR`;
- `emails_processed_total{status="failed"}` increments;
- Communication status becomes `failed`.

Recovery path verified:

- restarting MailHog and resetting the same Communication to `pending` lets the
  worker process it successfully;
- the recovery trace is successful;
- `emails_processed_total{status="sent"}` increments again.

Step 9 check: OK.

## Checklist

Lab 3 delivery status:

- Step 1: MZinga baseline metrics and traces checked;
- Step 2: structured JSON logs added;
- Step 3: OpenTelemetry tracing added;
- Step 4: custom Prometheus metrics added;
- Step 5: environment variables configured;
- Step 6: JSON log and trace correlation verified;
- Step 7: Jaeger trace shape verified;
- Step 8: worker metrics endpoint verified;
- Step 9: failure diagnosis and recovery verified.
