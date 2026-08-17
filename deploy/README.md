# `deploy/` — how Raje3 is installed and rolled

Layered **over** base-services. We own the values, the provisioning and the verification; the
chart, the images and the server scripts are theirs and are never edited.

## The one command

```bash
sudo bash deploy/bring-up.sh
```

Preflight → datastores → connection ceiling → secrets → databases and buckets → services →
verify. Idempotent: running it on a live cluster changes only what is not already true.

The order is the substance. The connection ceiling is raised *before* services start consuming it,
because raising it afterwards needs a fleet restart to take effect — and that is precisely the
rollout that cannot finish while the ceiling is full.

## What is ours, and why

| | |
|---|---|
| `bring-up.sh` | the whole install, in the order that works |
| `services/*.values.yaml` | one per service — the config, and the reasoning behind every non-default |
| `hooks/pre-deploy.sh` | one database per service, and the two object-store buckets |
| `repin.sh` | moves every values file to a release, **by digest** — a tag can be moved |
| `verify-pinned.sh` | reads what the cluster is *running* and compares it to what is pinned |
| `k3s/edge.yaml` | the Caddy edge for a host with no DNS (no ACME) |
| `edge/edge.json` | the ONE place the domain and the routes are written; `bring-up.sh` renders it |
| `monitoring/` | Prometheus, alert rules, a postgres exporter — written, not yet installed |

## What is theirs, and called rather than copied

`platform/deploy/server/`: `gen-secrets.py` (shared secrets minted once and written identically
everywhere), `update.sh` (health-gated rollout, one service at a time, with rollback),
`boot-heal.sh`, `preflight.sh`, `pull-images.sh`.

Reaching past these is how this project has broken its own cluster. A hand-written parallel restart
exhausted the connection pool and deadlocked the fleet; hand-cloned secrets nearly gave one service
another's database. The sequential health gate is the feature, not the slow part.

## Before you push

```bash
python3 ci/check_product_config.py     # the product identity is intact
python3 ci/check_deploy_wiring.py      # nine guards, each one a failure we have actually had
```

## After a rollout

`update.sh` reports what helm told it. `verify-pinned.sh` reads the running image of every
deployment. They are different claims, and only the second is evidence: services have been reported
failed while running the correct digest, and one the script walked past was never created at all.
