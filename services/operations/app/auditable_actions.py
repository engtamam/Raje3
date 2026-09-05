"""operations — auditable actions: what this service must be able to PROVE it did.

════════════════════════════════════════════════════════════════════════════════════
  COPY THIS FILE INTO YOUR SERVICE AND FILL IN THE LIST. That is the whole job.
════════════════════════════════════════════════════════════════════════════════════

Why this file exists at all: audit-service shipped a working, hash-chained log and for months not
one service wrote to it. Every test passed, the chain verified perfectly, and it contained nothing.
An empty audit log is worse than no audit log — it passes a compliance questionnaire and answers
nothing when someone asks "who did this?".

Nothing infers what is auditable. **What nobody declares, nobody logs**, and the failure is silent,
so the list is explicit and a gate (safety:audit-wiring) fails if a service declares nothing.

────────────────────────────────────────────────────────────────────────────────────
WHAT BELONGS HERE — four sources, and most people only think of the first
────────────────────────────────────────────────────────────────────────────────────

  source="admin"     an operator acting through the admin panel. Start from your admin_actions.py.
  source="user"      an end user acting on their own data. Start from your user_actions.py.
  source="internal"  SERVICE-TO-SERVICE calls on /internal/*. THE MOST-MISSED CATEGORY, and often
                     the most important: "this service deleted a person's data because a DSAR told
                     it to" is the single most audit-worthy thing it will ever do, and it appears
                     in no panel and no catalog.
  source="auth"      logins, MFA changes, token refreshes — and FAILED ones. These are pre-auth, so
                     they are deliberately absent from the action catalogs; a burst of failures is
                     the most common first sign of an attack.
  source="system"    scheduled work with no human actor: a retention purge deleted 500 rows, a
                     sweeper cancelled a job. Nobody clicked anything, and it still needs a record.

A catalog is therefore a SEED, not the answer: `auditable ⊇ admin ∪ user`, plus internal, auth and
system. Read your own routes — including every `/internal/*` one — rather than trusting a list.

────────────────────────────────────────────────────────────────────────────────────
THE ONE FIELD TO THINK HARDEST ABOUT: `critical`
────────────────────────────────────────────────────────────────────────────────────

`critical: True` means **the action is REFUSED if it cannot be recorded** (503). Not a severity
label — a behaviour, and one that trades availability for evidence.

Mark it True when an unprovable action is worse than a refused one. That is the test, and it is
usually true for exactly one family of things: **who was given power, and who took data out.**

    permission granted / role changed      an unattributable grant is indistinguishable
                                           from an attacker's
    credential or MFA changed              account takeover looks exactly like this
    data exported / bulk-read              the difference between a customer and a breach
    account suspended / deleted            someone lost access and can dispute it
    another person's data erased           you must be able to prove you did it, and when
    security setting changed               turning off a control must never be quiet

Mark it False for routine work — profile edits, reads, list endpoints. Refusing those during an
audit outage protects nothing and turns a logging blip into a partial platform outage.

If you are unsure: ask whether you would be comfortable telling a regulator "it happened, and we
have no record of it". If not, it is critical.

────────────────────────────────────────────────────────────────────────────────────
THE ACTOR IS ALWAYS A PSEUDONYM
────────────────────────────────────────────────────────────────────────────────────

Pass `subject_ref`, never a name, email or raw user id. An audit log holding raw identities becomes
a PII store in its own right — and one that CANNOT honour an erasure request, because deleting a
row from a hash chain is precisely what breaks the chain. Pseudonymise at the edge and the log
stays both useful and erasable: erase the linkage in identity-service and every entry here becomes
an orphan that names nobody, while the chain still verifies.

────────────────────────────────────────────────────────────────────────────────────
THEN EMIT IT — the other half of the job
────────────────────────────────────────────────────────────────────────────────────

Declaring an action does not record it. At the point the action happens:

    await request.app.state.auditor.record(
        "permission.granted",
        actor=subject_ref,               # a PSEUDONYM — see below
        resource=f"grant:{grant.id}",
        tenant=principal.tenant,
        ip=request.client.host,
        metadata={"capability": cap},
    )

For a `critical` action, let `AuditUnavailable` propagate — the API layer turns it into a 503. That
is the fail-closed decision doing its job, and swallowing it would quietly undo the whole point.

Emitting an action that is NOT in the list below raises: an event nobody declared is invisible to
the CI gate and to the investigator searching the log, so it would be audited in name only.

Where to point it (app/config.py has the full set):

    AUDIT_SINK_DRIVER=http   -> the receipt carries seq + hash; the event is sealed INTO the chain
    AUDIT_SINK_DRIVER=eventbus -> no hot-path cost, but the receipt means PUBLISHED, not recorded
    AUDIT_SINK_DRIVER=null   -> records nothing and says so; production refuses to boot on it

See app/adapters/audit_sink/*.py for the trade-off in full, and app/ports/audit_sink.py for the
wire contract.

────────────────────────────────────────────────────────────────────────────────────
FORMAT
────────────────────────────────────────────────────────────────────────────────────

A PURE literal — no imports, no f-strings, no variables, no computed values. It is read with
`ast.literal_eval`, so the gate can check it without importing (and therefore executing) your
service. A variable reference here breaks the gate, not just this file.

    action    dotted `noun.verb`, past tense: "user.suspended", not "suspend_user". It is a record
              of something that HAPPENED.
    source    admin | user | internal | auth | system   (see above)
    critical  True = refuse the action when it cannot be recorded
    resource  what kind of thing it acts on ("user", "invoice"). Not the id — that goes at runtime.
    why       REQUIRED when critical is True. One line: what an investigator would lose without it.
              If you cannot write this line, the action probably is not critical.
"""
from __future__ import annotations

