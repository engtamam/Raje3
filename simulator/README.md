# Simulator

A composable scenario simulator for exercising this platform's REAL services — not mocks, not unit
tests — to catch races, load pressure, security misuse, and edge cases that only show up when real
processes talk to each other over real HTTP against a real datastore.

## Why this exists

Unit tests (this repo has thousands) prove one function's logic in isolation. They cannot catch a
race between two concurrent requests hitting a real running server, or what happens to a real
Postgres connection pool under load, or whether a scenario that spans two services (e.g. referrals
+ operations) behaves correctly end to end. This project's own history has a concrete example: a
usage-cap bug in the referral system was invisible to `asyncio.gather`-based unit tests against an
in-memory datastore (which has no real `await` between steps, so nothing ever truly interleaves) and
was only found by reasoning about REAL concurrent HTTP callers. The simulator's whole point is to
make that kind of bug reproducible and automatic instead of something a human has to reason about by
hand.

## Building block by block

This is being built incrementally, one small piece at a time, confirmed before moving to the next.
Do not assume anything beyond what is actually in this folder right now — check the code, not this
paragraph, for current status.

**Status: stages 1-4 done.** `common/action.py` defines `Action`/`Context`/`ActionResult`;
`common/engine.py::run_one` runs exactly one action and returns pass/fail, catching any crash so
it never takes the engine down (6 tests in `tests/test_stage1_engine.py`). `common/scenario.py`
chains multiple actions into one ordered, fail-fast run sharing a single Context — built entirely
on top of `run_one` with no changes to it (7 tests in `tests/test_stage2_scenario.py`, including
proof that a later step reads what an earlier one wrote). `common/execution.py::run_concurrent`
runs the same, unmodified action genuinely in parallel (`asyncio.gather`) — proven real (not a
disguised sequential loop) by timing, and proven to actually surface a real lost-update race on a
shared, unlocked Context (deterministically, via a `sleep(0)` yield point), with a locked version
of the same action proving the fix the same way (6 tests in `tests/test_stage3_execution_modes.py`,
stable across repeated runs — no flakiness).

`common/environment.py::run_service` spawns a REAL `uvicorn` subprocess on a free port, waits for
a real `/healthz` 200, hands back a `ServiceHandle` an action can hit over real HTTP, and always
tears the process down afterward — success, failure, or an exception raised inside the block, all
take the same teardown path. Proven against a tiny, self-contained toy FastAPI app
(`tests/fixtures/toy_service/`, used only so stage 4 doesn't need this project's real services'
full config/secrets to prove the mechanism — a real project service is stage 5's own job): a real
process boots and answers real HTTP, teardown happens even when the caller raises, two services
get independent ports and don't collide, and a genuinely broken app import fails with the
process's own stdout attached rather than a bare connection error. `BlastRadius` (a scenario's
declared allowed tenant, checked against a real value) and `RollbackOnFailure` (runs only on
failure, before the exception propagates, distinct from ordinary teardown) are both proven too,
including BlastRadius checked against a real HTTP response from the real spawned service (9 tests
in `tests/test_stage4_environment.py`, 28 total across all four stages so far).

