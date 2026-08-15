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
        "action": "branch.created",
        "source": "admin",
        "critical": False,
        "resource": "branch",
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
    # ── the platform console. Changing a sector changes what EVERY establishment created
    # afterwards receives, which makes these the highest-leverage edits in the product — a wrong
    # cycle propagated to a thousand new tenants is invisible until their customers start getting
    # reminders at the wrong time.
    {
        "action": "platform.sector_changed",
        "source": "admin",
        "critical": True,
        "resource": "sector",
        "why": "it silently shapes every establishment created afterwards; without a record there "
               "is no way to answer why a cohort of tenants got the catalogue they got",
    },
    {
        "action": "platform.sector_deactivated",
        "source": "admin",
        "critical": True,
        "resource": "sector",
        "why": "a retired sector can no longer seed a catalogue, so a signup that used to work "
               "stops working — and the change must be attributable",
    },
    {
        "action": "platform.sector_fields_changed",
        "source": "admin",
        "critical": True,
        "resource": "sector_fields",
        "why": "it changes which inputs the field screen renders in every sector at once",
    },
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
]
