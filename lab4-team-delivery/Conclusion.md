> Content to be added later.

## Overview

- The four laboratories in this course follow a single thread: an architectural problem in a real production system, resolved through a sequence of decisions that each introduce new capability and new constraint. Our problem was, `MZinga's` synchronous in-process email sending blocks HTTP requests when the recipient list is large. Our resolution is simple, from a feature, to external polling worker, then an API-bound worker, then event-driven worker with observability options and finally ending with deployment methods to test how real-life deployments happen.

## Part 1 - Deploying the First Worker (Lab 1)

In our first lab, we have deployed our first work, version 1 of the worker with docker and Mzinga. We simply created infrastructures, `docker`, `RabbitMQ`,  `mailhog` and `MZinga`. With saw what the background processes are started and their settings are set within their files. We also write a `worker.py` file to change values within MZinga communication. 

## Part 2 - REST API Worker and Event-Driven Worker (Lab 2)

## Part 3 - Observability and Logging  (Lab 3)

## Part 4 - Deployment Models with Kubernetes (Lab 4)

## Part 5 - Deployment Methods Used During Labs

### 1. The v1-to-v2 Worker Transition: Why Recreate Is the Only Safe Option

### 2. Deploying the Monolith Change: Blue-Green and the Feature Toggle as a Two-Level Canary


## Part 6 — The Full Deployment Timeline

## Part 7 - Closing Reflection



