# Lab 1 Delivery - s324924

This file mirrors the sections of `docs/06-lab1-step-by-step.md` and includes the exact commands I used to execute the laboratory activity.

## Step 1 - Setup

### 1.1 Repos and branch
- Labs repo (delivery): `C:\Users\cekur\IdeaProjects\AY-25-26-labs`
- MZinga repo (runtime/local edits): `C:\Users\cekur\IdeaProjects\mzinga-apps`
- Delivery branch: `labs/s324924`

### 1.2 Prerequisites I used
```powershell
node -v
npm -v
py --version
docker --version
```

### 1.3 MZinga env
File: `C:\Users\cekur\IdeaProjects\mzinga-apps\.env`

Required lines:
```env
MONGO_PORT=27017
MONGODB_URI="mongodb://admin:admin@localhost:27017/mzinga?authSource=admin&directConnection=true"
DEBUG_EMAIL_SEND=1
COMMUNICATIONS_EXTERNAL_WORKER=true
```

### 1.4 Start infrastructure
I used the simplified compose file (fallback from the guide) because of the replica-set security key issue on Windows.

```powershell
docker compose -f "C:\Users\cekur\IdeaProjects\AY-25-26-labs\docs\docker-compose-simplified.yml" --env-file "C:\Users\cekur\IdeaProjects\mzinga-apps\.env" -p mzinga-lab1 up -d database messagebus cache
```

### 1.5 Start MailHog
```powershell
docker run -d --name lab1-mailhog -p 1025:1025 -p 8025:8025 mailhog/mailhog
```

### 1.6 Start MZinga
```powershell
cd "C:\Users\cekur\IdeaProjects\mzinga-apps"
npm run dev
```

Admin UI:
- `http://localhost:3000/admin`
- username/email: `admin.lab1@example.com`
- password: `Lab1Admin!2026`

RabbitMQ UI:
- `http://localhost:15672`
- username: `guest`
- password: `guest`

MailHog UI:
- `http://localhost:8025`

## Step 2 - Understand Current Email Flow

I inspected:
- `src/collections/Communications.ts` (`afterChange` hook)
- `src/utils/MailUtils.ts` (`DEBUG_EMAIL_SEND`)

I inspected MongoDB documents with:
```powershell
& "C:\Users\cekur\AppData\Local\Programs\mongosh\mongosh.exe" "mongodb://admin:admin@localhost:27017/mzinga?authSource=admin&directConnection=true"
```

Then:
```javascript
use mzinga
db.communications.findOne()
db.users.findOne({}, { email: 1 })
```

Observed sample shape from my run:

`users` sample:
```json
{
  "_id": "69e3ea2cd3f4a45a24ff1e12",
  "firstName": "Recipient",
  "lastName": "User",
  "roles": ["public"],
  "email": "recipient.lab1@example.com"
}
```

`communications` sample:
```json
{
  "_id": "69e4bd76e514ca03653682d1",
  "subject": "lab1 delivery test failed b 2026-04-19",
  "tos": [{ "value": "69e3ea2cd3f4a45a24ff1e12", "relationTo": "users" }],
  "ccs": [],
  "bccs": [],
  "body": [{ "type": "paragraph", "children": [{ "text": "lab1 delivery test failed path b" }] }],
  "status": "failed"
}
```

## Step 3 - Add `status` Field

Local file changed in MZinga repo:
- `C:\Users\cekur\IdeaProjects\mzinga-apps\src\collections\Communications.ts`

Implemented:
- `status` select field with:
  - `pending`
  - `processing`
  - `sent`
  - `failed`
- read-only in admin
- sidebar placement
- added to `admin.defaultColumns`

Snippet added:
```ts
admin: {
  ...collectionUtils.GeneratePreviewConfig(),
  useAsTitle: "subject",
  defaultColumns: ["subject", "status", "tos"],
  group: "Notifications",
  disableDuplicate: true,
  enableRichTextRelationship: false,
},
fields: [
  // status field used by mzinga + external worker
  {
    name: "status",
    type: "select",
    options: [
      { label: "Pending", value: "pending" },
      { label: "Processing", value: "processing" },
      { label: "Sent", value: "sent" },
      { label: "Failed", value: "failed" },
    ],
    admin: {
      readOnly: true,
      position: "sidebar",
    },
  },
]
```

## Step 4 - Feature Flag for External Worker

In `.env`:
```env
COMMUNICATIONS_EXTERNAL_WORKER=true
```

Behavior implemented in `afterChange`:
- if flag is not `"true"`: old in-process email logic runs
- if flag is `"true"`: set `status: "pending"` and return immediately

Snippet added:
```ts
hooks: {
  afterChange: [
    async ({ doc }) => {
      // external worker path
      if (process.env.COMMUNICATIONS_EXTERNAL_WORKER === "true") {
        // set pending and return without smtp work in mzinga
        if (doc.status !== "pending") {
          await payload.update({
            collection: Slugs.Communications,
            id: doc.id,
            data: { status: "pending" },
          });
        }
        return doc;
      }

      // fallback path: old in-process email logic
      const { tos, ccs, bccs, subject, body } = doc;
      // ...existing logic unchanged
    },
  ],
},
```

