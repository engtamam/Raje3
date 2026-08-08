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
