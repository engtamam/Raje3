# Audit — the till/POS integration door (`till.py`) against the rest of the platform

Date: 2026-09-13. Scope: `services/operations/app/api/v1/till.py` (the entire external
partner-integration surface today), read line by line, against every other feature the platform
now has. This is a follow-up to an earlier, shallower pass — this one reads actual core/api files
in each feature rather than summarising from grep hits, and cites `file:line` for every claim so it
can be verified.

---

## Executive Summary

`till.py` is a narrow, deliberately-scoped door: four endpoints, one machine capability
(`operations.record`), built to close a specific security hole (a shared internal token that could
write into any tenant) at the moment visit-registration was the only feature a POS company would
plausibly want. It has not grown since — not because it is broken, but because nobody has gone back
and asked what a POS/till integrator now wants given everything else the platform has built:
bookings, a WhatsApp AI assistant with its own control plane, a ratings pipeline, campaigns,
packages, insights, and more.

The **single most important finding**: a shop running both an integrated till and bookings has no
way to close the loop between the two. A customer books an appointment, the till records the
payment as a bare, disconnected "visit," and the booking itself is never marked `attended` — so
`intended_reward_id` (a loyalty reward the booking already promised at scheduling time,
`services/bookings/app/core/operations.py:522`) never fires, the no-show-risk statistic never
updates, and the shop's two systems (till ledger, booking calendar) silently diverge on what
actually happened. This is not a hypothetical: any shop that sells both the "تسجيل زيارة" app and
the "الحجوزات" app today has this gap in production.

Beyond that headline gap, this audit found:

- **Nine live `feature.*` billing keys** exist platform-wide; till.py touches exactly one of them
  directly (`feature.api`) and indirectly depends on a second (`feature.visit`, via
  `subscribed_write_or_visit`). The other seven — bookings, campaigns, contacts,
  insights.engine, loyalty, rating, whatsapp — have **no till-reachable surface at all**, not even
  a read.
- **Two real doc/code mismatches** in the integration guides: `/redeem`'s `branch_id` is documented
  as strictly rejecting an unrecognised branch, but the code actually resolves it permissively and
  silently drops it to empty — the opposite of what `/visits` does with the same field name. And
  neither guide discloses that `/redeem` and `/offer/apply` work even when the shop's subscription
  has lapsed, while `/visits` does not — a real, currently undocumented asymmetry.
- **No self-service billing/wallet/ceiling visibility.** An integrator discovers it hit a licence
  wall, a lookup ceiling, or a rate limit only by being refused — there is no endpoint that reports
  "what is my remaining allowance" ahead of time.
- **No real staff attribution.** `operator_id`, `actor`, and `approved_by` are free-text strings
  never checked against the real `Operator` records `staff.py` maintains — a cashier can type any
  name into `approved_by` and unlock an above-threshold reward with nothing to stop it.
- **No branch-discovery endpoint.** `branch_id` is validated against a shop's real branches, but
  only as a side effect of posting a visit — there is no `GET` a till credential can call to list
  or pre-validate branches before it tries.

None of this is presented as a defect in what exists — `till.py` does what it does carefully and
correctly, per the line-by-line read below. It is a scope observation: the door was sized for one
feature and the platform has grown six more around it.

---

## Current Capability Inventory

All four routes live in `services/operations/app/api/v1/till.py`, mounted under `/api/v1/till`, and
share exactly one capability dependency: `_TILL = require_capability("operations.record")`
(`till.py:57`). A credential minted for this capability is an OAuth2 client-credentials machine
token (subject prefixed `svc_`, `core/licence.py:116-117`) whose tenant is read from the token
itself and never accepted from the request body — no model below has a `tenant` field
(`till.py:72-74`).

### 1. `POST /till/visits` — batch-record visits (`till.py:161-334`)

- **Dependencies:** `subscribed_write_or_visit` (needs `feature.visit`, `api/subscribed.py:109-111`)
  and `rate_limit` (the generic per-window limiter, `till.py:161`).
- **Request model `TillBatchIn`** (`till.py:102-105`): `visits: list[TillVisitIn]`,
  `min_length=1, max_length=50` — an empty batch is a 422; the 50-cap exists so an SDK draining a
  backlog after a network outage does not put a thousand tills on the service in the same second
  (`till.py:103-104`).
