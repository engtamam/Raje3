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
