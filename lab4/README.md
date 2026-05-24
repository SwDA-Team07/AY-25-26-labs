# Lab 4 Delivery - s324924

This delivery follows:
- `docs/09-lab4-step-by-step.md`
- `docs/09-lab4-code-snippets.md`

## Implemented scope

- Step 1: build images and prepare namespace
- Step 2/3: rolling deployment, upgrade, rollback
- Step 4: recreate deployment, upgrade, rollback
- Step 5: blue-green deployment, switch, rollback
- Step 6: canary deployment and progressive scaling
- Step 7: all required deployment strategies covered

## Implementation files

- `lab4/lab4-k8s/app.py`
- `lab4/lab4-k8s/Dockerfile`
- `lab4/lab4-k8s/.dockerignore`
- `lab4/lab4-k8s/k8s/namespace.yaml`
- `lab4/lab4-k8s/k8s/rolling/service.yaml`
- `lab4/lab4-k8s/k8s/rolling/deployment-v1.yaml`
- `lab4/lab4-k8s/k8s/rolling/deployment-v2.yaml`
- `lab4/lab4-k8s/k8s/recreate/service.yaml`
- `lab4/lab4-k8s/k8s/recreate/deployment-v1.yaml`
- `lab4/lab4-k8s/k8s/recreate/deployment-v2.yaml`
- `lab4/lab4-k8s/k8s/blue-green/service.yaml`
- `lab4/lab4-k8s/k8s/blue-green/blue-deployment.yaml`
- `lab4/lab4-k8s/k8s/blue-green/green-deployment.yaml`
- `lab4/lab4-k8s/k8s/canary/service.yaml`
- `lab4/lab4-k8s/k8s/canary/stable-deployment.yaml`
- `lab4/lab4-k8s/k8s/canary/canary-deployment.yaml`

## Runtime verification

Execution evidence is in:
- `lab4/lab4-k8s/logs/runtime-verification-summary.log`

Verified in runtime:
- rolling: `1.0.0 -> 2.0.0 -> 1.0.0`
- recreate: `1.0.0 -> 2.0.0 -> 1.0.0`
- blue-green: `blue -> green -> blue`
- canary progression: `9/1 -> 7/3 -> 5/5 -> 0/10 -> 10/0`

## Cleanup state

After verification, Lab4 namespace resources were removed (`kubectl delete namespace mzinga-lab4`).
