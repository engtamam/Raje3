# Adding a new app to the platform — the methodology, not just the steps

**Who this is for:** any agent or developer, present or future, generating a new sellable app
(a new `services/<name>` microservice) on this platform. Written after actually doing it —
`services/bookings`, 2026-08-18 — and hitting every gap below in the order listed, one gate at a
time, because nothing before this documented them.

**The one lesson that would have prevented most of tonight's rework, stated first because it is
the whole point of this file:**

> **`platform/services/_template` is a starting point, not a source of truth. Diff every file
> that matters against a CURRENT REAL SERVICE (`loyalty` or `campaigns`), never against
> `_template` alone.** Nothing keeps `_template` in sync with what real services actually carry —
> it drifts, silently, and each gate below exists specifically because `_template` was stale in a
> way that only shows up once a second service tries to inherit from it.

---

## 0. Before writing a line of domain code

Read `docs/PLATFORM-PLAYBOOK.md` §3B — "Writing a service of our own — the eleven steps." That
section is the authority on ORDER (platform tax first, data model second, and so on). This file
is the authority on the SPECIFIC gaps `_template` currently has, which the playbook's step 1
("Generate from `_template`") does not warn you about.

## 1. Generate, then immediately diff against a REAL service — not the template

**A real generator exists — `platform/scripts/create_service.py`.** It clones `_template`,
drives explicit driver selection (`--cache redis`, etc.), stamps `service.spec.toml` recording
the choice, and self-verifies (pytest + a security gate) before committing, rolling back on any
failure. Read it before doing this by hand.

**It cannot be pointed at this repo.** `ROOT`/`SERVICES` inside it are computed from the script's
own file location (`platform/scripts/../services`), with no `--target`/`--root` flag — it only
ever writes into `platform/services/`, which is read-only to us. `services/loyalty/
service.spec.toml` and `services/operations/service.spec.toml` are the trace of someone running
it upstream, inside a writable platform checkout, and relocating the generated folder into this
repo by hand. Until such a flag exists (worth its own escalation), generating a service here means
the manual steps below — and writing `service.spec.toml` by hand afterward, matching its exact
shape, so the paper trail exists even though the tool that would have written it automatically
could not run against this repo.

**Two placeholder shapes, not one — the real generator's own `replace_placeholders()` handles
both (`text.replace("{service-name}", name).replace("service-template", name)`), and a hand-copy
must too.** The curly-brace form is the one worth stating explicitly: it hides in `.env.example`,
`Makefile`, `Dockerfile`, `pyproject.toml` and every `app/security/*.toml` file — none of which a
`--include=*.py` filter catches, so **do not filter by extension at all**; grep everything.

```
cp -r platform/services/_template services/<name>
grep -rl "{service-name}\|service-template\|service_template" services/<name> \
  | xargs sed -i 's/{service-name}/<name>/g; s/service-template/<name>/g; s/service_template/<name>/g'
grep -rn "{service-name}\|service-template\|service_template" services/<name>   # must be empty
find services/<name> -name "__pycache__" | xargs rm -rf
```

Run the inherited test suite immediately — `tests/unit`, `tests/contracts`, `tests/security`,
`tests/integration` — before touching anything else. If it does not pass out of the box, the copy
was wrong, not the domain.

**Then, before writing anything domain-specific, run these checks and fix everything they find.
Every one of them was red on the first honest attempt:**

### 1a. `SHARED COPY` modules must match a CURRENT service, not the template

```
grep -rl "SHARED COPY" services/loyalty/app          # the modules that must be byte-identical
diff services/loyalty/app/core/pii.py services/<name>/app/core/pii.py
diff services/loyalty/app/core/secret_store.py services/<name>/app/core/secret_store.py
```

If they differ, **copy the real service's version over the template's — do not hand-merge.**
Tonight's concrete case: `_template`'s `pii.py` was missing both the `SHARED COPY` marker line
*and* a real safety check (a guard against hashing an already-hashed pseudonym a second time,
which an erasure request needs to not report false success). The template had simply not been
updated when that guard was added to every real service. Fix:

