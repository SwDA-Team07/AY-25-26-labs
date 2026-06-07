# Lab 2 - REST API Worker and Event-Driven Worker

This folder documents the team Lab 2 delivery.

## Part A - State 2 REST API Worker

Part A replaces the worker's direct MongoDB dependency with calls to the MZinga
REST API. The worker polls pending Communications through MZinga's HTTP
contract, sends the email through SMTP, and writes status transitions back
through:

```http
PATCH /api/communications/:id
```

### Implemented Files

- `lab2-team-delivery/lab2-worker-rest/worker.py`
- `lab2-team-delivery/lab2-worker-rest/requirements.txt`
- `lab2-team-delivery/lab2-worker-rest/.env`
- `lab2-team-delivery/lab2-worker-rest/.gitignore`
- `lab2-team-delivery/logs/state2-rest.out.log`
- `lab2-team-delivery/screenshots/partA_mailhog.png`
- `lab2-team-delivery/screenshots/partA_mzinga_sent.png`

### Local Test Accounts

- worker/admin API user: `admin.lab1@example.com`
- recipient user: `user@example.com`

The worker uses the admin account only to authenticate against the REST API.
The recipient user is selected in the Communication document and is resolved
through `depth=1`.

### Runtime Requirements

MZinga must include the Lab 1 Communications changes before running the REST
worker:

- `Communications.ts` has the `status` field with values `pending`,
  `processing`, `sent`, and `failed`.
- `Communications.ts` allows authenticated admin `PATCH` requests so the worker
  can write back status transitions through the REST API.
- `COMMUNICATIONS_EXTERNAL_WORKER=true` prevents MZinga from sending the email
  in-process and leaves the document for the external worker.
- `Communications.ts` sets `pending` on create, so the REST worker can pick up
  the document.

### Worker Behavior

1. Authenticates with `POST /api/users/login` and stores the JWT token.
2. Polls pending Communications with:
   - `GET /api/communications?where[status][equals]=pending&depth=1`
3. Claims each document by setting status to `processing`.
4. Fetches the full document with:
   - `GET /api/communications/:id?depth=1`
5. Resolves `tos`, `ccs`, and `bccs` email addresses from the populated REST
   response.
6. Renders the Slate `body` field into simple HTML.
7. Sends the email through the configured SMTP sink.
8. Patches final status to `sent` or `failed`.
9. Re-authenticates once and retries when the REST API returns HTTP 401.

### Run

Start the infrastructure from the labs repo:

```sh
docker compose --env-file mzinga-apps/.env -f docs/docker-compose-simplified.yml up -d database cache messagebus
```

Start MailHog:

```sh
docker run -d --name lab2-mailhog -p 1025:1025 -p 8025:8025 mailhog/mailhog
```

Start MZinga:

```sh
cd <MZINGA_REPO_ROOT>
COMMUNICATIONS_EXTERNAL_WORKER=true npm run dev
```

Start the REST worker:

```sh
cd <LABS_REPO_ROOT>/lab2-team-delivery/lab2-worker-rest
source .venv/bin/activate
python worker.py
```

### Verification

Manual verification flow:

1. Login to MZinga admin at `http://localhost:3000/admin`.
2. Create or reuse the recipient user `user@example.com`.
3. Create a new Communication in `Notifications -> Communications`.
4. Select `user@example.com` as recipient.
5. Save the Communication.
6. Confirm the worker processes it:
   - `pending -> processing -> sent`
7. Confirm the email appears in MailHog at `http://localhost:8025`.
8. Confirm the REST worker has no direct MongoDB dependency:
   - `grep -RInE "mongodb|pymongo|MONGODB_URI" lab2-team-delivery/lab2-worker-rest`

Worker log from the successful local run:

```text
[lab2-worker-rest] authenticated to mzinga api
[lab2-worker-rest] worker started
[lab2-worker-rest] settings: api=http://localhost:3000, poll=5s
[lab2-worker-rest] 6a05cf6b1b9ff40938063014 set to processing
[lab2-worker-rest] 6a05cf6b1b9ff40938063014 sent
```

Recorded summary:

```text
STATE2 id=6a05cf6b1b9ff40938063014 final_status=sent
```

Evidence:

- `lab2-team-delivery/logs/state2-rest.out.log`
- `lab2-team-delivery/logs/verification-summary.log`
- `lab2-team-delivery/screenshots/partA_mailhog.png`
- `lab2-team-delivery/screenshots/partA_mzinga_sent.png`

