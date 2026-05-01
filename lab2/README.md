# Lab 2 - Sefa (Step B1 + B3 + B4)

This branch contains only my assigned Lab 2 Part B scope:
- Step B1: WebHooks/messageBus analysis
- Step B3: RabbitMQ event inspection
- Step B4: event-driven worker implementation

## Paths used
- Labs repo: `%USERPROFILE%\IdeaProjects\AY-25-26-labs`
- MZinga repo: `%USERPROFILE%\IdeaProjects\mzinga-apps`

## Step B1 - what I verified in MZinga code

Files inspected:
- `%USERPROFILE%\IdeaProjects\mzinga-apps\src\hooks\WebHooks.ts`
- `%USERPROFILE%\IdeaProjects\mzinga-apps\src\messageBusService.ts`

Observed behavior:
1. WebHooks scans env keys in format `HOOKSURL_<COLLECTION_SLUG>_<HOOK_TYPE>`.
2. With `HOOKSURL_COMMUNICATIONS_AFTERCHANGE=rabbitmq`, communication `afterChange` events are published.
3. Routing key equals env key name:
   - `HOOKSURL_COMMUNICATIONS_AFTERCHANGE`
4. Exchanges in message bus service:
   - `mzinga_events` (topic)
   - `mzinga_events_durable` (topic, durable, internal, no auto-delete)
5. Binding exists:
   - `mzinga_events` -> `mzinga_events_durable` with `#`

### Runtime note from this codebase

For the local run used in this delivery, two local MZinga runtime adjustments were needed so the expected event flow worked consistently:
- in `WebHooks.ts`, append webhook hooks instead of replacing existing hooks.
- in `Communications.ts`, set `pending` only on `create` and resolve id as `doc.id || doc._id`.

These are local runtime notes for this setup; they are not committed in this labs repo.

## Step B3 - event inspection flow

### MZinga env
In `%USERPROFILE%\IdeaProjects\mzinga-apps\.env`:

```env
COMMUNICATIONS_EXTERNAL_WORKER=true
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
HOOKSURL_COMMUNICATIONS_AFTERCHANGE=rabbitmq
```

### Start stack

```powershell
docker compose -f "%USERPROFILE%\IdeaProjects\AY-25-26-labs\docs\docker-compose-simplified.yml" --env-file "%USERPROFILE%\IdeaProjects\mzinga-apps\.env" -p mzinga-lab2 up -d database messagebus cache
docker run -d --name lab2-mailhog -p 1025:1025 -p 8025:8025 mailhog/mailhog
cd "%USERPROFILE%\IdeaProjects\mzinga-apps"
npm run dev
```

### RabbitMQ checks
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

## Step B4 - event-driven worker

Implemented files:
- `lab2/lab2-worker-events/worker.py`
- `lab2/lab2-worker-events/requirements.txt`
- `lab2/lab2-worker-events/.env`
- `lab2/lab2-worker-events/.gitignore`

Run command:
```powershell
cd "%USERPROFILE%\IdeaProjects\AY-25-26-labs\lab2\lab2-worker-events"
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

## Verification (B scope only)

Summary file:
- `lab2/logs/verification-summary.log`

Logged checks:
- state3 event-driven send (`sent`)
- durability check (`pending` while worker down -> `sent` after restart)
- queue counters snapshot before and after processing

### Screenshots

Folder:
- `lab2/screenshots/`

Files:
- `01_mzinga_login.png`
- `02_mzinga_comm_pending.png`
- `03_rabbitmq_queue_ready.png`
- `04_mailhog_inbox_pre.png`
- `05_mzinga_comm_sent.png`
- `06_rabbitmq_queue_after_processing.png`
- `07_mailhog_inbox_post.png`

### Logs

Folder:
- `lab2/logs/`

Files:
- `state3-event.out.log`
- `state3-durability-recovery.out.log`
- `verification-summary.log`

## Stop commands

```powershell
docker compose -f "%USERPROFILE%\IdeaProjects\AY-25-26-labs\docs\docker-compose-simplified.yml" --env-file "%USERPROFILE%\IdeaProjects\mzinga-apps\.env" -p mzinga-lab2 down
docker rm -f lab2-mailhog
```
