# Lab 4 Report - Baseline, Rolling, Recreate, Blue-Green

Team Lab 4 delivery notes.

## Goal

Prepare a local Kubernetes environment with Minikube and deploy a small
containerised HTTP service. The service returns its version, color, and Pod
hostname, so each deployment strategy can be checked with `curl`.

The baseline includes:

- the local Kubernetes prerequisites;
- the demo service used by the lab;
- the two Docker image variants required by the exercises;
- the initial v1 Kubernetes Deployment and Service.

## Covered Work

Covered:

- Prerequisites
- The Demo Service
- Step 1 - Build the Container Images
- Step 2 - Deploy the Initial Service (v1)
- Step 3 - In-Place Rolling Upgrade
- Step 4 - Recreate (Replace) Strategy
- Step 5 - Blue-Green Deployment
- Step 6 - Canary Release
- Step 7 - Pros and Cons, Comparison and Decision Framework

## Files

- `lab4-team-delivery/lab4-k8s/app.py`
- `lab4-team-delivery/lab4-k8s/Dockerfile`
- `lab4-team-delivery/lab4-k8s/.dockerignore`
- `lab4-team-delivery/lab4-k8s/k8s/namespace.yaml`
- `lab4-team-delivery/lab4-k8s/k8s/rolling/service.yaml`
- `lab4-team-delivery/lab4-k8s/k8s/rolling/deployment-v1.yaml`
- `lab4-team-delivery/lab4-k8s/k8s/rolling/deployment-v2.yaml`
- `lab4-team-delivery/lab4-k8s/k8s/recreate/service.yaml`
- `lab4-team-delivery/lab4-k8s/k8s/recreate/deployment-v1.yaml`
- `lab4-team-delivery/lab4-k8s/k8s/recreate/deployment-v2.yaml`
- `lab4-team-delivery/lab4-k8s/k8s/blue-green/service.yaml`
- `lab4-team-delivery/lab4-k8s/k8s/blue-green/blue-deployment.yaml`
- `lab4-team-delivery/lab4-k8s/k8s/blue-green/green-deployment.yaml`

## Prerequisites

The local environment was prepared with Docker, kubectl, and Minikube. Minikube
was installed through Homebrew and started with the Docker driver.

Verification:

```sh
$ minikube version
minikube version: v1.38.1

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

Run from `lab4-team-delivery/lab4-k8s`:

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

## Step 3 - In-Place Rolling Upgrade

Step 3 is already present on `main` and uses:

- `lab4-team-delivery/lab4-k8s/k8s/rolling/deployment-v2.yaml`

The deployment keeps the same name (`webapp`) and updates image/env values to
`mzinga-webapp:2.0.0`, `APP_VERSION=2.0.0`, `APP_COLOR=green`.

## Step 4 - Recreate Strategy (Sefa)

Step 4 is implemented in:

- `lab4-team-delivery/lab4-k8s/k8s/recreate/service.yaml`
- `lab4-team-delivery/lab4-k8s/k8s/recreate/deployment-v1.yaml`
- `lab4-team-delivery/lab4-k8s/k8s/recreate/deployment-v2.yaml`

The recreate deployments use:

- same deployment name: `webapp`
- `strategy.type: Recreate`
- v1 image/env in `deployment-v1.yaml`
- v2 image/env in `deployment-v2.yaml`

Apply flow:

```sh
kubectl apply -f k8s/recreate/service.yaml
kubectl apply -f k8s/recreate/deployment-v1.yaml
kubectl rollout status deployment/webapp -n mzinga-lab4

kubectl apply -f k8s/recreate/deployment-v2.yaml
kubectl rollout status deployment/webapp -n mzinga-lab4

kubectl rollout undo deployment/webapp -n mzinga-lab4
kubectl rollout status deployment/webapp -n mzinga-lab4
```

## Step 5 - Blue-Green Deployment

Step 5 is implemented in:

- `lab4-team-delivery/lab4-k8s/k8s/blue-green/service.yaml`
- `lab4-team-delivery/lab4-k8s/k8s/blue-green/blue-deployment.yaml`
- `lab4-team-delivery/lab4-k8s/k8s/blue-green/green-deployment.yaml`

Blue-green keeps two complete environments available at the same time:

- `webapp-blue` runs `mzinga-webapp:1.0.0` with `APP_COLOR=blue`.
- `webapp-green` runs `mzinga-webapp:2.0.0` with `APP_COLOR=green`.
- the `webapp` Service starts with selector `app: webapp, slot: blue`.

Traffic is switched by patching only the Service selector. Cutover and rollback
are atomic because both Deployments are already running before traffic is moved.

Apply flow:

```sh
kubectl apply -f k8s/blue-green/blue-deployment.yaml
kubectl apply -f k8s/blue-green/green-deployment.yaml
kubectl apply -f k8s/blue-green/service.yaml
kubectl rollout status deployment/webapp-blue -n mzinga-lab4
kubectl rollout status deployment/webapp-green -n mzinga-lab4