## Part B - State 3 Event-Driven Worker

Part B evolves the Part A REST worker from polling to RabbitMQ-driven
processing. The worker still uses the MZinga REST API as the source of truth for
reading Communications and writing status transitions.

### Scope

- Sefa: Step B1 WebHooks/messageBus analysis.
- Sefa: Step B3 RabbitMQ event inspection.
- Sefa: Step B4 initial event-driven worker implementation.
- Sefa: original State 3 verification artifacts.
- Filippo: worker ACK/requeue policy refinement and updated verification
  logs.

### Step B1 - WebHooks and Message Bus Analysis

Files inspected in the MZinga repo:

- `src/hooks/WebHooks.ts`
- `src/messageBusService.ts`

Observed behavior:

1. WebHooks scans env keys in format `HOOKSURL_<COLLECTION_SLUG>_<HOOK_TYPE>`.
2. With `HOOKSURL_COMMUNICATIONS_AFTERCHANGE=rabbitmq`, Communication
   `afterChange` events are published.
3. Routing key equals the env key name:
   - `HOOKSURL_COMMUNICATIONS_AFTERCHANGE`
4. Exchanges in the message bus service:
   - `mzinga_events` (topic)
   - `mzinga_events_durable` (topic, durable, internal, no auto-delete)
5. Binding exists:
   - `mzinga_events` -> `mzinga_events_durable` with `#`

### Runtime Notes

For the local Part B run, the MZinga runtime must include the Lab 1 and Lab 2
Part A Communication changes:

- `Communications.ts` has the `status` field (`pending`, `processing`, `sent`,
  `failed`).
- `Communications.ts` allows authenticated admin `PATCH` requests so the worker
  can write back status transitions through the REST API.
- `COMMUNICATIONS_EXTERNAL_WORKER=true` prevents MZinga from sending the email
  in-process.
- `Communications.ts` sets `pending` only on `create`, so worker status updates
  are not overwritten.
- `WebHooks.ts` appends webhook hooks instead of replacing existing collection
  hooks, so the `pending` hook and the RabbitMQ publisher hook both run.
- Communication id is resolved as `doc.id || doc._id` where needed.

These are local runtime notes for this setup; they are not committed in this
labs repo.

### Step B3 - Event Inspection Flow

MZinga `.env` values:

```env
COMMUNICATIONS_EXTERNAL_WORKER=true
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
HOOKSURL_COMMUNICATIONS_AFTERCHANGE=rabbitmq
```

Start stack:

```powershell
docker compose -f "%USERPROFILE%\IdeaProjects\AY-25-26-labs\docs\docker-compose-simplified.yml" --env-file "%USERPROFILE%\IdeaProjects\mzinga-apps\.env" -p mzinga-lab2 up -d database messagebus cache
docker run -d --name lab2-mailhog -p 1025:1025 -p 8025:8025 mailhog/mailhog
cd "%USERPROFILE%\IdeaProjects\mzinga-apps"
npm run dev
```

RabbitMQ checks:

- UI: `http://localhost:15672`
- login: `guest` / `guest`
- verify exchanges and queues

Optional subscriber command:

```powershell
cd "%USERPROFILE%\IdeaProjects\mzinga-apps\examples\servicebus-subscriber"
npm install
$env:RABBITMQ_URL="amqp://guest:guest@localhost:5672/"
$env:ROUTING_KEY="HOOKSURL_COMMUNICATIONS_AFTERCHANGE"
npm start
```

### Step B4 - Event-Driven Worker

Implemented files:

- `lab2-team-delivery/lab2-worker-events/worker.py`
- `lab2-team-delivery/lab2-worker-events/requirements.txt`
- `lab2-team-delivery/lab2-worker-events/.env`
- `lab2-team-delivery/lab2-worker-events/.gitignore`

Run command:

```powershell
cd "%USERPROFILE%\IdeaProjects\AY-25-26-labs\lab2-team-delivery\lab2-worker-events"
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python worker.py
```

Implemented behavior:

1. REST login and JWT use for API requests.
2. RabbitMQ robust connection.
3. Durable exchange declaration:
   - `mzinga_events_durable`
4. Durable named queue:
   - `communications-email-worker`
