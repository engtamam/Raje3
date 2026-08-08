# Raje3 — the build guide

**Read this before writing any code.** It tells you how to build Raje3 by *standing on*
`base-services` instead of building everything from scratch.

Three documents, and they do not overlap:

| Document | Answers |
| --- | --- |
| `docs/وصف-منصة-راجع.md` | **WHAT** and **WHY** — the product, in the owner's words. It wins on behaviour. |
| `docs/PLATFORM-PLAYBOOK.md` | **HOW to build any platform** on base-services — the general method, the traps, the per-service loop. Read it once, fully. |
| this file | **What is true about RAJE3 specifically** — our wave order, our services, our decisions, our open items. |

If you are new here: playbook first, then this.

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
| **`engtamam/base-services`** (private) | ~24 generic, production-grade backend microservices (FastAPI), plus a Helm chart and CI harness. Hexagonal, config-driven, deny-by-default, zero-hardcoded. | **CONSUME, NEVER EDIT.** We run its services from published images and adapt them via env vars / config / Helm values. We keep only its Helm **chart** + **CI harness** in-tree (sparse), never its service source. Pinned to a tag (see the appendix for the current pin; bump deliberately). |
| **`engtamam/imtithal`** (private) | A *real* product built the same way. | **REFERENCE ONLY**, and less needed now than it was: the deploy scripts we once adapted from it were superseded when base-services shipped its own `deploy/server/`. Still useful for seeing how another product structures itself. Never depend on it at runtime. |
| **`engtamam/raje3`** (this repo) | Raje3 itself. | **BUILD HERE.** Our product services, our UI, our deploy pipeline, our config. |

> Access note: both are private; you need read access. `base-services` is a git submodule,
> sparse-checked-out to the Helm chart + CI harness, and **read-only**. Reveal its source to
> read it (§4), never to change it.

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

## 5. Bring-up order — and where we actually are

Deployed and verified on the dev server. Each was read, configured, deployed and **proven with
real calls** before the next; the evidence is in each service's commit message.

| Wave | Services | Status |
| --- | --- | --- |
| **0** | K3s + Calico + metrics-server + postgres/redis + object store | ✅ policy enforcement proven by a denied packet |
| **1** | `tenant` → `authz` → `identity` → `audit` | ✅ isolation, rs256 flow, no-escalation, audit chain all proven |
| **2** | `api-gateway` · `job` · `file` | ✅ routing and guards proven; edge reachable from outside |
| **3** | `compliance` → `notification` · `feature-flag` | ✅ consent tenant-scoped, withdrawal instant, plan gating proven |
| **4** | `analytics` · `wallet` · `billing` | ✅ HLL uniques, fund priority, receipts without VAT |
| **5** | `ticket` · `onboarding` · `backup` · `search` | ✅ workflow capability boundary, trial grant, restore drill, Arabic normalisation |
| **6** | `webhook` · `connector` | ✅ SSRF guard refuses metadata, in-cluster and plain-http; mapping ops fail closed |
| **6** | `zatca` · `assistant` · `verification` | deferred by decision, not pending — see §11 |
| **7** | **our product services** | next, on a platform proven underneath them |

**Nineteen services on v0.13.1, every one verified from the CLUSTER** — `deploy/verify-pinned.sh`
compares each deployment's running image to its pinned digest. `update.sh` reports what helm told
it, which is a different claim: services have been reported failed while running the correct
digest, and one the script walked past was never created at all.

**Two ordering facts that are ours, not the platform's:**

- **`compliance` comes BEFORE `notification`**, not a wave later. notification declares
  consent-gated processing, and its boot guard refuses to start in production with a null
  consent gate. Found by reading, not by deploying.
- **`zatca` is deferred to VAT registration**, not to a sprint. An unregistered seller issues
  receipts and has nothing to report; deploying it now would wire a pipeline for documents that
  must not exist yet. The trigger and the four settings that move together are in §11.

**Per-service recipe:** the 8 steps live in the playbook (§3). Do not shorten them.

## 6. Our product services — build these last, one at a time

Generated from `base-services/_template` so each inherits the ports, auth, security gate and CI
gates, then the domain logic is ours. Internal names carry **no** product name (`operations`,
not `raje3-operations`).

| Service | Owns | Leans on |
| --- | --- | --- |
| **`operations`** | end customers, assets, service records, operators + PIN, field entry, branches (spec §4, §12, §13) | identity, audit, search |
| **`reminders`** | reminder rules, adaptive EWMA learning, min/max bounds, anomaly filtering, lead days, **the escalating follow-up sequence**, and the post-service check-ins tied to each service (spec §5) | job, notification |
| **`loyalty`** | points earn/redeem, thresholds, cross-branch balance (spec §9) | **nothing upstream** — `wallet` is a VAT-aware money ledger for prepaid message credit, not a points system |
| **`campaigns`** | segmentation, sending, anti-ban pacing, the consent gatekeeper (spec §7, §8) | notification, analytics, job, compliance |
| **`insights`** | the 20 metrics, adaptive and contextual re-sort, cross-sell matrix, at-risk lists, staff KPIs, the daily owner digest (spec §4.4, §10, §11.5) | analytics, job, notification |
| **`portal`** | the customer's own page — due date, points, visits, offers banner, notification preferences (spec §8.6.1) | operations, loyalty, compliance |

