# Lab 2 - Member 4 (Sefa): Step B1 + B3 + B4

This branch contains my Lab 2 Part B contribution on the event-infrastructure side:
- Step B1: WebHooks/message bus flow analysis from MZinga source code
- Step B3: RabbitMQ event inspection flow
- Step B4: event-driven worker implementation (`lab2-worker-events`)

## Paths used
- Labs repo: `%USERPROFILE%\IdeaProjects\AY-25-26-labs`
- MZinga repo: `%USERPROFILE%\IdeaProjects\mzinga-apps`

## Step B1 - what I verified in MZinga code

Files inspected:
- `%USERPROFILE%\IdeaProjects\mzinga-apps\src\hooks\WebHooks.ts`
- `%USERPROFILE%\IdeaProjects\mzinga-apps\src\messageBusService.ts`

Observed behavior:
1. `WebHooks.AddHooksFromList` scans env keys in this format:
   - `HOOKSURL_<COLLECTION_SLUG>_<HOOK_TYPE>`
2. If env value is `rabbitmq` and `RABBITMQ_URL` is configured, the hook publishes to RabbitMQ.
3. Published event shape comes from:
   - `messageBusService.publishEvent({ type: envUrlsKey, data: eventData })`
4. Routing key is exactly `event.type`, so for communications it is:
   - `HOOKSURL_COMMUNICATIONS_AFTERCHANGE`
5. Two exchanges are declared in `messageBusService`:
   - `mzinga_events` (topic)
   - `mzinga_events_durable` (topic, durable, internal, no auto-delete)
6. `mzinga_events` is bound to `mzinga_events_durable` with routing key `#`.
   - This means all events published to `mzinga_events` are forwarded to `mzinga_events_durable`.

## Step B3 - event inspection flow

### 1) Configure MZinga event publishing
In `%USERPROFILE%\IdeaProjects\mzinga-apps\.env`:

```env
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
HOOKSURL_COMMUNICATIONS_AFTERCHANGE=rabbitmq
```

Then restart MZinga:

```powershell
cd "%USERPROFILE%\IdeaProjects\mzinga-apps"
npm run dev
```

### 2) Check RabbitMQ UI
- Open `http://localhost:15672`
- Login with `guest` / `guest`
- Confirm exchanges:
  - `mzinga_events`
  - `mzinga_events_durable`

### 3) Print raw events with the existing subscriber example

```powershell
cd "%USERPROFILE%\IdeaProjects\mzinga-apps\examples\servicebus-subscriber"
npm install
$env:RABBITMQ_URL="amqp://guest:guest@localhost:5672/"
$env:ROUTING_KEY="HOOKSURL_COMMUNICATIONS_AFTERCHANGE"
npm start
```

Then create a communication from MZinga admin and verify:
- routing key is `HOOKSURL_COMMUNICATIONS_AFTERCHANGE`
- payload includes `data.doc` and `data.operation`
- operation is `create` on new communication
- operation is `update` when status is patched later

## Step B4 - event-driven worker

Implemented under:
- `lab2/lab2-worker-events/worker.py`
- `lab2/lab2-worker-events/requirements.txt`
- `lab2/lab2-worker-events/.env`

### Dependencies

```text
aio-pika==9.5.5
requests==2.32.3
python-dotenv==1.0.1
```

### Runtime behavior
1. Login to MZinga REST API (`/api/users/login`) and store JWT.
2. Connect to RabbitMQ with `aio_pika.connect_robust`.
3. Declare `mzinga_events_durable` exchange as topic/durable/internal/no-auto-delete.
4. Declare durable queue and bind with:
   - queue: `communications-email-worker`
   - routing key: `HOOKSURL_COMMUNICATIONS_AFTERCHANGE`
5. Set `prefetch_count=1`.
6. Consume loop:
   - parse event JSON
   - skip `operation=update` to avoid infinite self-trigger loop
   - fetch communication by id with `depth=1`
   - skip if status already `sent` or `processing`
   - patch status to `processing`
   - send SMTP email
   - patch status to `sent` or `failed`
7. If an API call returns 401, re-login and retry.

### Run commands (Windows PowerShell)

```powershell
cd "%USERPROFILE%\IdeaProjects\AY-25-26-labs\lab2\lab2-worker-events"
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python worker.py
```

## Manual check for this part
1. Keep MZinga running with:
   - `COMMUNICATIONS_EXTERNAL_WORKER=true`
   - `HOOKSURL_COMMUNICATIONS_AFTERCHANGE=rabbitmq`
2. Start this worker.
3. Create a communication from admin.
4. Validate:
   - event appears immediately in worker logs (no polling delay)
   - communication goes `pending -> processing -> sent`
   - MailHog gets the email
5. Stop worker, create another communication, start worker again.
   - durable queue should keep the event and process it after reconnect.

