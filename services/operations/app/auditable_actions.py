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
        # THE TILL'S OWN "attended" MARK — a cashier-integration caller (actor `till:{subject}`,
        # api/v1/till.py) telling us a booking was actually served at the counter. NOT critical:
        # an audit outage must not stop a real customer being checked off at the till, and the
        # booking record itself (bookings-service) is the primary evidence either way — this is
        # the same "attribute the write, don't gate it" posture visit.rated already takes.
        "action": "booking.attended_via_till",
        "source": "internal",
        "critical": False,
        "resource": "booking",
        "why": "which till integration marked a booking attended, and when — a cashier's own "
               "claim of service needs the same accountability any other write carries",
    },
    {
        # THE OWNER'S OWN ACT, from the console's «التقييمات» tab — never automatic (see
        # Visit.rating_handled_at's own docstring). Not critical for the same reason as
        # visit.rated: an audit outage must not stop him from acting on a rating he is looking at
        # right now.
        "action": "visit.rating_handled",
        "source": "admin",
        "critical": False,
        "resource": "visit",
        "why": "which staff member marked a customer's rating as handled, and when — the same "
               "accountability any other write to a visit gets",
    },
    {
        # A READ, not a write — recorded anyway because the export leaves the building as a real
        # file a person can forward or print, unlike the JSON screen it mirrors. Not critical: an
        # audit outage must not block a manager from getting his own report right now.
        "action": "staff_performance.exported",
        "source": "admin",
        "critical": False,
        "resource": "staff_performance",
        "why": "who pulled a staff-comparison document, in what format and over what window — a "
               "report that leaves the system as a file deserves the same trail a data export "
               "anywhere else in this product gets",
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
        "action": "subscription.whatsapp_connection_required",
        "source": "admin",
        "critical": False,
        "resource": "plan",
        "why": "an owner tried to buy an app that cannot be delivered at all without a connected "
               "WhatsApp number (feature.whatsapp, feature.rating, feature.campaigns — see "
               "apps.py::REQUIRES_WHATSAPP_KEYS) and was refused before any money moved. Same "
               "posture as `subscription.refused` — a decision of ours about somebody's money —",
    },
    {
        # A duplicate-purchase attempt is the same kind of fact as `subscription.refused` right
        # above it — a decision of ours about somebody's money — and it was the one refusal in
        # this route with no row at all (fixed 2026-09-12, a real gap a QA audit found).
        "action": "subscription.already_subscribed",
        "source": "admin",
        "critical": False,
        "resource": "plan",
        "why": "an owner (or a second manager) trying to buy an app the shop already holds is "
               "worth the same record `subscription.refused` already gets, and support could not "
               "see it before",
    },
    {
        # A request naming an interval billing does not recognise is an integration fault worth
        # seeing, not a shrug — same posture, and same prior gap, as `already_subscribed` above.
        "action": "subscription.bad_interval",
        "source": "admin",
        "critical": False,
        "resource": "plan",
        "why": "billing reads an unknown interval as a silent MONTH rather than refusing it, so "
               "this refusal is the only place the bad value is ever seen at all",
    },
    {
        # `api/v1/subscription.py::renew_now` — the owner forcing a subscription's billing cycle
        # early, via the same mechanism the WhatsApp renewal Flow already uses.
        "action": "subscription.renewed_early",
        "source": "admin",
        "critical": True,
        "resource": "plan",
        "why": "a real charge fires the moment this runs (renewal_provider.py's own `run_cycle`) "
               "ahead of the automatic date — same reasoning as `subscription.created`: an "
               "unattributable early charge cannot be reconciled against an invoice, and 'why did "
               "this renew today, not on its usual date' is the first question a billing dispute "
               "over it would ask",
    },
    {
        "action": "subscription.renew_now_refused",
        "source": "admin",
        "critical": False,
        "resource": "plan",
        "why": "same posture as `subscription.refused` above — the shop asked to renew early and "
               "we declined (not their own subscription, already mid-cycle, billing unreachable); "
               "without the record support is told 'I tried to renew and nothing happened' with "
               "nothing to answer with",
    },
    {
        # api/v1/subscription.py::checkout — a whole cart refused before anything is charged
        # (`may_add_bundle`'s own rule: a missing dependency, a duplicate, an unreadable line), OR
        # billing-service's own atomic checkout refused the cart (bad/duplicate/held plan, mixed
        # currency, bad interval, outage) — same event either way: nothing was charged.
        "action": "subscription.checkout_refused",
        "source": "admin",
        "critical": False,
        "resource": "plan",
        "why": "same posture as `subscription.refused` — a decision of ours (or billing's) about "
               "somebody's money, just for a cart instead of a single plan; support needs the same "
               "trail to answer 'I tried to check out and nothing happened'",
    },
    {
        "action": "subscription.checkout_completed",
        "source": "admin",
        "critical": True,
        "resource": "plan",
        "why": "a whole cart was charged in one atomic invoice — several real subscriptions (and a "
               "real charge) created in one request — 'who moved this shop onto these plans' is "
               "the first question a billing dispute over any one of them would ask",
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
        "action": "operator.pin_confirmed",
        "source": "user",
        "critical": False,
        "resource": "operator",
        "why": "a full history of who confirmed which visit cannot be reconstructed from failures alone",
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
        # Fixed 2026-09-12 — found undeclared by ci/check_audit_actions.py (the route itself
        # already emitted it; this was a missing declaration, not a missing audit call). The
        # owner's own security/data-collection decision — see core/whatsapp_auto_register.py's
        # own docstring on why this defaults off. CRITICAL: it widens who gets written into the
        # customer book, not just what a screen shows.
        "action": "shop.whatsapp_auto_register_changed",
        "source": "admin",
        "critical": True,
        "resource": "shop_whatsapp_auto_register",
        "why": "who widened (or narrowed) automatic جهات الاتصال registration for every new "
              "WhatsApp number that messages the shop, and when — a data-collection decision an "
              "owner disputing what got recorded about a stranger would need to explain.",
    },
    {
        # What the owner told the WhatsApp AI assistant about his own shop. Not critical: this is
        # a routine profile edit, redacted and length-capped before it is ever written, and refusing
        # to change it because the log is down protects nothing a customer would notice.
        "action": "shop.ai_notes_changed",
        "source": "admin",
        "critical": False,
        "resource": "shop_ai_notes",
    },
    {
        # The owner's own kill switch for the WhatsApp AI assistant — separate from the
        # subscription. Not critical: it never widens access (off is strictly narrower than on),
        # and refusing the switch because the log is down would leave an owner unable to silence
        # an assistant he explicitly wants quiet right now.
        "action": "shop.ai_toggle_changed",
        "source": "admin",
        "critical": False,
        "resource": "shop_ai_toggle",
    },
    {
        # The ceiling on a customer's single WhatsApp message before the assistant refuses it
        # without ever calling the model. Not critical for the same reason as ai_notes_changed —
        # a routine setting, not an access grant.
        "action": "shop.msg_word_limit_changed",
        "source": "admin",
        "critical": False,
        "resource": "shop_msg_word_limits",
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
        # A step's text/severity is SHARED — editing it here changes what every linked service's
        # checklist actually asks the field to do, same reasoning `service.updated` audits price.
        "action": "procedure_step.created",
        "source": "admin",
        "critical": False,
        "resource": "procedure_step",
    },
    {
        "action": "procedure_step.updated",
        "source": "admin",
        "critical": False,
        "resource": "procedure_step",
    },
    {
        # SAME REASONING AS `staff_performance.exported` ABOVE — a read that leaves the building as
        # a real file (handed to a customer or printed) gets the same trail any other export does.
        "action": "procedure_checklist.exported",
        "source": "admin",
        "critical": False,
        "resource": "service",
        "why": "who printed a service's procedure checklist, in what format and how many steps it "
               "carried at that moment — the document may leave the shop entirely, so the same "
               "accountability any other data export gets applies here too",
    },
    {
        "action": "service.image_set",
        "source": "admin",
        "critical": False,
        "resource": "service",
    },
    {
        "action": "package.image_set",
        "source": "admin",
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
    # Declared here because WHAT NOBODY DECLARES, NOBODY LOGS — this changes runtime policy, which
    # is the highest-privilege surface this service has. The credential-management pair
    # (operator.secret_set/secret_cleared) was removed with the rest of the unused SecretStore —
    # see git history for the incident (a free-text credential name box nothing here ever read).
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
        "action": "platform.whatsapp_flow_json_viewed",
        "source": "admin",
        "critical": False,
        "resource": "whatsapp-flow:{name}",
        "why": "an operator opened one Flow's real generated screens to preview it — read-only, no "
               "shop data involved, still worth naming who looked, same reasoning as "
               "whatsapp_diagnostics_viewed above.",
    },
    {
        "action": "platform.whatsapp_status_viewed",
        "source": "admin",
        "critical": False,
        "resource": "whatsapp:platform-status",
        "why": "an operator viewed the platform's OWN WhatsApp status glance (connection states plus "
               "aggregate send/bound-number/opt-out counts) — never one shop's data, so this is not "
               "a tenancy-wall crossing. Not critical (a missed record does not undo the read), but "
               "still worth naming who looked, same reasoning as whatsapp_diagnostics_viewed above.",
    },
    {
        "action": "platform.whatsapp_messaging_limit_viewed",
        "source": "admin",
        "critical": False,
        "resource": "whatsapp:{tenant}",
        "why": "an operator read one shop's own messaging-limit tier and quality rating (platform "
               "v0.19.9's `/internal/whatsapp/messaging-limit`, newly wired to this admin screen). "
               "Not critical (a missed record does not undo the read), same reasoning as "
               "whatsapp_diagnostics_viewed above.",
    },
    {
        "action": "platform.whatsapp_subscribed_fields_viewed",
        "source": "admin",
        "critical": False,
        "resource": "whatsapp:{tenant}",
        "why": "an operator read which webhook fields Meta is actually sending for one shop's WABA "
               "— read-only always (Meta has no per-WABA write for this). Not critical, same "
               "reasoning as whatsapp_diagnostics_viewed above.",
    },
    {
        "action": "platform.whatsapp_business_verification_viewed",
        "source": "admin",
        "critical": False,
        "resource": "whatsapp:{tenant}",
        "why": "an operator read one shop's WABA business-verification status — gates template-"
               "review speed and throughput, so worth naming who checked it. Not critical, same "
               "reasoning as whatsapp_diagnostics_viewed above.",
    },
    {
        "action": "platform.whatsapp_two_step_pin_set",
        "source": "admin",
        "critical": True,
        "resource": "whatsapp:{tenant}",
        "why": "an operator rotated a shop's own WhatsApp two-step-verification PIN — a live "
               "credential change on Meta's side, recorded write-ahead (before the call, same "
               "discipline as secrets.update) since a call that fails halfway must still be "
               "visible as attempted. The PIN value itself is never in this row, on purpose — "
               "matching the peer route's own write-only guarantee.",
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
        "action": "platform.customer_searched_by_phone",
        "source": "admin",
        "critical": False,
        "resource": "phone-suffix:{last4}",
        "why": "the cross-shop twin of customer.searched_by_phone above — a support/compliance "
               "operator, under platform.operations, searching ONE explicitly chosen establishment "
               "for a customer, not their own shop. Kept as a DISTINCT action (not the same one) so "
               "the two audiences stay separately answerable: who searched their own customers vs "
               "who used the platform-wide door into someone else's. Same discipline: last 4 digits "
               "only, every call witnessed hit or miss.",
    },
    {
        "action": "platform.coupon_tenant_searched_by_phone",
        "source": "admin",
        "critical": False,
        "resource": "phone-suffix:{last4}",
        "why": "resolves a phone to a tenant id for the coupon override screen, the same "
               "cross-tenant identity lookup platform.customer_searched_by_phone already audits",
    },
    {
        "action": "platform.customer_success_scanned",
        "source": "admin",
        "critical": False,
        "resource": "tenants:{count}",
        "why": "an operator ran the platform-wide stalled-shop scan — reads only (no shop's own "
               "record is exposed beyond a tenant id/name and two boolean flags this service "
               "already computes for its own operational reasons), so not critical, but the count "
               "of tenants scanned is worth a witness like every other platform.* glance in this "
               "file.",
    },
    {
        "action": "platform.subscription_renewal_flow_seeded",
        "source": "admin",
        "critical": True,
        "resource": "flow:{flow_id}",
        "why": "authors a real Flow on the platform's own WhatsApp account, once — a one-time,"
               " Meta-facing action an operator triggered by hand, not a read. Critical: unlike"
               " the scan above, this reaches Meta and creates something durable.",
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
    {
        "action": "points.redeemed",
        "source": "internal",
        "critical": False,
        "resource": "visit",
        "why": "a customer's own loyalty points were spent at the counter — the same money-off-an-"
               "invoice reasoning offer.applied already gives, for the sibling door onto the same "
               "one-slot entitlement (core/operations.py::Operations.redeem_points_reward).",
    },
    {
        # FOUND UNDECLARED 2026-09-07 by ci/check_audit_actions.py, itself found unwired into any
        # workflow the same day (see .github/workflows/guards.yml's own commit) — every call to
        # this, scheduled sweep or the "فحص الآن" button in AdminFinance's GatewayPanel alike, had
        # been 500ing on the auditor's own DeclarationError since the day it was written.
        "action": "billing.wallet_topups_reconciled",
        "source": "internal",
        "critical": False,
        "resource": "wallet-topups",
        "why": "a batch of pending wallet top-ups was checked against billing-service's own "
               "record — the number reconciled and failed is what an owner asking «where's my "
               "top-up?» is actually answered from",
    },
    {
        "action": "referral.register_attempt",
        "source": "internal",
        "critical": False,
        "resource": "referral_code",
        "why": "a cashier typed in someone else's referral code for a new customer — every "
               "attempt, successful or refused, is a promise (a discount, a referrer's reward) "
               "an owner needs explained later, same reasoning coupon.grant_attempt already "
               "documents for a shop-to-shop coupon",
    },
    {
        "action": "affiliate.added",
        "source": "internal",
        "critical": False,
        "resource": "affiliate",
        "why": "a distinct marketer tier the owner assigns directly, with its own negotiated "
               "code/discount/reward — an owner needs to see who was onboarded, by whom, and when",
    },
    {
        "action": "affiliate.status_changed",
        "source": "internal",
        "critical": False,
        "resource": "affiliate",
        "why": "pausing/resuming a marketer changes whether their code earns anything right now, "
               "without touching their negotiated terms or their unsettled balance",
    },
    {
        "action": "affiliate.settlement_recorded",
        "source": "internal",
        "critical": True,
        "resource": "affiliate_settlement",
        "why": "the platform moves no money for this at all (plan doc §5's own \"بلا أي تدخل "
               "مالي\") — which is exactly why the RECORD of what an owner claims was paid, by "
               "whom, and for how many points, is the only accountability that exists for it",
    },
    {
        "action": "coupon.grant_attempt",
        "source": "internal",
        "critical": False,
        "resource": "coupon_attempt",
        "why": "a shop tried to grant another shop a discount on its own subscription — every "
               "attempt, successful or refused, is money (or a refused act) an owner needs "
               "explained later",
    },
    {
        "action": "coupon.settings_updated",
        "source": "internal",
        "critical": True,
        "resource": "coupon_settings",
        "why": "the global ceiling and automatic tiers bound every shop's own grant cap at once — "
               "a wrong edit here silently raises what every granting shop on the platform may "
               "give away",
    },
    {
        "action": "coupon.tenant_override_set",
        "source": "internal",
        "critical": False,
        "resource": "coupon_override",
        "why": "one shop's own cap was raised or cleared by hand — a competitive/reward lever an "
               "owner reviewing that shop's account needs to see was pulled",
    },
    {
        "action": "coupon.preferences_set",
        "source": "internal",
        "critical": False,
        "resource": "coupon_preferences",
        "why": "a shop turned the visit-screen coupon checkbox on or off — an owner asking why "
               "staff stopped seeing it (or started) needs to see this was a deliberate switch",
    },
    {
        "action": "app_visibility.set",
        "source": "internal",
        "critical": False,
        "resource": "app_visibility_override",
        "why": "a platform operator made an otherwise-hidden app visible (or hid it again) for "
               "one specific tenant — never money-moving on its own, but the reason a shop's "
               "store shelf shows an app nobody else can see needs to be findable later.",
    },
    {
        "action": "mutual_benefit.propose",
        "source": "internal",
        "critical": False,
        "resource": "referral_agreement",
        "why": "a commitment against ANOTHER shop entirely — an owner reviewing his account needs "
               "to see who on his side proposed a cross-tenant partnership, and when",
    },
    {
        "action": "mutual_benefit.accept",
        "source": "internal",
        "critical": True,
        "resource": "referral_agreement",
        "why": "activates a cross-tenant partnership neither side can undo unilaterally — the one "
               "act that turns an incoming proposal into a live commitment",
    },
    {
        "action": "mutual_benefit.reject",
        "source": "internal",
        "critical": False,
        "resource": "referral_agreement",
        "why": "a proposed cross-tenant partnership was refused — worth explaining later if the "
               "other shop asks why nothing ever activated",
    },
    {
        "action": "mutual_benefit.cancel_request",
        "source": "internal",
        "critical": False,
        "resource": "referral_agreement",
        "why": "one side asked to end an active cross-tenant partnership early — it stays active "
               "until the other side confirms, but the request itself is a fact worth keeping",
    },
    {
        "action": "mutual_benefit.cancel_confirm",
        "source": "internal",
        "critical": True,
        "resource": "referral_agreement",
        "why": "the act that actually ends a cross-tenant partnership early, by mutual consent — "
               "critical because it stops eligibility detection for both shops at once",
    },
    {
        "action": "salla.connected",
        "source": "internal",
        "critical": False,
        "resource": "salla_merchant",
        "why": "a shop linked its Salla store to its account here — who did it and when, for "
               "support when an owner asks why a store they do not recognise appears connected",
    },
    {
        "action": "salla.disconnected",
        "source": "internal",
        "critical": False,
        "resource": "salla_connection",
        "why": "a shop removed its Salla link — support needs to know this was deliberate when "
               "an owner later asks why real orders stopped granting alliances automatically",
    },
    {
        "action": "mobile_request.created_manually",
        "source": "internal",
        "critical": False,
        "resource": "mobile_request",
        "why": "the request did not arrive over WhatsApp — who at the shop typed it in by hand, "
               "and when, matters exactly as much as who reviewed it afterward",
    },
    {
        "action": "mobile_request.assigned",
        "source": "internal",
        "critical": False,
        "resource": "mobile_request",
        "why": "who a request was handed to, by whom, and when — the same trail «من نفّذ هذا "
               "الطلب» needs later, and the record a manager checks after a customer names the "
               "wrong employee",
    },
    {
        "action": "mobile_request.accepted",
        "source": "internal",
        "critical": False,
        "resource": "mobile_request",
        "why": "who at the shop accepted a mobile-service request, and when — the moment the "
               "platform's own involvement ends and coordination moves outside it",
    },
    {
        "action": "mobile_request.rejected",
        "source": "internal",
        "critical": False,
        "resource": "mobile_request",
        "why": "a customer asking why nobody got back to them needs a real answer — this is the "
               "record that the shop actually looked at the request and said no",
    },
    {
        "action": "mobile_request.completed",
        "source": "internal",
        "critical": False,
        "resource": "mobile_request",
        "why": "the request that turned into a real, loyalty-earning visit — traceable back to "
               "the WhatsApp conversation that started it",
    },
    {
        "action": "mobile_request.no_show",
        "source": "internal",
        "critical": False,
        "resource": "mobile_request",
        "why": "feeds the next customer's own no-show risk read — an owner disputing that read "
               "needs to see exactly which past requests it is built from",
    },
    {
        "action": "whatsapp_order.preparing",
        "source": "user",
        "critical": False,
        "resource": "whatsapp_order",
        "why": "who at the shop started preparing a WhatsApp catalog order, and when — the moment "
               "the customer's own automatic status message was sent",
    },
    {
        "action": "whatsapp_order.ready",
        "source": "user",
        "critical": False,
        "resource": "whatsapp_order",
        "why": "same trail as preparing — traces the customer-facing 'ready' message back to who "
               "at the shop actually marked it",
    },
    {
        "action": "whatsapp_order.out_for_delivery",
        "source": "user",
        "critical": False,
        "resource": "whatsapp_order",
        "why": "the moment the shop said the order left for delivery — needed if a customer "
               "disputes how long delivery actually took",
    },
    {
        "action": "whatsapp_order.delivered",
        "source": "user",
        "critical": False,
        "resource": "whatsapp_order",
        "why": "the order that turned into a real, loyalty-earning visit — traceable back to the "
               "WhatsApp cart that started it, same reasoning as mobile_request.completed above",
    },
    {
        "action": "whatsapp_order.cancelled",
        "source": "user",
        "critical": False,
        "resource": "whatsapp_order",
        "why": "a customer asking why their order never arrived needs a real answer — this is the "
               "record that the shop cancelled it, by whom, and the stated reason",
    },
    {
        "action": "whatsapp_order.mismatch_resolved",
        "source": "user",
        "critical": True,
        "resource": "whatsapp_order",
        "why": "a human overrode a PAYMENT MISMATCH by hand, off-platform evidence only — this is "
               "money-adjacent enough that losing the record of who did it and when is not "
               "acceptable; refuse the action rather than lose the trail",
    },
    {
        "action": "whatsapp_order.pause_set",
        "source": "user",
        "critical": False,
        "resource": "branch",
        "why": "a shop that stopped taking WhatsApp orders for a stretch needs to be able to show "
               "exactly when and why — a customer who could not place an order during that window "
               "deserves a real answer, not a shrug",
    },
]