```
cp services/loyalty/app/core/pii.py services/<name>/app/core/pii.py
cp services/loyalty/app/core/secret_store.py services/<name>/app/core/secret_store.py
```

Gate: `ci/check_a_module_copied_into_every_service_stays_one_module.py` and
`ci/check_a_pseudonym_is_never_hashed_twice.py`.

### 1b. Driver registries carry deprecated drivers the fleet already removed

`_template`'s `app/container.py` and `app/config.py` still register every driver the platform
ever shipped — including ones the fleet has since decided against. Tonight's case: `vault` as a
secrets driver. This product's own decision (k3s secrets are enough; vault was evaluated and
explicitly not chosen) removed `vault` from every real service's `_SECRETS` registry, but
`_template` still imports `VaultSecrets` and lists it as selectable.

**Diff the whole driver-selection block against a current service, not just the modules that
already have a marker:**

```
diff <(grep -A5 '^_SECRETS' services/loyalty/app/container.py) \
     <(grep -A5 '^_SECRETS' services/<name>/app/container.py)
```

Do this for every `_DATASTORE`/`_CACHE`/`_EVENTBUS`/`_QUEUE`/`_OBJECTSTORE`/`_SECRETS`/`_TOKEN`/
`_RATELIMITER`/`_CONSENT_GATE` dict in `container.py`. Remove anything a real service has already
dropped, and its now-dead import and its now-dead `Settings` fields in `config.py`.

Gate: `ci/check_every_shipped_driver_is_held_to_its_contract.py` — but it only catches a
*registered-and-untested* driver, not a registered-and-removed-everywhere-else one. Diffing
against a real service catches both; the gate alone catches only the first.

### 1c. Contract tests must ALSO come from a real service, not the template

`_template`'s own `tests/contracts/test_*_contract.py` files parametrize only the `memory`
variant of each port. A real service's copy adds the real driver (`redis`, etc.) behind an
environment-variable opt-in, so the contract is actually held against production traffic when a
test server is available, and skips honestly — visibly, not silently — when one is not:

```python
_REDIS_URL = os.environ.get("REDIS_TEST_URL", "")
_PARAMS = [pytest.param(lambda: MemoryCache(), id="memory")]
if _REDIS_URL:
    _PARAMS.append(pytest.param(lambda: RedisCache(_REDIS_URL), id="redis"))
```

Copy all six wholesale from a current service:

```
for f in test_cache_contract.py test_event_bus_contract.py test_queue_contract.py \
         test_rate_limiter_contract.py test_secrets_contract.py test_token_verifier_contract.py; do
  cp "services/loyalty/tests/contracts/$f" "services/<name>/tests/contracts/$f"
done
```

Gate: same `ci/check_every_shipped_driver_is_held_to_its_contract.py` as 1b — this is why 1b and
1c must both be done, since fixing the registry without fixing the contract tests just moves the
red line from "driver nothing tests" to "driver still nothing tests, differently."

### 1d. `api/v1/*.py` route files raise where a real service returns

`_template`'s scaffolded route files (`operator.py` is the one that shipped it) use
`raise HTTPException(status_code, str(exc))` for a refusal a PERSON is meant to read. The
platform's global error handler strips `detail` from every raised `HTTPException` on purpose
(CWE-209 — information exposure through error messages), which is correct for a stack trace and
wrong for a sentence we wrote ourselves: it arrives at the caller as `{"error": "BAD_REQUEST"}`
with the actual reason gone.

Fix, mirroring `services/loyalty/app/api/v1/loyalty.py`'s own `_refuse`:

```python
def _refuse(reason: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> JSONResponse:
    return JSONResponse({"error": "BAD_REQUEST", "reason": reason}, status_code=status_code)
```

Replace every `raise HTTPException(..., str(exc)) from exc` written for a person (not a caller
mistake — an auth failure or a malformed request is fine raised) with `return _refuse(str(exc))`.

**The one trap inside this fix, worth stating explicitly because it looked like the "obviously
correct" fix and broke every route in the module:** do NOT widen the route's return annotation to
`-> dict | JSONResponse`. FastAPI tries to build a response model from that union at import time
and fails on every route in the file, not just the ones you touched — the whole service refuses
to boot, with a stack trace pointing at `fastapi/routing.py`, nowhere near the actual change. The
real services all keep the plain `-> dict` annotation even on routes that return a `JSONResponse`
at runtime; FastAPI recognizes an actual `Response` instance at runtime regardless of the
declared type, and only the explicit `Union` in the annotation itself causes the failure. Leave
the annotation exactly as it was.