`catalog` is **not** a service: sectors, services, dynamic fields and sector templates are
content under `data/`, edited and loaded without a deploy.

**Two product decisions that constrain these before a line is written:**

- **The customer page carries the establishment's identity alone.** No Raje3 name, logo, or
  attribution line anywhere on it. The owner paid us to bring his customers back, not to
  introduce them to us.
- **Metrics are free in every plan** and the retention engine is complete in every plan. What
  the plans gate is marketing and scale (spec §16). Do not build a metric behind a flag.

**Generate a new service:**
```bash
python scripts/create_service.py my-service --desc "..."
```

## 7. The deploy pipeline — theirs, not ours

`base-services` ships the whole pipeline in `platform/deploy/server/`: `provision-server.sh`,
`setup.sh`, `update.sh`, `reset-platform.sh`, `boot-heal.sh`, `gen-secrets.py`, `pull-images.sh`.
It is generalised for consumers and driven by environment variables.

**We wrote our own before that existed, and deleted them when it arrived.** Maintaining a
divergent copy of something upstream now maintains is the same mistake as forking a service.

**How we invoke it:**

```bash
sudo PRODUCT_NAME=raje3 NS=base-services      CHART=$HOME/raje3/platform/deploy/chart      VALUES_DIR=$HOME/raje3/deploy/services      bash platform/deploy/server/update.sh            # add --only <svc> or --dry-run
```

It renders every values file before touching the cluster, health-gates each release, rolls back
to the revision captured **before** the upgrade, lists anything not fully ready, exits non-zero
on any failure, and prunes superseded node images once everything is green.

**What stays ours, in `deploy/`:**

| Path | Why it is ours |
| --- | --- |
| `deploy/services/*.values.yaml` | Every Raje3 decision, with its reason |
| `deploy/hooks/pre-deploy.sh` | Our databases and object-store buckets — the seam their `setup.sh` calls |
| `deploy/k3s/edge.yaml` | Caddy at the edge. Modelled on theirs, not copied: their image digest is a placeholder and their probe path is unanswered by the shipped Caddyfile |

**Run it detached.** An interrupted rollout is worse than one never started, and a dropped SSH
session will kill it otherwise.

**Object store:** SeaweedFS, invoked from `platform/deploy/k3s/objectstore.yaml`. Apache-2.0.
MinIO is AGPLv3 and has no place under a product we sell — check the licence of anything you
deploy before it runs, not after.

## 8. Messaging — the model the whole product rests on

`notification-service` carries four channels: **email · SMS · WhatsApp · in-app**. It is not
"the WhatsApp service", and identity's verification mail depends on it.

**Two message classes, two different legal bases** (spec §8.4). Get this wrong in either
direction and the product either breaks or breaks the law:

| Class | Basis | Default | Consent |
| --- | --- | --- | --- |
| **Non-marketing** — confirmation, check-in, due reminder, operational, support reply | an existing relationship | ON | none needed |
| **Marketing** — offers, win-back, launches | explicit prior consent | OFF | required, recorded |

**In configuration this is `NOTIFY_CONSENT_PURPOSES`:** only templates listed there are gated.
Anything unlisted sends under contract. **Every marketing template added to the library must be
added to that map**, or it sends without a lawful basis — the most expensive single mistake
available in our values files.

**Two permissions, not one** (spec §8.5): contact permission is verbal, taken when the customer
gives their number; marketing consent is **electronic only**, from the customer's own page, by
their own tap. Never verbal, never entered by an operator on someone's behalf.

**And Meta's own policy sits above both:** a business-initiated message needs opt-in regardless
of category, templates are pre-approved per category, and the number's **quality rating** governs
how much it may send. A blocked number costs the shop its customers, not just our campaigns —
which is why pacing and the one-tap unsubscribe are product features, not politeness.

## 9. The working loop

**One service per iteration. Never batch. Never skip a step because a service looks simple.**

The 8 steps are in the playbook (§3): read → decide → pin by digest → provision → render →
deploy → **prove** → register with compliance. What follows is only what is specific to us.

1. **Read the whole surface**, not the summary. The platform's own one-line descriptions have
   been wrong about what a service is more than once, and a values file written from a summary
   is architecture built on a guess.
2. **Write the decision in the values file**, in terms of the spec section it serves. That file
   is the only documentation anyone reads at 3am.
3. **Prove one real product behaviour** and **tenant isolation on read and write**. A green
   `/readyz` proves the process started, nothing more.
