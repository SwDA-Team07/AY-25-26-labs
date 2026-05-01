# Lab 2 Delivery - s324924

This is my clean rerun of Lab 2 on **2026-05-01** with fresh evidence.

Scope completed:
- Part A (State 2): REST API worker
- Part B (State 3): event-driven worker with RabbitMQ

## Repos and paths
- Labs repo: `%USERPROFILE%\IdeaProjects\AY-25-26-labs`
- MZinga repo (local runtime): `%USERPROFILE%\IdeaProjects\mzinga-apps`

## Step A1 - Communications update access

Local file edited in MZinga:
- `%USERPROFILE%\IdeaProjects\mzinga-apps\src\collections\Communications.ts`

Snippet used:
```ts
access: {
  read: access.GetIsAdmin,
  create: access.GetIsAdmin,
  delete: () => false,
  update: access.GetIsAdmin,
},
```

This is required for worker `PATCH /api/communications/:id`.

## Local runtime fixes applied while running Lab 2

These were needed so the required Lab 2 flow works correctly in this setup.

### Communications hook guard
Local file:
- `%USERPROFILE%\IdeaProjects\mzinga-apps\src\collections\Communications.ts`

Snippet used:
```ts
hooks: {
  afterChange: [
    async ({ doc, operation }) => {
      if (process.env.COMMUNICATIONS_EXTERNAL_WORKER === "true") {
        const communicationId = doc?.id || doc?._id;
        // set pending only on create, do not reset worker updates
        if (operation === "create" && communicationId && doc.status !== "pending") {
          await payload.update({
            collection: Slugs.Communications,
            id: communicationId,
            data: { status: "pending" },
          });
        }
        return doc;
      }
      // fallback path unchanged
    },
  ],
},
```

### WebHooks merge behavior
Local file:
- `%USERPROFILE%\IdeaProjects\mzinga-apps\src\hooks\WebHooks.ts`

Snippet used:
```ts
// keep original hooks and append webhook hooks
originalHooks[hookType] = [].concat(originalHooks[hookType] || [], hooks);
```

Without this, the RabbitMQ webhook could replace the existing `afterChange` logic.

## Step A2 - REST API shape checks

Commands used:
```powershell
$base = "http://localhost:3000"
$loginBody = @{
  email = "admin.lab1@example.com"
  password = "Lab1Admin!2026"
} | ConvertTo-Json

$login = Invoke-RestMethod -Method Post -Uri "$base/api/users/login" -ContentType "application/json" -Body $loginBody
$token = $login.token
$headers = @{ Authorization = "Bearer $token" }

Invoke-RestMethod -Method Get -Uri "$base/api/communications?where[status][equals]=pending&depth=1" -Headers $headers
Invoke-RestMethod -Method Get -Uri "$base/api/communications/<id>?depth=1" -Headers $headers
Invoke-RestMethod -Method Patch -Uri "$base/api/communications/<id>" -Headers $headers -ContentType "application/json" -Body (@{ status = "sent" } | ConvertTo-Json)
```

## Step A3 - REST worker (implemented)

Folder:
- `lab2/lab2-worker-rest/`

Run:
```powershell
cd "%USERPROFILE%\IdeaProjects\AY-25-26-labs\lab2\lab2-worker-rest"
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python worker.py
```

## Step B1-B2-B3 (WebHooks + RabbitMQ setup and inspection)

MZinga `.env` values used:
```env
COMMUNICATIONS_EXTERNAL_WORKER=true
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
HOOKSURL_COMMUNICATIONS_AFTERCHANGE=rabbitmq
```

RabbitMQ UI:
- `http://localhost:15672`
- user: `guest`
- pass: `guest`

Subscriber check command:
```powershell
cd "%USERPROFILE%\IdeaProjects\mzinga-apps\examples\servicebus-subscriber"
npm install
$env:RABBITMQ_URL="amqp://guest:guest@localhost:5672/"
$env:ROUTING_KEY="HOOKSURL_COMMUNICATIONS_AFTERCHANGE"
npm start
```

## Step B4 - Event worker (implemented)

Folder:
- `lab2/lab2-worker-events/`

Run:
```powershell
cd "%USERPROFILE%\IdeaProjects\AY-25-26-labs\lab2\lab2-worker-events"
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python worker.py
```

Implemented behavior:
- durable exchange/queue
- routing key: `HOOKSURL_COMMUNICATIONS_AFTERCHANGE`
- `prefetch_count=1`
- skip `operation=update` to avoid loops
- REST `depth=1` fetch
- status write-back: `processing` -> `sent` / `failed`
- JWT re-login on 401

## Step A4 + B5 verification result (clean rerun)

Summary file:
- `lab2/logs/verification-summary.log`

Result lines:
- state2 communication processed to `sent`
- state3 communication processed to `sent`
- durability check passed (`pending` while worker down -> `sent` after restart)
- queue returned to zero after processing

## Screenshots (fresh run)

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

## Logs captured

Folder:
- `lab2/logs/`

Main files used in this rerun:
- `mzinga-dev.log`
- `state2-rest.out.log`
- `state3-event.out.log`
- `state3-durability-recovery.out.log`
- `state3-process-pending.out.log`
- `verification-summary.log`

## Stop services

```powershell
docker compose -f "%USERPROFILE%\IdeaProjects\AY-25-26-labs\docs\docker-compose-simplified.yml" --env-file "%USERPROFILE%\IdeaProjects\mzinga-apps\.env" -p mzinga-lab2 down
docker rm -f lab2-mailhog
```

## Lab 2 artifacts in this repo
- `lab2/README.md`
- `lab2/lab2-worker-rest/*`
- `lab2/lab2-worker-events/*`
- `lab2/screenshots/*`
- `lab2/logs/*`
