> Content to be added later.

## Overview

- The four laboratories in this course follow a single thread: an architectural problem in a real production system, resolved through a sequence of decisions that each introduce new capability and new constraint. Our problem was, `MZinga's` synchronous in-process email sending blocks HTTP requests when the recipient list is large. Our resolution is simple, from a feature, to external polling worker, then an API-bound worker, then event-driven worker with observability options and finally ending with deployment methods to test how real-life deployments happen.

## Part 1 - Deploying the First Worker (Lab 1)

In our first lab, we have deployed our first work, version 1 of the worker with docker and Mzinga. We simply created infrastructures, `docker`, `RabbitMQ`,  `mailhog` and `MZinga`. With saw what the background processes are started and their settings are set within their files. We also write a `worker.py` file to change values within MZinga communication. 

## Part 2 - REST API Worker and Event-Driven Worker (Lab 2)

In this Lab, we have replaced the worker's direct MongoDB dependency with the MZinga REST API. The worker polls pending Communications through MZinga's HTTP contract, sends the email through SMTP, and writes status transitions back. After finishing REST API, we have built an event-driven worker that does REST login and JWT with SMTP logs to PATCH status write-backs.

## Part 3 - Observability and Logging  (Lab 3)

In this lab, we have used OpenTelemetry and Jaeger with our worker to make our work more observable and ready-to-read logs of the worker/MZinga changes. We simple started a Jaeger instance in docker, then added its credentials to our `.env` file and made changes on `worker.py`. After making changes on MZinga, we can observe live changes that happened in MZinga directly within out worker. After observing the values, we have used prometheus with jaeger to see real-time information happened or happenening with our system.

## Part 4 - Deployment Models with Kubernetes (Lab 4)

In this lab, we have tested with container images and actualy Deployment methods. We first deployed our first service, V1. After that we used `Rolling Method` to simply roll into the next version available. After this, we have tested other method, `Recreate Strategy`. This method only makes one version stays active wile other version stays passive, making it simple to configure between versions, but while changing downtimes always happens. Then we have `blue-green` method, which simply 2 versions running at the same time without interupting each other. It does double the resources but changeing betwween versions are almost instant. And finally we tested `canary method`. In this method we can control which versions can be seen by users, making new version test happen with full traffic environments. But it is a complex to manage since we have two development environments at hand.

## Part 6 — The Full Deployment Timeline

## Part 7 - Closing Reflection