4. **Commit with the evidence in the message** — what was proven, and what was not. "Deployed,
   behaviour unproven" is an honest status; "done" is not.
5. **Update the spec** if a decision changed the product, and **this file** if it changed the
   method or the open items.

**When a result surprises you, understand it before reporting it.** A number that looks wrong
has more than once been a mechanism working exactly as designed — and the right response was to
change our configuration, not to file a bug.

## 10. Definition of done (per service)

A service — ours or an adapted base-services one — is "done" only when:

- [ ] It runs from a **pinned image** (digest / `vX.Y.Z`), never `:latest`.
- [ ] All behaviour comes from **config/env/values** — zero hardcoded values.
- [ ] **Tenant isolation** holds on every query (verified, not assumed).
- [ ] It has a **K3s manifest / values file** and passes `make verify`.
- [ ] It **health-gates** (`/readyz`) and an end-to-end check passes.
- [ ] For our services: **tests** pass, and it writes an **audit entry** for meaningful actions.
- [ ] **Registered in `compliance-service`**: present in `PRIVACY_TARGETS` and in the data map,
      with an erasure fan-out proven to reach it at least once. A service holding no personal
      data is exempt from the map but not from the decision — write it down.
- [ ] **One real product behaviour proven with real calls**, and the evidence in the commit.
- [ ] Anything unproven **stated plainly**, not implied by silence.
- [ ] Any decision is recorded in `docs/`.

---

## 11. Open items — read this before assuming something works

Honest state. Each is real, none is hidden in a commit message.

| Item | State |
| --- | --- |
| **Archives share a disk with their source** | The object store runs on the same node as the data it protects. A backup inside its own failure domain protects against nothing that actually happens. Unchanged, and the oldest item here. |
| **`/metrics` is not scraped yet** | The monitoring stack is installed and our alert rules are loaded, but `serviceMonitor` is still `false` in every values file — flipping it restarts every pod, so it waits for a quiet moment. Prometheus watches the cluster and the database; it does not yet watch the services' own counters. |
| **TLS is written, not applied** | `deploy/k3s/edge.production.yaml` is ready — ACME, HSTS, a PVC for the certificates, and a catch-all for unknown hosts. It cannot be applied until a hostname resolves to a production box. |
| **WhatsApp templates are not registered** | The channel is open (a `whatsapp` send reaches the engine) and the library is written (63 templates, three tones per type, spec Appendix A). None is registered with Meta, so no template send can succeed yet. This is the last thing between us and a real message. |
| **`zatca`** | Deferred to VAT registration, not to a sprint. On the day we register, four things move together: the tax calculator to `vat`, the document mode to a tax invoice, the e-invoicer to `zatca-http`, and the seller VAT number filled in `config/product.json`. Flipping one produces a document whose error a customer's accountant finds first. |
| **`assistant` · `verification`** | Deferred by decision. `assistant` answers from a knowledge base we have not written; support is served by `ticket`. `verification` checks a commercial registration through Wathq or an identity through Nafath — we hold no contract with either, and upstream rightly does not invent their endpoints. |

**Anything here that a platform release closes should be deleted from this table, not annotated.**
History belongs in git.

## 12. Reporting upstream

`base-services` is read-only. When it lacks something generic or behaves wrongly:

1. Give the file and line, the mechanism, and evidence from a live system.
2. State what a consumer can and cannot work around.
3. **Ask for a guard, not just a fix** — the CI rule or boot assertion that closes the whole
   class. That is worth more than the patch, and it catches instances nobody reported.

Work around it behind a port on our side, in `services/`, and delete our workaround when theirs
lands. If a workaround turns out not to work, **remove it** rather than leave configuration
claiming a mitigation it does not deliver.

## Appendix — quick reference

- **base-services pin:** see `platform` submodule (`git -C platform describe --tags`). Bump
  deliberately, re-read `platform/deploy/` for anything that supersedes ours, and re-run the
  proofs — a version bump has changed defaults before.
- **Consume base-services (fresh clone):**
  ```bash
  git submodule update --init platform
  git -C platform sparse-checkout init --cone
  git -C platform sparse-checkout set deploy tools/ci   # chart + CI harness only
  ```
- **Validate product identity:** `python3 ci/check_product_config.py`
- **Roll a release:** `sudo PRODUCT_NAME=raje3 NS=base-services CHART=…/platform/deploy/chart
  VALUES_DIR=…/deploy/services bash platform/deploy/server/update.sh` (detached; `--only`, `--dry-run`)
- **Read a service:** `git -C platform sparse-checkout disable` → read → `reapply`. Never edit.
- **Frozen identifiers** (in `config/product.json` — never change on a rename): `jwtIssuer`,
  `optoutLinkNs`, `eventNs`, `userAgent`.
- **The 3 things we touch on base-services:** config, env vars, Helm values. Nothing else.
- **The 5-second rule:** the field-entry screen must always feel instant.

*Build on the shoulders of `base-services`. Write only what makes Raje3 Raje3.*
