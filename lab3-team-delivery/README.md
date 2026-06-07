# Lab 3 Report

This report documents the Lab 3 team delivery work. The implementation starts
from the Lab 2 Part A REST worker and adds the observability requirements from
the Lab 3 guide.

## Objective

The goal is to establish the existing observability baseline in MZinga and add
structured logs, OpenTelemetry traces, and Prometheus metrics to the Python
email worker.

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
  names such as `worker_started`, `authenticated`, `starting_processing`,
  `communication_sent`, and `processing_failed`;
- bound `doc_id` while a single Communication is being processed, so all logs
  for that item can be correlated.

At this step, `trace_id` and `span_id` are prepared for the distributed tracing
work added in the following steps.

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

## Evidence

Runtime evidence collected from the local stack:

- Log file: MZinga metrics output showing `http_request_duration_seconds`,
  `http_requests_total`, and `up`.
- Screenshot: Jaeger search page at `http://localhost:16686` with the MZinga
  service visible.
- Screenshot: one opened Jaeger trace waterfall for a MZinga request.
- Log file: worker terminal output showing JSON logs with the same `doc_id` on
  `starting_processing` and `communication_sent`.

Evidence locations:

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
- `starting_processing` shows that a Communication was claimed by the worker.
- `communication_sent` shows that the same Communication was processed
  successfully.
- The repeated `doc_id` value `6a25da6f756b74d028d76839` links the processing
  and completion log entries to the same Communication.

Together, these lines verify the expected Step 2 behavior: the worker no longer
emits free-form text logs, and each processing event is represented as a
queryable JSON object with stable fields.


## Team Task Check (Step 5-6) on Team Baseline

### Objective

The goal of these steps is to establish the existing observability baseline in
MZinga and Jaeger UI, which is if both uses JSON format and showing traces in the same format.

### Baseline used:

- Lab3 base content from commit `6d1fef7` (`lab3: complete observability steps 1 and 2`)
- Lab3 base content `worker.py` and `.env` from `lab3: complete observability fix, step 4`

Lab 3 Step 1 and Step 2 for to see if the logs are in JSON format, Step 4 to add Jaeger Service and prometheus. 
- Must use important dependencies in `.env` file, which are:
  - `OTEL_EXPORTER_OTLP_ENDPOINT`: the Jaeger OTLP endpoint.
  - `OTEL_SERVICE_NAME`: the service name as it will appear in Jaeger.
  - `PROMETHEUS_PORT`: the port for the /metrics endpoint.
