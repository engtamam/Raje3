# secrets-admin

> The owner's own way to replace an EXTERNAL PROVIDER credential — without a developer, a
> kubeconfig, or a terminal.

## What it is for

Meta rotates an app secret. A 360dialog key ends up in a screenshot. A Gemini key is reissued.
Every one of those is an ordinary Tuesday, and until this service each one meant somebody with
cluster access running `kubectl create secret … --dry-run=client -o yaml | kubectl apply -f -` and
then remembering to restart the right Deployment — by hand, under time pressure, at a keyboard
where one wrong `-n` edits the wrong namespace.

Now it is a form, behind one capability, and every write is witnessed.

## The one rule

**Write-only.** A value can be set. It can never be read back — not by the API, not by the console,
not by the person who typed it thirty seconds ago. What the screen shows is:

* whether the key is configured at all,
* its **last four characters**, captured at the moment it was written,
* who set it, and when.

There is no `reveal` route, no `?show=true`, and no second capability that unlocks one. A
credential a console can display is a credential in every screenshot, every screen-share and every
browser history of everyone who has ever held that capability.

The GET handler is built so that this is a property of its *shape* rather than a promise about its
behaviour: it reads the k8s Secret's **annotations** and never fetches `data` at all, so there is
no variable in that scope that has ever held a credential.

## What it can touch

Five keys, in two Secret objects, restarting two Deployments — listed once in
`app/core/secret_registry.py`. That list is the allow-list, and the cluster Role in
`deploy/k3s/secrets-admin-rbac.yaml` names the same two objects with `resourceNames`, so the same
rule is enforced twice: once by this code, once by the API server that would refuse it anyway.

Adding a sixth is a one-line edit in each. It is deliberately not a generic secret editor: a route
that took an object name from the request body could rewrite `identity-service-secrets` — the
signing key every token in the product is verified against — from a form.

## What it holds

Nothing. There is no datastore, no queue, no event bus and no object store. The k8s Secret objects
*are* the store: the value in `data`, and the last4 / who / when in `metadata.annotations` on the
same object, written in one merge patch so the two can never disagree.

It is therefore not in the backup roster and not in the DSAR fan-out — not because it was skipped,
but because there is nothing of ours to back up (etcd covers the Secrets) and no person's data here
to erase.

## Talking to the cluster

Raw HTTPS to the in-cluster API server, using the pod's projected ServiceAccount token and the
cluster CA — no `kubernetes` package, no kubectl in the image. Two calls:

    PATCH /api/v1/namespaces/{ns}/secrets/{name}              application/merge-patch+json
    PATCH /apis/apps/v1/namespaces/{ns}/deployments/{name}    application/merge-patch+json

The second writes `kubectl.kubernetes.io/restartedAt` into the pod template — the same mechanism
`kubectl rollout restart` uses, so a person reading `kubectl describe` sees the field they expect.

`tests/unit/test_k8s_client.py` asserts the exact method, path, content-type and body of both.
That proves the shape; it does not prove a real API server accepts it. See below.

## Before it can go live

Two steps that cannot be done from a laptop, in order:

1. `kubectl apply -f deploy/k3s/secrets-admin-rbac.yaml` — creates the ServiceAccount, the
   namespaced Role and the RoleBinding.
2. The base chart currently hardcodes `automountServiceAccountToken: false` on every Deployment.
   Until it is made configurable, this pod gets no token and every write returns 401. See the
   header of `deploy/services/secrets-admin.values.yaml`.
