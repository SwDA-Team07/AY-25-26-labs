# Lab 2 Delivery - s324924

This folder contains my full Lab 2 implementation and manual run flow for:
- Part A (State 2): REST API worker
- Part B (State 3): event-driven worker with RabbitMQ

## Repos and paths
- Labs repo (delivery): `%USERPROFILE%\IdeaProjects\AY-25-26-labs`
- MZinga repo (local runtime changes): `%USERPROFILE%\IdeaProjects\mzinga-apps`

## Step A1 - enable Communications update for admin users

File edited in local MZinga repo:
- `%USERPROFILE%\IdeaProjects\mzinga-apps\src\collections\Communications.ts`

Change:
```ts
access: {
  read: access.GetIsAdmin,
  create: access.GetIsAdmin,
  delete: () => false,
  update: access.GetIsAdmin,
},
```

This is required so the worker can patch communication status over REST.

## Step A2 - inspect REST API shape

Start MZinga and infrastructure first:

```powershell
docker compose -f "%USERPROFILE%\IdeaProjects\AY-25-26-labs\docs\docker-compose-simplified.yml" --env-file "%USERPROFILE%\IdeaProjects\mzinga-apps\.env" -p mzinga-lab2 up -d database messagebus cache
cd "%USERPROFILE%\IdeaProjects\mzinga-apps"
npm run dev
```

Get JWT token:
```powershell
$base = "http://localhost:3000"
$loginBody = @{
  email = "admin.lab1@example.com"
  password = "Lab1Admin!2026"
} | ConvertTo-Json

$login = Invoke-RestMethod -Method Post -Uri "$base/api/users/login" -ContentType "application/json" -Body $loginBody
$token = $login.token
$headers = @{ Authorization = "Bearer $token" }
```

Inspect pending communications with resolved relationships:
```powershell
Invoke-RestMethod -Method Get -Uri "$base/api/communications?where[status][equals]=pending&depth=1" -Headers $headers
```

Inspect a specific communication:
```powershell
$id = "PUT_COMMUNICATION_ID_HERE"
Invoke-RestMethod -Method Get -Uri "$base/api/communications/$id?depth=1" -Headers $headers
```

Patch status:
```powershell
$patchBody = @{ status = "sent" } | ConvertTo-Json
Invoke-RestMethod -Method Patch -Uri "$base/api/communications/$id" -Headers $headers -ContentType "application/json" -Body $patchBody
```

## Step A3 - REST worker implementation

Implemented folder:
- `lab2/lab2-worker-rest`

Files:
- `lab2-worker-rest/worker.py`
- `lab2-worker-rest/requirements.txt`
- `lab2-worker-rest/.env`
- `lab2-worker-rest/.gitignore`

Install and run (Windows PowerShell):
```powershell
cd "%USERPROFILE%\IdeaProjects\AY-25-26-labs\lab2\lab2-worker-rest"
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python worker.py
```

## Step A4 - verify State 2 (REST polling worker)

1. Keep MZinga with:
   - `COMMUNICATIONS_EXTERNAL_WORKER=true`
2. Run REST worker.
3. Create a communication in MZinga admin.
4. Confirm:
   - initial status in admin is `pending`
   - worker updates `pending -> processing -> sent`
   - message appears in MailHog (`http://localhost:8025`)
5. Confirm there is no Mongo URI in `lab2-worker-rest`.

## Step B1 - MZinga WebHooks/messageBus analysis

Inspected:
- `%USERPROFILE%\IdeaProjects\mzinga-apps\src\hooks\WebHooks.ts`
- `%USERPROFILE%\IdeaProjects\mzinga-apps\src\messageBusService.ts`

Observed:
- Rabbit publish is enabled through env key:
  - `HOOKSURL_COMMUNICATIONS_AFTERCHANGE=rabbitmq`
- Routing key equals env key name:
  - `HOOKSURL_COMMUNICATIONS_AFTERCHANGE`
- Declared exchanges:
  - `mzinga_events`
  - `mzinga_events_durable` (durable, internal, no auto-delete)
- Bind:
  - `mzinga_events` -> `mzinga_events_durable` with `#`

## Step B2 - configure MZinga to publish events

Add in `%USERPROFILE%\IdeaProjects\mzinga-apps\.env`:
```env
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
HOOKSURL_COMMUNICATIONS_AFTERCHANGE=rabbitmq
```

Restart MZinga:
```powershell
cd "%USERPROFILE%\IdeaProjects\mzinga-apps"
npm run dev
```

## Step B3 - inspect RabbitMQ event flow

RabbitMQ UI:
- `http://localhost:15672`
- user: `guest`
- password: `guest`

Use MZinga subscriber example:
```powershell
cd "%USERPROFILE%\IdeaProjects\mzinga-apps\examples\servicebus-subscriber"
npm install
$env:RABBITMQ_URL="amqp://guest:guest@localhost:5672/"
$env:ROUTING_KEY="HOOKSURL_COMMUNICATIONS_AFTERCHANGE"
npm start
```

Then create a communication and check subscriber output:
- routing key is `HOOKSURL_COMMUNICATIONS_AFTERCHANGE`
- payload includes `data.doc`
- payload includes `data.operation` (`create`/`update`)

## Step B4 - event-driven worker implementation

Implemented folder:
- `lab2/lab2-worker-events`

Files:
- `lab2-worker-events/worker.py`
- `lab2-worker-events/requirements.txt`
- `lab2-worker-events/.env`
- `lab2-worker-events/.gitignore`

Install and run (Windows PowerShell):
```powershell
cd "%USERPROFILE%\IdeaProjects\AY-25-26-labs\lab2\lab2-worker-events"
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python worker.py
```

Behavior implemented:
- RabbitMQ durable exchange + named durable queue
- queue bind with routing key `HOOKSURL_COMMUNICATIONS_AFTERCHANGE`
- `prefetch_count=1`
- skips `operation=update` events to avoid self-trigger loops
- fetches communication via REST with `depth=1`
- status flow `pending -> processing -> sent/failed`
- re-authentication on HTTP 401

## Step B5 - verify State 3 (event-driven worker)

1. Stop REST worker.
2. Run event-driven worker.
3. Create communication in admin.
4. Confirm:
   - worker receives event immediately
   - status goes `pending -> processing -> sent`
   - MailHog receives the message
5. Durable queue check:
   - stop worker
   - create communication
   - start worker again
   - queued message should be processed after reconnect
6. In RabbitMQ Queues tab, verify queue exists and unacked goes back to 0 after processing.

## Stop services

```powershell
docker compose -f "%USERPROFILE%\IdeaProjects\AY-25-26-labs\docs\docker-compose-simplified.yml" --env-file "%USERPROFILE%\IdeaProjects\mzinga-apps\.env" -p mzinga-lab2 down
docker rm -f lab2-mailhog
```

## Lab 2 artifacts in this repo
- `lab2/README.md`
- `lab2/lab2-worker-rest/*`
- `lab2/lab2-worker-events/*`
