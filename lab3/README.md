# Lab 3 Delivery - s324924

This delivery follows the professor-pushed Lab 3 requirements from:
- `docs/08-lab3-step-by-step.md`
- `docs/08-lab3-code-snippets.md`

## Repos and paths
- Labs repo: `<LABS_REPO_ROOT>` (example: `~/IdeaProjects/AY-25-26-labs`)
- MZinga repo: `<MZINGA_REPO_ROOT>` (example: `~/IdeaProjects/mzinga-apps`)

## Prerequisites and run commands

### Infrastructure
```sh
docker compose -f <LABS_REPO_ROOT>/docs/docker-compose-simplified.yml \
  --env-file <MZINGA_REPO_ROOT>/.env \
  -p mzinga-lab3 up -d database messagebus cache jaeger
```

### MailHog
```sh
docker run -d --name lab3-mailhog -p 1025:1025 -p 8025:8025 mailhog/mailhog
```

### MZinga app
```sh
cd <MZINGA_REPO_ROOT>
npm install
npm run dev
```

### Worker
```sh
cd <LABS_REPO_ROOT>/lab3/lab3-worker-observable
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python worker.py
```

## Runtime snippet mirrored in this repo

To avoid pushing anything to `mzinga-apps`, the runtime-side `Communications.ts`
changes used during verification are mirrored here:
- `lab3/snippets/communications-ts-runtime-snippet.md`

## Step 1 - Explore existing MZinga observability

Evidence:
- `lab3/logs/step1-mzinga-metrics-extract.log`
- `lab3/logs/step1-jaeger-services.json`

Verified:
- `http_request_duration_seconds` present in MZinga metrics
- `up 1` present in MZinga metrics
- Jaeger services include `mzinga-apps-local-tenant-prod` and `email-worker`

## Step 2 - Structured logging

Implemented in:
- `lab3/lab3-worker-observable/worker.py`
- `lab3/lab3-worker-observable/requirements.txt`

Implemented behavior:
- JSON logs with `structlog`
- fixed `service="email-worker"`
- bound `doc_id` during processing
- injected `trace_id` and `span_id` from active span context

## Step 3 - Distributed tracing

Implemented in:
- `lab3/lab3-worker-observable/worker.py`

Implemented behavior:
- tracer provider + OTLP HTTP exporter to `http://localhost:4318/v1/traces`
- `RequestsInstrumentor` enabled
- manual spans:
  - `process_communication`
  - `serialize_body`
  - `send_email`

## Step 4 - Custom metrics

Implemented in:
- `lab3/lab3-worker-observable/worker.py`

Implemented metrics:
- `emails_processed_total`
- `email_processing_duration_seconds`
- `smtp_send_duration_seconds`
- `worker_poll_total`

Prometheus endpoint exposure:
- worker starts metrics HTTP server on `PROMETHEUS_PORT`
- verified at `http://localhost:8000/metrics`

## Step 5 - Environment configuration

Template committed:
- `lab3/lab3-worker-observable/.env.example`

Runtime `.env` used during verification:
```env
MZINGA_API_BASE_URL=http://localhost:3000
MZINGA_ADMIN_EMAIL=admin.lab1@example.com
MZINGA_ADMIN_PASSWORD=Lab1Admin!2026
POLL_INTERVAL_SECONDS=3
SMTP_HOST=localhost
SMTP_PORT=1025
EMAIL_FROM=worker@mzinga.io
OTEL_SERVICE_NAME=email-worker
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
PROMETHEUS_PORT=8000
```

## Step 6 - Verify logging

Evidence:
- `lab3/logs/step6-worker-json-success.log`

Verified:
- JSON logs are emitted
- same `doc_id` appears across processing events
- `trace_id` and `span_id` are present while spans are active

## Step 7 - Verify traces in Jaeger

Evidence:
- `lab3/logs/step7-jaeger-success-summary.log`

Verified:
- `process_communication` span present with `doc_id`
- `serialize_body` span present with `node_count`
- `send_email` span present with `recipient_count`
- GET/PATCH HTTP spans are present
- log trace id and Jaeger trace id match

## Step 8 - Verify metrics in Prometheus

Evidence:
- `lab3/logs/step8-worker-metrics-extract.log`

Verified:
- `emails_processed_total`
- `email_processing_duration_seconds_bucket`
- `smtp_send_duration_seconds_bucket`
- `worker_poll_total`

## Step 9 - Simulate and diagnose a failure

Failure simulation:
```sh
docker stop lab3-mailhog
```

Recovery:
```sh
docker start lab3-mailhog
# set failed communication back to pending via PATCH /api/communications/:id
```

Evidence:
- `lab3/logs/step9-worker-json-failure-recovery.log`
- `lab3/logs/step9-summary.log`

Verified:
- failure case sets status to `failed` and trace shows `send_email` as `ERROR`
- metrics increment for `status="failed"`
- after restart + pending reset, worker processes again to `sent`
- recovery trace shows `send_email` status `OK`

## Static checks

```sh
python3 -m py_compile lab3/lab3-worker-observable/worker.py
```
