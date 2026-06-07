# Lab 3 Report - Steps 1 and 2

This report documents the first two Lab 3 activities for branch `labs/s348651`.
The work starts from the Lab 2 Part A REST worker and prepares it for the
observability additions introduced later in Lab 3.

## Objective

The goal of these steps is to establish the existing observability baseline in
MZinga and replace the worker's plain text output with structured JSON logs.
The OpenTelemetry trace and metrics instrumentation is intentionally left for
the next Lab 3 steps.

## Prerequisite

Lab 2 Part A is the starting point. The worker must already be able to:

- authenticate against MZinga through the REST API;
- poll pending `Communications` documents;
- update status through `PATCH /api/communications/:id`;
- send email through the configured SMTP sink.

## Step 1 - Observability Baseline

No worker code was changed in this step. The baseline identified in MZinga is:

- Prometheus metrics are exposed by MZinga at `http://localhost:3000/metrics`.
- Relevant metric families are `http_request_duration_seconds`,
  `http_requests_total`, and `up`.
- Jaeger is available at `http://localhost:16686` when the infrastructure is
  started with the `jaeger` service.
- MZinga tracing is configured in `src/tracing.ts`, where Node
  auto-instrumentation exports HTTP, Express, MongoDB, and Mongoose spans to
  Jaeger through OTLP.

This provides the reference point for the Python worker instrumentation added in
the following steps.

## Step 2 - Structured Logging

A Lab 3 worker copy was created in:

```text
lab3-team-delivery/lab3-worker-observable/
```

The original Lab 2 REST worker remains unchanged. The new worker keeps the same
REST polling and SMTP behavior, but replaces plain text logging with
`structlog` JSON output.

Implemented changes:

- added `structlog==24.4.0` to `requirements.txt`;
- configured `structlog` with JSON rendering, log level, and UTC ISO
  timestamps;
- added a fixed `service="email-worker"` field to every log line;
- replaced text messages such as `[lab2-worker-rest] ...` with stable event
  names such as `worker_started`, `status_updated`,
  `processing_completed`, and `processing_failed`;
- bound `doc_id` while a single Communication is being processed, so all logs
  for that item can be correlated.

`trace_id` and `span_id` are not included yet because distributed tracing is
part of Lab 3 Step 3.

## Verification

Static checks completed:

```sh
python3 -m py_compile lab3-team-delivery/lab3-worker-observable/worker.py
```

The old text logger was also checked:

```sh
rg "print\\(|\\[lab2-worker-rest\\]" lab3-team-delivery/lab3-worker-observable
```

The search returns no matches, confirming that the Lab 3 worker no longer uses
the old `print`-based log format.

## Evidence To Add

Runtime evidence collected from the local stack:

- Log file: MZinga metrics output showing `http_request_duration_seconds`,
  `http_requests_total`, and `up`.
- Screenshot: Jaeger search page at `http://localhost:16686` with the MZinga
  service visible.
- Screenshot: one opened Jaeger trace waterfall for a MZinga request.
- Log file: worker terminal output showing JSON logs with the same `doc_id` on
  `status_updated` and `processing_completed`.
- Optional screenshot: final Communication status `sent` in the MZinga admin
  UI.

Suggested locations:

```text
lab3-team-delivery/logs/metrics.log
lab3-team-delivery/screenshots/step1-jaeger-search.png
lab3-team-delivery/screenshots/step1-jaeger-trace.png
lab3-team-delivery/screenshots/step2-mzinga-status-sent.png
lab3-team-delivery/logs/step2-worker-json.log
```

The metrics evidence is kept as a log file only. Jaeger remains screenshot-based
because the UI makes the service and trace waterfall easier to verify. For Step
2, the JSON worker log is the main evidence because it directly proves the
structured logging format and `doc_id` correlation.

## Evidence Interpretation

`lab3-team-delivery/logs/metrics.log` proves that MZinga exposes Prometheus metrics. The
`http_request_duration_seconds` histogram shows measured HTTP request latency,
with labels such as method, path, status code, tenant, project type, and
version. The `up 1` gauge confirms that the MZinga process was running when the
metrics endpoint was scraped.

`lab3-team-delivery/logs/step2-worker-json.log` proves that the Lab 3 worker writes structured
JSON logs:

- `authenticated` confirms that the worker successfully logged in to the
  MZinga REST API.
- `worker_started` records the API base URL and polling interval.
- `status_updated` with `status="processing"` shows that a Communication was
  claimed by the worker.
- `processing_completed` with `status="sent"` shows that the same
  Communication was processed successfully.
- The repeated `doc_id` value `6a05df60ce0e89964bdcf55c` links the processing
  and completion log entries to the same Communication.

