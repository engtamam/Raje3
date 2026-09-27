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

## Platform-scale infrastructure, piece 2 — populating a service with many real tenants at once

`common/population.py::populate` creates MANY real, independent tenants against one already-
running real service, bounded concurrency (same overload reasoning as `load.py::run_load`), kept
app-agnostic the same way `common/` already is everywhere else: the caller supplies
`make_action(tenant_id) -> Action` (today, `CreateBranchAction`; any other app's own "create my
first real record" action tomorrow, with zero changes to this module). Unlike `run_load` (which
repeats ONE caller `count` times), every invocation here is a DIFFERENT tenant with its own fresh,
isolated `Context` — not a style choice, a correctness requirement, since two tenants must never
share scratch data. Results come back aligned to `tenant_id`, never just completion order, since
"which tenant got which result" is the entire point of this call.

Proven at genuine scale against one real, already-spawned services/operations
(`tests/test_population_scale.py`): 300 real tenants created concurrently, each getting back its
own distinct branch id (never a shared or leaked one), plus a check that a tenant pulled out of
that population afterward behaves exactly like any hand-created tenant (a real `ListOperators`
call against it works). Full simulator suite: 74 passed.

## Platform-scale infrastructure, piece 3 — real background noise alongside a scenario

`common/background.py::run_background_noise` keeps a genuinely independent stream of real traffic
hitting a real spawned service WHILE a scenario's own deliberate action runs — a real platform is
never idle waiting for one scenario alone; other real tenants are always busy at the same time, and
a scenario proven only against a silent service proves far less than the same scenario proven while
the service is genuinely busy. App-agnostic like every other piece here: the caller supplies
`make_action() -> Action` (a fresh instance per tick, typically wrapping an already-`populate`-d
tenant pool), this module knows nothing about what the noise actually does.

An `asyncio.Event`-gated loop, not a fixed per-tick `sleep`: stopping on `async with` exit is
immediate (`asyncio.wait_for(stop.wait(), timeout=interval)` returns the instant `stop` fires),
never waiting out whatever tick happened to be mid-sleep — the scenario's own assertions right
after the block must see the noise already stopped, not still winding down.

Proven for real (`tests/test_background_noise.py`): noise ticks concurrently — measurably more
than zero ticks — while a real scenario action runs alongside it and still gets its own correct
result; and a slow-rate noise loop (a 2-second tick interval) still exits in well under a second
once told to stop, proving the stop is event-gated, not a sleep the caller has to wait out. Full
simulator suite: 76 passed. All three platform-scale pieces (fleet, population, noise) are
complete; resuming work on adding more apps is the next item, not part of this initial build.

## Visit recording wired in (`apps/operations/` — same real service, a different one of its doors)

`RecordVisitAction`/`RecordUniqueVisitAction` (`apps/operations/actions.py`) drive
`POST /api/v1/field/visits` (services/operations/app/api/v1/field.py) — "this endpoint is the
product, as far as the shop floor is concerned" in that route's own words, and the human-operator
door, distinct from `till.py`'s machine-credential door already covered by the branches/staff
module. `service_ids` needs no real catalogue entry to work here: the field door only ever refuses
an EMPTY list or a blank id (`allow_unknown_services` stays False on this path in
core/operations.py) — a made-up id is simply priced at 0, exactly like a shop that typed a
service's name before saving its catalogue row.

