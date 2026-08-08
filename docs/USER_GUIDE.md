# Raje3 — Build Guide for Claude Code

**Read this before writing any code.** It tells you how to build Raje3 by *standing on*
two existing repositories instead of building everything from scratch. Following it will
save months of work and keep the codebase consistent, secure, and production-grade.

This guide is the **HOW**. The product spec (the functional description you were given
separately) is the **WHAT** and **WHY**. When they seem to conflict, the spec defines the
product behaviour; this guide defines the engineering method — they do not actually conflict.

---

## 0. Prime directive (the one thing to get right)

> **Do NOT rebuild generic backend infrastructure. Raje3 runs on `base-services` — a
> production-grade platform of ~24 generic microservices — which we consume as published
> container images and adapt by CONFIGURATION ONLY. We never edit its code. We build ONLY
> our own business logic (the domain-specific services) on top of it.**

If you are about to write authentication, multi-tenancy, RBAC, billing, notifications,
job scheduling, analytics, audit logging, file storage, or an API gateway — **stop**. That
already exists in `base-services`. Configure it; do not write it.

You build only what is unique to Raje3: **customers, assets, service records, reminder
rules, loyalty points, campaigns, sectors.** Nobody else will ever build those for us.

---

## 1. The three repositories and their roles

| Repo | What it is | How we use it |
| --- | --- | --- |
| **`engtamam/base-services`** (private) | ~24 generic, production-grade backend microservices (FastAPI), plus a Helm chart and CI harness. Hexagonal, config-driven, deny-by-default, zero-hardcoded. | **CONSUME, NEVER EDIT.** We run its services from published images and adapt them via env vars / config / Helm values. We keep only its Helm **chart** + **CI harness** in-tree (sparse), never its service source. Pinned to a tag (currently **`v0.12.1`**). |
| **`engtamam/imtithal`** (private) | A *real* product built the same way — it consumes `base-services` and adds its own product services. Its deploy scripts are excellent. | **REFERENCE ONLY, DO NOT COPY VERBATIM.** Learn its repo structure and its `deploy/server/` scripts, then write Raje3's own equivalents. Never depend on it at runtime. |
| **`engtamam/raje3`** (this repo) | Raje3 itself. | **BUILD HERE.** Our product services, our UI, our deploy pipeline, our config. |

> Access note: both `base-services` and `imtithal` are private. You need read access to
> clone them. `base-services` is wired as a git submodule (read-only); `imtithal` is read
> once as a reference and not vendored.

---

## 2. The golden rules (non-negotiable)

These come straight from how `base-services` and `imtithal` are built. Breaking any of them
defeats the whole approach.

1. **Never fork, never patch `base-services`.** We touch exactly three things: **config,
   env vars, Helm values.** Nothing else, ever.
   - It has the feature → configure it.
   - It has a bug → report upstream, work around it behind a port on our side.
   - It lacks a **generic** feature → request it upstream; add a temporary adapter on our
     side; delete ours when theirs lands.
   - It lacks a **domain (Raje3-specific)** feature → it always will. Build it in `services/`.
2. **Zero hardcoding.** No URL, limit, path, secret, or vocabulary is ever written into
   code. Everything comes from config/env/values. This is enforced by CI in `base-services`
   and must be enforced in our services too (a "config-knob guard": every setting has a
   consumer; no knob ships without code that reads it).
3. **Deny-by-default.** Every capability is denied unless explicitly granted.
4. **Tenant isolation on every query.** A tenant can NEVER see another tenant's data. This
   is enforced at the data layer, not by a `WHERE` clause a developer must remember. For
   Raje3 this also means: an end-customer's opt-out, points, and history are per-establishment.
5. **Hexagonal (ports/adapters).** Every external dependency is a port with adapters chosen
   by config (`memory`, `postgres`, `redis`, `s3`, `http`, `null`…). Our escape hatch when
   `base-services` lacks something is a port with two adapters — never a patch.
6. **Immutable image tags.** Deploy images by digest or a fixed tag (`vX.Y.Z` / commit SHA),
   never `:latest` — otherwise rollback is not exact.
7. **Nothing ships without: tests, tenant isolation, an audit entry, and a K3s manifest.**
8. **Field-entry performance is sacred.** The operator screen must record a visit in **under
   5 seconds**; background work (reminders, sending) must never slow it.

---

## 3. Repository structure (adopt this)

Model the repo on `imtithal`'s layout (already scaffolded in this repo — reproduce it if the
repo is empty):