kubectl patch service webapp -n mzinga-lab4 \
  -p '{"spec":{"selector":{"app":"webapp","slot":"green"}}}'

kubectl patch service webapp -n mzinga-lab4 \
  -p '{"spec":{"selector":{"app":"webapp","slot":"blue"}}}'
```

## Verification

The command output is also stored in:

- `lab4-team-delivery/lab4-k8s/logs/baseline-verification.log`

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

## Notes

The `kubectl get nodes` output shows the local Minikube cluster running and
ready. The Pod list shows three healthy v1 replicas. The Service output shows
`webapp` exposed as a `ClusterIP` service on port `80`.

The `curl /` response shows traffic reaching a Kubernetes Pod through the
Service and returning the expected baseline version: `1.0.0` / `blue`. The
`curl /health` response shows the probe endpoint returning a successful JSON
response.

## Step 6 - Canary Release

### 6.1 - What Is It

A **canary release** (named after the "canary in a coal mine" — an early warning system) routes a controlled fraction of production traffic to the new version while the majority still runs on the stable version. This allows you to observe the new version's behaviour on real traffic — error rates, latency, business metrics — before committing to a full rollout.

### 6.2 — Create the Canary Manifests

Create a directory `k8s/canary/` and three YAML files named:
**`stable-deployment.yaml`**, **`canary-deployment.yaml`**, **`service.yaml`**

#### The recreate deployments use:
- Same deployment name used as: `webapp`
- Strategy type used: Canary Method
- `deployment-v1.yaml` similar to `stable-deployment.yaml`
- `deployment-v2.yaml` similar to `canary-deployment.yaml`

### 6.3 — Verifying the Traffic Split

- Before the verification we have set the kubectl with our releases:

```sh
kubectl apply -f k8s/canary/service.yaml
kubectl apply -f k8s/canary/stable-deployment.yaml
kubectl apply -f k8s/canary/canary-deployment.yaml
kubectl rollout status deployment/webapp-stable -n mzinga-lab4
kubectl rollout status deployment/webapp-canary -n mzinga-lab4
```

- After setting up, we use the code in below to see how many 1.0.0 and 2.0.0 are in the set:
```sh
for i in $(seq 1 20); do
  curl -s http://localhost:8080/ | python3 -c "import sys,json; print(json.load(sys.stdin)['version'])"
done | sort | uniq -c
```

- Result got in testing was :
```sh
{19 more as "Handling connection for 8080"}
Handling connection for 8080
    18 1.0.0
    2 2.0.0
```

### 6.4 — Gradually Increase the Canary and complete V2 Takeover

- **%70 1.0.0 / %30 2.0.0**
> This test is done with 10 release test, code used below:

```sh
for i in $(seq 1 10); do
  curl -s http://localhost:8080/ | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"{d['version']} {d['hostname']}\")"
done
```

```sh
{9 more as "Handling connection for 8080"}
Handling connection for 8080
    7 1.0.0
    3 2.0.0
```

- **%50 1.0.0 / %50 2.0.0**
> This test is done with 10 release test.

```sh
{9 more as "Handling connection for 8080"}
Handling connection for 8080
    5 1.0.0
    5 2.0.0
```

- **Complete Canary takeover**
> This test is done with 10 release test.

```sh
{9 more as "Handling connection for 8080"}
Handling connection for 8080
    0 1.0.0
    10 2.0.0
```

### 6.5 — Abort: Rollback the Canary

If the canary shows problems, remove it entirely and return to stable with the code below:
```sh
kubectl scale deployment/webapp-canary --replicas=0 -n mzinga-lab4
kubectl scale deployment/webapp-stable --replicas=10 -n mzinga-lab4
```

All traffic returns to v1 immediately.

- With the code below:
```sh
for i in $(seq 1 10); do
  curl -s http://localhost:8080/ | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"{d['version']} {d['hostname']}\")"
done
```

- After Rollback Results:
```sh
{9 more as "Handling connection for 8080"}
Handling connection for 8080
    10 1.0.0
    0 2.0.0
