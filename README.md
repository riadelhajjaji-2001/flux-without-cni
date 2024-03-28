# Flux version 2 without CNI

This repository is created to share an idea to deploy FluxCD without CNI without sacrificing HA.

Nowadays, some CNIs don't just provide networking but security and observability. Like other applications, you might want to manage your CNI deployment with GitOps methodology.

The challenge here is to provide connectivity between Pods without CNI. For example, you can remove Kube-proxy, which provides the service-to-service communication, or your DNS pods won't be able to start resolving DNS.

Of course, there is an option that you can have FluxCD control your CNI deployment after its deployment. So you need first to deploy CNI.

This repository provides a method to deploy FluxCD without CNI and ensure connectivity with Nginx-proxy. With this, I aim to eliminate the risk if CNI is broken or loses connectivity, your Flux will be functional to apply the resolution.

## Get started

### Prerequisites

- [Flux CLI](https://fluxcd.io/flux/cmd/)
- [Ansible](https://www.ansible.com/)
  - [kubernetes.core](https://docs.ansible.com/ansible/latest/collections/kubernetes/core/k8s_module.html)
- [kubectl-slice](https://github.com/patrickdappollonio/kubectl-slice)
- Clone the repository

You can choose any version with flux_version variable.

```yaml
    flux_version: "v0.36.0"
```

This setup forces the deployments to be on controller nodes since connectivity is provided with Nginx-proxy, so we need to define the IPs where deployments exist.

### Install FluxCD

```bash
$ ansible-playbook install-flux.yaml
.
localhost                  : ok=16   changed=11   unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
$ kubectl get pods -n flux-system
helm-controller-7f674d57fc-2xtm7                       0/1     Running             0          68s
helm-controller-7f674d57fc-42rbv                       0/1     Running             0          68s
helm-controller-7f674d57fc-p4ctm                       0/1     Running             0          68s
kustomize-controller-5777c68db-5xjc8                   1/1     Running             0          68s
kustomize-controller-5777c68db-9pw8f                   1/1     Running             0          68s
kustomize-controller-5777c68db-wrqmg                   1/1     Running             0          68s
notification-controller-79b9cbdb96-22jwh               1/1     Running             0          68s
notification-controller-79b9cbdb96-5ktt9               1/1     Running             0          68s
notification-controller-79b9cbdb96-hlw89               1/1     Running             0          68s
notification-controller-nginx-proxy-77766dc8b8-4ft2x   1/1     Running             0          68s
notification-controller-nginx-proxy-77766dc8b8-f67g5   1/1     Running             0          68s
notification-controller-nginx-proxy-77766dc8b8-snp54   1/1     Running             0          68s
source-controller-644f65fd54-2h46q                     1/1     Running             0          68s
source-controller-644f65fd54-k7t28                     1/1     Running             0          68s
source-controller-644f65fd54-x5gmf                     1/1     Running             0          68s
source-controller-nginx-proxy-5449b79b5b-9fxbx         1/1     Running             0          68s
source-controller-nginx-proxy-5449b79b5b-dwgc7         1/1     Running             0          67s
source-controller-nginx-proxy-5449b79b5b-m57cs         1/1     Running             0          67s
```

### Uninstall Flux

```bash
flux uninstall
```
# flux-without-cni


patches:
  - target:
      kind: Deployment
      labelSelector: app.kubernetes.io/part-of=flux
    patch: |-
      - op: replace
        path: /spec/strategy
        value:
          type: Recreate

      - op: replace
        path: /spec/template/spec/hostNetwork
        value: true

      - op: remove
        path: /spec/template/spec/containers/0/ports

      - op: remove
        path: /spec/template/spec/containers/0/livenessProbe

      - op: remove
        path: /spec/template/spec/containers/0/readinessProbe

      - op: remove
        path: /spec/template/spec/containers/0/args

      - op: add
        path: /spec/template/spec/tolerations
        value:
          - key: node.kubernetes.io/not-ready
          - key: node-role.kubernetes.io/master
            operator: Exists
            effect: NoSchedule
          - key: node-role.kubernetes.io/control-plane
            operator: Exists
            effect: NoSchedule

      - op: add
        path: /spec/template/spec/containers/0/env/-
        value:
          name: KUBERNETES_SERVICE_HOST
          value: "127.0.0.1"

      - op: add
        path: /spec/template/spec/containers/0/env/-
        value:
          name: KUBERNETES_SERVICE_PORT
          value: "6443"

  - target:
      kind: Deployment
      labelSelector: app.kubernetes.io/part-of=flux
    patch: |
      apiVersion: apps/v1
      kind: Deployment
      metadata:
        name: all
      spec:
        template:
          spec:
            affinity:
              nodeAffinity:
                requiredDuringSchedulingIgnoredDuringExecution:
                  nodeSelectorTerms:
                  - matchExpressions:
                    - key: node-role.kubernetes.io/master
                      operator: Exists
                    - key: node-role.kubernetes.io/control-plane
                      operator: Exists

  - target:
      kind: Deployment
      name: source-controller
    patch: |
      apiVersion: apps/v1
      kind: Deployment
      metadata:
        name: all
      spec:
        replicas: 1
        template:
          metadata:
            annotations:
              prometheus.io/port: "22570"
          spec:
            affinity:
              podAntiAffinity:
                requiredDuringSchedulingIgnoredDuringExecution:
                - labelSelector:
                    matchExpressions:
                    - key: app
                      operator: In
                      values:
                      - source-controller
                  topologyKey: "kubernetes.io/hostname"
            containers:
            - args:
              - --events-addr=http://127.0.0.1:22585
              - --storage-adv-addr=http://127.0.0.1:22575
              - --storage-addr=:22571
              - --metrics-addr=:22570
              - --health-addr=:22572
              - --watch-all-namespaces=true
              - --log-level=info
              - --log-encoding=json
              - --enable-leader-election
              - --storage-path=/data
              name: manager
              ports:
              - containerPort: 22571
                name: http
                protocol: TCP
              - containerPort: 22570
                name: http-prom
                protocol: TCP
              - containerPort: 22572
                name: healthz
                protocol: TCP
              readinessProbe:
                httpGet:
                  path: /readyz
                  port: healthz
                timeoutSeconds: 5
                initialDelaySeconds: 5
              livenessProbe:
                httpGet:
                  path: /healthz
                  port: healthz
                timeoutSeconds: 5
                initialDelaySeconds: 5

  - target:
      kind: Deployment
      name: notification-controller
    patch: |
      apiVersion: apps/v1
      kind: Deployment
      metadata:
        name: all
      spec:
        replicas: 1
        template:
          metadata:
            annotations:
              prometheus.io/port: "22580"
          spec:
            affinity:
              podAntiAffinity:
                requiredDuringSchedulingIgnoredDuringExecution:
                - labelSelector:
                    matchExpressions:
                    - key: app
                      operator: In
                      values:
                      - notification-controller
                  topologyKey: "kubernetes.io/hostname"
            containers:
            - args:
              - --receiverAddr=:22582
              - --events-addr=:22581
              - --metrics-addr=:22580
              - --health-addr=:22583
              - --watch-all-namespaces=true
              - --log-level=info
              - --log-encoding=json
              - --enable-leader-election
              name: manager
              ports:
              - containerPort: 22581
                name: http
                protocol: TCP
              - containerPort: 22582
                name: http-webhook
                protocol: TCP
              - containerPort: 22580
                name: http-prom
                protocol: TCP
              - containerPort: 22583
                name: healthz
                protocol: TCP
              livenessProbe:
                httpGet:
                  path: /healthz
                  port: healthz
                timeoutSeconds: 5
                initialDelaySeconds: 5
              readinessProbe:
                httpGet:
                  path: /readyz
                  port: healthz
                timeoutSeconds: 5
                initialDelaySeconds: 5

  - target:
      kind: Deployment
      name: kustomize-controller
    patch: |
      apiVersion: apps/v1
      kind: Deployment
      metadata:
        name: all
      spec:
        replicas: 1
        template:
          metadata:
            annotations:
              prometheus.io/port: "22590"
          spec:
            affinity:
              podAntiAffinity:
                requiredDuringSchedulingIgnoredDuringExecution:
                - labelSelector:
                    matchExpressions:
                    - key: app
                      operator: In
                      values:
                      - kustomize-controller
                  topologyKey: "kubernetes.io/hostname"
            containers:
            - args:
              - --events-addr=http://127.0.0.1:22581
              - --metrics-addr=:22590
              - --health-addr=:22591
              - --watch-all-namespaces=true
              - --log-level=info
              - --log-encoding=json
              - --enable-leader-election
              name: manager
              ports:
              - containerPort: 22590
                name: http-prom
                protocol: TCP
              - containerPort: 22591
                name: healthz
                protocol: TCP
              livenessProbe:
                httpGet:
                  path: /healthz
                  port: healthz
                timeoutSeconds: 5
                initialDelaySeconds: 5
              readinessProbe:
                httpGet:
                  path: /readyz
                  port: healthz
                timeoutSeconds: 5
                initialDelaySeconds: 5

  - target:
      kind: Deployment
      name: helm-controller
    patch: |
      apiVersion: apps/v1
      kind: Deployment
      metadata:
        name: all
      spec:
        replicas: 1
        template:
          metadata:
            annotations:
              prometheus.io/port: "22601"
          spec:
            affinity:
              podAntiAffinity:
                requiredDuringSchedulingIgnoredDuringExecution:
                - labelSelector:
                    matchExpressions:
                    - key: app
                      operator: In
                      values:
                      - helm-controller
                  topologyKey: "kubernetes.io/hostname"
            containers:
            - args:
              - --events-addr=http://127.0.0.1:22581
              - --metrics-addr=:22601
              - --health-addr=:22602
              - --watch-all-namespaces=true
              - --log-level=info
              - --log-encoding=json
              - --enable-leader-election
              name: manager
              ports:
              - containerPort: 22601
                name: http-prom
                protocol: TCP
              - containerPort: 22602
                name: healthz
                protocol: TCP
              livenessProbe:
                httpGet:
                  path: /healthz
                  port: healthz
                timeoutSeconds: 5
                initialDelaySeconds: 5
              readinessProbe:
                httpGet:
                  path: /readyz
                  port: healthz
                timeoutSeconds: 5
                initialDelaySeconds: 5
