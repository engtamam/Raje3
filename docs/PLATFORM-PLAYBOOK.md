# Building a platform on `base-services` — the method

**Who this is for.** An autonomous engineering agent that has been handed two files:

1. **A product description** — what to build and why, in the product owner's words.
2. **This document** — how to build it.

Nothing else is assumed. No prior context, no running system, no one to ask between steps.

**The claim this method makes.** Almost everything a SaaS platform needs already exists in
`base-services` — identity, tenancy, authorization, audit, billing, notifications, scheduling,
storage, analytics, compliance, search, e-invoicing, and more. What does not exist, and never
will, is the handful of services that make *your* product what it is. So the work is: consume
the platform by configuration, build only the domain, and prove every step against a running
system rather than a green dashboard.

This method was extracted from doing it. Every rule below is here because something went wrong
without it.

---

## 0. The three-sentence contract

> Consume `base-services` as published container images. Adapt it with **config, environment
> variables, and Helm values — nothing else, ever**. Build only your own domain services on top.

If you are about to write authentication, multi-tenancy, RBAC, billing, notifications, job
scheduling, analytics, audit logging, file storage, consent management or an API gateway —
**stop**. It exists. Configure it.

If the platform genuinely lacks something **generic**, report it upstream and work around it
behind a port on your side. Never patch. A local edit cannot be released, is lost on the next
version bump, and makes your deployment diverge from the images you actually run.

---

## Phase 1 — Read, then plan (do not write anything yet)

### 1.1 Read the product description completely

Not skimmed. Completely. Then write down, in your own words:

- Every **actor** and what each one can do.
- Every **entity** and what owns it.
- Every **hard constraint** — a latency budget, a regulatory rule, an isolation guarantee.
  These outrank features; they cannot be traded away later.
- Every **number** — plan prices, retention windows, limits. Note which are examples and which
  are requirements. Ask if it matters and you cannot tell.

### 1.2 Inventory the platform

List every service `base-services` provides. For each, write one line: *what it is, and whether
this product needs it*. Do not guess from the name.

### 1.3 Map requirement → service, and defend every mapping

For each requirement in the description, name the service that satisfies it. Three outcomes:

| Outcome | What it means | What to do |
| --- | --- | --- |
| A platform service covers it | Most requirements | Configure it. Nothing is written. |
| No service covers it, and it is **generic** | Rare | Request it upstream. Adapter on your side meanwhile. |
| No service covers it, and it is **domain** | Your actual product | Build it. This is the only code you write. |

**The mapping is where this method most often fails, and the failure mode is always the same
shape:** a service's name suggests a familiar concept, you map a requirement onto it, and the
service turns out to be something adjacent but materially different. Two patterns to expect:

- **A name that matches your domain word but not your domain meaning.** A "wallet" may be a
  currency-and-tax ledger rather than a points system; a "search" may index documents rather than
  people. If a service carries currency, tax rates, or units in its config, it is about money —
  and bending a money ledger into a rewards scheme attaches tax semantics to a free gift.
- **A name narrower than the thing.** A "notification" service is rarely one channel. Assuming it
  is the channel your product cares most about hides the other three — and hides which *other*
  services already depend on those channels, such as an account-verification flow you have not
  written yet.

Neither is caught by reading a summary; both are caught in about ten minutes of reading the
service. Two cheap tells: **the config knobs** (currency and tax basis points mean money;
plural `*_CHAIN` settings mean multiple channels) and **who else already points at it** — grep the
other services for its URL before you decide what it is for.

**Open the service before you claim what it does** — see §3.1.

### 1.4 Produce the plan

Output, before any file is written:

- **Wave order** for platform services, with a one-line reason for each position.
- **Your domain services**, with what each owns, expressed in the product's vocabulary.
- **Known gaps** — anything you will have to request upstream.
- **Open questions** — decisions the description does not settle. Ask them now, together, not
  one at a time over three days.

Then get the plan agreed before building. A wrong wave order is discovered four services later.

---

## 2. Wave order — and why it is not arbitrary

Bring services up in dependency order, one at a time, each verified before the next.

| Wave | Services | Why here |
| --- | --- | --- |
| **0** | Cluster, CNI, metrics, datastores | Nothing runs before these. Prove policy enforcement now. |
| **1** | tenancy → authorization → identity → audit | Tenancy is the source of truth; authz decides; identity issues; audit is the log the other three write to. Audit is **last** — first would mean an empty sink nobody had tested against. |
| **2** | gateway · scheduler · storage | The only public door; background work; blobs. |
| **3** | compliance → notification · feature flags | See below. |
| **4** | analytics · wallet · billing | The commercial layer. |
| **5** | support · onboarding · backup · search | Operations. |
| **6** | e-invoicing · webhooks · connectors · assistant · verification | On demand. |
| **7** | **Your domain services** | Last. Everything they lean on exists and is proven. |

**The order above is a starting point, not a fact.** At least one dependency will contradict it,
and the way you find out matters. A well-built service often has a **boot guard**: it refuses to
start in production when a driver it depends on is left at a safe-but-inert default. That guard is
a dependency declaration — it says, in code, "this other service must exist first" — and it is
cheaper to read than to discover by watching a pod fail to start.

**Rule:** before fixing a wave order, grep the services for their boot guards (`assert_*_ok`,
fail-fast validators, anything raising at startup). Each one you find either confirms the order or
corrects it. Expect one or two corrections per platform, and expect the source to be right.

**Your own services go last.** They are the only thing nobody else can build, and they are the
thing most likely to be redesigned once the platform underneath them is real.

---

## 3. The per-service loop

Run this for every service. Never batch. Never skip a step because the service "looks simple".

### 3.1 Read the service — the whole surface, in this order

| File | What it tells you |
| --- | --- |
| `README.md` | The design in the author's words, including the failure modes they built around |
| `app/manifest.py` | Capabilities, every endpoint and its tier, ports, events — **the best single map** |
| `app/api/v1/*`, `app/api/internal.py` | The actual routes, and the request models |
| `app/admin_actions.py`, `app/user_actions.py` | What operators and users may do |
| `app/auditable_actions.py` | What it records, and which actions are critical |
| `app/config.py` | Every knob, its default, and usually *why* that default |
| `app/ports/*` | Its dependencies, as interfaces |
| `app/core/*` | The real logic, where the hard decisions live |

Read the **request models** specifically, every time. A field name you can predict is a field name
you will predict wrongly: the difference between an amount and a *pre-tax* amount, between a
template and a template *key*, between an id and a *subject*, is exactly the kind of distinction a
careful service makes and a guess erases. Each wrong guess costs a full round trip through deploy
and test, and the schema was always one file away.

Config comments are the highest-value text in the repository. They routinely explain a failure
mode you were about to walk into. Read them.

### 3.2 Decide, and write the decision where it will be found

Produce one values file per service. Every non-default setting carries a comment saying **why**,
in terms of the product requirement it serves.

A values file is the only documentation anyone reads at 3am. Write it for that reader.