Proven for real (`tests/test_stage11_visits.py`): a visit round-trips a genuine customer and visit
record (phone normalised to E.164 by the real service, not echoed raw); an empty service list is
refused cleanly (HTTP 422 from `VisitIn`'s own `min_length=1`, never a crash); the SAME
idempotency-key race this project already proved once for referrals holds here too — 12 concurrent
callers recording the identical sale under one key get back the SAME visit id, never 12 counted
visits for one customer who tapped save once; and a load run of 40 independent new-customer visits
reports a clean 0% error rate. Full simulator suite: 80 passed.

## Mobile/on-the-go service-request queue wired in (`apps/operations/mobile_requests_actions.py`)

A technician sent TO the customer rather than the customer coming to the shop
(`app/api/v1/mobile_requests.py`) — the shop's own manual create door plus the full review-queue
lifecycle: create → assign → accept/reject → complete/no-show. Two capability tiers, matched
exactly as that route file's own docstring describes: `operations.mobile_requests_manage` (the
full queue, any request) and `operations.mobile_requests_execute` (a field operator's scoped half
— list and complete/no-show only their OWN assigned request, enforced server-side via
`expected_assignee`, never trusted from the caller's own claimed identity). Every action here takes
an explicit `caller_subject`/`caller_caps` (the same shape `ListOperatorsAction` already uses) —
this queue's whole design is WHO is calling, so proving the manager/execute split apart needs a
different identity per call, never one fixed one.

Proven for real (`tests/test_stage12_mobile_requests.py`, 6 tests): the full lifecycle from create
through complete records a genuine Visit with its own visit id; a rejected request refuses a later
accept rather than allowing it; a no-show never carries a visit id; an execute-tier operator can
complete only their OWN assigned request — a DIFFERENT operator's attempt on the same request is
refused, not silently no-op'd; two operators each assigned a different request see only their own
in `list`, never each other's; and a manager sees everything regardless. Full simulator suite: 86
passed.

## Generating Actions FROM a route's own schema (`common/autogen.py`)

The answer to "why do we write the scenario — can't the simulator understand the app and generate
the actions itself?" Two different things were being conflated: WHICH routes exist (already
smart-linked — `common/discovery.py` reads `user_actions.py`/`admin_actions.py` directly) versus
WHAT VALID CALL to make (a schema alone can say a field is a 3-32 char string; it cannot say it
should look like a Saudi phone number, or that a mobile request needs a branch to exist first —
business-meaningful, multi-step scenarios stay hand-written, same `apps/<name>/actions.py` files
this session already built).

