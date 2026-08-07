# deploy/ — the Raje3 server install pipeline

Layered **over** the base-services Helm chart (in `platform/deploy`). We own the
provisioning, the per-service values, secrets generation, DB provisioning, and the
health-gated rollout — the platform chart and images stay untouched.

Planned (Wave 0 of the infra roadmap):

```
server/provision-server.sh   blank Ubuntu -> hardened single-node k3s (idempotent, --dry-run)
server/setup.sh              THE ONE COMMAND: provision -> pull-secret -> bring-up -> edge -> boot-heal
server/reset-platform.sh     idempotent full bring-up + end-to-end verify
server/update.sh             health-gated rollout of OUR images, with auto-rollback
services/<svc>.values.yaml   our per-service deploy shape + config (base-services + product)
```

Nothing here edits base-services. We touch three things only: config, env vars, Helm values.