Gate: `ci/check_refusal_survives.py`.

### 1e. The template ships its own dead `.github/workflows/`

`_template` carries `services/<name>/.github/workflows/security.yml` after the copy. GitHub only
ever reads workflows from `.github/workflows/` at the REPOSITORY ROOT — this nested one has never
run and never will, and reads, to anyone who opens it, as a real pipeline guarding every push.
Delete it; CI for every service is centralized in the root `.github/workflows/services.yml`,
which needs the new service name added to its hardcoded matrix:

```
rm -rf services/<name>/.github
```

```yaml
matrix:
  service: [<name>, campaigns, insights, loyalty, operations, portal, reminders]
```

Gate: `ci/check_a_workflow_lives_where_github_reads_it.py`.

## 2. The licence gate — if this is a sold app

Mirror an existing app's `core/licence.py` exactly (`loyalty` or `campaigns`), not from scratch:
`KEY = "feature.<name>"`, `NullLicence`/`HttpLicence`/`build_licence`, and — the part that is easy
to skip — **decide the read/write asymmetry explicitly before writing the file**: what must fail
closed when billing is unreachable (anything that GROWS a commitment) versus what must never ask
at all (anything that HONOURS one already made). Write that decision as the module's own
docstring, the same way loyalty's does, because it is the whole design and not an implementation
detail.

Wire it in three places, all required:
- `config.py`: `BILLING_SERVICE_URL`, `BILLING_CHECK_PATH`, `PEER_TIMEOUT_SECONDS`, and a boot
  guard (`assert_licence_config_ok`) that refuses to start in production with billing unconfigured
  — mirror `assert_pii_config_ok`'s shape and its placement, and call it from `main.py` alongside
  the other `assert_*_config_ok()` calls.
- `container.py`: `container.licence = build_licence(settings)`, attached after `Container(...)`
  is constructed (it is a plain `@dataclass`, so this is a normal attribute assignment, not a
  declared field).
- A dedicated `tests/unit/test_licence.py`, copied and adapted from an existing service's — every
  test in it, including the two failure-mode ones (fails closed on outage, fails closed on a
  malformed answer) and the two boot-guard ones (refuses in production unconfigured, boots clean
  configured).

## 3. Registering a new paid feature key — two files, both required, or the gate fails