**Stage 5 — the proof stage — is done.** `apps/operations/` spawns a REAL, unmodified
services/operations (stage 4's own `run_service`) and drives it with real Actions
(`AddAffiliateAction`, `RegisterReferralAction`) over real HTTP — no shortcuts through the
service's own Python code. `shared/auth.py` mints real, verifiable JWTs; `shared/service_env.py`
holds the base boot env every service in this fleet needs. Composed with stage 2's `Scenario` and
raced with stage 3's `run_concurrent`, this reproduces — automatically, against a real running
server — the exact shape of the double-registration race this project found and fixed by hand
earlier this session (`_REGISTER_LOCK` in `referral_redemption.py`): N genuinely concurrent HTTP
callers register the SAME code for the SAME beneficiary phone, and the real invariant (exactly ONE
grant ever gets created, independently verified through the real reporting endpoint's own
`registered_count` — register() is deliberately idempotent, so "how many callers reported success"
is NOT the same question) is confirmed to hold — repeated 3 times to rule out a fluke. 6 tests in
`tests/test_stage5_first_real_action.py`, 34 total across all five stages so far.

**Stage 6 — faults — is done.** `common/faults.py::unreachable_url` is the one truly generic
fault (a real closed socket — a genuine ECONNREFUSED, no domain knowledge needed). `apps/
operations/faults.py::fake_referrals_peer` is a REAL, controllable, running stand-in for
services/referrals' own internal API (a real FastAPI fixture, `tests/fixtures/fake_referrals_
peer/`) with three real modes — healthy, slow (sleeps past `ReferralsDesk`'s own fixed 5s
timeout), garbled (200 with an invalid-JSON body) — none of it a Python-level mock patched into
operations' own process. The SAME, unmodified `RegisterReferralAction` from stage 5 is run against
all three broken states plus a healthy control: an unreachable peer, a real 5s timeout genuinely
hit (elapsed time asserted, not assumed), and a garbled response are all turned into the SAME
clean `ReferralsPeerUnavailable` refusal — never a crash, never a hang — while the healthy control
proves that refusal is specifically about peer health, never a message that fires regardless (4
tests in `tests/test_stage6_faults.py`, 38 total across all six stages so far).

**Stage 7 — checks — is done.** `common/checks.py` defines four checks that take a plain
(method, url, headers, body) — never a specific Action class — so any future action, in any app,
gets them for free: a forged-signature refusal (401), a missing-capability refusal (403, kept
distinct from a signature failure), an adversarial-input refusal (never a 5xx), and a cross-tenant
isolation check (the same URL, two tenants' own real tokens, tenant B must never see tenant A's
data). Proven genuinely generic by running the SAME four functions against TWO entirely different
real routes (add-affiliate and till-register) with no route-specific check code anywhere (8 tests
in `tests/test_stage7_checks.py`, 46 total across all seven stages so far).

**Stage 8 — observation, tolerances, and load — is done. The full 8-stage build plan is
complete.** `common/report.py::Report`/`summarize` aggregates a batch of results into counts,
error rate, and latency figures (mean/p95/max) — answering `None` for every latency figure when no
timing was captured, never a fabricated number. `Tolerance` is the explicit pass/fail gate against
a Report (Chaos Toolkit's own "steady-state hypothesis + tolerance" pairing), proven to both PASS
a healthy report and genuinely FAIL an unreasonable one, naming exactly which figure it failed on.
`common/load.py::run_load` repeats an action at real scale under BOUNDED concurrency (proven
distinct from stage 3's unbounded `run_concurrent` by timing: real batches, not all-at-once and
not sequential), with real per-invocation timing `run_concurrent` never captured. The full
pipeline — load, against a REAL running services/operations, through 30 independent new customers
(`RegisterUniqueReferralAction`, a fresh random beneficiary phone per call, composing stage 5's
own `RegisterReferralAction` rather than duplicating it) — is summarized and checked against a
real tolerance that passes, and the same real report is checked against a deliberately unreasonable
one that correctly fails (13 tests in `tests/test_stage8_observation_and_load.py`, 59 total across
all eight stages).

## Where this stands now

Every stage in the original build plan is built and proven, each on top of the last, with zero
changes to an earlier stage required to add a later one — the composability the whole design was
meant to test for itself, not just claim. `simulator/apps/operations/` is the one app wired in so
far; the taxonomy (`apps/<name>/` per real service) is what the next app (referrals, or any other
service) plugs into without touching anything in `common/` or `shared/`. Scaling this out to more
apps, more scenarios, and a genuinely adversarial/security-focused scenario library is future work,
not part of this initial build.

## Roles/capabilities module (built after the 8-stage plan, same principles)

Research first (see the design discussion this was built from): every existing CI gate around
roles/capabilities is STATIC analysis (do the two role-seed files agree, does the owner hold every
capability, is every capability reachable by someone) — confirmed as a real, load-bearing set of
guards (`ci/check_roles.py`, `ci/check_deploy_wiring.py`'s own guard 14, `ci/check_capability_
truth.py`), but NOTHING actually calls every route as every role over real HTTP and watches what
happens. This module is that missing dynamic check, and it is deliberately "smart-linked" to the
real code rather than hand-maintained:

- `shared/roles.py::load_roles` reads `deploy/seed/roles.json` directly — a new role, or a new
  capability grant to an existing one, is picked up the next time this runs, zero edits here.
- `common/discovery.py::discover_actions` reads a service's own `app/user_actions.py`/
  `admin_actions.py` (the exact `ast.literal_eval`-safe parsing every other catalog gate in this
  repo already uses) — a new declared route is picked up the same way.
- `common/rbac_matrix.py::check_action_against_every_role` is the actual check: a role holding the
  route's declared capability must never get 403; a role without it must always get 403.

Run for real against services/operations' own catalog (119 real declared actions discovered, not
a fixture), this surfaced a genuine, useful limit of the single-capability model itself — not a
platform bug: a handful of real routes are gated by `require_any_capability` (an OR the
declaration only names one side of), or declare a capability purely for catalog grouping with no
real enforcement (both admitted in the real source's own comments), or need an identity claim
beyond any capability (`partner.*`). These are a short, source-documented allowlist in
`tests/test_stage9_rbac_matrix.py` — every OTHER action in the sweep is asserted strictly, so a
genuinely new mismatch anywhere else is caught, not hidden (5 tests, 64 total across the whole
simulator now).

As agreed when this was scoped: this stays an on-demand deep tool (it spawns a real server), not a
fast per-commit gate — a lightweight static "every capability is reachable by someone" check
already exists in `ci/check_deploy_wiring.py`'s own guard 14, so nothing new was needed there.

## Branches module — and a real bug it found on its first real run

`apps/identity/` spawns a REAL `platform/services/identity-service` alongside services/
operations — needed because branch-scope isolation can only be tested with a REAL login
(`person_id`), which the four-digit PIN never provides (attribution only, never authentication).
`apps/identity/directory.py::lookup_person_id` resolves a hired phone to its real `person_id` via
identity's own internal member directory, since `hire_member`'s own HTTP response deliberately
never returns it (a real privacy boundary, not a gap this module works around). New Actions:
`CreateBranchAction`, `HireMemberAction`, `SetOperatorScopeAction`, `ListOperatorsAction` — all
real HTTP against services/operations' real `staff.py` routes.

**Run for real, this immediately found a genuine, live security bug — not a simulator artifact
(`tests/test_stage10_branches.py`'s own capstone test):** stopping an employee
(`update_operator`) blanks their `person_id` (so nothing later mistakes the row for a live login)
— but left NOTHING behind for `api/scope.py::branch_scope` to match a dismissed employee's own
still-valid, unexpired JWT against (revoking their membership at identity does not invalidate a
token already issued). That lookup fell through to "no row for this subject at all", which reads
as UNASSIGNED — the same answer an owner gets — widening the person just stopped to see every
branch. The exact regression `branch_scope`'s own docstring already named as fixed once, reopened
by a later, unrelated change (blanking `person_id`).

**Fixed for real, immediately, in the actual platform code** (not just in the simulator):
`Operator.revoked_person_id` (core/models.py) is where that identity now moves to instead of
vanishing; `update_operator` sets it the same moment it blanks `person_id`; `branch_scope` checks
it as a second, explicit match. Proven at three levels: the simulator's own end-to-end HTTP test,
a new unit test on `branch_scope` itself constructing the exact shape a stop leaves behind
(`test_branches.py`), and a new route-level test on `update_operator` proving the field is set
correctly (`test_operator_api.py`) — 290 existing operations tests re-run clean, full suite green
(2599 passed), `check_deploy_wiring.py` clean.

## Platform-scale infrastructure, piece 1 — running a fleet of real services together

Before adding more apps, the platform itself needs to feel real: many real services running
together, wired to each other automatically, so a new app plugs into a busy platform instead of an
empty sandbox. Piece 1 of that (a bulk tenant/population generator and real background "noise"
activity are pieces 2 and 3, not yet built): `common/fleet.py`.

Every `apps/<name>/service.py::spawn(*, port=None, extra_env=None)` already exists — a fleet is
just a list of `ServiceSpec(name, spawn, needs={ENV_VAR: "other service's name"}, extra_env={...})`.
`run_fleet` topologically sorts them (a post-order DFS — `FleetCycleError`/
`FleetUnknownDependencyError` refused up front, before anything spawns, never discovered as a
missing env var deep inside some other service's own boot failure), spawns each only once every
service it needs is already up and healthy, resolves each `needs` entry to that dependency's real
`base_url` automatically, and tears every one down together in reverse order the moment the
fleet's own `with` block exits — success, failure, or an exception raised inside it, the same
teardown guarantee `environment.py::run_service` already gives one process, extended to however
many a scenario asks for.

Proven against the same two real services `test_stage10_branches.py` already wired by hand
(identity + operations): the fleet-wired pair hires a real member end to end through
`IDENTITY_SERVICE_URL` resolved automatically, with none of that manual base_url-passing
(`tests/test_platform_fleet.py`, 5 tests — the happy path, partial-teardown-on-failure via a
side-channel wrapper since a failing `__aenter__` never binds `fleet` in the caller's `with` body,
unknown-dependency refusal, cycle refusal, and a fleet of one). Full simulator suite: 72 passed.

## The taxonomy

Validated against real precedent (Chaos Toolkit, Gremlin, LitmusChaos, Locust/Gatling, Hypothesis,
Schemathesis — see the design discussion for sources) before committing to it. Every piece below
composes onto an action without the action itself knowing about it — the same principle real chaos
and fuzzing tools use (decorator-style wrapping, never baked into the business logic being tested).

- **Engine** (`common/`) — not a component itself, the frame everything else runs inside. Owns no
  domain knowledge, never imports from `apps/`. Knows how to compose an action with an execution
  mode, an optional fault, and optional checks, run the result, and collect it.
- **Actions** — the real business step ("record a visit", "register a referral code"). Split into:
  - `shared/` — reusable across MULTIPLE apps (minting an auth token, generating a fresh isolated
    tenant id) — knows this platform's conventions, not any one app's domain logic.
  - `apps/<name>/` — one folder per real service, that app's own actions only.
- **Execution modes** (`common/`) — how an action runs, independent of what it is: solo, real
  concurrency (many callers at once), load (repeat at scale, a shape/ramp over time), artificial
  slowness. Matches Gatling's scenario-vs-injection-profile split and Locust's LoadTestShape.
- **Faults** (`common/faults.py` + per-app fault definitions) — a deliberately broken dependency, a
  slow/garbled response, corrupted upstream data. Named "faults" to match LitmusChaos's own term for
  an atomic, injectable break (as opposed to a whole composed chaos experiment).
- **Checks** — a generic pass/fail rule applicable to ANY action regardless of domain: a forged
  token, a cross-tenant/cross-branch boundary jump, an adversarial/injection input, rapid replay of
  the same request. Named "checks" to match Schemathesis's own term for schema/endpoint-agnostic
  validations.
- **Observation** (`common/report.py`) — capturing what happened (latency, error rate, DB pressure)
  AND the pass/fail tolerance against it (a "steady-state hypothesis" in Chaos Toolkit's terms) —
  the two travel together, not left for a human to eyeball separately.
- **Environment** (`common/service_process.py`) — spinning up a real service process and a real
  database, and tearing both down afterward. Two safety primitives borrowed from real chaos tooling
  that we are treating as first-class here, not an afterthought:
  - **Blast radius** (Gremlin's term) — every scenario must declare which tenant/branch/data it is
    allowed to touch, so an adversarial/security scenario can never drift into real data by accident.
  - **Rollback-on-failure** (Chaos Toolkit's term) — distinct from ordinary teardown: if a fault
    injection fails mid-scenario, there is an explicit "leave the system clean" step, not just
    "delete what we made at the end."
- **Scenarios** (`scenarios/`) — the actual recipes: take one or more actions (shared and/or
  app-specific), wire an execution mode + optional fault + optional checks around them, and run.

## Build plan (each stage confirmed before the next)

1. **Empty engine** — runs one plain action, returns pass/fail. Nothing else.
2. **Composition** — chain more than one action into a single ordered scenario.
3. **Execution modes** — add "run this same action concurrently" on top of an existing action,
   without touching the action itself — proves the separation actually holds.
4. **Real environment** — spin up a real running service (a real process) + blast-radius scoping +
   teardown/rollback.
5. **First real action** — one real action from the referrals app (likely the same registration
   path whose usage-cap race we already found this session), run through all of the above. The
   proof stage: if this works, everything after is an addition on a proven foundation.
6. **Faults** — deliberately break something (a dependency down, a slow reply) on top of the same
   action.
7. **Checks** — the generic security checklist (forged token, cross-tenant jump, adversarial input),
   applicable to any action.
8. **Observation, tolerances, and load** — capture results with explicit pass/fail tolerances, and
   the ability to repeat a scenario at real scale.
