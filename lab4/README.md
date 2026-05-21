# Lab 4 Report - Kubernetes Baseline

This report documents Filippo's Lab 4 activity on branch `labs/s348651`.
The work covers the setup and baseline Kubernetes deployment required before
the later deployment strategies: rolling update, recreate, blue-green, and
canary.

## Objective

The goal of this part is to prepare a local Kubernetes environment with
Minikube and deploy a minimal containerised HTTP service. The service reports
its version, color, and Pod hostname, which makes later deployment strategies
observable with simple `curl` requests.

This baseline establishes:

- the local Kubernetes prerequisites;
- the demo service used by the lab;
- the two Docker image variants required by the exercises;
- the initial v1 Kubernetes Deployment and Service.

## Scope

Covered steps from `docs/09-lab4-step-by-step.md`:

- Prerequisites
- The Demo Service
- Step 1 - Build the Container Images
- Step 2 - Deploy the Initial Service (v1)

The upgrade strategies from Step 3 onward are left for the following Lab 4
activities.

## Implemented Files

- `lab4/lab4-k8s/app.py`
- `lab4/lab4-k8s/Dockerfile`
- `lab4/lab4-k8s/.dockerignore`
- `lab4/lab4-k8s/k8s/namespace.yaml`
- `lab4/lab4-k8s/k8s/rolling/service.yaml`
- `lab4/lab4-k8s/k8s/rolling/deployment-v1.yaml`

## Prerequisites

The local environment was prepared with Docker, kubectl, and Minikube. Minikube
was installed through Homebrew and started with the Docker driver.

Verification:

```sh
$ minikube version
minikube version: v1.38.1
commit: c93a4cb9311efc66b90d33ea03f75f2c4120e9b0

$ docker --version
Docker version 29.4.1, build 055a478

$ kubectl version --client
Client Version: v1.34.1
Kustomize Version: v5.7.1

$ kubectl get nodes
NAME       STATUS   ROLES           AGE     VERSION
minikube   Ready    control-plane   7m34s   v1.35.1
```

## Demo Service

The demo service is a small Python HTTP server implemented with the standard
library only. It exposes two endpoints:

- `GET /` returns the application version, color, hostname, and a short message.
- `GET /health` returns `{"status": "ok"}` and is used by Kubernetes probes.

The version and color values are read from environment variables:

- `APP_VERSION`
- `APP_COLOR`

The hostname comes from `socket.gethostname()`. Inside Kubernetes this maps to
the Pod hostname, so responses show which Pod handled each request.

## Step 1 - Build the Container Images

The Dockerfile uses `python:3.12-slim`, copies `app.py`, exposes port `8080`,
and maps build arguments into runtime environment variables.

Run from `lab4/lab4-k8s`:

```sh
docker build --build-arg APP_VERSION=1.0.0 --build-arg APP_COLOR=blue -t mzinga-webapp:1.0.0 .
docker build --build-arg APP_VERSION=2.0.0 --build-arg APP_COLOR=green -t mzinga-webapp:2.0.0 .
```

The two images simulate the before/after versions used in the deployment
strategy exercises:

- `mzinga-webapp:1.0.0` reports `version: "1.0.0"` and `color: "blue"`.
- `mzinga-webapp:2.0.0` reports `version: "2.0.0"` and `color: "green"`.

The images were loaded into Minikube because the manifests use
`imagePullPolicy: Never` and the images are not published to a remote registry.

```sh
minikube image load mzinga-webapp:1.0.0
minikube image load mzinga-webapp:2.0.0
```

## Step 2 - Deploy the Initial Service

A dedicated namespace was created for the lab:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: mzinga-lab4
```

The initial Kubernetes baseline contains:

- one `Service` named `webapp`;
- one `Deployment` named `webapp`;
- three v1 replicas;
- readiness and liveness probes on `/health`;
- `imagePullPolicy: Never`;
- a rolling update strategy with `maxUnavailable: 1` and `maxSurge: 1`.

Apply commands:

```sh
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/rolling/service.yaml
kubectl apply -f k8s/rolling/deployment-v1.yaml
kubectl rollout status deployment/webapp -n mzinga-lab4
```

The Service exposes port `80` inside the cluster and forwards traffic to port
`8080` on the Pods. Local access is done with `kubectl port-forward`.

## Verification Evidence

The command output is also stored in:

- `lab4/lab4-k8s/logs/baseline-verification.log`

Kubernetes resources after deploying the baseline:

```sh
$ kubectl get pods -n mzinga-lab4
NAME                      READY   STATUS    RESTARTS   AGE
webapp-5f4f778774-hc6d4   1/1     Running   0          7m11s
webapp-5f4f778774-wsz2c   1/1     Running   0          7m11s
webapp-5f4f778774-zth26   1/1     Running   0          7m11s

$ kubectl get svc -n mzinga-lab4
NAME     TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE
webapp   ClusterIP   10.106.69.178   <none>        80/TCP    7m20s
```

Service response through port-forward:

```sh
$ kubectl port-forward service/webapp 8080:80 -n mzinga-lab4
Forwarding from 127.0.0.1:8080 -> 8080
Forwarding from [::1]:8080 -> 8080

$ curl -s http://localhost:8080/
{"version": "1.0.0", "color": "blue", "hostname": "webapp-5f4f778774-hc6d4", "message": "Hello from version 1.0.0"}

$ curl -s http://localhost:8080/health
{"status": "ok"}
```

## Evidence Interpretation

The `kubectl get nodes` output confirms that the local Minikube cluster is
running and ready. The Pod list confirms that the initial Deployment created
three healthy replicas of the v1 service. The Service output confirms that
`webapp` is exposed as a `ClusterIP` service on port `80`.

The `curl /` response proves that traffic reaches a Kubernetes Pod through the
Service and that the application is running the expected baseline version:
`1.0.0` / `blue`. The `curl /health` response proves that the health endpoint
used by the readiness and liveness probes is available and returns a successful
JSON response.