from typing import Any

AUDITABLE_ACTIONS: list[dict[str, Any]] = [
    {
        "action": "visit.recorded",
        "source": "user",
        # CRITICAL, and the choice deserves defending because it costs something. A visit that
        # cannot be witnessed is refused, which means an audit outage stops the shop floor.
        # The alternative is worse: the visit record is what a reminder, a loyalty point and an
        # owner's revenue figure are all derived from, and an unattributable one lets an operator
        # record work that was never done, or delete the evidence that it was.
        "critical": True,
        "resource": "visit",
        "why": "every reminder, point and revenue figure derives from a visit; an unrecorded one "
               "cannot be disputed, corrected, or attributed to whoever entered it",
    },
    {
        "action": "visit.rated",
        "source": "internal",
        # NOT CRITICAL — unlike visit.recorded, an audit outage must not turn away a customer's
        # rating: the visit already happened and is already witnessed; this is a fact ABOUT it,
        # not the evidence that it occurred.
        "critical": False,
        "resource": "visit",
        "why": "a customer's WhatsApp Flow reply writes a rating and free-text comment onto an "
               "existing visit — attributing which call did that, and when, matters the same way "
               "any other write to a visit does",
    },
    {
        "action": "subscription.created",
        "source": "admin",
        "critical": True,
        "resource": "plan",
        "why": "money changes hands and the establishment's entitlements change with it; an "
               "unattributable subscription cannot be reconciled against an invoice, and 'who "
               "moved this shop onto this plan' is the first question asked about a billing "
               "dispute",
    },
    {
        "action": "subscription.refused",
        "source": "admin",
        "critical": False,
        "resource": "plan",
        "why": "a refusal is a decision OF OURS about somebody's money — the shop tried to pay "
               "and we declined. Without the record, support is told 'I tried to subscribe and "
               "nothing happened' and has nothing to answer with; with it, the reason and the "
               "moment are both there",
    },
    {
        "action": "operator.created",
        "source": "admin",
        "critical": True,
        "resource": "operator",
        "why": "a new operator is a new person who can record work in this establishment's name; "
               "an unattributable creation is indistinguishable from an intruder adding himself",
    },
    {
        "action": "operator.pin_rejected",
        "source": "user",
        # NOT critical: a failed PIN must not be able to take the screen down. One is a fat
        # finger. The value is in the PATTERN, and a pattern cannot be seen if failures go
        # unrecorded — which is exactly how PIN-guessing goes unnoticed everywhere it goes
        # unnoticed.
        "critical": False,
        "resource": "operator",
    },
    {
        # Moving somebody to a branch decides where his work is counted — and stopping him ends
        # his access to the shared screen.
        "action": "operator.updated",
        "source": "admin",
        "critical": False,
        "resource": "operator",
    },
    {
        # A custom schedule narrower than the shop's own hours — worth its own row rather than
        # folding into `operator.updated`: this changes which bookings can even reach him, not
        # merely his name or branch.
        "action": "staff_hours.changed",
        "source": "admin",
        "critical": False,
        "resource": "operator",
    },
    {
        "action": "branch.created",
        "source": "admin",
        "critical": False,
        "resource": "branch",
    },
    {
        # THE SHOP'S NAME. It signs every WhatsApp message and heads the customer's own page, so
        # «when did this shop start calling itself that, and who changed it» is a question both
        # support and a template review can ask months later.
        "action": "shop.renamed",
        "source": "admin",
        "critical": False,
        "resource": "tenant",
    },
    {
        # A one-way change to how the whole establishment sends. Recorded because "when did we
        # become per-branch, and who decided" is the first question support will ask.
        "action": "shop.mode_changed",
        "source": "admin",
        "critical": False,
        "resource": "shop_mode",
    },
    {
        # Whether this shop works on cars — the switch «تسجيل زيارة» changes shape for. Recorded
        # because the visible symptom is somebody else's: an operator rings to say the plate page
        # vanished, and «who turned it off, and when» is the whole of the answer.
        "action": "shop.vehicles_changed",
        "source": "admin",
        "critical": False,
        "resource": "shop_vehicles",
    },
    {
        "action": "member.hired",
        "source": "admin",
        # CRITICAL: this is a person being given access to an establishment's data. An unrecorded
        # grant is indistinguishable from an attacker's, and it is the one family of acts where a
        # refused action is better than an unprovable one.
        "critical": True,
        "resource": "member",
        "why": "who was given access to a shop's customers, and by whom — a grant nobody can "
               "attribute cannot be disputed, revoked with confidence, or explained to a regulator",
    },
    {
        # Renaming or closing a place — the name appears on every report about it, and closing one
        # changes which places a shop is paying for.
        "action": "branch.updated",
        "source": "admin",
        "critical": False,
        "resource": "branch",
    },
    {
        "action": "service.created",
        "source": "admin",
        "critical": False,
        "resource": "service",
    },
    {
        "action": "service.updated",
        "source": "admin",
        # NOT critical, but audited for a specific reason: this route changes PRICES. A dispute
        # about what a service cost last month is answered by this record and by nothing else.
        "critical": False,
        "resource": "service",
    },
    {
        "action": "package.created",
        "source": "admin",
        "critical": False,
        "resource": "package",
    },
    {
        "action": "package.updated",
        "source": "admin",
        # Same reason as service.updated — this route changes what a package costs and what it's
        # made of.
        "critical": False,
        "resource": "package",
    },
    {
        "action": "service.bulk_imported",
        "source": "admin",
        # Same reason as service.updated — a whole catalogue's prices can change in one call, and
        # deactivate_missing can retire a whole batch at once. The metadata (created/updated/
        # reactivated/deactivated counts) is what makes this record actually useful to a dispute,
        # not just proof that SOMETHING happened.
        "critical": False,
        "resource": "service",
    },
    {
        "action": "subject.erased",
        "source": "internal",
        "critical": True,
        "resource": "subject",
        "why": "erasure is irreversible and this service holds the phone number itself; without a "
               "record we cannot prove we honoured the request, and the data is gone so nothing "
               "else can show it",
    },
    # ── the operator surface, inherited from the template and emitted by app/api/v1/operator.py.
    # Declared here because WHAT NOBODY DECLARES, NOBODY LOGS — and these three change credentials
    # and runtime policy, which is the highest-privilege surface this service has.
    {
        "action": "operator.secret_set",
        "source": "admin",
        "critical": True,
        "resource": "secret",
        "why": "the previous value is overwritten by the action itself, so an unrecorded rotation "
               "is unreconstructable",
    },
    {
        "action": "operator.secret_cleared",
        "source": "admin",
        "critical": True,
        "resource": "secret",
        "why": "removing a credential can silently disable an integration; without a record there "
               "is nothing to point at when it stops working",
    },
    {
        "action": "operator.config_changed",
        "source": "admin",
        "critical": True,
        "resource": "config",
        "why": "runtime policy changed without a deploy — the only trace it happened at all",
    },
    # ── the platform console. Editing the message library changes what EVERY establishment sends
    # afterwards, which makes these the highest-leverage edits in the product — a wrong word
    # propagated to a thousand shops is invisible until their customers read it.
    {
        "action": "platform.template_changed",
        "source": "admin",
        "critical": True,
        "resource": "template",
        "why": "the text every establishment sends afterwards; a wrong edit reaches thousands of "
               "customers under an establishment's name, not ours",
    },
    {
        "action": "platform.template_deactivated",
        "source": "admin",
        "critical": True,
        "resource": "template",
        "why": "a retired template stops a message class going out, and the symptom is silence",
    },
    {
        "action": "partner.stamped",
        "source": "admin",
        "critical": True,
        "resource": "partner_stamp",
        "why": "the record of who brought an establishment, and therefore of who gets paid for it "
               "every month it stays subscribed. It is written once and never rewritten, so the "
               "log is the only place a disputed attribution can be examined",
    },
    {
        "action": "partner.created",
        "source": "admin",
        "critical": True,
        "resource": "partner",
        "why": "mints a bearer credential that directs commission. The key itself is never logged "
               "— what is logged is that one was issued, by whom, and when",
    },
    {
        "action": "partner.key_rotated",
        "source": "admin",
        "critical": True,
        "resource": "partner",
        "why": "a rotation is usually somebody reacting to a leak, and the window during which "
               "two keys authenticate is exactly the period anyone investigating will ask about",
    },
    {
        "action": "partner.deactivated",
        "source": "admin",
        "critical": True,
        "resource": "partner",
        "why": "stops new attributions and is often the first act of a commercial dispute — the "
               "log is where the date is settled",
    },
    {
        "action": "retention.swept",
        "source": "system",
        "critical": True,
        "resource": "subject",
        "why": "the one deletion nobody asked for. A DSAR leaves a request behind it and a manual "
               "deletion leaves an operator; a retention sweep leaves nothing at all — absence is "
               "not evidence, so 'what did we delete, for which establishment, and on what date' "
               "exists only if it is written here as it happens",
    },
    {
        "action": "retention.establishment_erased",
        "source": "system",
        "critical": True,
        "resource": "tenant",
        "why": "a whole establishment's customer data, erased because its grace after leaving ran "
               "out. If it ever returns asking where its history went, this record is the only "
               "answer — including the date we first observed it had no subscription",
    },
    {
        "action": "whatsapp.connected",
        "source": "user",
        "critical": True,
        "resource": "whatsapp_connection",
        "why": "the moment an establishment's WhatsApp becomes ours to send from. Every message "
               "that follows is sent in its name and billed to it by Meta, so when it is charged "
               "for a message it does not recognise, this row is where the relationship began",
    },
    {
        "action": "whatsapp.connect_refused",
        "source": "user",
        "critical": True,
        "resource": "whatsapp_connection",
        "why": "somebody tried to bind a shop's WhatsApp from an account opened on a phone number "
               "nobody ever proved. It is critical because the innocent explanation and the theft "
               "look identical here — an owner who skipped the code screen, and a stranger who "
               "opened a shop on a number he does not hold — and only the second one leaves a real "
               "business sending in a name it never claimed",
    },
    {
        "action": "whatsapp.connect_failed",
        "source": "user",
        "critical": False,
        "resource": "whatsapp_connection",
        "why": "a failed exchange is the support call we will receive, and the only place the "
               "reason survives — Meta refusing a 30-second code and our own credential being "
               "wrong look identical to an owner and are entirely different problems",
    },
    {
        "action": "whatsapp.connect_stopped",
        "source": "user",
        "critical": False,
        "resource": "whatsapp_connection",
        "why": "where an owner gave up tells us which step of Meta's flow is losing people, and "
               "one of those steps is not a cancellation at all — closing on the final screen "
               "means the signup completed",
    },
    {
        "action": "platform.branch_locations_viewed",
        "source": "admin",
        "critical": False,
        "resource": "branches:all-tenants",
        "why": "a read that crosses the tenancy wall — every other branch and location a shop "
               "holds is theirs alone. Not critical (a missed record does not undo the read), but "
               "who looked at every shop's own address, and when, is a real question worth an "
               "answer",
    },
    {
        "action": "platform.tenant_capacity_viewed",
        "source": "admin",
        "critical": False,
        "resource": "tenant:{tenant_id}",
        "why": "another tenancy-wall crossing read (this shop's own branch/staff count, for the "
               "console's «العملاء والدعم» screen) — same reasoning as branch_locations_viewed "
               "above: not critical, but who looked at one establishment's headcount is worth an "
               "answer",
    },
    {
        "action": "platform.whatsapp_diagnostics_viewed",
        "source": "admin",
        "critical": False,
        "resource": "whatsapp:{tenant|phone_number_id}",
        "why": "a support read of one shop's own delivery history and its refusal reasons — no "
               "message text is ever exposed, only whether it sent and why not. Not critical (a "
               "missed record does not undo the read), but still worth naming who looked and when.",
    },
    {
        "action": "compliance.evidence_exported",
        "source": "internal",
        "critical": True,
        "resource": "evidence_file",
        "why": "an evidence file is a disclosure — it leaves this system toward a regulator, a "
               "lawyer or a support ticket. Who asked for it, about which establishment and for "
               "which window is the one thing an audit trail cannot survive not knowing, and it "
               "is recorded BEFORE the file is handed over rather than after",
    },
    {
        "action": "whatsapp.number_registered",
        "source": "user",
        "critical": True,
        "resource": "whatsapp_connection",
        "why": "the moment a shop's number became able to send. Meta refuses to send from an "
               "unregistered number, so this is the line between a connection that works and one "
               "that is green and mute — and it is the first thing to look at when an owner says "
               "his messages stopped",
    },
    {
        "action": "whatsapp.register_failed",
        "source": "user",
        "critical": False,
        "resource": "whatsapp_connection",
        "why": "Meta locks a number after ten registration attempts in 72 hours. Counting the "
               "failures is the only way to tell a mistyped PIN apart from a shop that is now "
               "locked out — and to know it before he calls",
    },
    {
        "action": "whatsapp.connection_lost",
        "source": "system",
        "critical": True,
        "resource": "whatsapp_connection",
        "why": "the hour a shop's WhatsApp access ended — revoked in its Business Manager or "
               "disabled by Meta. Every message attempted afterwards fails, so this row is where "
               "«منذ متى توقّفت رسائلي» is answered, and it is the only record of a decision taken "
               "outside our product",
    },
    {
        "action": "privacy.requested",
        "source": "user",
        "critical": True,
        "resource": "privacy_request",
        "why": "the hour a customer asked for his data — the moment PDPL's thirty-day clock starts. "
               "Without this row we cannot say when the clock began, and «we answered in time» "
               "stops being a claim we can support",
    },
    {
        "action": "privacy.answered",
        "source": "admin",
        "critical": True,
        "resource": "privacy_request",
        "why": "the hour the establishment says it answered him — the other half of "
               "`privacy.requested`, and the half that exonerates. Only the accusation was in the "
               "ledger: the ask was audited from the day it existed and the answer was a field on "
               "a row, so «we answered within thirty days» was a claim with no witness",
    },
    {
        "action": "customer.erasure_requested",
        "source": "admin",
        "critical": True,
        "resource": "subject",
        "why": "the establishment acting on a customer's erasure request. Recorded BEFORE the "
               "erasure so that a deletion which fails halfway is still visible as attempted — "
               "the one shape a repair cannot be planned without",
    },
    {
        "action": "customer.searched_by_phone",
        "source": "user",
        "critical": False,
        "resource": "phone-suffix:{last4}",
        "why": "this service holds the phone number in the clear (core/models.py explains why — "
               "prefix search needs it, a salted hash cannot be prefix-searched), so this is the "
               "one read an insider can abuse: checking a specific number out of curiosity, or "
               "probing whether someone is a customer here at all. Not critical (a missed record "
               "does not undo the read), but every call — hit or miss — is worth a witness. Only "
               "the searched number's last 4 digits are recorded, on purpose: an audit trail that "
               "stored the full number would recreate the exact exposure it exists to catch abuse "
               "of, in a second table.",
    },
    {
        "action": "partner.statements_issued",
        "source": "system",
        "critical": True,
        "resource": "partner_statement",
        "why": "the monthly run that turns a month of referrals into money owed. A statement "
               "somebody disputes is answered from this row and its timestamp, not from memory",
    },
    {
        "action": "partner.statement_paid",
        "source": "admin",
        "critical": True,
        "resource": "partner_statement",
        "why": "we said we paid a partner. Money leaving on our word needs a name and an hour "
               "attached to it",
    },
    {
        "action": "partner.statement_disputed",
        "source": "admin",
        "critical": True,
        "resource": "partner_statement",
        "why": "a partner says the number is wrong. When it is settled, this row is what the "
               "settlement is measured against",
    },
    {
        "action": "tenant.sandboxed",
        "source": "admin",
        "critical": True,
        "resource": "tenant",
        "why": "an establishment was moved out of the live fleet by us. It stops sending from that "
               "moment, so «why did my messages stop» has exactly one honest answer and it is here",
    },
    {
        "action": "loyalty.redeemed",
        "source": "internal",
        "critical": True,
        "resource": "balance",
        "why": "points spent at the counter through an integrated till. The customer gave up a "
               "balance he earned, and the till is the one surface where neither he nor the owner "
               "is looking at our screen — so this row is the only account of what happened",
    },
    {
        "action": "subscription.gate_unreadable",
        "source": "system",
        "critical": False,
        "resource": "subscription",
        "why": "the duplicate-purchase check could not read billing, so the purchase was REFUSED "
               "rather than let through. It used to be let through — and that charged a card for "
               "a second base, recoverable only by noticing and refunding it, while refusing "
               "costs one press. A cluster of these rows is what a billing outage looks like "
               "from the product side",
    },
    {
        "action": "offer.applied",
        "source": "internal",
        "critical": False,
        "resource": "visit",
        "why": "a discount was honoured at an integrated till. It is money off an invoice the shop "
               "has to explain later, and the till is the one surface where neither the owner nor "
               "the customer is looking at our screen",
    },
]