```
config/     product identity. The ONE place the product name/brand lives (config/product.json).
ci/         guards that fail the build before production does (e.g. check_product_config.py).
services/   OUR product services (business logic), each generated from base-services/_template.
platform/   base-services: the Helm CHART + CI harness only (sparse submodule). NEVER edited.
deploy/     the server install pipeline — k3s manifests + provision/install/update scripts.
ui/         portals (establishment: dashboard + field-entry; super-admin console).
data/       "the axes" — sectors, services, templates. Content that grows without a deploy.
docs/       design, written before code. This guide lives here.
brand/      colour tokens + logos.
```

**`config/product.json`** is the single source of the product's identity (name, brand,
locale, and FROZEN identifiers like `jwtIssuer` and `optoutLinkNs`). Renaming the product is
a one-file edit. A CI guard (`ci/check_product_config.py`) validates it and fails if the
product name leaks into a service name. Arabic-first (`ar`), `SAR`, `Asia/Riyadh`.

---

## 4. How to adapt a `base-services` service WITHOUT its code

The image is a **fixed engine**; all its behaviour is read from OUTSIDE at runtime. You steer
it with four levers — never by editing it:

| Lever | What you set | Example |
| --- | --- | --- |
| **1. Env vars / config** | limits, vocabulary, locale, timezone, feature knobs | `DEFAULT_LOCALE=ar`, `TIMEZONE=Asia/Riyadh` |
| **2. Adapter choice** | which infrastructure it runs on (same image, different backend) | `DATASTORE_DRIVER=postgres`, `SMS_CHAIN=unifonic,console`, `STORAGE_DRIVER=s3` |
| **3. Helm values** | deploy shape: replicas, resources, secrets, ingress | `deploy/services/<svc>.values.yaml` |
| **4. Data via API** | our content, injected at runtime through the service's endpoints | `POST /api/v1/templates`, seed roles/plans/tenants |

**To learn which knobs exist**, read (do not edit) two files inside the service:
- `app/config.py` — every configurable knob. Nothing is hardcoded elsewhere.
- `app/manifest.py` — the routes and capabilities it serves.

To reveal the source temporarily (the submodule hides it by default):
```bash
git -C platform sparse-checkout disable   # reveal base-services source to read it
git -C platform sparse-checkout reapply    # hide it again — we never edit it
```

**The boundary of adaptation:** if a behaviour is exposed by a knob → set it. If no knob
exposes it → either request it upstream (if generic, e.g. a WhatsApp channel) or build it in
our own `services/` (if domain-specific). Never edit the image to get it.

---

## 5. Bring-up order for `base-services` (do this in waves)

Bring services up one wave at a time; each wave builds on the previous. **Enable only what a
wave needs** — an unused service is left out of the values, not deployed.

| Wave | Services | Why in this order | MVP? |
| --- | --- | --- | --- |
| **0 — Foundation** | K3s + Calico + metrics-server + **postgres/redis/minio**; run `make verify` (proves default-deny NetworkPolicy) | nothing runs before the cluster + datastores | ✅ |
| **1 — Spine** | `tenant` → `authz` → `identity` → `audit` | tenancy is the source of truth; then authz decisions; then auth; then the log everything writes to | ✅ |
| **2 — Door & async** | `api-gateway` · `job` · `file` | the only public door; the scheduler (reminders need it); storage (tenant logos) | ✅ |
| **3 — Messaging & control** | `notification` (**WhatsApp available since `v0.12.1`** — `meta` / `webhook` / `console`) · `feature-flag` | the send channel; per-plan feature gating | ✅ |
| **4 — Growth** | `analytics` · `wallet` · `billing` · `compliance` | KPI base (the 20 dashboard metrics); points base; subscriptions/plans/quotas; opt-out/PDPL | ✅ |
| **5 — Ops & support** | `backup` · `ticket` · `onboarding` · `webhook` · `connector` · `assistant` · `verification` · `search` · `zatca` | backups, support tickets, sign-up, POS integrations, KB, Nafath/CR, Arabic search, e-invoicing | ✅ |

**Per-service adaptation recipe (the same 7 steps every time):**
1. Pull the image from the registry (never the code) — pinned by digest/tag.
2. Write our `deploy/services/<svc>.values.yaml` (deploy shape).
3. Set env vars + config (choose adapters: postgres/redis/s3…).
4. Provision its isolated database (`provision-db`).
5. Apply the manifest via the Helm chart.
6. Health-gate: wait for readiness, assert `/readyz`.
7. Verify end-to-end (hit a real endpoint), then move to the next service.

**Scope decision (binding): Raje3 ships as a COMPLETE platform, not an MVP.** All five waves
are in scope. The order above is a *build sequence*, not a scope filter — we still bring
services up one wave at a time (never big-bang), but no wave is dropped. Waves 0–3 make the
field flow work; waves 4–5 are what make it a product you can sell, bill, support, and
operate (spec §9, §10, §15, §16).