Together, these lines verify the expected Step 2 behavior: the worker no longer
emits free-form text logs, and each processing event is represented as a
queryable JSON object with stable fields.

## Team Task Check (Step 7-8-9) on Team Baseline

Check date: **2026-05-21**

Baseline used:

- `origin/main` at `c029dcc`
- Lab3 base content from commit `6d1fef7` (`lab3: complete observability steps 1 and 2`)

### Step 7 (Traces) - Partial

Evidence:

- `lab3-team-delivery/logs/step7-team-baseline-check.log`

Observed:

- log + Jaeger trace correlation works (`trace_id` matches)
- spans `process_communication`, `serialize_body`, `send_email` are present
- span attributes (`doc_id`, `node_count`, `recipient_count`) are present
- expected auto HTTP spans (`GET`/`PATCH`) were not observed in this run

Status:

- Step 7 can be pushed as **partially verified** on the baseline used for this check.

### Step 8 (Metrics) - Blocked

Evidence:

- `lab3-team-delivery/logs/step8-team-baseline-blocker.log`

Observed:

- `http://localhost:8000/metrics` not exposed on baseline worker
- required custom metrics families are unavailable

Status:

- Step 8 was **blocked** until Step 4 metrics implementation was merged in the
  team branch. **It is now unblocked** by the Step 4 metrics work documented
  below: the worker exposes `/metrics` on `PROMETHEUS_PORT` (8000) and defines the
  four required instruments. Re-run the Step 8 verification on the updated
  baseline to finalise shared evidence.

### Step 9 (Failure + Recovery) - Verified with Step 8 Limitation

Evidence:

- `lab3-team-delivery/logs/step9-team-baseline-check.log`

Observed:

- failure simulation sets communication to `failed`
- failure trace shows `send_email` status `ERROR`
- recovery path returns same communication to `sent`
- recovery trace shows `send_email` status `OK`

Status:

- Step 9 log/trace/status behavior is verified.
- Step 9 metrics part is unblocked together with Step 8 (see Step 4 below).

## Step 4 - Custom Prometheus Metrics

This step adds the third observability pillar to the worker and is what unblocks
Steps 8 and 9 (metrics side). It builds on the existing OpenTelemetry tracing,
reusing the same `Resource` and `service.name` (`email-worker`).

Implemented changes in `lab3-team-delivery/lab3-worker-observable/`:

- `requirements.txt` - added `opentelemetry-exporter-prometheus==0.45b0` and
  `prometheus-client==0.20.0` (both compatible with the pinned
  `opentelemetry-sdk==1.24.0`).
- `worker.py` - initialised the metrics SDK at startup alongside the tracer
  provider: `start_http_server(PROMETHEUS_PORT)` exposes the scrape endpoint, a
  `PrometheusMetricReader` is registered on a `MeterProvider` that reuses the
  tracing `Resource`, and a single `meter = get_meter("email-worker")` is obtained.
- `worker.py` - defined four instruments and recorded measurements at the right
  points in the existing flow:

  | Instrument | Type | Where recorded | Labels |
  |---|---|---|---|
  | `emails_processed_total` | Counter | end of `process_communication` | `status` (`sent`/`failed`), `recipient_count` |
  | `email_processing_duration_seconds` | Histogram | end-to-end span time in `process_communication` | - |
  | `smtp_send_duration_seconds` | Histogram | around `smtp.sendmail` in `send_email` | - |
  | `worker_poll_total` | Counter | each poll cycle in `main()` | `result` (`found`/`empty`) |

  The `status="failed"` increment is emitted in the `except` block of
  `process_communication`, next to the span ERROR status, so a failure surfaces
  consistently across trace, log, and metric.
- `.env` - added `PROMETHEUS_PORT=8000` and documented
  `OTEL_EXPORTER_OTLP_ENDPOINT`.

### Verification

Static check:

```sh
python3 -m py_compile lab3-team-delivery/lab3-worker-observable/worker.py
```

Runtime check (with the lab stack running):

```sh
pip install -r lab3-team-delivery/lab3-worker-observable/requirements.txt
python lab3-team-delivery/lab3-worker-observable/worker.py
curl -s http://localhost:8000/metrics | grep -E \
  'emails_processed_total|email_processing_duration_seconds_bucket|smtp_send_duration_seconds_bucket|worker_poll_total'
```

Create a Communication in the MZinga admin UI and refresh the metrics endpoint:
the counters increment and the histogram buckets accumulate. Stopping MailHog and
sending again increments `emails_processed_total{status="failed"}`. With this in
place, the Step 8 blocker (`curl :8000/metrics` connection refused) is resolved
and the Step 9 metrics path can be finalised.
