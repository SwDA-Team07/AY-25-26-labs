# Lab 2: Mzinga Evolution - Step B2 (Event-Driven Setup)

## 1. Step B2: Event-Driven Infrastructure Configuration

### 1.1 Goal
The objective of this step was to transition MZinga from a passive system to an event-driven architecture. By connecting MZinga to RabbitMQ, we enable the system to automatically publish messages to a message bus whenever a Communication record is created or updated. This eliminates the need for future workers to poll the database, reducing latency and resource consumption.

### 1.2 Configuration Changes
I configured the MZinga environment to activate the RabbitMQ webhook infrastructure. No TypeScript code changes were required as the system uses the existing `WebHooks.ts` logic triggered by environment variables.

**File:** `mzinga-apps/.env`
- **RABBITMQ_URL**: Set to `amqp://guest:guest@localhost:5672` to establish the connection with the message bus.
- **HOOKSURL_COMMUNICATIONS_AFTERCHANGE**: Set to `rabbitmq` to instruct the WebHooks system to attach a publisher hook to the Communications collection.

---

## 2. Verification Procedure

The implementation was verified by monitoring the message bus behavior during document lifecycle events.

### 2.1 Infrastructure Check
Upon restarting the MZinga application, I verified the following in the RabbitMQ Management UI (`http://localhost:15672`):
- **Exchanges Created**: The exchanges `mzinga_events` and `mzinga_events_durable` were correctly declared by the monolith.
- **Service Connection**: The MZinga terminal confirmed a successful connection to the RabbitMQ broker.

### 2.2 Event Publication Test
To verify the "Trigger" mechanism, I performed a manual test:
1. Navigated to the **Communications** collection in the MZinga Admin UI.
2. Created and saved a new Communication document.
3. Monitored the **mzinga_events_durable** exchange in the RabbitMQ dashboard.

**Outcome:**
The RabbitMQ Management UI showed an immediate spike in the **Message rate (Publish)** graph. This confirms that the `afterChange` hook successfully captured the event and routed the document payload to the message bus.

### 2.3 Conclusion
The infrastructure is now ready for State 3. MZinga is successfully acting as a **Producer**, and any future event-driven worker (Subscriber) will be able to process these communications in real-time without polling.