## Step 5 - Build Python Worker

Worker folder (delivery artifact):
- `C:\Users\cekur\IdeaProjects\AY-25-26-labs\lab1\lab1-worker`

Files:
- `worker.py`
- `requirements.txt`
- `.env`

Install and run:
```powershell
cd "C:\Users\cekur\IdeaProjects\AY-25-26-labs\lab1\lab1-worker"
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe worker.py
```

What worker does:
- polls `communications` with `status: pending`
- claims doc as `processing`
- resolves `tos/ccs/bccs` from `users`
- serializes Slate rich text to HTML
- sends email via SMTP (`localhost:1025` -> MailHog)
- updates status to `sent` or `failed`

Main loop snippet:
```python
while True:
    # poll one pending document and claim it
    claimed_doc = communication_collection.find_one_and_update(
        {"status": "pending"},
        {"$set": {"status": "processing"}},
        sort=[("createdAt", 1)],
        return_document=ReturnDocument.AFTER,
    )

    if claimed_doc is None:
        time.sleep(poll_interval)
        continue

    # resolve users + serialize html + send smtp
    process_communication(
        claimed_doc,
        communication_collection,
        users_collection,
        config,
    )
```

## Step 6 - End-to-End Verification

### 6.1 External worker mode (`COMMUNICATIONS_EXTERNAL_WORKER=true`)
Manual flow:
1. Login in MZinga admin.
2. Create one recipient in `Admin -> Users`.
3. Create one communication in `Notifications -> Communications`.
4. Save.

Expected:
- quick save (no blocking send in MZinga)
- status `pending` then `sent`
- mail visible in MailHog inbox
- worker log shows `claimed` and `sent`

Worker logs:
```powershell
Get-Content -Tail 100 "C:\Users\cekur\IdeaProjects\AY-25-26-labs\lab1\lab1-worker\worker.log"
Get-Content -Tail 100 "C:\Users\cekur\IdeaProjects\AY-25-26-labs\lab1\lab1-worker\worker.err.log"
```

### 6.2 Rollback check (`COMMUNICATIONS_EXTERNAL_WORKER=false`)
1. Set in `mzinga-apps\.env`:
```env
COMMUNICATIONS_EXTERNAL_WORKER=false
```
2. Restart MZinga (`npm run dev`).
3. Create a communication.

Expected:
- old in-process path is active
- `MailUtils:message` and `MailUtils:result` appear in MZinga logs

### 6.3 Failure and recovery
Stop SMTP sink:
```powershell
docker rm -f lab1-mailhog
```

Create a communication while worker is running.

Expected:
- status becomes `failed`

Start MailHog again:
```powershell
docker run -d --name lab1-mailhog -p 1025:1025 -p 8025:8025 mailhog/mailhog
```

Reset failed document to pending:
```powershell
& "C:\Users\cekur\AppData\Local\Programs\mongosh\mongosh.exe" "mongodb://admin:admin@localhost:27017/mzinga?authSource=admin&directConnection=true"
```

Then:
```javascript
use mzinga
db.communications.updateOne(
  { _id: ObjectId("PUT_COMMUNICATION_ID_HERE") },
  { $set: { status: "pending" } }
)
```

Expected:
- worker picks it up and final status is `sent`

## Stop Everything

Stop MZinga/worker from their terminals (`Ctrl+C`), then:
```powershell
docker compose -f "C:\Users\cekur\IdeaProjects\AY-25-26-labs\docs\docker-compose-simplified.yml" --env-file "C:\Users\cekur\IdeaProjects\mzinga-apps\.env" -p mzinga-lab1 down
docker rm -f lab1-mailhog
```

## Delivery Artifacts in This Repo
- `lab1/lab1-worker/worker.py`
- `lab1/lab1-worker/requirements.txt`
- `lab1/lab1-worker/.env`
- `lab1/README.md`

## Screenshots
Screenshots are under:
- `C:\Users\cekur\IdeaProjects\AY-25-26-labs\lab1\screenshots`

Files:
- `01_mzinga_login.png` (mzinga admin login page)
- `02_mzinga_users.png` (users list with admin + recipients)
- `03_mzinga_comm_pending.png` (communication detail with `status = pending`)
- `04_mzinga_comm_sent.png` (communication detail with `status = sent`)
- `05_mzinga_comm_failed.png` (communication detail with `status = failed` while smtp sink is down)
- `06_mzinga_comm_recovery_sent.png` (communication after manual reset to `pending`, final `status = sent`)
- `07_rabbitmq_queues.png` (rabbitmq queues tab with queue counters)
- `08_mailhog_after_recovery.png` (mailhog inbox where subjects explicitly include status names: pending, failed, sent)
- `09_mzinga_comm_list_mixed_states.png` (communications list showing mixed statuses in one view: pending, failed, sent)