---

## 6. Our product services (build these from `_template`, one at a time)

These are Raje3's business logic — the part `base-services` will never build. Generate each
from `base-services/_template` so it inherits the ports, auth, security gate, and CI gate,
then implement the domain logic. Internal names carry **no** product name (`operations`, not
`raje3-operations`).

| Service | Owns (spec section) | Leans on (base-services) | Phase |
| --- | --- | --- | --- |
| **`operations`** | end customers, assets (car/device), service records, operators + PIN, field entry, branches (§4, §12, §13) | identity, audit | 1 |
| **`reminders`** | reminder rules (time / usage / custom) + adaptive EWMA learning + min/max bounds + anomaly filtering + lead-days + next-due computation (§5) | job, notification | 1 |
| **`catalog`** *(as `data/`, not code)* | sectors, services (name/icon/colour/rule/points), dynamic fields, sector templates (§1.2, §4.6) | — grows without deploy | 1 |
| **`loyalty`** | points earn/redeem, thresholds, cross-branch balance (§9) | wallet | 2 |
| **`campaigns`** | segmentation, campaign send, anti-ban pacing (random delay + rate limit), opt-out gatekeeper (§7, §8) | notification, analytics, job | 2 |
| **`insights`** | the 20 dashboard metrics, adaptive/contextual service re-sort, cross-sell matrix, at-risk lists, staff KPIs, daily owner digest (§4.4, §10, §11.4) | analytics, job, notification | 3 |

**All six are in scope.** The numbers are build ORDER, not a cut line: 1 makes the field flow
real, 2 makes it retain and market, 3 makes it insightful. Nothing here is deferred out of
the product — only sequenced. Do not start the next number before the previous one is
verified end-to-end (§10).

**Generate a new service:**
```bash
# from inside base-services (read-only reference) or its published tooling:
python scripts/create_service.py my-service --desc "..."
# it arrives with guards, gates, and a deploy values file already wired.
```
Then implement the domain logic in the generated service, keeping every base-services
discipline (ports/adapters, zero-hardcode, tenant isolation, tests, hot-path benchmark,
config-knob guard).

---

## 7. The deploy pipeline (K3s) — adapt from `imtithal`, don't copy

`imtithal/deploy/server/` has battle-tested scripts. **Study them, then write Raje3's own**
(they are wired to imtithal's names/DBs/seeds — the *structure and patterns* transfer, not the
files). Reproduce these, adapted for Raje3:

| Script | What it must do | Patterns to keep |
| --- | --- | --- |
| `provision-server.sh` | blank Ubuntu → hardened single-node k3s | **idempotent + resumable** (stamps), `--dry-run`, SSH hardening that **refuses to lock you out** without a key, UFW/fail2ban/swap/kernel tuning, Traefik disabled (own edge) |
| `setup.sh` | THE ONE COMMAND: provision → pull-secret → bring-up → edge/TLS → boot-heal | each phase idempotent, fast no-op if already done |
| `reset-platform.sh` | idempotent full bring-up + end-to-end verify | every phase **retries transient failures, asserts success, fails loud at the exact phase**; handles real footguns (PVC delete doesn't wipe host dir; consistent secret generation); ends by minting a token and hitting services |
| `update.sh` | continuous delivery of OUR images | roll each deployment, **health-gate each rollout, auto-rollback on failure**, `--only` guard, warn that `:latest` breaks rollback; **leave base-services images untouched** |
| `boot-heal.sh` | survive an ungraceful reboot | systemd unit that clears stale pods after power-off |

**Design qualities to carry into every script:** idempotent + resumable; `--dry-run`; fail
LOUD at the exact step (never silently); **assert success, don't assume it**; health-gated
rollouts with auto-rollback; immutable tags; safety guards (never lock out SSH, never wipe
without verifying, never touch base-services images).

The base-services Helm chart already **refuses to render a mistake** (scale-out on in-memory
drivers, HPA without CPU requests, unpinned images, `/internal` exposed publicly, a values key
nothing reads). Run `make verify` before `make deploy` — it *proves* the cluster enforces what
the chart promises.

---

## 8. WhatsApp — the gap is closed (upstream, as of `v0.12.1`)

This section used to describe Raje3's one blocking gap: `notification-service` had Email /
SMS / in-app but no WhatsApp, the core channel for the whole product (spec §6). We requested
it upstream rather than building it, because a WhatsApp channel is generic. **It shipped in
base-services `v0.12.1`** — exactly the config-driven shape we asked for. We wrote no code
for it and we still edit nothing.

The knobs (read from `services/notification-service/app/config.py`, never edited):

| Knob | What it does |
| --- | --- |
| `WHATSAPP_CHAIN` | provider chain, e.g. `meta,console`. `console` · `webhook` · `meta` |
| `WHATSAPP_ACCESS_TOKEN` / `WHATSAPP_PHONE_NUMBER_ID` | per-tenant credential + sending number, resolved via the secret store |
| `WHATSAPP_GRAPH_BASE` | Meta Cloud API base — config, never a value from a request |
| `WHATSAPP_TEMPLATE_MANAGER` | `console` \| `meta` — the approved-template lifecycle |
| `WHATSAPP_BUSINESS_ACCOUNT_ID` | WABA id for the template-management endpoint |
| `WHATSAPP_TEMPLATE_SYNC_LIMIT` | pending templates reconciled per sweep |
| `WHATSAPP_WEBHOOK_URL` / `_BEARER` | generic gateway/QR relay — host must be in `EGRESS_ALLOWED_HOSTS` (SSRF guard) |

This maps onto the spec's two channels directly (§6.1): the **official channel** is
`meta`, the **fast QR channel** is `webhook` pointed at a relay. `console` stays the dev
and test driver. Switching between them is a values change, not a deploy of different code.

**What stays ours regardless:** *which* template is chosen for *which* service, the sector
template library, the variable values, and the encrypted per-tenant opt-out links
(`optoutLinkNs`). Upstream owns the pipe; we own the message.

**The lesson, not the exception:** the gap closed because it was reported upstream instead
of patched locally. When base-services lacks something generic, that is the move — never a
local edit. See §2 rule 1.

---

## 9. The working loop (how to proceed, one service per iteration)

Work in small, verifiable increments. **One service (or one wave step) per iteration.** Never
big-bang.

**Iteration checklist:**
1. **Pick the next item** from the wave order (§5) or the product-service list (§6).
2. If it's a `base-services` service → apply the **7-step recipe** (§5): image → values →
   config/adapters → DB → apply → health-gate → verify. Adapt it to Raje3 by config only.
3. If it's a Raje3 product service → generate from `_template`, implement the domain logic,
   keep every discipline (§2), write its tests + deploy values.
4. **Verify end-to-end** before moving on (hit a real endpoint; prove the behaviour).
5. **Commit** with a clear message. Small commits, each one green.
6. **Update `docs/`** with any decision you made and why.
7. Only then start the next item.

**Recommended first two weeks:**
- Week 1 — Wave 0 + Wave 1: scaffold (if empty) → `provision-server.sh` → K3s up → bring up
  `tenant`/`authz`/`identity`/`audit`, and prove a full auth flow (token + authz decision +
  tenant isolation) works end-to-end.
- Week 2 — Wave 2 + Wave 3: `api-gateway`/`job`/`file`/`notification`/`feature-flag`. At this
  point the platform is ready to build our `operations` + `reminders` on top of it.

After that, keep the same loop through waves 4–5 and product services 2–3. The three UIs
(`ui/`) are built alongside the services that back them: the field-entry screen with
`operations`, the establishment dashboard with `insights`, the super-admin console with
`billing`/`ticket`/`analytics` (spec §15).

---

## 10. Definition of done (per service)

A service — ours or an adapted base-services one — is "done" only when:

- [ ] It runs from a **pinned image** (digest / `vX.Y.Z`), never `:latest`.
- [ ] All behaviour comes from **config/env/values** — zero hardcoded values.
- [ ] **Tenant isolation** holds on every query (verified, not assumed).
- [ ] It has a **K3s manifest / values file** and passes `make verify`.
- [ ] It **health-gates** (`/readyz`) and an end-to-end check passes.
- [ ] For our services: **tests** pass, and it writes an **audit entry** for meaningful actions.
- [ ] Any decision is recorded in `docs/`.

---

## Appendix — quick reference

- **base-services pin:** `v0.12.1` (bump deliberately; test `make verify` after).
- **Consume base-services (fresh clone):**
  ```bash
  git submodule update --init platform
  git -C platform sparse-checkout init --cone
  git -C platform sparse-checkout set deploy tools/ci   # chart + CI harness only
  ```
- **Validate product identity:** `python3 ci/check_product_config.py`
- **Frozen identifiers** (in `config/product.json` — never change on a rename): `jwtIssuer`,
  `optoutLinkNs`, `eventNs`, `userAgent`.
- **The 3 things we touch on base-services:** config, env vars, Helm values. Nothing else.
- **The 5-second rule:** the field-entry screen must always feel instant.

*Build on the shoulders of `base-services`. Write only what makes Raje3 Raje3.*