`autogen.py` automates the MECHANICAL part a schema fully determines: it reads a spawned service's
own LIVE `/openapi.json` (the smartest possible link — not parsed source, the running app's own
answer to "what do you accept", the same document this repo's generated SDKs already come from;
`ENV=test`, which every spawned service boots with, is what keeps it switched on — `main.py`
disables it only in production), matches each declared route from `discovery.py` to its real
request-body schema, and generates ONE schema-valid instance per required field (boundary-aware:
nearest to a field's own minimum/length, never a full property-based search — that duplicates
Schemathesis' own job on a spec, not something to reinvent here) — a single, real HTTP call needing
zero hand-written code per route.

An auto-generated call can only honestly claim one thing: the route did not CRASH. A well-formed
but business-meaningless body (a random phone, a made-up service id) is routinely and correctly
refused (4xx) by a rule this generator knows nothing about — that is success for THIS purpose.
503 is excluded from "crash" too, deliberately: this codebase's own documented posture, seen
already in several routes this simulator drives (till.py's licence check, field.py's PDF export,
subscription's own checkout) is "an unreachable PEER refuses cleanly (503) rather than guesses",
and a route under test here has no billing/pdf-conversion/payment peer behind it at all — so a 503
is that exact, correct, by-design refusal, not a bug. Only a genuine 500 is `ok=False`.

Proven for real (`tests/test_stage13_autogen.py`): a body generated purely from `/api/v1/field/
visits`'s own live schema — never hand-typed — is accepted by the real route (HTTP 201); and every
declared, parameterless route in services/operations' real catalogue (dozens, discovered, not
listed by hand) is auto-called with its own generated body and none of them 500 — the first run
surfaced real 503s from exactly the peer-dependent routes named above, confirmed as the
by-design refusal rather than a defect before excluding them. Full simulator suite: 89 passed.

## Two real gaps closed together (`tests/test_stage14_integration.py`)

Two things this session had proven only apart, never together, closed with two more tests:

1. **The mobile-requests app's own BRANCH dimension, with REAL hired operators.**
   `test_stage12_mobile_requests.py`'s own manager/execute split used made-up operator ids
   (`"op-a"`, `"op-b"`, ...) that resolve to no real Operator row at all — `_operator_branch`
   always answered `""` (unassigned, always visible), so branch narrowing was never actually
   exercised for this app, only capability-tier narrowing. Here a real Fleet (identity+operations)
   hires a real manager scoped to branch A (`visible_branch_ids`) and a real technician at branch
   B, assigns a request to that technician, and proves the branch-A manager never sees it while
   the unnarrowed owner still does — the exact branch-scoping discipline `branches.py`'s own
   module docstring describes, now proven for this app too, not assumed to carry over.
2. **Visit recording running ALONGSIDE the platform-scale pieces, not alone.** A real Fleet, a real
   `populate`-d pool of 10 tenants, real background noise (`RecordUniqueVisitAction` ticking
   against that pool), and the scenario's own deliberate visit recording running concurrently with
   all of it — proving the pieces compose the way `population.py`/`background.py`'s own
   "app-agnostic" design claims, not just each piece proven alone.

Full simulator suite: 91 passed.

## A real, safe speed-up (`common/httpclient.py`) — and two attempts that were NOT safe

The suite runs real uvicorn subprocesses per test, so it is slow by design — that cost buys the
whole premise (see the top of this README). Two speed-ups were tried and reverted; one was kept:

- **Kept: pooled HTTP connections.** Every Action used to open a brand-new `httpx.AsyncClient()`
  per call — fine at low volume, but a load/population/noise run already fires hundreds of
  individual short-lived connections at one spawned service within seconds, and none of them were
  ever reused. `common/httpclient.py` pools ONE client per (event loop, origin) pair via a
  `WeakKeyDictionary` keyed on the loop object itself (never `id(loop)` — Python can and does
  reuse a closed loop's integer id for a brand new one, which would silently hand a fresh loop a
  dead client). Applied across every Action/check/matrix-sweep call site. Real, measured, safe:
  full suite time roughly halved (257s -> 130s), zero behaviour change, 91/91 still passing.
- **Reverted: one server shared across an entire test session.** Every test spawning its own
  server is most of the suite's own wall-clock cost, so sharing one across many tests looked like
  the obvious win. First attempt (session-scoped, shared across ALL files) failed with
  intermittent `ConnectError`s under cumulative load. Second attempt (module-scoped, one server
  per FILE, tried again after the pooling fix above) failed just as hard, and traced to something
  more fundamental than load: `asyncio.run()` calls `loop.shutdown_asyncgens()` on exit, which
  sends `GeneratorExit` into ANY async generator still suspended in that loop — including
  `run_service`'s own generator sitting at its `yield`, whose `finally` block terminates the
  spawned process. A fixture that enters a service with one `asyncio.run()` call and exits it with
  a LATER, separate one has the server torn down the instant the FIRST call returns, before any
  test ever runs against it. Making a shared server survive this would need its own persistent
  background event loop (a dedicated thread), a real, separate piece of infrastructure — not a
  quick fixture — so it was reverted rather than half-built. Every test in this suite still spawns
  its own server, and that is intentional, not an oversight.

## A genuinely SECOND real app: services/loyalty (`apps/loyalty/`)

Every app before this one was another door on services/operations — proving the pieces work
together says nothing about whether `common/`'s own "app-agnostic" claim is real, or just true by
accident because operations was the only app that ever exercised it. `services/loyalty` is a
wholly separate real service (own process, own datastore, own capabilities) — its own
`assert_peers_config_ok`/`assert_licence_config_ok` boot guards only fire in production, so
`ENV=test` (every spawned service's own default) lets it spawn standalone with no billing/
reminders/tenant peer wired in.

`EarnPointsAction` drives the INTERNAL door (`/internal/loyalty/earn`, `X-Internal-Token`) — the
same one the real event bus/catch-up calls, and the ONLY way a point ever enters the ledger (no
public "grant yourself points" route exists, by design). Every other action
(`BalanceAction`/`RedeemAction`/`AdjustPointsAction`/`CreateRewardAction`/`SetGeneralPointsAction`)
drives the ordinary `/api/v1/loyalty/*` capability-gated door.

A REAL GAP THIS OWN FIRST RUN FOUND, in the ACTIONS not the platform: a fresh tenant starts with
NOTHING configured in its earning tree, and `service_ids=[]` (this simulator's own usual
"no real catalogue needed" convention, borrowed from `RecordVisitAction`) earns ZERO regardless —
`EarnTree.points_for` sums a rate PER SERVICE ID in the list, so an empty list sums nothing no
matter how high the general rate is set. Fixed by giving `EarnPointsAction` the same non-empty
default `service_ids` `RecordVisitAction` already uses, and adding `SetGeneralPointsAction` so a
scenario configures a real earning rule first, the same as an owner would from the settings screen
before a single visit is ever recorded.

Proven for real (`tests/test_stage15_loyalty.py`, 4 tests): earning against a real visit grows the
real balance by exactly the configured rate; 8 concurrent deliveries of the SAME `visit_id` earn
points exactly ONCE (only the first carries a `balance` in its own response — every later one is a
documented `{"earned": 0, "duplicate": True}`, not a gap); a full earn -> create-reward -> redeem
lifecycle lowers the real balance by the reward's own cost; and a manual adjustment can never push
a balance negative. Full simulator suite: 95 passed.

## The simulator composing its OWN scenario (`common/story.py` + `apps/operations/story.py`)

Every scenario before this one was a human hand-ordering real Actions ("create a branch, THEN
hire, THEN visit"). This is the missing piece: given a CATALOG of `StoryStep`s, each honest about
what world state it needs (`eligible`) and what it changes (`after`), the composer itself decides,
at every step, which moves are even valid right now and picks among them — never a fixed order,
never an invalid call (assigning a request that does not exist yet).

DELIBERATELY NOT A GENERAL PLANNER — no goal, no lookahead, no backtracking, plain STRIPS-style
preconditions only. Composing a realistic, valid, MULTI-STEP business narrative on its own is the
win; inventing a genuinely new business goal is a different, harder problem this does not claim to
solve. App-agnostic like every other `common/` piece: `apps/operations/story.py` is the first real
step catalog, built entirely on Actions this session already hand-wrote and proved — no new HTTP
logic, only the CHOICE of when each one is a valid move. Self-contained on purpose (no
`hire_member`/branch-scoping steps — that combination is already proven elsewhere), so it runs
against one spawned services/operations with no identity-service peer needed.

Proven for real (`tests/test_stage16_story.py`): a single run picks a real, varied, 10+-move
narrative touching several distinct kinds of moves, with EVERY single one of the composer's own
choices a genuinely valid call (never refused); two different random seeds produce two different
move SEQUENCES (proving this is genuinely composed, not a fixed script wearing a random label);
and a long enough run drives at least one of its own created mobile requests all the way to a real
terminal status. Full simulator suite: 98 passed.

## A third real app: services/bookings (`apps/bookings/`) — the first one that NEEDS a real peer

Every app before this one could spawn and do something meaningful alone. Bookings genuinely
cannot: `create()` asks operations over real HTTP for TWO real answers before it will write
anything — a service's own configured duration in minutes (`POST /internal/operations/
service-durations`) and whether `customer_id` resolves to a real customer at all (`POST /internal/
operations/customers/subject-ref`) — so every test here spawns a real `Fleet` (operations +
bookings), proving `common/fleet.py` composes with a THIRD real app, not just the two it was built
against.

A REAL GAP THIS OWN FIRST RUN FOUND, in the actions again, not the platform: this simulator's own
usual "a made-up id is fine, no real catalogue entry needed" convention (used safely everywhere
else — `RecordVisitAction`'s service ids, `AssignMobileRequestAction`'s operator id) does NOT hold
for bookings' own `customer_id`, because bookings genuinely calls out to verify it. Fixed by adding
`EnsureCustomerAction` (operations' own `POST /api/v1/field/customers/ensure`) so a scenario gets a
REAL customer id first — the same lesson `EarnPointsAction`'s empty `service_ids` taught for
loyalty, a different app, the identical shape of mistake: this simulator's own conventions are
per-app facts, never something to assume carries over.

Proven for real (`tests/test_stage17_bookings.py`, 5 tests): a made-up `customer_id` is refused by
name, and a real, `ensure`-d one lets the identical booking through; an unconfigured (0-minute)
service refuses a booking by name too; a full create -> list -> reschedule -> attend lifecycle
works end to end; the one guarantee a bookings product actually sells — two customers can never
both be told the same technician is free at the same time — holds for real (the second of two
identical-time bookings for the same operator is refused); and cancelling a booking correctly
refuses a later no-show on it. Full simulator suite: 103 passed.

## Mutual-benefit (shop-to-shop referral partnership) — a real, honest environmental limit found

Another operations door (`apps/operations/mutual_benefit_actions.py`, `/staff/mutual-benefit/*`).
Its own `propose()` checks a real billing/plans peer BEFORE it ever looks up `shop_b_phone` —
every operations instance this simulator spawns boots with the default `NullPlans` driver (no
`BILLING_PLANS_DRIVER=http` anywhere in this fleet yet), whose own docstring names the choice
explicitly: "a trial of zero is the strict default ... the permissive default would let an
unconfigured deployment take money for a plan nobody can read." So `propose()` is CORRECTLY,
provably gated shut in every environment this simulator currently builds — proven, not a gap to
paper over.

GOING FURTHER — SignupShopAction (`POST /api/v1/signup`, needed to register a real owner phone
in `PHONE_INDEX` so `_lookup_tenant_by_phone` can ever resolve a real shop_b) is written and real,
but not yet usable: `open_shop` itself calls out to a THIRD real peer, `TENANT_SERVICE_URL`
(`platform/services/tenant-service`), which no `apps/` module spawns yet. A full propose ->
accept lifecycle needs a real four-service Fleet (identity + tenant-service + billing-service +
operations) — a real, larger piece of future work, named here rather than faked around.

Proven for real (`tests/test_stage18_mutual_benefit.py`): proposing a partnership with no billing
peer configured is refused with a clean HTTP 402, never a crash; and listing agreements for a
tenant that never had any returns a clean, empty, real list. Full simulator suite: 105 passed.

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
