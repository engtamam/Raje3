"""loyalty — auditable actions: what this service must be able to PROVE it did.

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
    # operator.secret_set / operator.secret_cleared were removed with the dead SecretStore —
    # see git history for the incident.
    {
        "action": "operator.config_changed",
        "source": "admin",
        "critical": False,
        "resource": "config",
        "why": "policy changes explain later behaviour — why a sweep deleted more, why a limit "
               "started refusing — and that history is unavailable anywhere else. Not critical: "
               "refusing to change a retention period because the log is down protects nothing",
    },
    # ── Delete these examples and declare your own ────────────────────────────
    {
        "action": "loyalty.redeemed",
        "source": "user",
        "critical": True,
        "resource": "redemption",
        "why": "spends something the customer owns, performed by an employee with the customer "
               "standing there. When a balance is disputed months later this log and the "
               "customer's own receipt are the only two records, and they must agree",
    },
    {
        "action": "loyalty.settings_changed",
        "source": "admin",
        "critical": False,
        "resource": "loyalty_settings",
        "why": "changes what every future visit is worth, which an owner notices weeks later and "
               "asks about. Not critical: refusing an edit because the log is down would leave "
               "the shop unable to correct a number it just discovered was wrong",
    },
    {
        "action": "loyalty.reward_changed",
        "source": "admin",
        "critical": False,
        "resource": "reward",
        "why": "repricing or retiring a reward changes what customers were promised. The "
               "redemption rows keep their own snapshot, so this log answers when the promise "
               "changed rather than what any one customer received",
    },
    {
        "action": "loyalty.reconciled",
        "source": "internal",
        "critical": True,
        "resource": "balance",
        "why": "a balance was rewritten from its ledger because the two disagreed. That is either "
               "a crash we recovered from or a bug we have not found, and an unlogged repair "
               "makes the second indistinguishable from the first",
    },
    {
        "action": "loyalty.reconcile_result",
        "source": "internal",
        "critical": True,
        "resource": "balance",
        "why": "the number the repair replaced, and the number it wrote. Without it the entry "
               "above says only that somebody repaired something: neither the shop nor the "
               "customer can argue with a correction whose before-value nothing remembers, and "
               "that is the second of the three things §8.3 promises about a repair",
    },
    {
        "action": "loyalty.platform_balance_viewed",
        "source": "internal",
        "critical": False,
        "resource": "balance",
        "why": "the read-side companion of loyalty.reconciled — a platform capability reading one "
               "specific customer's private ledger in an establishment that is not the caller's "
               "own. Not critical: nothing changed, but who looked at whose balance is worth "
               "keeping, the same posture compliance-service already holds for a cross-tenant read",
    },
    {
        "action": "loyalty.platform_history_viewed",
        "source": "internal",
        "critical": False,
        "resource": "balance",
        "why": "same reasoning as loyalty.platform_balance_viewed, for the movement history "
               "instead of the total — a support agent reading what happened to a specific "
               "customer's points before deciding whether to reconcile anything",
    },
    {
        "action": "loyalty.adjusted",
        "source": "admin",
        "critical": True,
        "resource": "balance",
        "why": "someone changed a customer's balance by hand rather than by earning or spending. "
               "It is the one movement the ledger cannot explain by itself, so who did it and why "
               "has to be written down beside it",
    },
    {
        "action": "loyalty.rating_bonus_credited",
        "source": "internal",
        "critical": False,
        "resource": "balance",
        "why": "the rating app's own CTA (rating_cta.py) tells a customer he will earn points for "
               "answering — this is the one call that makes that sentence true. Unlike the regular "
               "per-visit `earn` (unaudited, one row per visit, every shop, since the day it "
               "shipped), this fires once per SUBMITTED RATING, a rarer and more disputable event: "
               "a customer who answered and was not paid asks the shop, and the shop needs a record "
               "that says whether the credit happened and for how much. Not critical — refusing a "
               "genuine rating's credit because the audit log is briefly down would punish the "
               "customer for an outage that is ours, not his",
    },
    {
        "action": "loyalty.award_credited",
        "source": "internal",
        "critical": False,
        "resource": "balance",
        "why": "a credit with no visit and no rating behind it — a campaign's own gift (2026-09-13,"
               " built ahead of any template that uses it). Not critical for the same reason "
               "rating_bonus_credited is not: refusing a genuine award because the audit log is "
               "briefly down would punish the customer, not the outage.",
    },
]