- **`TillVisitIn`** (`till.py:69-99`): `phone`, `name`, `plate` (all optional, ≤32/128/32 chars);
  `branch_id` (**required**, `min_length=1, max_length=64` — made mandatory specifically because it
  used to be optional and every branch's visits landed in one heap, silently disabling
  «قارن فروعك» for chain shops, `till.py:79-85`); `operator_id` (optional free text, ≤64 chars, never
  validated against a real record — see Correctness/Security Notes); `meter` (odometer, 0 to
  10,000,000); `note` (≤1000 chars); `lines: list[TillLineIn]` (≤50 items); `invoice_id`,
  `idempotency_key` (both optional strings); `occurred_at` (the till's own clock, unix seconds).
- **`TillLineIn`** (`till.py:60-66`): `product_id`, `name`, `qty` (0-100,000), `amount_minor`
  (halalas, 0 to 1,000,000,000). The shop's catalogue is auto-built from these lines
  (`core/integration.py`, see below).
- **Deduplication is the one hard rule.** Every visit must carry at least one of
  `idempotency_key`, `invoice_id`, or `occurred_at` (`till.py:235-236`); a visit with none of the
  three is rejected by item, naming all three in the refusal reason. The idempotency key itself is
  derived in priority order — the till's own key, else `inv:{tenant}:{branch_id}:{invoice_id}`
  (namespaced by branch because multi-branch shops often restart invoice numbering per branch,
  `till.py:145-157`), else a content-fingerprint hash of the sale itself sorted by line so
  reordering lines between retries does not break dedup (`content_key`, `till.py:108-137`).
- **Per-item verdicts, never all-or-nothing** (`till.py:164-169`). A batch containing one
  permanently-invalid item does not block the other 49 forever — the response reports
  `{accepted, total, results: [{index, status, reason?}]}` with `status` one of `accepted`,
  `duplicate`, `rejected`, matched back to the caller's own array position by `index`
  (`till.py:307-315`).
- **Unknown-branch handling:** `branch_id` is checked against `operations.known_branches(tenant)`
  (`till.py:262`, backed by `core/operations.py:138`) and any id not in that set is rejected by
  name, not silently dropped — a deliberate divergence from the platform's normal permissive
  `core/branches.py::resolve()` behaviour used everywhere else, explained at `till.py:250-258`: a
  silently-ignorable mandatory field would recreate the exact bucketing bug the mandatory field was
  added to fix.
- **Licence gate:** `feature.api` is checked separately from `feature.visit`
  (`refuses_machine_writes`, `till.py:205-220`) — a shop can hold `feature.visit` (the field-screen
  app) without ever having bought the programmatic link, and a machine credential posting without
  `feature.api` gets every item in the batch rejected with the same English reason string
  (`core/licence.py:43-44`), reported per-item in the same shape as any other rejection so an SDK
  reading `results[i]` does not silently drop the whole batch (`till.py:209-213`).
- **Fails open on an unreachable billing peer, not on an unknown shop.** `refuses_machine_writes`
  only refuses on a definite `False`; `None` ("could not ask") lets the sale through, because a
  fleet-wide billing hiccup must never stop every till in the country from recording its day
  (`core/licence.py:15-26`, `95-99`).
- **The lookup-allowance ledger is funded here.** Every accepted visit raises this credential's
  daily customer-lookup allowance by one (`till.py:321-322`, `note_visit`, see till_budget.py
  below).
- **A health "pulse" is written on every response**, whatever the outcome, keyed by tenant
  (`till.py:171-192`, `324-333`, `core/till_health.py`) — accepted/rejected/duplicate counts and the
  most recent rejection reason, feeding an internal partner-health panel that tells staff which
  shop's till has gone quiet. This never blocks the sale (`till.py:331-332`) and is entirely
  invisible to the integrator — no endpoint exposes it back to them.

### 2. `GET /till/customer` — customer lookup (`till.py:354-448`)

- **Dependency:** only `rate_limit` — no subscription gate at all, on the reasoning that a customer
  standing at the till is already owed the answer regardless of the shop's billing state
  (`core/licence.py:10-13`).
- **Query params:** `phone`, `plate` (either).
- **No 404 for a new customer** — `{"found": false}` (`till.py:395`), because a first-time
  customer is the ordinary case at a counter, not a fault (`till.py:359-360`).
- **Never returns the pseudonym** (`subject_ref`) — the cross-service join key has no use to a
  third party and is a durable identifier risk with no benefit if leaked into their database
  (`till.py:362-364`).
- **Charged against the lookup-abuse ceiling before the read happens** (`till.py:381-387`,
  `core/till_budget.py`) — see Correctness/Security Notes for the mechanism. A ceiling breach is a
  `429`, never a `403`: the credential is still valid (`till.py:383-387`).
- **Response shape**, built up conditionally:
  - `found`, `name`, `visits` (read from `c.visit_count`, deliberately not a bare `getattr(...,
    "visits", 0)` — see Correctness/Security Notes for the bug this replaced, `till.py:397-401`).
  - If no loyalty desk is wired, or the shop has no `subject_ref` on file: stop here, silently — a
    shop without the loyalty feature gets no points section, not a zero (`till.py:403-408`).
  - If the loyalty peer is unreachable: `points_unavailable: true` rather than a `0`
    (`till.py:410-414`) — the distinction is the whole point of the endpoint's design (see the
    module's own "three states" framing, `till.py:340-350`).
  - If loyalty answers but does not know whether this shop runs a programme at all (`bal` missing
    `has_programme`): also `points_unavailable: true` (`till.py:429-431`).
  - If the shop genuinely has no programme: no points section, silently (`till.py:432-433`).
  - Otherwise: `points`, `to_next_reward`, `manager_threshold` (the shop's manager-approval
    threshold — a recent fix, `till.py:439-444`, because affordability and manager-approval are
    different questions and the till was previously offering un-approvable rewards as if they were
    free to redeem), and `rewards: [{id, name, cost, needs_approval}]` — only what the customer can
    actually afford, matching the field screen's own presentation (`till.py:437-447`).

### 3. `POST /till/redeem` — spend a loyalty reward (`till.py:451-544`)

- **Dependencies:** `subscribed_write` (a generic "any paid app" gate, **not**
  `refuses_machine_writes`/`feature.api`) and `rate_limit` (`till.py:472`).
- **`TillRedeemIn`** (`till.py:451-469`): `phone`, `plate` (either); `reward_id` (required);
  `idempotency_key` (**required**, no default — a self-generated key would be new on every retry and
  double-spend the customer's points, `till.py:457-459`); `actor` (optional cashier id, free text);
  `approved_by` (required only for a reward above the shop's manager-approval threshold — loyalty
  itself refuses those without a name, `till.py:461-464`); `branch_id` (**required** on the model,
  `min_length=1`, `till.py:469`).
- **Deliberately NOT gated by `feature.api`** (`till.py:488-505`) — this is the one place in the
  file where the ordinary "is this establishment entitled" billing question is explicitly the wrong
  question: a customer standing at the counter holding points the shop already promised is not a
  party to the shop's own invoice, and a lapsed subscription must not confiscate what he has earned
  (§9.9, quoted verbatim in the code comment, `till.py:496-501`). Only the programmatic link itself
  (recording a visit) stays billing-gated.
- **Branch resolution is permissive here**, unlike `/visits`: `svc.resolve_branch(tenant,
  body.branch_id)` (`till.py:534`) silently drops an unrecognised id to empty rather than rejecting
  the call — see Correctness/Security Notes, this is the doc/code mismatch found in this audit.
- **Audited before the attempt, not after** — a redemption the audit log could not record must not
  happen at all, because it is a customer's balance being spent (`till.py:522-526`).
- **Response:** on success, whatever `loyalty_desk.redeem()` returns, unwrapped
  (`transaction_ref`, `discount_halalas`, `reward_name`, `cost`, `balance`, `duplicate` — verified
  against the docs' example, not against `loyalty`'s own source, which is out of this file's scope);
  on failure, `{"ok": false, "reason": "NOT_FOUND"|"UNAVAILABLE"|"REFUSED", "message": "..."}` — the
  message is a full sentence meant to be read aloud to the customer directly, not an error code
  (`till.py:540-544`).

### 4. `POST /till/offer/apply` — apply a reminders-issued offer to a visit (`till.py:547-618`)

- **Dependencies:** `subscribed_write` and `rate_limit` (`till.py:558`) — same billing-exemption
  reasoning as `/redeem` and stated explicitly again (`till.py:580-583`): an offer already promised
  to a customer in a message he is holding is not something a lapsed invoice can revoke.
- **`TillOfferIn`** (`till.py:547-555`): `visit_id` (required — the offer is stamped onto the
  *visit*, never onto the offer itself, so a till that has not recorded a visit has nothing to mark,
  `till.py:550-551`); `phone`, `plate` (either); `actor` (optional).
- **Which offer applies is never the till's decision.** `reminders` alone judges scope/expiry/which
  offer is live for this customer; the till only names the visit it should be stamped against
  (`till.py:568-572`).
- **Idempotent per visit** — a second tap on the same visit returns the same offer and spends
  nothing further (`till.py:572-573`, `615-617`).
- **A write-ahead audit entry, corrected on refusal** — `offer.applied` is logged optimistically
  before the attempt, and if `apply_offer` raises, a second corrective audit entry is written naming
  the real outcome (`till.py:596-613`) — a fix from a 2026-09-12 QA finding that the write-ahead
  entry could otherwise claim success for an offer that was never actually applied.
- **Errors are returned, never raised** (`till.py:603-606`) — the platform strips detail off a
  raised HTTP exception, and this sentence is read aloud to a customer standing at the counter.

### Supporting infrastructure read in full for this audit

- **`core/till_budget.py`** — the customer-lookup ceiling. `allowance(visits_today) = FLOOR(40) +
  FACTOR(5) × visits_today` (lines 42-46, 62-63) — a *ratio* to real work, not a fixed window,
  because a per-window burst limiter alone does not stop a patient extractor holding a
  years-long-lived credential (module docstring, lines 1-33). Fails **closed**: an unreadable
  counter refuses the lookup rather than allowing it (lines 82-95) — the deliberate hard choice the
  module's own docstring names (lines 29-33). Keys the day by the shop's own Riyadh-local calendar
  day, not UTC (`_day`, lines 55-59) — fixed from an earlier bug where the allowance reset at 03:00
  Riyadh time, cutting a still-open shift's morning grace short.
- **`core/till_health.py`** — one row per tenant, written on every batch regardless of outcome
  (`record`, lines 30-58), read by an internal panel (`for_tenants`, lines 63-100) that reports
  three states — `never`, `quiet` (no post in `quiet_days`, default 7), `sending` — specifically so
  a shop whose vendor never finished integrating shows up distinctly from one whose till simply
  stopped posting. **No API surfaces this to the integrator themselves** — it is purely an internal
  ops tool today.
- **`core/licence.py`** — `feature.api`'s gate, `HttpApiLicence.allowed()` returns `True/False/None`
  (lines 72-92), offloaded to a thread pool so a slow billing peer cannot freeze the shared event
  loop for every other tenant's till (lines 79-92, a real historical incident this fixes).
  `is_machine_subject()`/`refuses_machine_write()` (lines 116-128) is what lets the *same*
  capability (`operations.record`) be held by both a till and a human field-screen operator while
  only the machine's writes are billing-gated.
- **`core/integration.py`** — the catalogue auto-adoption behind the first invoice a till ever
  sends. `note_invoice()` (lines 155-173) runs once per tenant (idempotent via a `STANDING` row),
  retiring only seeded, unused, unclaimed catalogue rows (`_retire_unused_seeds`, lines 175-193) —
  anything the owner edited, anything ever sold, or anything the till already matched by name is
  left untouched. Deactivates rather than deletes (`active = False`), reversible from «خدماتي».
  Scans at most the most recent 5000 visits (`_SCAN_CAP`, line 138) to decide "ever sold," failing
  safe toward *not* retiring a row rather than guessing.
- **`core/partners.py`** — commission attribution. First partner key to touch a tenant stamps it
  permanently (`_stamp_row`, lines 240-271); a directly-acquired shop is stamped with the sentinel
  `DIRECT` rather than left unstamped, so a partner integrating months later cannot claim a shop our
  own marketing brought in. Keys are bearer credentials, hashed with HMAC + a shared salt, shown
  once at creation (lines 28-30, 57-64, 95-119). Rotation supports a caller-chosen overlap window
  defaulting to **zero** (immediate cutover) rather than a lingering grace period, on the reasoning
  that an operator who does not explicitly ask for an overlap should never get one silently (lines
  131-169) — most relevant to a leaked key, which is exactly the case where an overlap is wrong.
- **`ci/gen_till_contract.py`** — both integration guides (English and Arabic) are generated from
  `till.py`'s own Pydantic models and route decorators, not hand-typed, and CI (`--check`) fails the
  build if either goes stale or a mounted route is undocumented (lines 607-636). This is a strong
  process control against future doc/code drift, though it does not (and structurally cannot) catch
  the two behavioural mismatches this audit found, because both are about *runtime behaviour*
  (branch resolution strategy, billing-exemption logic) that the generator has no way to introspect
  from field names and types alone.

---

## Feature-by-Feature Gap Analysis

### Bookings

Two services own booking logic: `services/bookings` (the authoritative state machine) and
`services/whatsapp-assistant` (a conversational/Flow client of it with its own availability-merge
layer for the AI and native-Flow channels).

**Capability inventory** (`services/bookings/app/core/operations.py`, class `BookingOperations`
starting line 188): `create()` (line 318, licence-gated, supports service-list or package bookings,
idempotency key, `payment_status` of `none`/`deposit`/`paid`, `intended_reward_id` — a loyalty
reward this booking already intends to redeem at attendance); `reschedule()` (line 446, re-checks
staff eligibility); `edit_services()` (line 466); `edit_note()` (line 488); `set_payment_status()`
(line 498, editable even on a closed booking); `set_intended_reward()` (line 522); `cancel()` (line
536, idempotent, refuses on an already-terminal booking); **`attend()`** (line 560 — **the only
path that turns a booking into a real Visit**, via a `VisitGateway` call into the same visit-record
shape `till.py` posts to, and then spends `intended_reward_id` via a `RewardGateway`); `no_show()`
(line 616, terminal, updates the no-show-risk statistic); `no_show_risk()` (line 635, a rolling
window/threshold read); `working_hours()`/`set_working_hours()` (lines 663, 685); booking-history
reads by customer id, pseudonym, or creating actor (lines 705, 713, 721); `nearest_slot()` (line
732, single-operator); `nearest_slots_any()` (line 802, multi-operator merged search with an
algorithm choice — nearest/least-loaded/manual-order); `day_slots_any()` (line 870, the WhatsApp
Flow's per-day availability read). Store-level reads add `no_show_summary` (per-operator
total/no-show tally, `stores.py:219`) and `counts_between` (calendar-view day tallies, `stores.py:263`).

The WhatsApp channel adds its own layer: `whatsapp-assistant/app/core/tools.py` exposes
`check_availability`, `propose_booking`, `list_my_bookings`, `propose_cancel_booking`,
`propose_reschedule_booking` to the LLM — all "propose," never a direct write; only
`execute_confirmed_proposal` (lines 571/614) actually commits, after a customer's own button tap.
`core/booking_assignment.py::RealBookingProvider` (line 84) is the HTTP client into `bookings` for
this channel; `core/flow_booking_backend.py::FlowBookingBackend` (line 82) backs the native
WhatsApp Flow booking UI.

**Licence key:** `feature.bookings` (`bookings/app/core/licence.py:40`), checked on `create`,
`reschedule`, `edit_services` — never on reads or on the terminal-state transitions
(`attend`/`cancel`/`no_show`) themselves, since those act on a booking already paid for.

**Gap list:**

1. **A till cannot mark a booking `attended` when the customer pays at the counter.** This is the
   headline finding of this audit (see Executive Summary): the till can record an unstructured
   visit, but has no route to call `bookings.attend(booking_id)`, so the booking's own state,
   `intended_reward_id` spend, and no-show-risk statistic never update from a till-driven checkout.
   A shop selling both `feature.visit` and `feature.bookings` has two systems that do not reconcile
   a single real-world event.
2. **A till cannot look up a customer's upcoming or past bookings** (`bookings_for_customer` /
   `bookings_for_subject`) — a cashier has no way to see "she has a 4pm appointment" or reconcile a
   walk-in payment against an existing booking.
3. **A till cannot create or reschedule a booking** — a customer asking to book their next visit at
   checkout has no path from the POS into `create`/`reschedule`.
4. **A till cannot mark `no_show` or `cancel`** — relevant when a customer calls the shop's own
   landline/counter rather than messaging WhatsApp.
5. **A till cannot flip `payment_status`** (e.g. `deposit` → `paid`) when the till itself just
   recorded the payment — payment state is tracked twice, in the till's own ledger and in the
   booking record, with nothing to reconcile them.
6. **A till cannot read `working_hours`/`nearest_slot` availability** — an integrated POS wanting to
   offer "book your next visit" at checkout has no availability query available to it.
7. **A till cannot read `no_show_risk`** for a customer at the counter — useful input to a
   deposit-required decision, currently console-only.

### WhatsApp AI Assistant

**Licence/control-plane surface:** `feature.whatsapp` is the priced entitlement
(`whatsapp-assistant/app/core/licence.py:30`), checked live (never cached) via
`HttpLicence.allowed(tenant)` and wrapped by `ToggleGatedLicence`, which ANDs that billing answer
with the shop owner's own on/off switch (`operations/app/core/ai_toggle.py`:
`AiToggleStore.get(tenant)`/`.set(tenant, enabled)`, absent = on). The toggle-off state is
indistinguishable to the customer from "never subscribed" — same refusal text
(`conversation.py:149`).

**Conversation engine** (`whatsapp-assistant/app/core/conversation.py`): a mandatory first-message
triage gate (`awaiting_triage`, lines 29-41) that can route straight to human escalation without
ever touching the LLM; a branch-selection gate for multi-branch shops (lines 122-136); explicit
human-handover triggers on request-pattern match, frustration detection, or wallet depletion; a
per-message LLM-cost wallet hold (`_reserve_llm_hold`, line 823); and an output sanitizer
(`_sanitize_reply`, line 425) that strips claimed-action phrases, model self-disclosure, fabricated
discounts, and raw phone-number-shaped strings before anything reaches the customer.

**Gap list:**

1. **A till/POS integration cannot toggle the AI assistant on/off** — only the console UI writes
   `ai_toggle`; a shop wanting the AI to auto-mute when the counter is short-staffed has no
   programmatic path.
2. **No read of whether a customer's WhatsApp thread is mid-escalation** — a cashier picking up a
   phone call from a customer already escalated to a human has no way to know that from the till.
3. **No till-writable channel to influence conversation context** — e.g. "this customer just paid
   cash" cannot reach the AI's context builder from outside.
4. **No wallet/usage-balance read** — an integrator dashboard cannot query the shop's AI wallet
   balance the way it might want to alongside its own billing view.

*(Most of the assistant's customer-facing tool capabilities — points summaries, redeemable-offer
suggestions, package listing — already have a till equivalent via `/till/customer` and `/till/redeem`;
the real gaps here are about controlling/observing the AI channel itself, which a till is not a
natural client for by default, but which an integrator building a unified back-office might still
plausibly want.)*

### Ratings

Ratings span `operations` (storage + aggregates), `reminders` (the request Flow + reply consumer),
and the console (handling UI).

**Storage/aggregate surface:** `Visit.rating` (`operations/app/core/models.py:417`, 0 = unrated,
never confused with a real 1-5 value), `feedback_text`, `rated_at`, `rating_handled_at`,
`rating_handled_note` (lines 420-424, owner-settable from the console only).
`VisitStore.ratings(tenant, *, stars, handled, operator_id, ...)` (`stores.py:390`) backs the
console's ratings tab; a per-operator aggregate (`stores.py:355`) returns
`{visits, ratings, rating_sum}` over a window, feeding the staff-performance comparison export.

**Trigger surface** (`reminders/app/core`): `rating_request.py` remembers one row per sent Flow,
single-use; `rating_reply.py::parse_rating_reply` parses Meta's Flow completion payload;
`rating_consumer.py` resolves the pending request and writes the rating via
`rating_writer.py::HttpRatingWriter.write(...)`, optionally awarding bonus points;
`rating_settings.py` holds per-tenant `enabled`/`points`/`delay_minutes`. A rolling-window quality
alert (`operations/app/core/rating_alerts.py::evaluate()`) fires
`operations.staff_rating_dropped` to branch managers when an operator's last 10 rated visits
(min 5 samples) average below 4.5.

**Licence key:** `feature.rating` (`operations/container.py:353`), gating whether the bonus-points
Flow variant is used — the underlying delay-timing setting applies to every shop regardless of
ownership.

**Gap list:**

1. **A till cannot trigger an immediate rating request** at checkout — only reminders' own delayed
   schedule sends the Flow; there is no way for a till to ask "send the rating request for this
   visit now."
2. **A till cannot read a customer's rating history** — whether their last visit was rated, or what
   they rated it, is invisible at the counter.
3. **A till/dashboard cannot read the per-operator rating aggregate** (`{visits, ratings,
   rating_sum}`) — a POS wanting to show "this stylist: 4.8★" at assignment time has no source for
   it.
4. **A till/back-office cannot mark a rating "handled"** or attach a handling note — console-only.
5. **No API surface for the rating-drop alert** — it only reaches in-app branch managers.
6. **No programmatic configuration of `rating_settings`** — a chain running many branches through
   one POS backend cannot bulk-configure rating behaviour; console-only today.

### Campaigns

`services/campaigns/app/api/v1/campaigns.py`, `core/goals.py`, `core/audience.py`.

**Capability inventory:** `GET /campaigns/goals` (goal cards with lock state and usage stats,
`campaigns.py:147-215`); `POST /campaigns/preview` (computed message + audience count, no write,
`218-349`); `POST /campaigns` (create/fire, `361-647`); `GET /campaigns`, `GET
/campaigns/{id}/runs` (list + per-firing totals including a `redeemed` count, `650-698`); `POST
/campaigns/{id}/pause` (`701-717`); platform-only audience-cap admin (`758-792`). The audience
engine (`core/audience.py::resolve()`, lines 116-186) computes per-goal candidates using each
customer's own cycle — e.g. `win_back` at 1.5× their usual interval.

**Licence key:** `feature.campaigns` (`campaigns/app/core/licence.py:46`).

**Gap list:**

1. **A till cannot report a conversion/attribution event back to a specific campaign.** The
   internal `redeemed` count (`campaigns.py:694`) is reconciliation-only; `POST /till/offer/apply`
   applies whatever offer reminders judges valid but never lets the till assert *which* campaign it
   came from, and non-offer goals (`announce`, `win_back`, `reward_loyal`) leave no redemption
   artifact at all — a shop cannot see "this till sale was the win-back campaign working."
2. **No query for "which campaigns currently target this customer"** independent of an
   already-recorded visit — useful for a pricing decision before ringing up a sale, not just after.
3. **No till-facing way to record marketing consent at the point of sale** — consent lives in
   reminders' own store, read only by campaigns internally.
4. **`GET /campaigns` / `GET /campaigns/{id}/runs` require an owner/staff token**, not the machine
   `operations.record` capability — a POS back-office wanting to reconcile "what went out this
   week" has no read access at all today.

### Packages

No dedicated `packages.py` core file exists; the model lives directly in `operations/app/core/models.py`
(`class Package`, line 245) and `stores.py::PackageStore` (line 280), with CRUD routes mounted in
`staff.py` (`GET/POST /packages` at lines 1686/1699, `PATCH /packages/{id}` at 1759) under the same
capability as service-catalogue management. A package is a named, priced bundle of ≥2 of the
shop's own services (`_validate_package_services`, line 1657); `Visit.package_id`
(`operations/app/core/models.py:412`) lets a visit be tagged as fulfilling one. There is **no
`feature.package*` licence key anywhere** — packages ride on whichever base entitlement gates the
field/booking screen.

**Gap list:**

1. **`TillVisitIn` has no `package_id` field** — despite `Visit.package_id` existing and being
   written internally by the field screen, a till has no way to tell Raje3 a sale fulfilled a
   specific package; it can only send free-text invoice lines.
2. **No API to check a customer's package status** — since a package here is a one-shot bundle
   rather than a multi-session balance (confirmed: no `remaining`/`sessions_left` field anywhere in
   `Package`), this gap is narrower than it first appears, but the tagging gap above (#1) still
   means till-recorded package fulfilment is invisible to any package-usage reporting.
3. **No API to purchase/create a package for a customer** at all — package purchase has zero API
   surface, internal or external; it is a catalogue-management action only.

### Insights

`services/insights/app/api/v1/insights.py` + `features.py` + `operator.py`;
`core/{associations,audit,backup,bundles,coverage,digest,dispute_report,erasure,indicators,models,
next_step,plans,rollup,runtime_config,tick}.py`.

**Read surface:** `GET /insights/dashboard` (a nightly-precomputed snapshot: indicators, coverage
flags, branch scoping, next-step card, staleness flags, consented-audience count — lines 73-255);
`GET /insights/associations` (product-pair verdicts, gated separately, lines 268-287); `GET
/insights/bundles` (suggested-bundle cards feeding packages' "suggested" source, 290-307); `GET
/insights/branches` (per-branch comparison, 310-348); `GET/PUT /insights/digest` (weekly email
toggle, 380-413); `POST /insights/refresh` (on-demand recompute, 15-minute cooldown, 422-461).
Platform-only: recompute/summary and a dispute-report generator.

**Licence keys:** RBAC capabilities (`insights.read`, `platform.insights`, `platform.compliance`)
gate the routes; the billing key is `feature.insights.engine`
(`operations/app/core/apps.py:216`), which specifically gates the associations sub-feature via
`insights.can_see("associations", …)` — there is no bare `feature.insights` key for the dashboard
itself.

**Gap list:**

1. **No machine/API-key access exists at all.** Every route requires a human `Principal` token;
   unlike `till.py` there is no machine-credential door into insights, so an external dashboard has
   zero entry point regardless of what it might want to read.
2. **No live/request-time KPI feed** — the dashboard is a nightly batch snapshot (`tick.py`), not
   computed on demand, which would matter even if a machine-credential door existed.
3. **No webhook/event surface** — pull-only, and the pull requires login, not an API key.

*(Insights is judged here as a clean, structural "no gap the till specifically should close" —
these are read-only, human-facing, low-frequency reports; nothing about a POS integration
plausibly needs a KPI dashboard feed through the same door that posts sales.)*

### Contacts

No dedicated `contacts.py` core file, no `class Contact`, no `/contacts` route anywhere in
`services/operations`. `feature.contacts` ("جهات الاتصال") is a billing/app-catalogue entry
(`apps.py:237-241`) riding the same field-screen mechanism as visits and bookings — the only real
entity is `Customer`, created or updated purely as a byproduct of `record_visit`
(`operations.py:246`) or `POST /field/customers/ensure` (`field.py:482-483`, gated by
`subscribed_write_or_customer_creating_app`, which accepts `contacts_licence` OR
`bookings_licence` — `api/subscribed.py:97-104`).

**Gap list:**

1. **No standalone contact CRUD independent of a visit or booking** — every customer write goes
   through one of those two paths; there is no way to pre-populate or bulk-import a customer book
   before any visit exists.
2. **No contact-merge/dedup API** — `customer_by_phone`/`customer_by_plate` are read-only lookups;
   a till capturing a phone number in a different format (e.g. with/without a country code) has no
   way to request a merge.
3. **No consent field settable via the till** — a POS collecting marketing consent at the counter
   has nowhere to send it; consent lives entirely in `reminders`' own store, written elsewhere.

### Staff / Branches / Teams

Confirmed by direct read of `till.py` and `services/operations/app/core/branches.py` plus
`api/v1/staff.py`.

**What exists internally:** a real staff/operator system — `POST /operators` (`staff.py:137`), `GET
/operators` (`staff.py:562`), PIN verification (`POST /operators/verify-pin`, `staff.py:634`),
mandatory per-operator branch assignment at creation (`staff.py:130-134`). A real branch-listing
route, `GET /branches` (`staff.py:1213`), gated by a **different** capability
(`_READ_BRANCHES`) than the till's `operations.record` — a till credential cannot call it. The
platform's normal, permissive branch resolution (`branches.py:56-88::resolve()`) silently drops an
unrecognised branch id to empty rather than rejecting; `till.py` deliberately overrides this for
`/visits` (hard reject, `till.py:250-268`) but **not** for `/redeem` (`till.py:534`, uses the
permissive `resolve_branch` — see Correctness/Security Notes).

**Gap list:**

1. **No branch-discovery endpoint reachable by a till credential.** `branch_id` validation happens
   only as a side effect of posting a visit and being told which id was wrong — there is no `GET`
   a till can call ahead of time to list or pre-validate a shop's real branches. `GET /branches`
   exists but requires a different capability a till credential does not and cannot hold.
2. **No real staff-record attribution.** `operator_id` (`TillVisitIn`), `actor` (`TillRedeemIn`,
   `TillOfferIn`), and `approved_by` (`TillRedeemIn`) are all free-text strings, documented as such
   deliberately ("Stored as sent — we do not build a second accounts system," `pos-integration-guide.md:47`)
   — but never cross-checked against the real `Operator` table `staff.py` maintains. This is a
   correctness/security note as much as a gap: see below.

### Wallet / billing self-service

Read in full: `operations/app/core/licence.py`, plus a search across
`subscribe.py`/`wallet_topup_reconcile.py`/`whatsapp_licence.py`/`feature_licence.py`/`msg_limits.py`/`seats.py`.

**Gap list:**

1. **No endpoint reports the shop's own subscription/entitlement state to an integrator.** The only
   signal a till gets that `feature.api` is missing is its entire visits batch coming back rejected
   with an English sentence (`core/licence.py:43-44`) — there is no way to check ahead of time.
2. **No endpoint reports remaining lookup allowance** (`till_budget.py`'s ratio) — a till only
   discovers it hit the ceiling via a `429`, with no "you have N lookups left today" number
   available beforehand.
3. **No endpoint reports WhatsApp message ceilings, wallet balance, or any other billing/usage
   state** an integrator's own back-office might want to display alongside its own metrics.

All of this is enforced correctly and safely server-side (see `refuses_machine_writes`'s
fail-open-on-outage design, a genuinely careful piece of engineering) — the gap is specifically the
absence of a *read* an integrator could poll proactively, not any weakness in the enforcement
itself.

### Full `feature.*` key enumeration (whole `services/` tree)

Nine live keys confirmed by direct grep across every `core/licence.py`-equivalent file
(`feature.base` was retired 2026-09-10 and excluded; `feature.md` and `feature.a`/`feature.b`
grep hits were false positives — a doc filename and f-string fragments respectively):

| Key | Defined | till.py coverage |
|---|---|---|
| `feature.api` | `operations/core/licence.py:38` | **Covered** — the one key `till.py` checks directly, gating `/visits`. |
| `feature.visit` | `operations/core/subscribe.py:182`, checked via `subscribed_write_or_visit` | **Covered indirectly** — `/visits` also requires this. |
| `feature.bookings` | `bookings/core/licence.py:40` | **Gap** — no till surface at all (see Bookings above). |
| `feature.campaigns` | `campaigns/core/licence.py:46` | **Gap** — no attribution/query surface (see Campaigns above). |
| `feature.contacts` | referenced `operations/container.py:348`, `apps.py:240` | **Gap** — no standalone CRUD (see Contacts above). |
| `feature.loyalty` | `loyalty/core/licence.py:44` | **Partially covered** — `/redeem` and the points section of `/customer` cover the core loop; no read of loyalty configuration or history beyond current balance. |
| `feature.rating` | referenced `operations/container.py:353` | **Gap** — no trigger/read/config surface (see Ratings above). |
| `feature.whatsapp` | `whatsapp-assistant/core/licence.py:30` | **Gap** — no control-plane surface (see WhatsApp above). |
| `feature.insights.engine` | `operations/core/apps.py:216` | **No gap identified** — insights is read-only/human-facing/batch by nature; not a plausible till use case (see Insights above). |

No `feature.package*` key exists (packages are unlicensed independently of the base app that
gates the screen they're managed from).

---

## Correctness / Security Notes

These are secondary findings from the line-by-line read — none block the audit's main purpose, but
each is a real, specific observation a careful reviewer would flag.

1. **`/redeem`'s branch handling silently contradicts its own documentation and its sibling
   endpoint's behaviour.** `till.py:534` resolves `branch_id` via `svc.resolve_branch()` — the
   platform's normal *permissive* resolver, which drops an unrecognised id to empty
   (`branches.py:56-88`) — while `/visits` (`till.py:250-268`) and the documentation for both
   endpoints (`pos-integration-guide.md:46,162`) describe branch_id as strictly rejecting an
   unrecognised id "the same way" on every door. It is not the same way: a redemption with a typo'd
   branch id is silently recorded under "no branch" rather than refused and named back to the
   caller, while the identical mistake on a visit stops the whole item. The in-code comment at
   `till.py:532-533` ("A till that sends no branch — most of them, since the field is optional")
   also appears to be stale leftover text from before `branch_id` became a required Pydantic field
   (`min_length=1`, `till.py:469`) — the comment and the field constraint disagree with each other.
2. **The subscription-lapse exemption on `/redeem` and `/offer/apply` is undocumented in both
   integration guides.** `till.py:486-505` and `till.py:580-583` deliberately do not gate these two
   routes on `feature.api`/billing state — a sound design decision, correctly reasoned in the code
   comments — but neither `docs/pos-integration-guide.md` nor `docs/دليل-ربط-الكاشير.md` states
   that a shop with a lapsed subscription can still redeem loyalty points and apply offers via the
   till while it cannot post new visits. An integrator building error-handling logic around a
   uniform "subscription lapsed → everything 402s" assumption would get this wrong.
3. **`operator_id`, `actor`, and `approved_by` are never validated against real staff records.**
   Confirmed by direct read: `till.py:87, 460, 464, 555` are all free-text `str` fields, forwarded
   or logged as-received with no join against `staff.py`'s `Operator` table. This is documented as
   deliberate ("we do not build a second accounts system," `pos-integration-guide.md:47`) for
   `operator_id`, which is a reasonable design choice for a field that's purely descriptive — but
   `approved_by` is functionally different: it exists specifically to satisfy loyalty's
   manager-approval gate for above-threshold rewards (`till.py:461-464`), and as implemented, any
   non-empty string satisfies that gate. A cashier's own POS terminal can type a manager's name into
   this field with nothing to verify it was actually that manager who approved anything.
4. **The generic per-window `rate_limit` dependency present on every route
   (`till.py:161,354,472,558`) is entirely undocumented** — both integration guides describe only
   the lookup-ratio limiter (and only for `/customer`), never the ordinary burst limiter that also
   sits on `/visits`, `/redeem`, and `/offer/apply`. An integrator would not expect a `429` from a
   plain traffic burst on those three routes based on reading the docs alone.
5. **`GET /till/customer`'s response shape has no formal field table**, unlike the other three
   endpoints — it is documented only via worked JSON examples (`pos-integration-guide.md:120-148`).
   This is a structural documentation gap: any future field added to the response (the way
   `manager_threshold` was recently added, `till.py:444`) is invisible to a reader unless it
   happens to appear in an example, whereas the generator (`ci/gen_till_contract.py`) *does*
   auto-derive field tables for every `Till*In` request model — the asymmetry is that no
   `Till*Out`-style response model exists for the generator to read from, since these are built as
   raw dicts.
6. **A well-reasoned, worth-noting design correctness win:** the `visit_count` field read
   (`till.py:397-401`) is explicit (`c.visit_count`) rather than a defaulting `getattr(c, "visits",
   0)` specifically because the earlier version's default silently answered `0` for a customer who
   had visited for two years — a real historical bug the current code comment documents by name.
   Flagged here as a positive correctness pattern worth preserving as a review habit elsewhere in
   the codebase: prefer an attribute access that fails loudly on a rename over a `getattr` default
   that fails silently, on any field a human reads as a fact about the world.
7. **Rate-limit key composition for a till credential is per-subject-and-IP, not per-tenant.**
   `services/operations/app/config.py:635-639` shows the default `RATELIMIT_KEY_PARTS =
   "subject,ip"` and no `/till`-specific route entry in `RATELIMIT_ROUTES` — so every till
   credential shares the platform-wide default of 100 requests/60 seconds, keyed by its own
   `svc_…` subject (stable) and calling IP (usually stable for a shop's own till). This is generous
   enough for a real counter and is not itself a flaw, but it means a single credential's window is
   shared across *all four* routes together (a burst of lookups can eat into the budget a
   simultaneous visit-posting burst needs, and vice versa) — worth knowing if a future incident
   ever needs to reason about why a till hit a 429 on `/visits` right after a lookup burst on
   `/customer`.

---

## Recommended v-next Endpoint List

Grounded directly in the gaps enumerated above, in rough priority order given how concretely each
gap was demonstrated:

1. **`POST /till/bookings/{booking_id}/attend`** — closes the single largest gap found (Bookings
   #1): let a till mark a booking fulfilled at the moment of till payment, spending
   `intended_reward_id` and updating no-show-risk the same way the field screen's own attend action
   does.
2. **`GET /till/bookings?phone=…|plate=…`** — surface a customer's upcoming/recent bookings at the
   counter (Bookings #2), the natural read pairing with #1.
3. **`GET /till/branches`** — a branch-listing/pre-validation endpoint reachable by the till's own
   `operations.record` capability (Staff/Branches #1), instead of requiring a customer to discover
   a bad `branch_id` only by having a visit rejected.
4. **Fix, not build: make `/redeem`'s branch handling match `/visits`'s** (hard-reject an unknown
   id, matching what both integration guides already promise) — a correctness fix, not a new
   surface (Correctness Note #1).
5. **`GET /till/status`** — a self-service read of the shop's own `feature.api`/`feature.visit`
   entitlement state and remaining lookup allowance, so an integrator can proactively surface "your
   link needs renewing" rather than discovering it via a batch of rejections (Wallet/billing gap
   #1-2).
6. **`POST /till/redeem` — require `approved_by` to name a real operator** (a join against
   `staff.py`'s `Operator` table, or at minimum a PIN-style verification reusing the existing
   `POST /operators/verify-pin` mechanism) — closes Correctness Note #3, a real approval-bypass
   surface.
7. **`invoice_id`/package tagging on `TillVisitIn`: add an optional `package_id` field** — lets a
   till-recorded sale be attributed to a specific package the way the field screen already can
   (Packages #1).
8. **`POST /till/offer/apply` — extend to accept an optional `campaign_id` or return which campaign
   the applied offer came from** — closes the attribution gap that keeps a shop from ever seeing "the
   win-back campaign worked" from till-recorded evidence (Campaigns #1).
9. **`POST /till/rating-request`** — let a till trigger an immediate rating request for a
   just-recorded visit rather than waiting for reminders' scheduled delay (Ratings #1), the most
   concretely useful of the ratings gaps because it turns a passive wait into a counter-moment
   action, matching the same "say it at the counter" design philosophy `till.py`'s own module
   docstring already argues for regarding loyalty and offers.

Deliberately **not** recommended, with reasoning: a machine-credential door into `insights`
(read-only, human-facing, nightly-batch data has no natural fit with a till's write-heavy,
real-time traffic pattern); a till-writable AI-toggle or conversation-context channel (the
WhatsApp control plane is an owner/console decision by design, and a till acting on it would blur
who is actually in charge of the customer-facing channel); standalone contact CRUD as a *new* door
(the existing `POST /field/customers/ensure`, already reachable by `contacts_licence` OR
`bookings_licence`, is the right shape for this — extending till.py to duplicate it would create a
second, divergent customer-creation path rather than closing a real gap).