- Must show `Communications` changes in JSON.
- The `traceid` from output can be seen in jaeger, either by searching its id
or observing in the main page ( http://localhost:16686/search ).

In the Jaeger UI, Jaeger UI must:
- `trace_id` or `doc_id` of the output must match the trace visible in Jaeger and need to be in JSON format.

### Changes in .env part: 
```
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
OTEL_SERVICE_NAME=email-worker
PROMETHEUS_PORT=8000
```

#### Important Note:

- It is important to note here that, in the `worker.py` has the functions beforehand, so there is no need to add any code to the `worker.py`.

### Step 5 - Testing and Collecting Evidence

- 1. Running `worker.py` with the changes in `.env`:
Starting the process to see if the system can be reachable, can be connected with possible admin login.
- 2. Using MZinga webpage to create a new communication:
After the worker is online an working, using the mzinga webpage, create a new communication document.
- 3. Checking `worker.py` results for the output:
We are looking for output to be shown in JSON format, if it's shown in JSON, this test is a success

### Results of Step 5:

- Single line code in readable form:
```code
{
  "service": "email-worker",
  "event": "email_delivery_completed",
  "doc_id": "6a0f99ff29f2803fe4392894",
  "level": "info",
  "timestamp": "2026-05-21T23:49:22.996115Z",
  "trace_id": "c1f758e272feffda77bc4cd34fe11b07",
  "span_id": "4c5fc795facf5303"
}
```
- `trace_id` extracted from the code:
```code
"trace_id": "c1f758e272feffda77bc4cd34fe11b07"
```
- `doc_id` extracted from the code:
```code
"doc_id": "6a0f99ff29f2803fe4392894"
```

### Step 6 - Checking Jaeger for Observability.

- After extracting "trace.id", we can lookup to changes happened by `worker.py` in Jaeger observability tool .
- In the Jaeger (localhost:16686 in this test environment), in "search tab", choosing service and operation, 
then pressing `find traces`, we can see timetable and traces. In the top left, there is a `Search by trace.id` bar.
- Entering `trace.id` we extracted to here, The Jaeger simply opens the specific trace in a new page.
- In the new page, extending the operation tables shows us every data they have on them. Crosschecking `doc.id` to see 
if we are on the right page.
- After crosschecking, we can see that In Jaeger, data can be seen in JSON, which is proof that this test is successful.

### Results of Step 6:

- The worker environment was configured with the required OpenTelemetry and Prometheus variables through the .env file, allowing integration with Jaeger and observability tooling.
- After starting the worker and creating new Communication documents through the MZinga admin UI, the worker successfully processed communications and produced structured JSON log output instead of plain-text logs. The logs included important observability fields such as: `doc_id` and `trace_id`.

The generated `trace_id`values were successfully matched with traces visible in Jaeger, confirming that distributed tracing and log correlation were functioning correctly. 

## Evidence To Add

For proof of observation and changes the screenshots named below can be checked for proof.

```text
lab3-team-delivery/screenshots/step5_6_worker_output_pure.png
lab3-team-delivery/screenshots/step5_6_worker_output_readable.png
lab3-team-delivery/screenshots/step5_6_jaeger_proof_closelook.png
lab3-team-delivery/screenshots/step5_6_jaeger_proof_JSON.png
```

## Evidence Interpretation

- `step5_6_worker_output_pure.png` is a direct screenshot of the aftermath of process. `step5_6_worker_output_readable.png` is a fixed verison of the output.
- Within the worker output, output can be seen as JSON format.
- `lab3-team-delivery/screenshots/step5_6_jaeger_proof_closelook.png` is a screenshot from Jaeger to show results of the process. Also in this photo, in the top left the process is searched with `doc_id`.
- `lab3-team-delivery/screenshots/step5_6_jaeger_proof_JSON.png` is a screenshot of the Jaeger with process details on the screen. It has `trace_id` observable in the JSON form.

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

  The `status="failed"` increment is emitted from `process_communication` when
  an exception is handled, next to the span ERROR status, so a failure surfaces
  consistently across trace, log, and metric. Processing and SMTP durations are
  recorded for the failure path as well.
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
sending again increments `emails_processed_total{status="failed"}`. Restarting
MailHog and resetting the same Communication to `pending` verifies the recovery
path and increments `emails_processed_total{status="sent"}` again.

## Step 7 - Verify Traces in Jaeger

Evidence:

- `lab3-team-delivery/logs/step7-team-baseline-check.log`

Observed:

- log + Jaeger trace correlation works (`trace_id` matches)
- spans `process_communication`, `serialize_body`, `send_email` are present
- span attributes (`doc_id`, `node_count`, `recipient_count`) are present
- auto HTTP spans for `GET /api/communications/:id` and
  `PATCH /api/communications/:id` are present as children of
  `process_communication`
- MZinga server spans are linked under the worker HTTP client spans

Status:

- Step 7 is verified on the team delivery branch.

## Step 8 - Verify Metrics in Prometheus

Evidence:

- `lab3-team-delivery/logs/step8-team-metrics-check.log`

Observed:

- `http://localhost:8000/metrics` is exposed by the worker
- `emails_processed_total` is present with `status` and `recipient_count`
- `email_processing_duration_seconds_bucket` is present
- `smtp_send_duration_seconds_bucket` is present
- `worker_poll_total` is present with `result`
- success, failure, and recovery runs increment the expected counters

Status:

- Step 8 is verified on the team delivery branch.

## Step 9 - Simulate and Diagnose a Failure

Evidence:

- `lab3-team-delivery/logs/step9-team-baseline-check.log`

Observed:

- failure simulation sets communication to `failed`
- failure metrics increment `emails_processed_total{status="failed"}`
- failure trace shows `process_communication` and `send_email` status `ERROR`
- recovery path returns same communication to `sent`
- recovery trace shows `send_email` status `OK`
- recovery metrics increment `emails_processed_total{status="sent"}`

Status:

- Step 9 is verified on the team delivery branch.
