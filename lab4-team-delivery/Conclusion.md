## Overview

- The four laboratories in this course follow a single thread: an architectural problem in a real production system, resolved through a sequence of decisions that each introduce new capability and new constraint. Our problem was, `MZinga's` synchronous in-process email sending blocks HTTP requests when the recipient list is large. Our solution evolved from a feature flag to an external polling worker, then an API-bound worker, then event-driven worker with observability options and finally ending with deployment methods to test how real-life deployments happen.

## Part 1 - Deploying the First Worker (Lab 1)

In our first lab, we have deployed our first work, version 1 of the worker with docker and Mzinga. We simply created infrastructures, `docker`, `MongoDB`, `RabbitMQ`,  `mailhog` and `MZinga`. After installing the background processes, we setup our MZinga with it's `Communications.ts` settings. From there we then set our `worker.py` with its `.env` file that connects to `MongoDB`, then get documents in the collection `Communications` that currently has `status:pending`, after that we serialise body to HTML, and finally sending the email with Python's built-in `smtplib`. After these steps, we can observe that the document's status changes to `sent`.

## Part 2 - REST API Worker and Event-Driven Worker (Lab 2)

In this Lab, we have replaced the worker's direct MongoDB dependency with the `MZinga` `REST API`. Since changes to `MZinga` could inadvertently break the worker, we have implemented `REST API` to the worker. The worker polls pending Communications through `MZinga's` HTTP contract, sends the email through SMTP, and writes status transitions back. After finishing REST API, we have built an event-driven worker that does REST login and JWT with SMTP logs to PATCH status write-backs.

## Part 3 - Observability and Logging  (Lab 3)

In this lab, we have used `OpenTelemetr`y and `Jaeger` with our worker to make our work more observable and ready-to-read logs of the `worker.py/MZinga` changes. Before we worked on `Jaeger`, `MZinga` is already exposing more baseline data and logs with prometheus metrics. After seeing Prometheus logs, We simply started a `Jaeger` instance in docker to see traces of the work done in `MZinga`, then added its credentials to our `.env` file and made changes on `worker.py` to add structured logging. After making changes on `MZinga`, we can observe live changes that happened in `MZinga` directly within out worker. After observing the values, we have used prometheus with `Jaeger` to observe real-time information about events occurring within the system.

## Part 4 - Deployment Models with Kubernetes (Lab 4)

In this lab, we have tested with container images and Deployment methods. We first deployed our first service, V1. After that we used `Rolling Method` to simply roll into the next version available. After this, we have tested other method, `Recreate Strategy`. This method ensures that only one version remains active while the other remains inactive, making it simple to configure between versions, but while changing downtimes always happens. Then we have `blue-green` method, which simply 2 versions running at the same time without interrupting each other. It does double the resources but changeing betwween versions are almost instant. And finally we tested `canary method`. In this method we can control which versions can be seen by users, allowing new versions to be tested under real production traffic. But it is a complex to manage since we have two development environments at hand.

## Part 5 — The Full Deployment Timeline

| Deployment event | Deployment Strategy Used | Reason That happened|
|---|---|---|
| mzinga-apps `Ver1`, updated to `Ver2` that added feature to flag | Blue-Green Method used | Verifying new `Communications.ts` in isolation before switching any traffic. |
| Enabling `COMMUNICATIONS_USE_EXTERNAL_WORKER` flag | Feature Change | Application-level change, not a deployment change.|
| Lab 1 worker (first deploy) | Any Method can be used as Deployment.| This is a New service, means there are no previous versions, so nothing to conflict.|
| Lab 1 worker `Ver1` → Lab 2 worker `Ver2` | Recreate Method used. | `Ver1` (Database) and `Ver2` (API) cannot claim documents; so concurrent operation produces duplicate emails. |
| Lab 2 worker `ver2` → Lab 3 worker `Ver3` | Rolling Update, Simple New Deployment | `Ver3` deployed but in passive state. Ther are no conflicts with `Ver2` which is still polling. |
| Lab 2 worker `Ver2` decommission | Scale to 0; Canary Release Method | Draining active documents slowly before activating RabbitMQ publishing. |
| mzinga-apps config change (`HOOKSURL_COMMUNICATIONS_AFTERCHANGE=rabbitmq`) | Rolling Update Deployment. | It has backwards-compatible additions. Pods with new configs published to RabbitMQ. |
| Lab 3 worker scale-out | kubectl scale | RabbitMQ delivery semantics provide coordination, so there is no application-level change required. |


## Part 6 - Final Summary

Throughout the four laboratories, we transformed MZinga's communications workflow from a tightly coupled synchronous process into a scalable, observable, and deployable distributed system. 

The original problem was that email delivery occurred directly within the application's request path. As the number of recipients increased, HTTP requests became slower and less reliable. To address this issue, we progressively separated responsibilities from the main application into dedicated worker services.

In Lab 1, we introduced the first external worker that processed pending communications independently of the application. This removed email delivery from the user request path and established the foundation for asynchronous processing.

In Lab 2, we improved the architecture by replacing direct database access with REST API communication and later introducing an event-driven design using RabbitMQ. These changes reduced coupling between components, established clearer service boundaries, and enabled more scalable message processing.

In Lab 3, we added observability through OpenTelemetry, Jaeger, Prometheus, and structured logging. These additions made it possible to trace requests across services, monitor system behaviour, and diagnose problems more effectively in a distributed environment.

Finally, in Lab 4, we explored deployment strategies in Kubernetes. Rolling updates, recreate deployments, blue-green deployments, and canary releases demonstrated different approaches to balancing availability, risk, resource consumption, and operational complexity during software delivery.

Conversely, the adoption of RabbitMQ in Lab 3 was not merely a decoupling improvement. It enabled a deployment capability: multiple worker replicas could be deployed and scaled without application-level coordination because message ownership was handled by the queue itself. This demonstrates that architectural choices directly influence operational flexibility. The deployment patterns explored in Lab 4 are therefore not interchangeable techniques but responses to specific constraints. Rolling updates require compatibility between versions, recreate deployments are necessary when coexistence is unsafe, blue-green deployments trade resources for reduced risk, and canary releases depend on observability to validate gradual rollouts. Understanding these constraints is more important than memorising the deployment patterns themselves.

Overall, the laboratories illustrate how a production system evolves beyond simply adding features. Every architectural decision introduces both capabilities and constraints. By the end of the course, MZinga had evolved from a monolithic synchronous workflow into a distributed, observable, and operationally mature platform that better reflects the realities of modern software systems.