5. Binding key:
   - `HOOKSURL_COMMUNICATIONS_AFTERCHANGE`
6. `prefetch_count=1`.
7. Consume loop:
   - parse JSON message
   - skip `operation=update`
   - fetch communication with `depth=1`
   - idempotency guard (`sent`/`processing` skip)
   - patch status `processing` then `sent` / `failed`
8. Token refresh path on HTTP 401.
9. `doc.id` / `doc._id` fallback handling in event payload.
10. SMTP delivery through the configured SMTP sink (`localhost:1025` for
    MailHog).
11. PATCH write-back to MZinga REST API:
    - `processing` before delivery
    - `sent` after successful SMTP delivery
    - `failed` after delivery errors
12. Explicit ACK/reject policy:
    - update events, not-found documents, and already processed documents are
      acknowledged and skipped.
    - invalid JSON, missing payload data, and missing ids are rejected without
      requeue because retrying cannot fix them.
    - transient REST failures while fetching or claiming a document are rejected
      with requeue enabled.
    - valid create events are acknowledged only after the worker has completed
      the REST fetch, SMTP processing, and final status write-back.
    - if SMTP delivery fails but the document is successfully marked `failed`,
      the message is acknowledged because the failure has been persisted in
      MZinga.
    - if the worker cannot persist the final `failed` status, the message is
      rejected with requeue enabled.
13. `prefetch_count=1` keeps only one unacknowledged message per worker
    instance.

### B4 Completion Notes

The event payload is treated as a trigger, not as the source of truth. The
worker extracts only the Communication id from `data.doc.id` / `data.doc._id`,
then fetches the current document through:

```http
GET /api/communications/:id?depth=1
```

This is important because `depth=1` resolves `tos`, `ccs`, and `bccs` into user
objects with email addresses. The SMTP message is built from that resolved REST
response, and the final state is written back through:

```http
PATCH /api/communications/:id
```

The idempotency guard skips documents already in `sent` or `processing`, which
protects the worker from duplicate RabbitMQ delivery and repeated create events.
The `operation=update` filter prevents the worker's own status PATCH operations
from creating an infinite event loop.

### Step B5 - State 3 Verification

Verification procedure:

1. Stop the REST polling worker from Part A.
2. Start MailHog and MZinga with RabbitMQ publishing enabled.
3. Start `lab2-team-delivery/lab2-worker-events/worker.py`.
4. Create a Communication document in the MZinga admin UI.
5. Confirm the worker processes the message immediately without polling.
6. Confirm status transitions in MZinga:
   - `pending -> processing -> sent`
7. Stop the worker, create another Communication document, then restart the
   worker.
8. Confirm the durable queue keeps the message while the worker is offline and
   drains after reconnect.
9. Confirm RabbitMQ queue `communications-email-worker` returns to zero
   ready/unacknowledged messages after processing.

Summary file:

- `lab2-team-delivery/logs/verification-summary.log`

Recorded summary lines:

- `STATE3 id=69f9f707eb3427ce5f483bbc ... final_status=sent`
- `DURABILITY id=69f9f767eb3427ce5f483be6 ... status_before=pending status_after=sent queue_ready_before=2 queue_ready_after=0 queue_unacked_after=0`
- `QUEUE_SNAPSHOT ready_before_processing=2 ready_after_processing=0`
- `MAILHOG_SNAPSHOT total_after_processing=2 ...`

Logs:

- `lab2-team-delivery/logs/state3-event.out.log`
- `lab2-team-delivery/logs/state3-durability-recovery.out.log`
- `lab2-team-delivery/logs/verification-summary.log`

Screenshots:

- `lab2-team-delivery/screenshots/01_mzinga_login.png`
- `lab2-team-delivery/screenshots/02_mzinga_comm_pending.png`
- `lab2-team-delivery/screenshots/03_rabbitmq_queue_ready.png`
- `lab2-team-delivery/screenshots/04_mailhog_inbox_pre.png`
- `lab2-team-delivery/screenshots/05_mzinga_comm_sent.png`
- `lab2-team-delivery/screenshots/06_rabbitmq_queue_after_processing.png`
- `lab2-team-delivery/screenshots/07_mailhog_inbox_post.png`

## Stop

```sh
docker compose --env-file mzinga-apps/.env -f docs/docker-compose-simplified.yml down
docker rm -f lab2-mailhog
```