`ci/check_entitlements.py` compares `deploy/seed/plans.json` (what is SOLD) against every
`"feature.*"` string literal in `services/*/app/**/*.py` (what is ENFORCED — your fresh
`licence.py`'s `KEY` already counts) and `apps/console/src/billingShared.tsx`'s `LIMIT_KEYS`
block (what has a sentence to show).

1. `deploy/seed/plans.json`: a new plan row for the app itself, **and** the key added at
   `limit: 0` to **every plan that already enumerates every key** — the base plan and any
   enterprise-shaped plan. "0 is not absence": every existing subscription needs an explicit
   answer for the new key or the console cannot tell "not bought" from "never heard of it." Check
   `ci/check_plans_shape.py` catches a plan that is missing the key entirely, not just a wrong
   value.
2. `apps/console/src/billingShared.tsx`'s `LIMIT_KEYS`: one Arabic sentence, even if the app is
   not launched yet — see below.

**If the app is not actually usable yet (no screen, no working flow): set `"listed": false` on
its plan row.** This hides the plan CARD entirely (`launcher/useAppBilling.ts` filters
`listed !== false` before rendering), so the wording you just added to satisfy the gate never
actually reaches a real customer — but it exists, ready, the day `listed` flips to `true`, rather
than being written under launch pressure. This is not optional: selling a key nothing serves is
the exact mirror of the defect `check_entitlements.py` exists to catch on the other side (a key
enforced with nothing sold).

## 3b. Six more registration lists, all found by `ci/check_deploy_wiring.py` alone

The single biggest gate for this whole exercise — run it early and often, not just at the end.
A brand-new service touches SIX separate hand-maintained lists across the repo, each one a
plain-text roster with no shared source, and missing any one of them is silent (the service
boots, looks healthy, and simply never receives what that list was for):

1. **`app/manifest.py`'s `capabilities: []`** — a template leftover, literally the wrong answer
   by default. If `admin_actions.py` declares operator routes requiring `platform.secrets` /
   `platform.config` (§1d/§2), those capabilities must be listed here or "nobody can ever be
   granted them" — the routes exist, are wired, and are permanently unreachable.
2. **`deploy/hooks/pre-deploy.sh`'s `SERVICES=` list** — creates the Postgres database. Omitted,
   the service starts, passes `/healthz`, and fails on its first write.
3. **`deploy/services/compliance-service.values.yaml`'s `PRIVACY_TARGETS`** — every service an
   erasure (DSAR) request must reach. Omitted, a deletion request silently never arrives here and
   still closes as `COMPLETED` — a breach reported as a success.
4. **`deploy/services/operations.values.yaml`'s `TENANT_DATA_MAP`** — where a shop's data lives,
   the map a service being IN `PRIVACY_TARGETS` (#3) actually depends on: an erasure fan-out reads
   this to know a tenant even HAS data here to erase. Both #3 and #4 are required together, or the
   first is a promise the second never lets fire.
5. **`deploy/services/api-gateway.values.yaml`'s `ADMIN_SERVICES`** — the gateway asks each URL
   here for its `admin_actions`. Omitted, every action declared in step 1d/§2 is real, wired, and
   the console panel simply never asks for them — renders empty, nothing fails.
6. **The new service's own values file mentioning `BACKUP_KEK`** — every service serving
   `/internal/backup/export` needs this SHARED secret named in its own values file (a comment
   plus `# secretRefs: BACKUP_KEK, PII_SALT, INTERNAL_SERVICE_TOKEN` is the convention every real
   service uses — copy loyalty's exact block). Without it the endpoint answers a bare 503 while
   the nightly archive looks complete.

For a brand-new service with no domain routes yet (Stage 1: platform tax only), 1, 2, 3+4, 5 and
6 are all still required the moment the manifest declares `/internal/backup/export` and
`/internal/privacy/erase` — which `_template` does by default, before a single domain route
exists. Do not defer these to "when the domain is built"; they are already load-bearing.

## 3c. A pure, store-free module (`ci/check_dead_core.py`) still needs a real caller

A staged plan can legitimately want one stage to be "just the derivation, pure and testable,
before the store or the route exists" (docs/خطة-تنفيذ-الحجوزات.md's own Stage 2 was written this
way). `ci/check_dead_core.py` does not honor that staging — a `core/` module none of `app/`
imports outside `core/` itself fails the build immediately, tests or no tests: "a module kept 'for
later' is a promise the product does not keep."

**The fix is not to fight the gate — pull forward the smallest honest slice of the next stage
that gives the pure module a real caller.** For an availability-shaped module that will not have
a real store until a later stage, that meant a genuine internal route
(`/internal/availability/check`) that accepts the schedule and busy intervals in the request body
rather than reading them from a store that does not exist yet — still real, still callable, still
tested via `TestClient`, and it becomes the exact interface a peer/console/portal client calls
once the store lands (the design doc's own §7 requirement — "a clean internal interface from day
one" — turns out to already demand this). Nothing about the derivation's own signature changes
later; only where `busy` comes from does.

## 4. Run gates in two halves, not only at the very end

`ci/check_*.py` is ~140 files; running all of them only after every file is written means a
finding from file #3 surfaces after file #140 was already written on top of it. Split the list in
half and run each half as you go — every fix in this document was found this way, not by writing
everything first and debugging a wall of red at the end.

## 5. What this document does NOT cover

The data model, the write path, the read path, attribution, seams, and the five traps — all of
§3B–§4 of `docs/PLATFORM-PLAYBOOK.md`, unchanged and still the authority on those. This file is
specifically the gap between "run `cp -r _template`" and "the platform tax actually passes,"
because that gap turned out to be nonzero and undocumented.