```

## Step 7 — Pros and Cons, Comparison and Decision Framework

### 7.1 - Rolling Update Pros and Cons

#### Pros:
- Zero additional infrastructure cost.
- Built in Kubernetes without external tools, no need to use other tools for logging or look-up.
- Fast and quick rollback with simple code.
- If new version crashes, only some pods are affected.
#### Cons:
- Both versions are live simultaneously during the transition. If there is new database schema, message format, or API contract, it causes inconsistency.
- Traffic split is NOT controlled. New version cannot be directed to internal users.
- Rollback requires re-running a full rolling replacement.

### 7.2 - Recreate Pros and Cons

#### Pros:
- only one version runs at any point guaranteed, This is only useful when v1 and v2 cannot exist in same time.
- Simple to configure. Within a single field.
- No old Pods could interfere with the new version's exclusive resources.
- Minimal extra resource cost, not more than replica count.
#### Cons:
- Downtime always happen, There is always going to be a gap between all old Pods terminating and the first new Pod becoming ready.
- Downtime scales with `terminationGracePeriodSeconds` and application startup time.
- Full on gamble, no way to validate or terst new version before it receives all of the traffic.
- Rollback happens at the same downtime again.
- Users must either be informed of the maintenance window.

### 7.3 - Blue-Green Pros and Cons

#### Pros:
- Zero traffic to the new version until you needed to switch, both are not serving user traffic at the same time nor simultaneously.
- instantaneous rollback happens with just one patch. There are no delays or downtime.
- Safe for breaking changes when v2 can be initialised in parallel with v1.
- New version can be tested before it receives any user traffic.
- No risk of the new version destabilising the old version
#### Cons:
- Since both environments runs at full capacity continueously, It simply doubles resources.
- All-or-nothing, there is no way to direct some percent of traffic to green to validate.
- Cannot be used when the incompatibility prevents starting v2 while v1 is running

### 7.4 - Canary Release Pros and Cons

#### Pros:
- With the Canary Release, we can control what and when the new versions are seen by the users. With that we can control the exposure.
- Before new version release, new version can be tested in the real traffic.
- Within seconds, canary or stable, both can absorb traffic with in seconds, making it fast and reliable.
#### Cons:
- Both of the versions are live together, This can break API and schema.
- You cannot get 1% without a very large number of total replicas, which causes coarse traffic proportion.
- Observability required to be useful without metrics comparing error rates and latency.
- Very complex to manage since we have two developments at hand.


### 7.5 - Strategy Comparison and Decision Framework

| Factor | Rolling Update | Recreate | Blue-Green | Canary |
|--------|---------------|---------|------------|--------|
| **Both versions live simultaneously** | Yes, in transition | **Never** | No | Yes, during transition |
| **Downtime** | Near-zero | **Yes — Always Planned** | Zero | Zero |
| **Rollback mechanism** | `kubectl rollout undo` | `kubectl rollout undo` | Patch Service selector | Scaled with number|
| **Rollback speed** | Minutes | **Minutes + downtime** | Seconds | Seconds |
| **Extra resource cost** | `maxSurge` Pods only | None | 2× full replica count | Proportional to canary size |
| **Traffic control** | None (Kubernetes decides) | None | Binary: all-or-nothing | Granular: by replica ratio |
| **Breaking changes safe?** | No | **With Downtime** | Yes-Zero Downtime | No |
| **v2 must start alongside v1?** | Yes | **No** | Yes | Yes |
| **Requires observability** | No | No | No | Yes |
| **Operational complexity** | Low | **Low** | Medium | Medium-High |
| **Time to full rollout** | Minutes | Minutes | Immediate after switch | Hours to days (progressive) |

- Table is from the file `09-lab4-step-by-step.md`, simplified to be more readable.

### 7.6 How to Choose Which Method?

The methods are all useful to one point, but they can shine at the some specific constrains:

**1. Database or schema changes:**
Most important one. If v2 add a non-nullable column, renames a field, or changes a message format, v1 and v2 cannot run simultaneously or data corruption/errors occur.
- If v2 can be started while v1 is active, `blue-green` mitigates schema while green is passive, then switcheds and closes blue.
- If v2 cannot start with v1 active, `Recreate` terminates v1 first, migrates and starts v2.
- Never use rolling update or canary for any breaking schema change

**2. v2 cannot even begin alongside v1:**
This is a critical constraint that differs Recreate from Blue-Green. If v2 attempts to get an exclusive lock or port at startup, and v1 holds it, v2 will fail to initiate itself. Blue-Green cannot work in this scenario because it requires v2 to warm up fully before traffic is switched. Recreate is the only option.

**3. Observability:**
Canary is only valuable if you can measure if the canary is behaving correctly. Without metrics to compare error rates and latency between stable and canary, there is no safety from the canary approach.

**4. Traffic:**
For a meaningful canary validation, there should be enough traffic passing within the canary to detect anomalies. At 10%, canary on a service handling 100 requests per minute, only 10 requests per minute hit the canary — a statistically weak signal. At 100,000 requests per minute, 10% gives you a strong signal within seconds. If traffic is low, blue-green with thorough pre-switch testing may be more effective.

**5. Team experience:**
Since not all of the team need to know advanced knowlegde on implementation, some methods are easy to manage. As example:
- Rolling update is built into Kubernetes and requires no additional tooling or procedures.
- Recreate adds one field change and a maintenance window procedure.
- Blue-green requires managing two Deployments and a manual switch procedure.
- Canary requires two Deployments, a progressive scaling procedure, and defined promotion criteria.
From top to bottom, with this line-up, can be used from start of the project to end of it. It can be scaleable to be used when needed.

**6. Rollback time:**
If an outage costs a lot per minute or hour, rollback speed becomes very important. For each method:
- **Blue-green** is the fastest, reliable rollback with zero downtime.
- **Canary** rollback is fast and zero-downtime, but requires you to know what was the problem.
- **Rolling update**, minutes, not seconds, but no downtime. Rollback does re-runs the full rolling replacement.
- **Recreate** rollback is a full replace cycle, which takes minutes plus another full downtime window.