State what you did **not** enable, and why. Silence and oversight are indistinguishable six
months later.

### 3.3 Pin the image by digest

Never a tag. A moving tag means a rollback is not a rollback: `IfNotPresent` silently keeps
whatever the node already has, and two servers on the same tag are not provably the same bytes.

Resolve the digest from the registry at the version you intend, and record it.

### 3.4 Provision what it needs

Its own database. Its secrets. Two of these are shared across **every** service and getting them
wrong is silent:

- **The PII salt.** Two different salts fold one person into two pseudonyms. Everything boots,
  everything looks correct, and the data is wrong.
- **The internal service token.** The shared credential guarding the internal tier.

Asymmetric signing: exactly one service holds the private key; every other service gets only the
public key. A shared symmetric secret means any service holding it can mint a token for any
subject — one compromise becomes platform-wide forgery.

### 3.5 Render before you deploy

`helm template` (or your chart's equivalent) before touching the cluster. A values file that
cannot render must fail here, not halfway through a rollout with half your services on the new
release.

A good chart refuses to render mistakes. Treat every refusal as the guard working, and read what
it actually said.

### 3.6 Deploy, health-gated

One service at a time, waiting for readiness, with automatic rollback on failure. Use a script,
not a hand-typed loop — see §5.

### 3.7 Prove it

**A green rollout proves nothing.** Make real calls and check real answers. Minimum, per service:

- Its readiness endpoint reports every dependency healthy — read the body, not the status code.
- Its **scheduled jobs exist and have run at least once** (see §4.1).
- **One behaviour the product actually depends on**, proven end to end.
- **Tenant isolation**: tenant A's token is refused on tenant B's data, for read *and* write.

When a result surprises you, **do not report it until you understand it**. A count of 2 where 3
was expected turned out to be a late-event threshold working exactly as designed — and the
correct response was to change the threshold, not to file a bug or quietly accept the number.

**Some capabilities cannot be proven by any endpoint.** A backup is the clearest case: readiness,
a successful run, and a stored archive together prove nothing about whether the data comes back.
Only a restore does. If the service ships a drill or verify step, run it — on our first real run
it caught an archive that was recorded as taken, looked healthy everywhere, and could not be
restored. Ask, for every service: *what would still be false if every green light here were true?*

If you cannot prove it, say so. "Deployed and green, behaviour unproven" is an honest status.
"Done" is not.

### 3.8 Register it with compliance

Any service holding personal data must be registered as an erasure target **and** in the data
map, before it counts as deployed.

This is not bookkeeping. An erasure request fans out one task per **registered** target and
completes only when every one acknowledges. An unregistered holder is never asked, never
acknowledges, and is therefore **never missed** — the request closes green on an erasure that
did not happen. A breach of the subject's rights, recorded as a success.

A service holding no personal data is exempt from the map, not from the decision. Write down
that it holds none.

---

## 3B. Writing a service of our own — the eleven steps, in this order

§3 is the loop for CONSUMING a base service. This is the loop for the ones we write, and it was
derived from `operations` — the first one built this way, and the only reason the order below is
not a guess.

**1 · Generate from `_template`, and PAY THE PLATFORM TAX FIRST.** Auth, capabilities, rate limit,
audit, backup export/import, privacy erase, manifest, `admin_actions`/`user_actions` — all of it
wired and passing before a single line of domain logic exists.

This is step one and not step nine for one reason: **a service that gets its obligations last never
gets them.** Once the domain works, the erase endpoint is a chore nobody schedules — and the shape
that follows is §4.18, an endpoint that exists and does nothing. Written first, the domain grows
inside them. `_template` already carries them, so the cost of doing it first is nearly zero and the
cost of doing it later is a service that ships without them.

**2 · The data model, and the identifier decision.** Decide what identifies a subject HERE and what
goes to peers. Raw identifiers stay in the service that already had them; peers get the
`subject_ref` pseudonym. Write down why, at the field.

**3 · The platform obligations proven, not just present.** Erase and export called once, by hand,
before anything depends on them.

**4 · The write path**, under its latency budget.

**5 · The read path** — what the screen actually needs, not what the model contains.

**6 · Attribution and access** — who did it, and what a token must carry to.

**7 · The seams** — index, event, telemetry: all AFTER the response, each in its own try/except,
none able to lose the write.

**8 · Content as data, not code.** Anything our own people will revise — sectors, templates,
catalogues — lives in the datastore with a one-time seed file, never in the image. A word that
costs a rebuild is a word that never gets fixed.

**9 · Deploy and PROVE with real calls** against the running image, on its pinned digest.

**10 · Register with compliance**, and prove the ack.

**11 · The five traps no guard can catch** — the last task of every service, always.

**And one rule that came out of step 11 the hard way:** for every rule enforced in the core, one
test must reach it through the HTTP route with the real request model in the way. See §4.20.

---

## 4. The traps

Every one of these was hit. Each is silent by construction — none produces a red dashboard.

### 4.1 A scheduled endpoint without its schedule

Charts commonly ship an empty schedule list while services ship endpoints that **do nothing unless
you schedule them**: retention enforcement, queue drains, scheduler ticks, dunning runs, hold
sweeps, reconciliation. Each one reads as healthy without its schedule, because the endpoint works
perfectly when called by hand.

| Missing schedule | What it looks like | What it actually is |
| --- | --- | --- |
| Retention purge | A retention policy in config | Nothing is ever deleted. A compliance finding. |
| Scheduler tick | A healthy scheduler | Nothing is ever due. No background work fires. |
| Queue drain | Delivery mode "queued" | Everything queues and nothing sends. |
| Hold sweep | Reserved balance | An interrupted operation locks that balance forever. |

This is the single most repeated trap in the whole method — expect it in most services that have
any notion of time.

**Rule:** when a service exposes an endpoint meant to be called on a schedule, schedule it in the
same values file. Verify it exists *and has run* after deploying. Modern platforms may ship a CI
gate for this; if yours does, read what it enforces, because it will also tell you which endpoints
it considers scheduler-driven.

### 4.2 A setting that is configured and inert

`RETENTION_DAYS=1095` with no job to enforce it. `TOKEN_VERIFIER_DRIVER` unset, defaulting to
`null`, denying every token while readiness stays green. A rollout percentage defaulting to 100
so a flag's `default: false` never applies and every tenant gets a feature they did not buy.

**Rule:** for every setting that promises a behaviour, prove the behaviour. The setting being
present is not the behaviour.

### 4.3 Deny-by-default defaults that are correct and fatal

Good platforms default to denying. That is right, and it means an unset knob does not misbehave
— it refuses everything, quietly, while every health check passes.

**Rule:** enumerate the security-relevant drivers for each service and set them explicitly, even
when you are setting them to the default. Token verifier, consent gate, audit sink, entitlement
checker.

### 4.4 Blackholed egress

A network policy that **drops** rather than refuses does not produce a connection error. It
produces silence: liveness stays 200 (it touches no dependency, by design), readiness hangs
until the probe times out, the pod sits `Running 0/1`, and nothing in any log or event names the
cause. It reads as a slow start, then a bad image, then a missing bucket — in that order,
wasting an afternoon.

**Rule:** when a pod is `Running 0/1` with a healthy liveness and a hanging readiness, suspect
egress **first**. Test the specific port from inside the pod.

### 4.5 Network-layer versus application-layer allowlists

An "allowed hosts" setting is usually an application-level guard on the service's own HTTP
client. The network policy's internet toggle is all-or-nothing. Both matter; they are not the
same layer, and one does not imply the other.

**Rule:** measure it. From inside the pod, try a host that should be blocked.

### 4.6 A declared capability nobody implements

A service declared several auditable actions and recorded none of them — they went to the event
bus, not the audit sink. The contract file said the action was witnessed; the chain was empty.
Declared-and-absent is the worst shape a control takes, because it passes review.

**Rule:** for anything a service *declares*, verify it *does*. Especially compliance controls.

### 4.7 Licence

Check the licence of every third-party component before you deploy it, not after. A default
choice was AGPLv3 — untenable under a commercial SaaS, and it had already been running for
hours. The replacement spoke the same API and cost one manifest change.

**Rule:** permissive licences only (MIT/BSD/Apache/ISC) for anything you ship or host. Check
before deploying.

---

### 4.8 A path scheduled by its name instead of its signature

Two CronJobs were added because an endpoint's *name* looked like a sweep. Both returned 422 on
every run — they take required parameters a scheduled POST does not send. One of them was worse
than useless: it resumes a single stalled signup by re-attempting **deletes**, and upstream's own
comment says a blanket sweep would "re-attempt them on runs an operator may be mid-way through".
A timer had been retrying deletions against in-progress signups every ten minutes.

**Rule:** before scheduling a path, read the handler signature. If the platform ships a values
file and does **not** schedule that endpoint, treat the absence as the answer, not an oversight.

### 4.9 A shared secret nobody tells you is shared

Some values must be **identical across every service** — typically a pseudonymisation salt and a
shared internal token, both usually documented. Any cross-service feature that seals or signs
something adds another, and those are rarely documented anywhere the operator will look: the
explanation tends to live in a comment on the *calling* service, while the field sits
uncommented on every target.

The failure is quiet by design. A service that cannot find its key correctly **refuses** rather
than proceeding insecurely — which is right — and the refusal is often a bare status code with no
body, because naming the missing key on an unauthenticated path would leak configuration.

**Rule:** for any feature spanning two services, list the secrets *both ends* must agree on before
deploying either. Check the target's config, not just the caller's. When a cross-service call
fails with an unexplained refusal, suspect a shared secret before suspecting the network.

### 4.10 A capability you assumed was universal

A cross-cutting capability — backup, erasure fan-out, health reporting — is usually implemented as
"every service exposes endpoint X, and one service calls all of them". That design is only as
broad as its least-covered participant, and partial coverage looks identical to full coverage from
the calling side: the collector reports what it collected, not what it could not reach.

**Rule:** never accept "the platform has X" as an answer. Enumerate which services actually
implement the endpoint, count them, and write the number in the values file. Re-count on every
platform upgrade — coverage moves, in both directions.

**How to check:** ask each service's manifest whether it declares the endpoint, rather than
trusting a summary. Then look at *which* services are missing: a gap covering peripheral services
is a scheduling matter; a gap covering the ones holding identity, money or consent is a different
conversation.

### 4.11 A name that is a reference, not a value

A field called something like `token_ref` holds the **name** of a stored secret, not the secret.
Registered with the value, or empty, every call is a 401 that names nothing.

**Rule:** read the field's comment, not its type. `_ref`, `_name` and `_key` frequently mean
indirection.

### 4.12 A key that is not a setting at all

Worse than §4.2, and quieter. A configuration loader that validates its fields will usually **drop
an unknown key in silence** — no error, no warning, no log line. So a misspelled name, or a real
name borrowed from a service that does declare it, produces a file that asserts a behaviour and a
process that never sees the assertion.

We shipped `DEFAULT_LOCALE: "ar"` in eighteen values files. Exactly two services declare that
setting. Sixteen ran on their defaults for weeks while every file said otherwise, and nothing
anywhere disagreed.

**Rule:** every key you set must be a field the service **declares**. Check it against the config
source, and make a build guard do it — this is the cheapest check you will ever write and it
catches the failure with no symptom at all.

### 4.13 A finite resource with no owner

Each service takes a share of something shared — database connections, file handles, a rate limit
at a provider — and each share is reasonable on its own. Nobody multiplies by the number of
services, because no single service is in a position to.

The arithmetic that bit us: every service opened a connection pool that filled to ten on first use
and never released, against a database whose ceiling was one hundred. Ten services fill it. The
platform ships twenty-four. And it was not a startup failure — the pool filled **lazily, on first
query** — so the cluster looked healthy for hours and then deadlocked on an ordinary request,
because that service happened to be the one that crossed the line. It correlates with success: the
more of the platform a customer uses, the sooner it arrives.

**Rule:** for every shared finite resource, write the multiplication down — per-service share ×
number of services versus the ceiling — and put it in a preflight that REFUSES the install. A floor
that does not fit is not a risk, it is a scheduled outage.

### 4.14 The step you skipped was the control

Deployment tooling that looks slow is usually slow **on purpose**. A health-gated rollout that
moves one service at a time is not an unoptimised loop; the gate is the product.

We replaced one with a hand-written parallel restart of ten deployments, and deadlocked the
cluster: the new pods could not get connections while the old pods still held them, and with
`maxUnavailable: 0` the old ones were never retired. The sequential gate would have absorbed it
without noticing.

The same failure twice in one day, in a second shape: a script left in `/tmp` instead of the
repository, deleted by our own cleanup, and rewritten from memory.

**Rule:** use the tooling that exists before writing your own, and read its flags first — the
`--only` that would have turned a thirty-minute rollout into two minutes was there from the start.
Anything worth running twice lives in the repository, not in `/tmp`.

### 4.15 A guard that cries wolf gets switched off

The guards you write to catch these traps have their own failure mode, and it is fatal to their
purpose: a false positive on a tree that is already correct. People do not debug a noisy guard,
they disable it.

Ours produced four on its first run, all of the same species — reading the file as text when the
question was about structure. It read a trailing `# v0.12.6` comment as part of a digest and
rejected every correctly-pinned file. It matched a setting name inside a **comment explaining that
setting**, in files that argue their own choices at length. It assumed a mechanical
service→database name transform that one service breaks. And a byte-range regex for Arabic-Indic
digits matched clean English shell scripts.

**Rule:** a new guard's first job is to run clean against a tree already known to be good. Match on
structure, not on the presence of a substring somewhere in a file.

### 4.16 Silence read as success

The worst failure reports nothing. An installer that hangs while every step inside it succeeds in
isolation; piped through `tail`, it shows a clean exit and an empty output, and the operator
believes the thing is installed.

That is how a deploy host ended up with **no boot recovery at all**: the leftover unit from another
product had been removed, the replacement had silently never landed, and only `systemctl` told the
truth. A visible failure would have been strictly better.

The same shape in a different place: a script with `set -e` aborting on a `helm --wait` timeout
whose pods came up healthy a minute later — so the monitoring stack installed its dashboards and
never installed the exporter that feeds its most important alert.

**Rule:** verify against the system's own state, never the installer's exit code. `systemctl
is-enabled`, the running image of a deployment, the series actually present in Prometheus. And
distinguish "I looked and there is nothing" from "I could not tell" — only one of those should
reassure anyone.

### 4.17 A defect in your test harness wearing another service's face

You will spend hours on a service that is fine because your own probe was wrong, and the symptom
will point somewhere else entirely.

A hand-minted test token used `tenant_id` for a claim the service reads as `tenant`. That did not
fail at the token check. It left the tenant empty, the empty value travelled into an audit record,
and **audit-service** rejected it — so a perfectly healthy service returned `503
AUDIT_UNAVAILABLE`, and the investigation went to the audit service and toward an escalation that
had no defect behind it.

**Rule:** before escalating anything, reproduce the failing call by hand with values you control.
Posting the exact payload directly to the service that rejected it returned 200 — which proved the
contract was fine and the sender's input was not, in one call.

### 4.18 Endpoint present is not endpoint working

A release note that says thirteen services gained a capability is a statement about code, not about
your cluster. Measure it.

Ours did: thirteen services gained a backup export endpoint, and three of seventeen could actually
produce an archive. The other fourteen answered a bare `503`, because the endpoint needed a shared
secret only the original three held. The fleet looked covered while most of it could not produce a
readable archive.

**Rule:** for every capability you depend on, call it on every service that claims it and count the
successes. "It is implemented" and "it works here" are different claims, and only the second one is
yours to make.

### 4.19 A value that was valid where it was written

Copying a working value across a boundary is how a correct string becomes a broken one. A
connection string, a service URL, a path — each is resolved relative to something, and the
something travels with the reader, not with the value.

We took a database DSN out of a service's secret and handed it to an exporter in a different
namespace. The services address the database as `@postgres:5432` — a short name that resolves only
inside their own namespace. In the monitoring namespace it means nothing. The exporter started,
went Ready, logged `lookup postgres: no such host` where nobody was reading, and Prometheus simply
had no series. **Everything was green and the alert we built the stack for was blind.**

It was found only because the installer verifies its own outcome (§4.16) rather than trusting its
exit code.

**Rule:** when a value crosses a namespace, a cluster or a host, qualify it fully at the crossing.
And expect this class specifically wherever you reuse a credential or an address that was written
for somewhere else.

### 4.20 A rule enforced in the core and bypassed at the door

`TemplateLibrary.upsert()` refuses a template that asks the owner to fill more than one field.
The unit test proved it. The live call did not: the console's pydantic model never declared
`fills`, so the field was dropped on the way in, the core received an empty list, checked nothing,
and answered **200**.

The rule was real. The path to it was not.

Pydantic drops an undeclared key **silently and successfully** — the same mechanism that made
`DEFAULT_LOCALE` sit unread in eighteen values files (4.12), wearing a different hat. And a unit
test cannot see it, because a unit test calls the core directly and never crosses the model.

**Whenever a rule lives in the core, one test must reach it through the actual door** — the HTTP
route, with the real request model in the way. If your only proof of a refusal is a direct call to
the function that refuses, you have proven the function, not the product.

### 4.21 Their gate suite is rooted in their repo, not yours

Running `platform/tools/ci/run_all_gates.sh` from a consumer's tree reported twelve failures.
None was about our code: no `pytest` in the interpreter it picked, no `.github/workflows/ci.yml`
in a submodule that has none, `no app/core/ found`, and a privacy fan-out complaint about the
platform's own values directory.

Worse, the run BEFORE that one reported **ALL RUNNABLE GATES PASSED** while running nothing at
all — twenty-eight gates skipped because the host has `python3` and not `python`. Their own runner
warns about exactly this shape, and it still reads as a pass at a glance.

**Their gates guard their repo. Ours guard ours.** Run theirs when reading their code; never quote
its result as evidence about a service in `services/`. And on any suite that can skip: read the
skip list before reading the verdict.

### 4.22 "Rolled successfully" does not mean "rolled what you built"

`update.sh` reported **every service on its pinned digest**, and it was telling the truth. The pod
was running exactly the digest written in the values file — ON THE SERVER. That file was two
versions old, because the sync that carried the new one had timed out before it finished extracting
the archive, and the timeout scrolled past under a load spike.

So the deploy verified an old artifact against an old declaration and found them consistent. Every
signal was green. The only way to see it was to read the running pod's `imageID` and compare it to
the digest **in the working tree**, not to the digest the deploy was reading.

The tell was that the proof did not change: the tick returned the same numbers it had before the
fix that was supposed to change them. **A proof that produces the identical result before and after
a fix is not a passing proof — it is evidence the fix is not there.**

Verify the artifact, not the report: read `imageID` off the pod and diff it against the local
values file, every time.

### 4.23 Deleting "not Running" pods deletes the rollout you are waiting for

A node was thrashing — load 44 on eight cores, containerd returning `context deadline exceeded` on
every container create — so a cleanup ran:

```
kubectl -n base-services delete pods --field-selector=status.phase!=Running
```

It read as "clear the wreckage". What it actually matched included **Pending**, and the pod pending
at that moment was the new version trying to start. The rollout was deleted by the command meant to
unblock it, and the deployment sat on the old image looking healthy.

`status.phase!=Running` is not "broken". It is Pending, Succeeded, Failed and Unknown — three of
which are normal states a healthy cluster passes through constantly.

Delete by the state you actually mean: `--field-selector=status.phase==Failed`, or
`status.phase==Succeeded` for finished job pods. And when a rollout is in flight, delete nothing
that belongs to it.

### 4.24 `rollout restart` does not pick up a new image

After the pod above was deleted, `kubectl rollout restart` looked like the way to get the new
version running. It is not: restart re-creates pods from the SAME pod spec, so it restarted the old
image, cleanly, and reported success.

A restart changes nothing about what is deployed. Only re-applying the chart with the new values
does — which on a loaded node is exactly the operation that keeps timing out, which is why the
temptation to reach for restart appears in the first place.

### 4.25 A refusal the user is never told

Every service in this product writes careful, actionable refusals — "the reward name is longer than
40 characters", "invoice earning needs a till" — raises them as `HTTPException(400, message)`, and
none of them has ever reached a user. The platform's error handler strips `detail` from every
exception by design (CWE-209: information exposure through error messages), so what arrives is
`{"error": "BAD_REQUEST"}`.

That default is right. A stack trace, an ORM message or a reflected input must never leave the
process. But an author-written sentence naming a RULE is none of those, and the handler cannot tell
the difference — so the careful message is discarded along with the dangerous one.

**Both layers read correctly in isolation**, which is why this survived three services. The route
says "400 with the owner's sentence"; the handler says "never leak detail". Only a test that reads
`response.text` and asserts the sentence is in it finds the gap, and a test that asserts on the
status code alone passes forever.

The fix is not to weaken the handler. It is to RETURN the refusal rather than raise it:

```python
return JSONResponse({"error": "BAD_REQUEST", "reason": reason}, status_code=400)
```

with one rule attached: `reason` must stay author-written text. The moment it interpolates caller
input it becomes a reflection, and the handler was right after all.

### 4.26 A materialised total, and the crash between two writes

Anything kept alongside the record it summarises — a running balance, a counter, a cached
aggregate — can drift from it, and the drift is invisible because the wrong number stays entirely
plausible. `loyalty` writes the ledger entry first and the total second, so a crash between them
leaves a movement the total has not caught up with; the other order loses the entry and leaves a
total nobody can explain.

Three things make that survivable, and all three are cheap only if they are designed in:

- the ledger is the truth and the total is explicitly a **read** of it,
- each entry carries the balance it produced, so drift is **locatable** and not merely detectable,
- a `reconcile` exists and is exposed on a platform-capability route, because "where did my points
  go?" is a support question about a shop that is not the caller's.

### 4.27 An out-of-order event that moves a clock backwards

Events carry their own timestamp, and a queue drained after an outage delivers old ones late. Any
field written as `field = event.time` will therefore move BACKWARDS when a stale event lands — and
if that field drives an expiry, a retention window or a schedule, the stale event silently ages a
record that was current. `max(field, event.time)` is one word longer and is almost always what was
meant.

Found by a test that ran the sweep twice with a stale visit in between. Nothing in the read path
would ever have shown it.

### 4.28 A counter that counts intended work rather than done work

The expiry sweep incremented `expired` next to the call that expired a balance, not based on
whether the call did anything. When the movement was refused as a duplicate, the tick still
reported the work. That is the quietest wrong number there is, because it is exactly the number an
operator reads to decide the sweep is healthy.

If a function can legitimately return "already done", the caller must count its RESULT.

### 4.29 A digest reference is a NAME, and names can be re-pointed

`ctr images import` stores an image under its TAG, so shipping to a digest-pinned deployment needs
`ctr images tag repo:tag repo@sha256:…`. That command creates a *name*. It does not verify that the
content behind the name matches the digest in it, and nothing later does either.

So a pod can be admitted against `repo@sha256:914…`, run whatever that name pointed at THAT day, and
keep running it after the name is re-pointed. `kubectl get pod -o jsonpath '{.spec…image}'` then
reports the pinned digest — because the spec is what was asked for — while `imageID` reports the
content actually running. Portal ran three hours on an image two versions old with both the values
file and the deployment spec showing the correct pin.

**The only reliable check is `imageID`, and only for single-platform images we build ourselves.**
Multi-arch images from a registry pin by index digest and report the platform manifest digest, so
they mismatch legitimately — which is why the fleet check must know which images are ours before it
can accuse anything.

The fix when it happens is to re-ship, not to re-tag: a fresh import gives the name new content and
forces a new pod.

### 4.30 A plan carried on the token

Reading a subscription tier from a claim the caller presents is a server-side decision enforced
client-side (CWE-602), and it has a second failure that is worse because it looks like nothing:

**a token minted before an upgrade keeps saying what it said.** A shop that pays at 10am is refused
the thing it just bought until its session is reissued — for as long as the access TTL, or longer
if the claim is only set at login. No error is raised anywhere, and support cannot reproduce it
because *their* token is new.

Ask the billing service per request instead. It is one call, it is cacheable for seconds, and it
turns "did he pay?" into a question with one answer rather than a copy that ages.

Two rules come with it:

- **fail closed.** An unreachable billing denies. Showing a paid surface to somebody who has not
  bought it cannot be taken back; refusing during an outage is a minute that fixes itself.
- **never rank plan names.** No `TIERS` tuple, no `rank()`. A surface is keyed on an entitlement —
  `feature.x.y` — so pricing can change without deploying the services, and a plan can be added
  between two others without editing an ordering. It also lets a customer buy one feature without
  the ladder underneath it, which an ordering cannot express at all.

And the tell that this has gone wrong is silence: every test of the tier logic passes, because the
bug is in READING the claim rather than in judging it. Ours read `principal.plan` on an object that
keeps its extra claims in `principal.raw`, so every paying establishment was quietly served the
entry-plan surface. Only a route test with a real token found it.

### 4.31 An upsert that resets a status

`register()` on a WhatsApp template registry preserves the id and the created date — and rebuilds
the row with `status=PENDING`. Re-registering an identical, already-approved template therefore
un-approves it, and the send path then correctly refuses to send anything.

The dangerous part is that the natural operation is "make sure this tenant has the library". Anyone
adding one new template runs it over the whole set, and every other template goes back to pending.
Every business-initiated message that establishment sends stops, for hours, and the call returned
201.

**Look for this shape in any "create or update" that rebuilds a record from its inputs**: the
fields the CALLER supplies are correct, and the fields the SYSTEM owns — status, approval, verified,
last_seen — are silently reset to their defaults. A test that checks the row exists afterwards
passes.

Found by running our own seeder twice and reading its counters: `registered=72 existing=0` is not
what "already registered" looks like.

### 4.32 Read the third party's documentation before you build against their adapter

We were one command away from submitting seventy-two WhatsApp templates through the platform's Meta
driver. Reading Meta's own documentation first, instead, found four things — and the first meant
**not one of them could have been created**:

- Meta requires an **example value for every parameter**, and the adapter sent none. Every template
  in the library has a placeholder, so every submission would have been refused.
- Two documented statuses, `PAUSED` and `DISABLED`, were unmapped and fell through a `.get(...,
  "pending")` default — so a template Meta paused would read as "still under review" for ever. And
  those two states come from customer behaviour, not from a reviewer: low read rates and repeated
  complaints. They are the states a messaging product most needs to see.
- The manager is built once from configuration, so the whole deployment submits into ONE business
  account — while a product whose customers message under their own name has one per tenant.
- The Graph version was four releases behind the current documentation.

Each would have surfaced as a rejection hours after the submission, against template names that
**cannot be reused with different content and cannot be renamed after approval**. The cost of
learning by trying was not a retry; it was burning twenty-four names per tone.

**The rule:** when an adapter wraps somebody else's API, the adapter is not the contract — their
documentation is. Read it before the first call, and diff it against what the adapter actually
sends. That is an hour, and it is the cheapest hour available.

The tell that this hour is worth spending: the adapter's docstring describes the SHAPE it builds
("we shape them into Meta's component format and forward") without quoting the requirement it is
shaping toward. A description of the code is not a description of the contract.

### 4.33 "Not published" and "we could not tell" are different answers

Our re-pin script resolved twenty-five image digests from the registry, reported *"15 moved, 10 not
published at this tag"*, and exited clean. Four of those ten were sitting in the registry the whole
time; every one of them resolved on the first try when asked alone.

We called it rate limiting. It was **DNS** — and how that was learned matters more than the
answer. The registry theory fitted every symptom and survived two rounds of fixes built on top of
it. What disproved it came from somewhere else entirely: a kubelet on the same node failing to pull
an image with `dial tcp: lookup pkg-containers.githubusercontent.com: Try again`. That is a
resolver refusing a query, not a registry refusing a request. `curl` reports a failed lookup as
HTTP 000, which is indistinguishable from a throttled API unless you go looking.

The damage was never the cause, though: the script printed a **reassuring sentence about the
registry** for a condition that was actually *"we do not know"*, and the release would have left
four services a version behind with the summary line agreeing that everything was fine.

An empty result has two causes that mean opposite things. A 404 is a fact you can act on. A timeout
is the absence of a fact. Code that collapses them into one message picks the comforting reading.

**The rule:** read the STATUS, not the absence of a value. Retry what is transient, with real
backoff — a flat two seconds retried into the same closed rate-limit window three times and
reported the same four services missing. And when it still will not resolve, **fail**: "we could not
tell" is not a state a release may exit successfully in.

### 4.34 A proof that only looks at the first minute

We proved message packs against the running service: a plan of 2 plus a pack of 3 answers 5, and
buying does not reset what was already spent. All true. The task was marked done.

Then, reading the resolver for a different reason, we found `_INTERVAL = {"month": …, "once": 0}` —
so a `once` subscription is created with `current_period_end = now + 0`, and the newly added
period-lapse check drops any row whose period has passed. Running the service's own resolver
confirmed it: kept at `now + 60`, `period_lapsed` at `now + 2 days`.

A customer pays 50 riyals for 500 messages, sends for one day, and the balance silently reverts to
his plan's. **Our proof passed because it ran seconds after the purchase.**

**The rule:** a proof that exercises only `now` proves only `now`. When behaviour depends on time —
a period, an expiry, a grace, a trial — the test must run the code at a time on the other side of
the boundary. You cannot wait a day, and you do not need to: import the service's own logic and
call it with a forged clock. That is a five-line script and it is decisive, where a live smoke test
against a real cluster is neither.

The related tell: `trial_end` in the same service is written at signup and read by **nothing**. A
field that is only ever written is not a feature — it is a promise the code never keeps, and
`grep -c` finds it in a second.

### 4.35 A guard that cries too much gets switched off

Adding the message-pack prices to the "no price in code" guard took it from zero false positives to
forty-one. The pack prices are 50 and 90 riyals — 5000 and 9000 halalas — and every one of those is
a port, a row limit or a batch size somewhere in the repo. `OBJECTSTORE_ENDPOINT_URL` ends in
`:9000`.

The first version of the same guard failed on twenty-six "prices" that were all CWE identifiers in
a generated security catalogue (CWE-148, CWE-298 and CWE-598 — all three) and colour tuples inside
a vendored dependency.

A guard nobody can satisfy is a guard somebody disables, and it takes the cases it was working for
with it.

**The rule:** narrow the SCOPE before loosening the PATTERN. Skip vendored trees and generated
files; exempt a genuinely-not-a-price number by name with the reason written down. And when a value
is simply not distinctive enough to guard — two-digit prices are not — say so in the file and rely
on the other control, rather than shipping a check that fires on everything.

### 4.36 A line rule cannot tell a gate from the gate it is looking for

Three attempts at one guard, and the failures are more instructive than the result.

The rule wanted: the dashboard must keep rendering for an establishment that stopped paying, so
`insights` must not gate what it serves on a subscription — except for the association engine,
which is genuinely a paid feature.

*Attempt 1: ban any mention of billing in insights.* It failed on six legitimate places, including
the weekly report's balance line — a number about HIS shop that must keep being shown precisely
when he has stopped paying.

*Attempt 2: flag lines that look like gating.* It flagged `allowed_keys()` and
`peers.entitled(...)`, which **are** the engine gate. A per-line heuristic cannot distinguish the
gate from the one gate that is allowed, because they are the same lines.

*Attempt 3, which works:* the SET of entitlement keys named anywhere in `insights/app/core` must be
exactly `{feature.insights.engine}`. One key, one paid feature, everything else served to everybody.

**The rule:** when a per-line check keeps flagging the thing you meant to allow, the property you
are checking is not a property of lines. Find the set-level invariant — what may EXIST, not what
may appear on a line — and check that instead.

### 4.37 When the feedback loop destroys inventory, buy the rules instead of learning them

Seventy-two WhatsApp templates, ready to submit. They had passed everything we owned: generated
from the specification, four content checks, variable numbering, tone coverage, the
examples-are-not-names rule. Then we wrote Meta's own documented rules down as a check and ran it
once.

**Eleven failures, in nine templates.** Six bodies that begin with a variable, three that end with
one, two with two variables side by side. Every one is a documented rejection.

None of them would have failed at submission. The API accepts the payload; a human rejects it hours
later. And a template name **cannot be reused with different content and cannot be renamed after
approval** — so each rejection permanently burns a name, and the replacement is `_v2`, then `_v3`,
for the life of the product.

That combination is what makes this different from an ordinary integration:

- the feedback arrives **hours** after the action, so the loop is a day wide;
- each turn of the loop **destroys inventory** rather than costing a retry;
- and the local mock approves everything, so nothing before it can fail.

**The rule:** when a third party's feedback is slow AND its failures are irreversible, do not learn
its rules by submitting. Transcribe them from the documentation into a check and run it against
exactly the payload you will send — expanded, not as stored. Ours expands 24 texts into the 72 rows
Meta receives, because checking the stored shape checks something nobody submits.

An hour of reading bought back nine names. There is no rate at which trial-and-error competes with
that.

## 5. Automate the deployment on day one

Do not deploy by hand-typed loops. The first real use of one had the repository replaced
underneath it mid-run: nine of twelve services failed, and it exited zero.

Your deploy script must:

- **Assert its preconditions** — chart present, cluster reachable, tooling installed. One clear
  line beats N identical errors buried in a log.
- **Render before applying.**
- **Health-gate each service** and **roll back to the revision captured before the upgrade**.
- **Support `--only` and `--dry-run`.**
- **Print a summary that cannot lie** — name what failed, list anything not fully ready, and
  **exit non-zero on any failure**.
- **Prune superseded images** after a fully successful roll, and only then: a rollback still
  needs the previous image.
- **Survive a dropped connection.** Run it detached; an interrupted deployment is worse than one
  never started.

**Check whether the platform already ships this — and check again after every upgrade.** A living
platform grows toward its consumers: the thing you built because it was missing is a strong
candidate for what arrives in the next release, often carrying the same decisions you reached, and
generalised. Keeping your copy then means maintaining a divergent fork of something now maintained
for you. The rule that governs services governs scripts: consume it, do not reimplement it. Re-read
the platform's own deploy directory on each version bump and delete what has been superseded.

If a reference implementation exists, **take it whole and adapt it**. Do not rewrite from
scratch what someone has already debugged in production. Change what your shape genuinely
requires, keep the rest, and say in a comment which parts are theirs and why they are unchanged.

---

## 6. Working with upstream

**Report, never patch.** When you find a defect:

1. Give the exact file and line.
2. Explain the mechanism, not just the symptom.
3. Show evidence from a live system — the request, the response, the log.
4. State what a consumer can and cannot work around.
5. Propose a fix, and mention the test that would have caught it.

**Ask for a guard, not just a fix.** The most valuable outcome of a report is not the patch — it is
a build gate that makes the whole class impossible. When you report, name the check that would
have caught it: a CI rule, a boot-time assertion, a test. A maintainer who accepts that suggestion
closes the defect permanently, for every consumer, including the instances neither of you knew
about.

Expect the guard to find things you did not report, and to catch mistakes of your own. That is the
point of it.

**If a workaround does not work, remove it.** A stopgap was tried, verified as ineffective, and
deleted rather than left in place. Configuration that claims a mitigation it does not deliver is
the same failure as the inert setting in §4.2.

---

## 7. Definition of done, per service

- [ ] Read: manifest, routes, request models, actions, config, ports, core.
- [ ] Values file written, every non-default choice justified against a product requirement.
- [ ] Image pinned by digest.
- [ ] Own database; shared salt and internal token identical to every other service.
- [ ] Renders clean.
- [ ] Deployed by script, health-gated, readiness body shows every dependency healthy.
- [ ] Scheduled jobs exist **and have run**.
- [ ] One real product behaviour proven with real calls.
- [ ] Tenant isolation proven — read and write.
- [ ] Registered with compliance, or explicitly recorded as holding no personal data.
- [ ] Anything unproven stated plainly rather than implied.

---

## 8. How to report progress

- Say what is **proven**, what is **deployed but unproven**, and what is **blocked**. Keep those
  three separate.
- When a test result contradicts your expectation, investigate before reporting. A wrong
  explanation delivered confidently is worse than a delay.
- When you were wrong, correct it in one line and continue. Do not re-litigate it.
- Never mark a task complete on partial work. Split it and complete the part you finished.

---

## 9. The order, one line each

1. Read the description completely. Write down actors, entities, hard constraints, numbers.
2. Inventory the platform. One honest line per service.
3. Map requirement → service. Defend every mapping by opening the service.
4. Produce the wave plan and the domain-service list. Ask your open questions together.
5. Wave 0: cluster, and **prove** policy enforcement rather than assuming it.
6. For each service in wave order: read → decide → pin → provision → render → deploy →
   **prove** → register.
7. Automate deployment before the third service, not after the twelfth.
8. Report defects upstream with evidence. Never patch.
9. Build your domain services last, on a platform that is proven underneath them.
10. Ship nothing you have not seen work.

---

*The platform is not the product. Configure the platform; build the product; prove both.*

### 4.38 A resolver that finds nothing prints the same line as a system with nothing wrong

A gate was written to assert that the capability an action DECLARES is the one its handler
ENFORCES. It parsed the routers, resolved `require_capability(...)` bindings, matched them against
the declared actions, and reported: **49 actions checked, no mismatch**.

Sixteen were wrong at that moment.

The resolver built each route's path as `/api/v1` + the router prefix + the decorator path. Most of
our routers carry a relative prefix (`/subscription`), so that is right. `operator.py` carries the
absolute one (`/api/v1/operator`) — so its routes resolved to `/api/v1/api/v1/operator/secrets`,
matched nothing, and every operator action fell into the "no capability dependency on that route"
branch, which is deliberately silent because public and internal routes land there too.

**The shape of the bug is the lesson, not the prefix.** A check that filters before it compares has
two silences that look identical from the outside:

- *nothing matched the filter* — the check learned nothing;
- *everything matched and agreed* — the check learned something.

Both print the green line. And the more thorough the filtering, the more places this can hide: the
`continue` that skips unparseable files, the `if not bound` that skips routers with no capability,
the `if actual is None` that skips unmatched routes. Every one is correct in isolation.

**What to do about it, in order of how much it costs:**

- **Print the denominator.** The green line says "49 action(s) checked against the routers". That
  number is what exposed the bug: 49 was implausibly low for six services, and it was the only
  visible symptom.
- **Assert the denominator is not zero** when the input is not empty. A gate over six services that
  resolves zero routes should fail loudly, not pass quietly.
- **Break it on purpose once.** Change one declaration to a wrong value and confirm the gate goes
  red. This is the only method that distinguishes the two silences with certainty, and it costs one
  minute. Every gate in `ci/` that was written today was proven this way; the one that was not is
  the one that lied.

The same failure has three earlier entries in this playbook wearing different clothes: a canary
secret that was never created so every grep for it returned a meaningless zero (4.28); a proof
script whose two dead files answered 127 in a place nobody read (4.33 and the CRLF fix); a
completeness gate that reads declared actions, so a route declared nowhere is a route it never
considers. The pattern outranks all of them: **before trusting a check that passes, make it fail.**

### 4.39 Editing a shell script while it is running corrupts it mid-execution

`ship.sh` completed successfully — "operations is running the image this command built" — and then
died with two errors that made no sense against the file on disk:

    ./deploy/ship.sh: line 134: -o: command not found
    ./deploy/ship.sh: line 135: live: unbound variable

`bash -n` said the file was fine. It was fine. The script had been edited **while it was running**.

Bash does not load a script into memory. It reads it incrementally, remembering a BYTE OFFSET. Add
four lines near the top of a running script and every offset after that point now lands in the
middle of a different line — so a continuation like

    live="$(... kubectl get pod $running \
        -o jsonpath='…')"

is re-entered after the backslash, and `-o` is read as a command. The variable that line was meant
to set is then unset, and the next line fails on it. Both messages are true and neither describes
the cause.

**The tell is that the errors do not match the file.** If `bash -n` passes on the exact file the
error names, stop reading the script and ask what changed underneath it.

**What to do instead:** finish the run, or copy the script and edit the copy. A script that must be
edited during a long run is a script to launch from a snapshot — `cp x.sh /tmp/x.$$.sh && bash
/tmp/x.$$.sh` — which is one line and removes the whole class.

It belongs beside 4.38 for the same reason: the failure was reported at a place with nothing wrong
with it, and time went into the wrong file. There, a check found nothing and printed the same line
as a system with nothing wrong; here, a correct file printed errors from a version that no longer
existed. **Both are cases where the message and the cause are in different places — and the first
question in that situation is not "what is wrong here" but "am I looking at what actually ran".**

### 4.40 A complete feature that nothing calls — thirteen times, one shape

The single most expensive defect in this product, by a distance. Not one of these was a bug in the
code that was written; every one of them was code that was written, tested, deployed, and reachable
by nothing:

| Built and unreachable | What the owner saw |
| --- | --- |
| The redemption path, with its idempotency key and its ledger | Customers earned points for ever and could never spend them |
| Earning on a visit — the engine, fully tested | Every balance stayed at zero |
| `svc_visit_redeemed`, three tones, shipped in the seed | The redemption confirmation never went out |
| The send log — "the only question this service generates" | Every correct refusal read as a fault |
| The PDPL data map | An export request was distributed to nobody |
| The DSAR verification code | Minted at creation, delivered to no channel, so no request could ever be verified |
| Erasure of one customer | The establishment is the controller and had no button |
| The whole campaign engine — goals, audiences, spread, reserve | «حملاتي» explained what a campaign is and offered no way to launch one |
| `campaigns.runs` — the log the service calls its most important | "It didn't arrive" had no answer |
| Associations, bundles, branch comparison | Computed nightly at 04:00 and rendered nowhere |
| The weekly report's subscription switch | An optional notice that could not be switched off |
| `reminders.set_general` | «العام» was a value an owner could return to and never choose |
| The adaptive learning engine (§5.2) | Not one number it learned was ever displayed |

**They share one cause, and it is not laziness.** A backend task ends when the tests pass; a screen
task ends when the screen renders. Neither ends at "a person can now do this", so the last hop —
the button — belongs to nobody. And nothing fails: no test goes red, no line appears in a log. The
feature is simply absent, and absence is the hardest state in a product to see.

**Three things that catch it, cheapest first:**

1. `ci/check_unused_actions.py` — every declared action, and whether any screen calls it. It is the
   opposite question to "does every action a screen names exist?", which only catches typos. A typo
   fails on the first click; an orphan is silent for months.
2. An allow-list WITH REASONS for the deliberate ones, so "we know about that one" becomes
   something the repository says rather than something a person remembers.
3. The definition of done for a feature is **a person can do it**, not "the endpoint answers".

**And the guard has to be in CI.** Half the guards in this repository — including the one written on
the afternoon every scheduled job was found silently failing — ran only when somebody remembered.
A guard outside CI is a note.

### 4.41 A required request body, against a scheduler that sends none

Every heartbeat in the product was failing, nightly, for days: the insights snapshot, the loyalty
expiry sweep, the campaign tick, the reminder tick. The platform's scheduled-job template posts an
EMPTY payload with a JSON content type, and a route that declares a required Pydantic body answers
422 before a line of its own code runs.

Nothing said so. Every probe green, every route answering, every dashboard showing «أحسب الآن» for
ever and every reminder simply not going out. The only evidence anywhere was a Job's exit code — a
resource nobody reads on a good day. It was found because an owner photographed a screen that had
been "computing" for eighteen hours.

**The rule:** a route a scheduler calls must accept the request that scheduler actually sends. Give
the body a default, keep the fields' defaults inside it, and let an empty POST mean what a scheduled
pass means — all of it. `ci/check_cron_bodies.py` reads every `cronJobs` entry in every values file,
finds the route it targets, and fails on a required body or a path nothing serves.

### 4.42 Two copies of one library, and only one of them reaches the customer

The WhatsApp template library existed twice: generated from the specification for our seeding
script, and curated inside operations for what is actually pushed into an establishment's registry
when it connects. Both were legitimate. Nothing compared them, and they had drifted by three whole
TYPES and thirteen texts — two of which differed in variable COUNT, which is a rejected send under
a name Meta had already approved.

The three missing types — a weekly digest, a safety notice, a DSAR code — were written, wired,
tested and sending, and were submitted for nobody. And it failed silently by design: the send path
checks approval and correctly declines a template the account never had.

**The rule:** when the same content lives in two places for two legitimate reasons, compare the
overlap in CI — the fields that must agree — and leave the rest alone. `ci/check_template_libraries.py`
compares type, tone, class, category, header and the body word for word, and ignores the curated
fields that are one side's own.

### 4.43 An install that ends with a running cluster and an empty product

`bring-up.sh` deployed every service, verified every digest, and seeded nothing: no roles, no price
list, no legal documents. Every probe was green and a shop signing up would have received a login
that could do nothing — no capability to grant, no plan to buy, and no agreement to accept.

The legal library was the sharpest case: eight documents, authored, filled in and guarded by CI,
with nothing anywhere that loaded them into the service that serves them. So an owner signed up and
accepted nothing, and there was no processing agreement between us and the establishment whose
customers' data we then processed — the one document Article 17 requires to exist BEFORE the
processing does.

**The rule:** an install is not done when the services run. It is done when the product WORKS — and
the seeds belong in the install script, in dependency order, each idempotent enough that re-running
the install is safe. And the day the publisher is written is the day the files are first parsed:
two of those eight documents did not parse at all, because the CI guard reads them line by line with
a regex and a regex does not see nesting.

### 4.44 A test that fails for a reason unrelated to the code

Six suites reported a failure for weeks. The licence gate walks every distribution in the running
interpreter — inside the service's image that is exactly its dependency tree, which is the thing the
gate exists to police; run from a checkout it is whatever that machine has ever pip-installed. So
all six failed over packages belonging to no service in the repository.

**«1 failed» became the expected output.** That is how a real failure hides: not by being missed,
but by arriving in a place people have learned produces noise. Skip with a stated reason when the
environment is not the one the check is about, and make the marker something real — the service's
package being INSTALLED, not merely named in a pyproject that is always on disk.

It is 4.35 again from the other side: there, a guard that cried too much got switched off; here, a
test that cried for the wrong reason took five green suites down with it.

### 4.45 A peer's response shape, assumed rather than read

`/search/suggest` answers `{"suggestions": ["0527463428", …]}` — a list of **terms**, which is what
an autocomplete is. The client mapped `r.phone` over each one, got `undefined` from a string, and
dropped the row. Measured on the live cluster: «05» returned five numbers and the screen showed
none. Every suggestion list in the product — the phone keypad and the plate alike — had been empty
since the day it was written.

**The failure renders as a truthful-looking answer.** «No customer found» is a sentence the screen
is supposed to be able to say; nothing about an empty list looks like a defect. So the operator
registers a customer he already has, the visit history splits in two, and the product's premise —
bringing people back — quietly stops working for that shop.

**And the fix is a second call, not a cleverer mapping.** Terms are not documents: `POST /search`
with the suggested term (a whole token by construction) returns the records. Two round trips,
bounded, and correct — which is the shape the peer's API actually offers.

**The rule: read the peer's response in its source, and probe it live before building on it.** A
field name that is merely plausible produces code that compiles, passes review, renders, and is
wrong every single time.

### 4.46 A label bound to nothing

The design system's `Field` generates an id, points its `<label htmlFor>` at it, and leaves wiring
that id onto the control to the caller. Omit it and the label renders perfectly — and is attached
to nothing: unnamed to a screen reader, unfocusable by tap, and invisible to `getByLabel`, so the
e2e test that fills it dies as a 60-second timeout with no clue why. Six shipped that way.

**What makes it dangerous is that the eye cannot see it.** The screenshot is correct. Only a screen
reader, a thumb, or a test locator notices — three users nobody was watching. It is now a guard
(`ci/check_field_labels.py`): every `<Field label=…>` carries `htmlFor`, and a control under it
carries that id.
