"""The heartbeat: due schedules become messages, or become suppressions with a reason.

THIS IS WHERE EVERY OTHER FILE MEETS. The gate decides, rendering fills, the sender delivers, and
the ledger remembers. The tick's only job is to do that in an order that survives being
interrupted — because it will be interrupted, by a pod eviction, a rollout, or a peer timing out.

THE ORDER, AND WHY EACH STEP IS WHERE IT IS:

  1. Claim the row.       Marked in-flight BEFORE anything external happens. Two replicas run this
                          cron; without a claim they both send.
  2. Gate it.             Cheap and pure. A refusal here costs no peer call at all.
  3. Render it.           Can fail on bad data, and failing before the send costs nothing.
  4. Send.                The only irreversible step, and it carries an idempotency key we
                          generated and stored, so a retry after a timeout cannot double-send.
  5. Record.              Ledger, then schedule state.

STEP 5 IS AFTER STEP 4 AND THAT IS A REAL RISK, ACCEPTED DELIBERATELY. If we crash between the
send and the ledger write, the message went out and we do not know it. The alternative — record
first — means a peer failure leaves a ledger entry for a message that never existed, which
silently consumes the customer's cap and suppresses a REAL message later. Given a choice between
losing the record of a sent message and inventing the record of an unsent one, we lose the record:
the idempotency key makes the resend harmless, and an invented cap consumption is invisible.

BOUNDED, ALWAYS. A batch limit per tenant per tick. An unbounded sweep is how a slow query becomes
a missed batch becomes a day of reminders that never went out.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from app.core import engagement as E
from app.core import gate as G
from app.core.custom_templates import CustomTemplateStore
from app.core import quota as Q
from app.core import ceiling as C
from app.core import ladder as L
# `LINKS`, not `L`: the ladder already owns that name here, and an address composed by the
# wrong module is the kind of mistake a one-letter alias makes easy.
from app.core import links as LINKS
from app.core import reasons as TR
from app.core import merge as M
from app.core import ceiling_notice as CN
from app.core.reach import Reach

# How long a message waits after WhatsApp refused it for the ceiling. A DEFAULT: the right delay
# depends on when in the rolling window the refusal happened, and the only wrong answer is "an
# hour", which walks back into the same closed door. Deployments set CEILING_DEFER_SECONDS.
_DEFAULT_CEILING_DEFER = 12 * 3600

# HOW MANY TIMES A ROW MAY THROW BEFORE WE STOP ASKING. At one try an hour this spans most of a
# day: far past any outage worth waiting through, and far short of for ever — which is what it was
# before, for a peer that will never accept this particular message.
#
# A CONSTANT AND NOT A SETTING, deliberately. A deployment that could raise this would be handed
# the ability to restore the defect by configuration, and nothing about one cluster makes «keep
# retrying a permanently rejected message» right.
MAX_ATTEMPTS = 20
from app.core import rendering as R
from app.core.models import SendLog, as_row, key_of
from app.adapters.message_sender import CeilingReached, Unsendable
from app.core.consent import Consent
from app.core.stores import (CLAIM_LEASE_SECONDS, EngagementStore, PrefsStore, RuleStore,
                             ScheduleStore, SendLogStore)


def _sending_identity(tenant: str, row: dict) -> str:
    """`tenant` or `tenant:branch` — see operations/core/sending_identity.py, which owns the shape.

    RESOLVED FROM THE SCHEDULE, NOT RE-DERIVED. The row was written when the visit was ingested and
    already holds the branch that visit belongs to; asking again here would be a second opinion
    that disagrees the day an owner reassigns a branch.

    AND A ROW WITH NO BRANCH SENDS FROM THE ESTABLISHMENT, which is every shop that has not moved
    to a number per branch — so this changes nothing for them.
    """
    branch = str(row.get("branch_id") or "").strip()
    return f"{tenant}:{branch}" if branch else tenant


@dataclass
class Room:
    """Today's remaining allowance, shared across one tenant's pass.

    A MUTABLE HOLDER RATHER THAN AN INT, and the reason is a bug this had for exactly one commit:
    `room` was passed as an integer and decremented inside the per-row call, where the decrement
    went nowhere. Four hundred due messages with fifty left would every one of them have seen
    fifty, passed the check, and been refused by Meta one at a time.

    `left < 0` means unknown, which never blocks.
    """

    left: int = -1
    # Whether the row currently being worked is holding a slot it has not yet spent on a send.
    # Reset by `confirm`, `settle` or `exhaust` — see `settle` for why this is here and not a
    # local flag in the caller.
    _held: bool = False

    def known(self) -> bool:
        return self.left >= 0

    def take(self) -> bool:
        """Reserve one slot for this row. False when there is none left.

        Reserved, not spent: it is given back by `settle` unless a message actually went out.
        """
        if not self.known():
            # Unknown never blocks, and nothing is held — there is no count to correct.
            return True
        if self.left <= 0:
            return False
        self.left -= 1
        self._held = True
        return True

    def confirm(self) -> None:
        """The message went out. The slot taken for it is spent for real."""
        self._held = False

    def settle(self) -> None:
        """Give back a slot taken for a message that did not go out.

        A SLOT IS A RESERVATION UNTIL THE SEND SUCCEEDS, and this is what makes that structural
        rather than a flag threaded through a dozen returns. The slot is spent before the send,
        like the quota unit beside it, because both have to be decided before the expensive part —
        but unlike the quota it was never given back on any of the ways a row can end without a
        message: a lapsed subscription, a template still in Meta's review, a peer that is down, a
        render that failed. Every one of them reached nobody and every one of them shrank the
        shop's own room by one.

        Four hundred due rows behind one broken template closed the day at a ceiling nobody hit,
        and every message after them waited until tomorrow for nothing.

        Called from the row loop's `finally`, so a path that forgets to think about it is correct
        by default — which is the opposite of what a flag gives you.
        """
        if self._held:
            self._held = False
            if self.known():
                self.left += 1

    def exhaust(self) -> None:
        """Meta itself refused: there is no room, whatever we counted.

        NOT `settle`, deliberately. `CeilingReached` is the ceiling answering, and handing the
        slot back would send the next row into the same refusal, and the row after that — one
        rejected API call per remaining message, from a shop already at its limit, which is
        precisely the behaviour that gets a number rate-limited.
        """
        self._held = False
        if self.known():
            self.left = 0


@dataclass
class TickResult:
    sent: int = 0
    suppressed: int = 0
    # COUNTED SEPARATELY FROM `failed`, and that separation is the whole point: the reason counts
    # are how an operator sees a real peer outage, and a daily, expected, self-resolving ceiling
    # would drown it. It is also the number that moves an owner to verify his business (§6.2.2):
    # "twelve customers did not get your messages" cannot be said unless these are counted alone.
    ceiling: int = 0
    deferred: int = 0
    # Rows folded into another message rather than sent on their own (spec §5.8.1). Counted
    # apart from `suppressed`: nothing was withheld from the customer, two messages became one.
    merged: int = 0
    failed: int = 0
    scanned: int = 0
    # Suppression reasons, counted. This is the number an operator actually needs: "312 suppressed"
    # is an alarm, "312 suppressed, all outside the window" is a working system doing its job.
    reasons: dict[str, int] = field(default_factory=dict)

    def note(self, reason: str) -> None:
        key = reason[:80]
        self.reasons[key] = self.reasons.get(key, 0) + 1


def _own_template(choices: Any, ids: list[str]) -> str:
    """The name of HIS OWN approved text for whichever reason fired this message, or empty.

    ONE MESSAGE CAN ANSWER SEVERAL REASONS — a visit confirmation that also carries the points
    receipt — so the candidates arrive as a list and the FIRST one he has re-texted wins. Any other
    rule would need a precedence nobody has ever stated; this one is «the reason he customised is
    the one he meant».
    """
    if choices is None:
        return ""
    for reason_id in ids:
        name = choices.template_name(reason_id)
        if name:
            return name
    return ""


# Serialises `_claim()` per schedule row — added 2026-09-12, a real gap a QA audit found; see
# `_claim()`'s own docstring for the full reasoning. Short: the claim decision itself (a get, a
# state check, an upsert) takes a handful of milliseconds; this only needs to outlive that.
_CLAIM_LOCKS = "reminders_row_claim_locks"
CLAIM_LOCK_TTL_SECONDS = 10


class Tick:
    def __init__(self, *, store, sender, limits: G.Limits, eng_cfg: E.EngagementConfig,
                 batch: int = 100, telemetry=None, quota=None, approved=None,
                 reach_window: int = 0, ceiling_defer_seconds: int = 0, ceiling=None,
                 holdout_enabled: bool = False, holdout_share: int = 10,
                 public_base_url: str = "") -> None:
        self._store = store
        # WHERE A CUSTOMER READS HIS PAGE. Held here rather than read from settings deeper
        # down: the renderer must not know what a Settings object is, and a link composed
        # from a value this class never saw is a link nobody can trace to a configuration.
        self._public_base_url = public_base_url
        # WHETHER THE ONE-TAP STOP CAN BE REACHED AT ALL. Marketing carries a mandatory exit
        # («إيقاف الرسائل الترويجية», §8.3) and that exit is a link — `{base}/p/{ref}/stop`. With
        # no base URL there is no link to put in the message, so the exit does not exist, and
        # marketing without a working opt-out breaches both the regulation and Meta's policy for
        # the category. The gate refuses rather than sending; see core/gate.py.
        #
        # DERIVED, NEVER PASSED IN. It was a parameter defaulting to True, which meant every
        # caller in the product silently asserted «the stop link works» without anyone checking —
        # a guard whose value nothing computes is a guard that has never once said no. The one
        # fact it depends on is already right here, and it is the same value the renderer composes
        # the link from, so the two cannot disagree.
        self._withdrawal_reachable = bool(public_base_url.strip())
        self._sched = ScheduleStore(store)
        self._log = SendLogStore(store)
        self._prefs = PrefsStore(store)
        # Marketing consent is a SEPARATE record from the send preferences, because
        # 'did not refuse' and 'agreed' are different facts (core/consent.py).
        self._consent = Consent(store)
        # WHO WE HAVE ALREADY REACHED TODAY. WhatsApp's ceiling counts PEOPLE in a rolling 24
        # hours, not messages, so this is the only counter that can answer "how close is he".
        # The window is Meta's number and the delay is ours; neither belongs in this file. Zero
        # means "take the module default", so a test constructs a Tick without knowing either.
        self._reach = Reach(store, window=reach_window) if reach_window else Reach(store)
        self._ceiling_defer = int(ceiling_defer_seconds or _DEFAULT_CEILING_DEFER)
        # THE SHOP'S CEILING, read from Meta through notification-service. Absent answers unknown,
        # and unknown never blocks — see core/ceiling.py.
        self._ceiling = ceiling or C.NullCeiling()
        # That we told this shop, once, that its ceiling cost it customers (spec §6.2.2).
        self._notices = CN.NoticeStore(store)
        self._eng = EngagementStore(store)
        self._sender = sender
        # THE MESSAGE QUOTA. Defaults to the null counter so every existing test keeps working;
        # production refuses that driver at boot (config.py), because a service that sends without
        # counting is exactly the defect core/quota.py exists to fix.
        self._quota = quota or Q.NullQuota()
        # Which templates WhatsApp has approved for this tenant. Unconfigured answers None, which
        # means NOT KNOWN and behaves exactly as this service did before it existed.
        self._approved = approved or R.ApprovedTemplates()
        self._limits = limits
        self._eng_cfg = eng_cfg
        # THE MEASUREMENT GROUP (proof 2). Held here rather than read per message: it is one
        # establishment-level answer, and reading it inside the loop would be a store call per
        # customer for a value that cannot change mid-pass.
        self._holdout_enabled = holdout_enabled
        self._holdout_share = holdout_share
        self._batch = batch
        self._t = telemetry

    async def prune_reach(self, *, now: int) -> int:
        """Drop reach rows that have aged out of the 24h window. GLOBAL, not per-tenant.

        USED TO BE CALLED FROM `run()`, ONCE PER TENANT IN THE LOOP — but `Reach.prune()` scans the
        *entire* `reached_24h` collection with no tenant filter (unlike every other reach read,
        which is tenant-scoped); it is housekeeping for one shared table, not a per-shop answer.
        Calling it from inside the per-tenant loop in `api/internal.py::tick()` re-ran that same
        unscoped scan once per tenant with due work — up to `TICK_MAX_TENANTS` (200) times in a
        single tick, each one a fresh up-to-5000-row read of every tenant's rows, for a job that
        only needs to happen once per tick. Hoisted out here so the caller runs it exactly once.
        """
        return await self._reach.prune(now=now)

    async def run(self, tenant: str, *, now: int, library: list[dict[str, Any]],
                  service_names: dict[str, str], establishment: str,
                  customer_names: dict[str, str] | None = None,
                  tone: str = "masculine", choices: Any = None) -> TickResult:
        """One pass over one tenant's due schedules.

        Per tenant rather than across all of them, so a single establishment with a large backlog
        cannot starve every other one — and so the tenant-scoped query in the store stays the only
        query there is.
        """
        res = TickResult()
        names = customer_names or {}
        due = await self._sched.due(tenant, now=now, limit=self._batch)
        res.scanned = len(due)

        # ONE READ PER TENANT PER TICK, beside the library it belongs with. A shop with 300 due
        # reminders would otherwise ask notification-service 300 times for an answer that cannot
        # change while this loop runs. None means NOT KNOWN — see ApprovedTemplates.
        approved = await self._approved.names(tenant) if due else None
        # EACH TEMPLATE'S DEFERRAL POLICY, ONCE PER TENANT PER TICK — beside `approved`, for the
        # same reason. `_one` used to scan `library` for a row's `template_type` up to twice per
        # due row; the library cannot change while this loop runs, so a dict built once here
        # answers every lookup below in O(1) instead of an O(len(library)) scan per row.
        policy_by_type = {t.get("type"): str(t.get("deferral") or "defer") for t in library}
        # NO `self._reach.prune()` HERE, DELIBERATELY — see `prune_reach()`'s own docstring just
        # above this class: that GLOBAL, unscoped sweep used to be called from inside this exact
        # per-tenant loop and was hoisted OUT specifically because of that cost (an unscoped scan
        # of the whole `reached_24h` collection, up to 200x per tick instead of once). Re-adding a
        # call here would reintroduce the bug `prune_reach` exists to have fixed.

        # HOW MANY NEW PEOPLE MAY STILL BE STARTED WITH TODAY. Read once per tenant, like the
        # library and the approved set — it cannot change meaningfully while this loop runs, and
        # asking per message would be 300 calls for one answer.
        #
        # KNOWING IT BEFORE THE SEND IS THE WHOLE POINT. Without it every message past the ceiling
        # is a round trip to notification-service, a resolve of the customer's phone number from
        # operations, and a rejection from Meta — for a shop that has 400 due reminders and 50
        # left, that is 350 pointless resolutions of a phone number, which is the one read this
        # product tries hardest not to make.
        #
        # None means unknown: `remaining` answers -1 and nothing below changes behaviour.
        room = Room()
        ceiling = C.Ceiling()
        reached = 0
        if due:
            ceiling = await self._ceiling.read(tenant)
            reached = await self._reach.count(tenant, now=now) if ceiling.known() else 0
            room = Room(left=ceiling.remaining(reached))

        # PRIORITY ORDER (spec 8.4.2 section 4). Two messages competing for one daily slot must
        # resolve the same way every time, and the losing one must be the lower-priority one — not
        # whichever the datastore happened to return first.
        due.sort(key=lambda r: (G.priority(r.get("cls", "service")), int(r.get("due_at", 0))))

        for row in due:
            try:
                await self._one(tenant, row, now=now, res=res, library=library,
                                service_names=service_names, establishment=establishment,
                                customer_name=names.get(row.get("subject_ref", ""), ""),
                                tone=tone, approved=approved, room=room, choices=choices,
                                policy_by_type=policy_by_type)
            except Unsendable as exc:
                # PERMANENT, not transient. There is nobody to send to — erased, or never there.
                # Retrying would ask operations about a forgotten customer on every tick forever,
                # which is both useless and the opposite of what they asked for.
                #
                # AND IT LEAVES A ROW, which it did not. The schedule ended and the log said
                # nothing, so an owner asking why a customer heard nothing found no record that a
                # message had ever been owed him — the send log is the only place that fact lives.
                #
                # THE SUBJECT REFERENCE IS ALL THIS ROW CARRIES OF HIM, and that is the point: he
                # was erased, so there is nothing else left to write and nothing else may be
                # written. A pseudonym in our own ledger is not a re-identification of somebody
                # who asked to be forgotten (§PDPL, and `_a_pseudonym_is_not_a_subject`).
                why = f"لا يوجد مستقبِل: {exc}"
                await self._log.append(tenant, as_row(SendLog(
                    tenant=tenant, subject_ref=row.get("subject_ref", ""),
                    cls=row.get("cls", "service"), at=now, schedule_id=row.get("id", ""),
                    branch_id=str(row.get("branch_id") or ""),
                    outcome="suppressed", reason=why)))
                await self._close(tenant, row, "suppressed", why, now)
                res.suppressed += 1
                res.note("no recipient")
            except Exception as exc:                                        # noqa: BLE001
                # ONE ROW'S FAILURE MUST NOT END THE BATCH. The alternative is one malformed
                # schedule stopping every reminder for that establishment, indefinitely, with the
                # symptom appearing as "the product does not work" rather than as one bad row.
                res.failed += 1
                await self._fail(tenant, row, str(exc)[:200], now)
                if self._t is not None:
                    self._t.event("tick_row_failed", tenant=tenant,
                                  schedule=row.get("id", ""), error=str(exc)[:200])
            finally:
                # THE ROW'S CEILING SLOT, IF IT DID NOT SPEND ONE. `_one` takes a slot before the
                # render and the send, and half a dozen paths after that end the row without a
                # message — a lapsed subscription, a template in review, a render error, a peer
                # down. Settled here rather than at each of them so a path added later is right
                # without anybody remembering this exists. `confirm` inside `_one` is what makes a
                # slot that DID become a message stay spent.
                room.settle()

        # ── the ceiling cost him customers, and he should hear it once ────────────────────────
        # AFTER the loop, because the number the sentence is about — how many were stopped — only
        # exists once the pass is done. And `res.ceiling` counts exactly that, which is why it was
        # kept apart from `failed` in the first place.
        await self._maybe_notice(tenant, res=res, ceiling=ceiling, reached=reached,
                                 establishment=establishment, now=now)
        return res

    async def _maybe_notice(self, tenant: str, *, res: TickResult, ceiling: Any,
                            reached: int, establishment: str, now: int) -> None:
        """RECORD that the ceiling cost him customers today. Send nothing.

        THE MESSAGE WAS DESIGNED AND THEN DROPPED, and the reason is worth keeping because it is
        not obvious: a WhatsApp notice to the owner IS a business-initiated message. It comes out
        of the same ceiling and is billed to the same account — so a "your ceiling is full" notice
        is spent from the allowance it is reporting on, and sent at precisely the moment there is
        none left. Meta would refuse it, every day, for as long as the condition lasted. We would
        have built a notice that cannot be delivered by definition.

        So what survives is the FACT: how many were missed, against what ceiling, on what day.
        The dashboard reads it without costing him anything, and the operator panel reads it to
        know who is worth a call — which is how we said this should work anyway (spec §6.2.2):
        we reach out, rather than waiting on a button.

        Failures are swallowed. This is a note about a condition that resolves itself, and failing
        a tick over it would stop the very reminders it is describing.
        """
        try:
            if not CN.should_notify(missed=res.ceiling, ceiling=ceiling.limit,
                                    already_told=await self._notices.told(tenant)):
                return
            await self._notices.record(CN.Notice(
                tenant=tenant, at=now, reached=reached,
                ceiling=ceiling.limit, missed=res.ceiling))
        except Exception:                                                   # noqa: BLE001
            return

    async def send_one(self, tenant: str, row: dict[str, Any], *, now: int,
                       library: list[dict[str, Any]], service_names: dict[str, str],
                       establishment: str, tone: str = "masculine",
                       approved: set[str] | None = None,
                       choices: Any = None) -> dict[str, Any]:
        """Send ONE message that is not on a schedule — the campaigns path.

        THE SAME GATE, THE SAME TEMPLATE SELECTION, THE SAME SANITISER, THE SAME LEDGER. What it
        skips is only the schedule bookkeeping, because a campaign message has no schedule to
        close: it is decided, sent, and recorded, and nothing waits for it.

        A campaign-shaped shortcut around the gate would be a second set of rules, and the second
        one is always the one missing a check the day somebody adds one to the first. So this
        reuses the decision rather than repeating it.

        Returns `{"sent": bool, "reason": str}` — the gate's own sentence, carried verbatim into
        the campaign's run report.
        """
        subject = row.get("subject_ref", "")
        cls = row.get("cls", "marketing")

        # ── the shop's own switch, on this path too ───────────────────────────────────────────
        # IT WAS ENFORCED ON THE TICK ALONE, and every message a PEER sends comes through here:
        # the points receipt, the expiry warning, the weekly digest, every campaign. So switching
        # one of those off in «رسائلي» stored an answer that nothing ever read — a control that
        # appears to work and does nothing, which is worse than not offering it.
        ids = TR.candidates(str(row.get("kind", "")), str(row.get("template_type", "")))
        if ids and choices is not None and not any(choices.enabled(i) for i in ids):
            reason = "أوقفتَ هذا النوع من الرسائل"
            await self._log.append(tenant, as_row(SendLog(
                tenant=tenant, subject_ref=subject, cls=cls, at=now,
                schedule_id=row.get("id", ""), branch_id=str(row.get("branch_id") or ""), outcome="suppressed", reason=reason)))
            return {"sent": False, "reason": reason}

        prefs = await self._prefs.get(tenant, subject) or {}
        eng = await self._eng.get(tenant, subject) or {}
        recent = await self._log.since(tenant, subject, since=now - 31 * 86400)
        # READ FOR EVERY CLASS, AND THE OLD SHORTCUT WAS THE WHOLE DEFECT.
        #
        # It read consent only when `cls == "marketing"`, reasoning that no other class needs a
        # grant to be sent. True — and it made the invitation impossible. Every utility text now
        # ends with the one line that asks for consent (core/invite.py), and that line has two
        # forms: an invitation for somebody who has not agreed, and an acknowledgement for
        # somebody who has. A send path that cannot tell them apart either invites a customer who
        # agreed months ago — in every message, forever — or invites nobody at all.
        #
        # So the read is unconditional. It is one keyed lookup per message, against a store this
        # path already opens for the preferences, the engagement score and the send log.
        consent = await self._consent.state(tenant, subject)
        decision = G.evaluate(
            cls=cls, template_type=row.get("template_type", ""), now=now, limits=self._limits,
            prefs_stopped=prefs.get("stopped") or {},
            engagement_score=float(eng.get("score") or 0.0),
            engagement_at=int(eng.get("scored_at") or 0),
            recent_sends=recent, eng_cfg=self._eng_cfg,
            marketing_consent=consent,
            withdrawal_reachable=self._withdrawal_reachable,
            tenant=tenant, subject_ref=subject,
            holdout_enabled=self._holdout_enabled, holdout_share=self._holdout_share,
            class_enabled=any(t.get("type") == row.get("template_type") for t in library))

        if not decision.allowed:
            # RECORDED AS A SUPPRESSION, exactly like a reminder's. The ledger is what every cap is
            # counted against, and a refusal that leaves no row is a refusal nobody can explain.
            await self._log.append(tenant, as_row(SendLog(
                tenant=tenant, subject_ref=subject, cls=cls, at=now,
                schedule_id=row.get("id", ""), branch_id=str(row.get("branch_id") or ""), outcome="suppressed", reason=decision.reason)))
            return {"sent": False, "reason": decision.reason}

        try:
            own_name = _own_template(choices, ids)
            # READ WITH THE NAME, because `render` fills by the template's own declaration and the
            # name alone declares nothing — see rendering.choose.
            own_row = (await CustomTemplateStore(self._store).get(tenant, own_name)
                       if own_name else None)
            template = R.choose(template_type=row.get("template_type", ""), tone=tone,
                                library=library, approved=approved,
                                # THE RUNG'S OWN VOICE (د-7). Stamped by `_ladder` and, until now,
                                # read by nothing — so the second rung repeated the first verbatim.
                                tone_index=int(row.get("tone_index") or 1),
                                own=own_name, own_row=own_row)
            # SLOT BY SLOT, FROM THE TEMPLATE'S OWN DECLARATION. The previous version put the
            # owner's single sentence into slots 3 AND 4 through all three source dicts, so a
            # four-variable template said the same thing twice; and it passed slot 1 empty, which
            # greeted every customer «عميلنا العزيز» although we hold their names. A typed slot
            # (a discount, an end date) had no value to take at all.
            values = R.campaign_slots(
                template,
                establishment=establishment,
                owner_text=row.get("owner_text", ""),
                service_text=R.merged_service_text(
                    [service_names.get(s, s) for s in (row.get("offer_services") or [])]),
                offer_value=str(row.get("offer_value", "")),
                expires_at=int(row.get("offer_expires_at") or 0))
            # ONE DICT, PASSED AS ALL THREE. `campaign_slots` has already answered per source, so
            # handing the renderer three different maps would be deciding the same thing twice and
            # inviting them to disagree.
            rendered = R.render(template=template, system=values, catalogue=values,
                                owner=values,
                                public_base_url=self._public_base_url,
                                # THE REFERENCE PORTAL READS, NOT THE BARE SUBJECT. It mints
                                # `{tenant}.{subject}` and splits on the dot; a link built from
                                # the subject alone opens a page that knows nobody.
                                reference=LINKS.reference_for(tenant, row.get("subject_ref", "")),
                                marketing_consent=consent)
        except R.RenderError as exc:
            # RECORDED, LIKE EVERY OTHER REFUSAL ON THIS PATH. It was the one that mattered most
            # and the one that wrote nothing: with the public base unset every service wording
            # fails here, so a campaign to a hundred and forty people produced a hundred and forty
            # silent refusals and a screen with no rows on it.
            await self._log.append(tenant, as_row(SendLog(
                tenant=tenant, subject_ref=subject, cls=cls, at=now,
                schedule_id=row.get("id", ""), branch_id=str(row.get("branch_id") or ""),
                outcome="suppressed", reason=str(exc))))
            return {"sent": False, "reason": str(exc)}

        key = row.get("idempotency_key") or f"cmp_{row.get('id','')}"

        # THE QUOTA, IMMEDIATELY BEFORE THE SEND AND NOWHERE EARLIER. Everything above this line
        # can still refuse — the gate, the render — and a message we decided not to send must not
        # have cost the shop anything. Atomic check-and-increment, keyed by the SEND's own key so
        # a redelivery spends nothing (core/quota.py).
        try:
            await self._quota.consume(tenant=tenant, idempotency_key=key)
        except Q.QuotaError as exc:
            await self._log.append(tenant, as_row(SendLog(
                tenant=tenant, subject_ref=subject, cls=cls, at=now,
                schedule_id=row.get("id", ""), branch_id=str(row.get("branch_id") or ""), outcome="suppressed", reason=str(exc))))
            return {"sent": False, "reason": str(exc)}

        try:
            delivery_id = await self._sender.send(
                tenant=tenant, subject_ref=subject, template_name=rendered.template_name,
                variables=rendered.variables, cls=cls, idempotency_key=key,
                # WHICH NUMBER IT LEAVES FROM. The schedule already carries the branch the visit
                # happened at; this is the one line that turns it into the credentials the message
                # is actually sent with. `""` — every shop in the default mode — resolves to the
                # establishment inside the sender, exactly as before.
                sending_identity=_sending_identity(tenant, row),
                # THE SAME OPTIONAL FLOW-BUTTON FIELDS THE SCHEDULED RATING SEND USES BELOW
                # (`flow_token=f"rate:{visit_id}"`), read off THIS row instead of computed here —
                # `send_one` serves every caller of `/internal/reminders/send` (campaigns AND
                # insights' weekly digest), so it has no visit of its own to derive a token from;
                # the caller (campaign_send) is the one that knows whether this particular send
                # opens a Flow, and passes both fields straight through the schedule dict it
                # already builds. Empty on every existing caller, so this is a no-op for them —
                # `HttpSender.send` already omits `flow_token` from the wire body entirely when
                # it is "".
                flow_token=str(row.get("flow_token") or ""),
                flow_action_data=row.get("flow_action_data") or None,
                # THE UNIFIED SINGLE-ITEM QUICK-REPLY BUTTON (2026-09-13) — same "the caller
                # already knows, this just carries it" posture as flow_token above. Empty for
                # every existing caller, so this is a no-op for them.
                button_item_id=str(row.get("button_item_id") or ""),
                button_kind=str(row.get("button_kind") or "service"),
                branch_id=str(row.get("branch_id") or ""))
        except Unsendable as exc:
            # GIVE THE UNIT BACK. The consume had to come first to be atomic, so a send that did
            # not happen leaves a unit spent — and an erased recipient is not something the shop
            # should pay for.
            await self._quota.release(tenant=tenant, idempotency_key=key)
            # THE SUBJECT REFERENCE IS ALL THAT IS LEFT OF HIM, and all that may be written: he was
            # erased, and a pseudonym in our own ledger is not a re-identification.
            gone = f"لا يوجد مستقبِل: {exc}"
            await self._log.append(tenant, as_row(SendLog(
                tenant=tenant, subject_ref=subject, cls=cls, at=now,
                schedule_id=row.get("id", ""), branch_id=str(row.get("branch_id") or ""),
                outcome="suppressed", reason=gone)))
            return {"sent": False, "reason": gone}
        except CeilingReached as exc:
            # A campaign message is always deferrable — see the 8.4.3 table, where every mkt_* is
            # `defer`. It goes when the ceiling opens; nobody is waiting for an offer.
            await self._quota.release(tenant=tenant, idempotency_key=key)
            # «سترسل تلقائياً» WAS A PROMISE NOTHING KEPT, and this is the campaign path.
            #
            # `send_one`'s own docstring two hundred lines up says it: a campaign message has no
            # schedule to close, «it is decided, sent, and recorded, and nothing waits for it». So
            # there was no row for anything to retry, the subject was never written to the reached
            # set, and no queue held him. A shop near its ceiling read «سترسل تلقائياً» beside a
            # hundred and forty customers, waited, and the offer expired unsent.
            #
            # WHAT IS TRUE — and it is better news than the lie was: pressing send again continues
            # from where it stopped. `_already_reached` means the second pass contacts only the
            # remainder, so nobody is messaged twice and the owner keeps the decision about a
            # marketing send, which is the whole reason a manual campaign is manual.
            capped = (f"سقف واتساب اليومي ({exc.code}) — لم تُرسل. أعد الإرسال غداً "
                      f"وتُكمل من حيث توقّفت دون تكرار على أحد.")
            # AND THE ROW IS WHAT MAKES «تُكمل من حيث توقّفت» CHECKABLE. Without it the sentence is
            # a promise with no evidence behind it: nobody — not the owner, not support — could
            # say which customers the ceiling stopped and which were never reached at all.
            await self._log.append(tenant, as_row(SendLog(
                tenant=tenant, subject_ref=subject, cls=cls, at=now,
                schedule_id=row.get("id", ""), branch_id=str(row.get("branch_id") or ""),
                outcome="suppressed", reason=capped)))
            return {"sent": False, "reason": capped}
        except Exception:
            # Every other failure — a template still in Meta's review, a peer down — is transient
            # and retried. It must not be charged either.
            await self._quota.release(tenant=tenant, idempotency_key=key)
            raise

        await self._reach.record(tenant, subject, now=now)
        # THE OFFER IS RECORDED ONLY ON A MESSAGE THAT WENT OUT, which is the whole point: the send
        # log is the entitlement. Whoever received this holds the offer until it expires; whoever
        # did not, never held it — no second table, and nothing to argue about at the counter.
        await self._log.append(tenant, as_row(SendLog(
            tenant=tenant, subject_ref=subject, cls=cls, at=now,
            schedule_id=row.get("id", ""), branch_id=str(row.get("branch_id") or ""), template_name=rendered.template_name,
            outcome="sent", idempotency_key=key, delivery_id=delivery_id,
            offer_text=row.get("offer_text", ""),
            offer_expires_at=int(row.get("offer_expires_at") or 0),
            offer_services=list(row.get("offer_services") or []),
            # THE WORDS, NOT ONLY THE KEYS (أ-4). They were used to render this very message and
            # then thrown away, so his page — read days later, by which time nobody holds the
            # catalogue map — printed «على: svc_9f2a…» to a customer.
            offer_service_names=[service_names[s] for s in (row.get("offer_services") or [])
                                 if s in service_names],
            # RECORDED WITH THE OFFER: it is a fact about what was granted, and every reader of
            # this row needs it to say what the discount actually is.
            offer_value=str(row.get("offer_value", "")))))
        return {"sent": True, "reason": ""}

    async def _one(self, tenant: str, row: dict[str, Any], *, now: int, res: TickResult,
                   library: list[dict[str, Any]], service_names: dict[str, str],
                   establishment: str, customer_name: str, tone: str,
                   approved: set[str] | None = None, room: Room | None = None,
                   choices: Any = None,
                   policy_by_type: dict[str, str] | None = None) -> None:
        subject = row.get("subject_ref", "")
        cls = row.get("cls", "service")

        # ── 0. did the shop switch this off? ──────────────────────────────────────────────────
        # BEFORE THE CLAIM AND BEFORE THE GATE, because a message the owner turned off is not a
        # message that lost a decision — it is one that was never his to send. Claiming it first
        # would spend a row's state on it, and gating it first would count it against caps it is
        # not part of.
        #
        # CLOSED, NOT LEFT PENDING. A schedule that stays pending is retried on every tick for
        # ever, and «رسائلي» would show a queue that never drains for a switch he deliberately
        # threw. It reappears the moment he switches it back on, because the next visit schedules
        # a new one — the switch decides the future, not the past.
        reason = TR.for_row(str(row.get("kind", "")), str(row.get("template_type", "")))
        if reason and choices is not None and not choices.enabled(reason):
            # AND IT IS WRITTEN DOWN. This was the one refusal in the engine with no row behind
            # it, and it is the one an owner asks about most: he throws a switch in the evening
            # and wants to know in the morning whether anything went out under it, or how many
            # were stopped. «لم يخرج شيء» and «لا سجلّ» are different answers, and only one of
            # them was available.
            off = "أوقفتَ هذا النوع من الرسائل"
            await self._log.append(tenant, as_row(SendLog(
                tenant=tenant, subject_ref=subject, cls=cls, at=now,
                schedule_id=row.get("id", ""), branch_id=str(row.get("branch_id") or ""),
                outcome="suppressed", reason=off)))
            await self._close(tenant, row, "suppressed", off, now)
            res.suppressed += 1
            res.reasons["أوقفتَ هذا النوع من الرسائل"] = (
                res.reasons.get("أوقفتَ هذا النوع من الرسائل", 0) + 1)
            return

        # ── 1. claim ──────────────────────────────────────────────────────────────────────────
        # Two replicas run this cron. Without the claim they both read `pending` and both send.
        claimed = await self._claim(tenant, row, now)
        if not claimed:
            return

        # ── 2. gate ───────────────────────────────────────────────────────────────────────────
        prefs = await self._prefs.get(tenant, subject) or {}
        eng = await self._eng.get(tenant, subject) or {}
        recent = await self._log.since(tenant, subject, since=now - 31 * 86400)
        # READ FOR EVERY CLASS, AND THE OLD SHORTCUT WAS THE WHOLE DEFECT.
        #
        # It read consent only when `cls == "marketing"`, reasoning that no other class needs a
        # grant to be sent. True — and it made the invitation impossible. Every utility text now
        # ends with the one line that asks for consent (core/invite.py), and that line has two
        # forms: an invitation for somebody who has not agreed, and an acknowledgement for
        # somebody who has. A send path that cannot tell them apart either invites a customer who
        # agreed months ago — in every message, forever — or invites nobody at all.
        #
        # So the read is unconditional. It is one keyed lookup per message, against a store this
        # path already opens for the preferences, the engagement score and the send log.
        consent = await self._consent.state(tenant, subject)
        decision = G.evaluate(
            cls=cls, template_type=row.get("template_type", ""), now=now, limits=self._limits,
            prefs_stopped=prefs.get("stopped") or {},
            engagement_score=float(eng.get("score") or 0.0),
            engagement_at=int(eng.get("scored_at") or 0),
            recent_sends=recent, eng_cfg=self._eng_cfg,
            marketing_consent=consent,
            withdrawal_reachable=self._withdrawal_reachable,
            tenant=tenant, subject_ref=subject,
            holdout_enabled=self._holdout_enabled, holdout_share=self._holdout_share,
            class_enabled=any(t.get("type") == row.get("template_type") for t in library))

        if not decision.allowed:
            # `drop` MEANS DROP AT BOTH GATES (د-11).
            #
            # A template declares `deferral: drop` when arriving late is worse than not arriving:
            # «سجّلنا زيارتك» tomorrow morning is not a late confirmation, it is a strange one —
            # the customer left the shop yesterday. The CEILING branch below has always read this
            # policy. This branch did not, so a quiet-hours or engagement deferral pushed exactly
            # those messages a full day into the future — the case the policy was written to
            # prevent, reached by the other door.
            policies = policy_by_type if policy_by_type is not None else {
                t.get("type"): str(t.get("deferral") or "defer") for t in library}
            policy = policies.get(row.get("template_type"), "")

            if decision.retry_at and policy != "drop":
                # DEFERRED: the row goes back to pending with a new due date. Deliberately not a
                # terminal state — "wait" and "never" are different answers and an owner reading
                # the log must be able to tell them apart.
                row["state"] = "pending"
                row["due_at"] = decision.retry_at
                row["reason"] = decision.reason
                row["updated"] = now
                await self._sched.upsert(tenant, _key(row), row)
                res.deferred += 1
            else:
                await self._close(tenant, row, "suppressed", decision.reason, now)
                await self._log.append(tenant, as_row(SendLog(
                    tenant=tenant, subject_ref=subject, cls=cls, at=now,
                    schedule_id=row.get("id", ""), branch_id=str(row.get("branch_id") or ""), outcome="suppressed",
                    reason=decision.reason)))
                res.suppressed += 1
            res.note(decision.reason)
            return

        # ── 2b. the shop's remaining room for TODAY ───────────────────────────────────────────
        # AFTER the gate, because a message the gate refuses costs no ceiling either — and before
        # the render and the send, which is where the expensive part starts.
        #
        # ONLY SOMEBODY NEW COSTS ANYTHING. The ceiling counts unique customers, so a second
        # message to a person already reached in this window is free and must not be blocked by a
        # count of people. Checking this the naive way — "is there room" without asking whether
        # this person is new — would silence a shop's follow-ups the moment it hit its ceiling,
        # for customers it had already paid to reach.
        room = room or Room()
        if room.known() and await self._reach.would_be_new(tenant, subject, now=now):
            if not room.take():
                policies = policy_by_type if policy_by_type is not None else {
                    t.get("type"): str(t.get("deferral") or "defer") for t in library}
                policy = policies.get(row.get("template_type"), "")
                res.ceiling += 1
                if policy == "drop":
                    await self._log.append(tenant, as_row(SendLog(
                        tenant=tenant, subject_ref=subject, cls=cls, at=now,
                        schedule_id=row.get("id", ""), branch_id=str(row.get("branch_id") or ""), outcome="suppressed",
                        reason="سقف واتساب اليومي")))
                    await self._close(tenant, row, "suppressed", "سقف واتساب اليومي", now)
                    res.suppressed += 1
                else:
                    await self._defer_to_tomorrow(tenant, row, now, "known")
                    res.deferred += 1
                return
        # ── 2c. fold in what is due within days ───────────────────────────────────────────────
        # AFTER the gate and the ceiling, and BEFORE the render — the only place it can be.
        #
        # Before the gate it would merge messages that are then refused, and the folded rows would
        # be closed for a message that never went. After the render it would be too late to name
        # them. And it belongs here rather than at scheduling time because a visit cannot see the
        # visit that has not happened yet: two visits days apart book two reminders days apart, and
        # nothing in the system knows they are one man until this moment (spec §5.8.1).
        pending = await self._sched.pending_for_subject(tenant, subject)
        folding = M.plan(row, pending, now=now)
        if folding.merged:
            row = folding.lead

        # ── 3. render ─────────────────────────────────────────────────────────────────────────
        own_name2 = _own_template(choices, [reason] if reason else [])
        own_row2 = (await CustomTemplateStore(self._store).get(tenant, own_name2)
                    if own_name2 else None)
        # ── A MESSAGE THAT CANNOT BE BUILT IS AN ANSWER, NOT AN OUTAGE ────────────────────────
        #
        # These two calls were the only ones in the product outside a handler that names
        # `RenderError`. The campaign path a few hundred lines above has caught it since it was
        # written; this path — the visit confirmation, the most frequent message the product
        # sends — did not, so the exception left `_one` entirely and landed in the batch's generic
        # `except Exception`, which calls `_fail`: back to pending, due in an hour, for ever.
        #
        # WHY THAT IS THE WORST OF THE AVAILABLE OUTCOMES. `_fail` is written for a peer being
        # briefly unavailable, and every reason `render` refuses is the opposite of brief: no
        # approved template of this type, a numbering gap, an owner's text that breaks a rule,
        # or — the live one — the public base being unset, which kills all 36 service wordings
        # while the customer page is switched off. The same inputs produce the same refusal next
        # hour and every hour after. Nothing reached the send log, because as far as the log was
        # concerned nothing was attempted; nothing was closed, so it retried for ever; and the
        # only number that moved was `res.failed`, which no screen reads. An owner watching this
        # saw a product that never messaged anybody, with no row and no reason to ask about.
        #
        # RECORDED AND CLOSED, THEREFORE — and `suppressed` rather than a new outcome word,
        # because the log's vocabulary is "sent" or "suppressed" and every counter in the product
        # reads it. What separates this from a policy suppression is the REASON, which carries the
        # renderer's own sentence: the one thing that tells an owner whether he is waiting on
        # Meta, on his own text, or on us.
        # THE RATING APP'S OWN NUMBER, ONLY FOR ITS OWN KIND. A direct store read here, not a
        # peer call scheduling.py would have to be taught — tick.py already reads several stores
        # per row (prefs, engagement, consent above), and this is the same shape, asked only for
        # the one kind that needs it.
        is_rating = row.get("kind") == "rating_request"
        rating_points = 0
        if is_rating:
            from app.core.rating_settings import RatingSettingsStore
            rating_points = (await RatingSettingsStore(self._store).load(tenant)).points

        try:
            template = R.choose(template_type=row.get("template_type", ""), tone=tone,
                                library=library, approved=approved,
                                # HIS OWN TEXT ON THIS PATH TOO. Two render sites is two chances to
                                # wire one of them and believe the feature works: an owner who
                                # customised his visit confirmation would see it on some messages and
                                # ours on others, which reads as a product that cannot make up its mind.
                                tone_index=int(row.get("tone_index") or 1),
                                own=own_name2, own_row=own_row2)
            service_text = R.merged_service_text(
                [service_names.get(s, s) for s in
                 [row.get("service_id", "")] + list(row.get("also_services") or [])])
            # THE REDEMPTION, IF ONE JOINED THIS MESSAGE (§9.6). A confirmation waits ten minutes on
            # purpose, and that is exactly the window in which a redemption happens at the counter —
            # so it rides along instead of becoming a second message. Slots 3 and 4 of
            # `svc_visit_redeemed`: what it cost, what is left.
            #
            # THE REWARD'S OWN NAME IS DELIBERATELY NOT ONE OF THEM (2026-09-13, the owner's own
            # instruction) — naming it made the sentence longer for no real benefit (the customer
            # just redeemed it at the counter; the balance is the only new information the message
            # carries), and a wording that names a specific service breaks the moment a visit ever
            # covers more than one, which a fixed slot cannot express — the balance-only sentence
            # has no such ceiling.
            #
            # 3 IS A SHARED SLOT. On every other template it holds the service text; on this one the
            # reward's own cost. Same numbering, different template — which is the whole reason this
            # is a template VARIANT rather than an optional sentence: WhatsApp has no optional part,
            # and a visit without a redemption has nothing true to put in it.
            redeemed = row.get("redeemed_name", "")
            # A BOOKING CONFIRMATION IS NOT A VISIT'S SHAPE. Slot 3 on `svc_visit_confirmation`'s
            # kin is the service or the redemption's cost; on `svc_booking_confirmation` it is the
            # appointment's own day and hour (Schedule.appt_time, phrased once at scheduling time
            # by rendering.arabic_appointment — never re-derived here). Falling through to
            # `service_text` for this kind would put `service_id`'s raw value on the row — which
            # for a booking schedule IS THE BOOKING ID (see Scheduler.on_booking) — into a
            # customer-facing message.
            is_booking = row.get("kind") == "booking_confirmation"
            slot_3 = row.get("appt_time", "") if is_booking else (
                str(row.get("redeemed_cost", "")) if redeemed else service_text)
            rendered = R.render(
                template=template,
                system={"1": customer_name, "2": establishment,
                        "3": slot_3,
                        "4": str(row.get("redeemed_remaining", "")) if redeemed else service_text},
                catalogue={"3": service_text, "4": service_text},
                owner={"3": row.get("owner_text", ""), "4": row.get("owner_text", "")},
                # THE SAME VALUES, KEYED BY WHAT THEY MEAN (ح-1). A template the OWNER wrote declares
                # its blanks by meaning, not by position — «{{2}} is the service» in his text and «the
                # shop name» in the library's. Handing the renderer only the positional dicts is what
                # made his sentence arrive rewritten.
                by_meaning={
                    "customer": customer_name,
                    "shop": establishment,
                    "service": service_text,
                    "reward": redeemed,
                    "points": str(row.get("redeemed_cost", "")) if redeemed else "",
                    "balance": str(row.get("redeemed_remaining", "")),
                    "free_text": row.get("owner_text", ""),
                },
                public_base_url=self._public_base_url,
                # Same reason as the campaign path above: portal reads `{tenant}.{subject}`.
                reference=LINKS.reference_for(tenant, subject),
                # WHAT THE INVITE LINE NEEDS, AND IT COMES FROM THE READ THE GATE ALREADY DID.
                # A second read here would be a second answer, and the two could disagree across
                # the milliseconds between them — the message would then invite somebody the gate
                # had just recorded as having agreed.
                marketing_consent=consent,
                # IGNORED BY EVERY TEMPLATE EXCEPT svc_visit_confirmation_rating's own rating_cta
                # slot (rendering.py) — harmless to pass on every other kind.
                rating_points=rating_points)
        except R.RenderError as exc:
            # `why`, NOT `reason` — the name is already taken on this path by the trigger that
            # scheduled the row, and it is read a few lines above to find the owner's own text.
            why = f"تعذّر بناء الرسالة: {exc}"
            await self._log.append(tenant, as_row(SendLog(
                tenant=tenant, subject_ref=subject, cls=cls, at=now,
                schedule_id=row.get("id", ""), branch_id=str(row.get("branch_id") or ""),
                outcome="suppressed", reason=why)))
            await self._close(tenant, row, "suppressed", why, now)
            res.suppressed += 1
            res.note("render failed")
            return

        # ── 4. send ───────────────────────────────────────────────────────────────────────────
        # The key is generated and stored BEFORE the call and reused on every retry: a timeout is
        # not evidence that nothing was sent, and the customer must not pay for our uncertainty.
        key = row.get("idempotency_key") or _send_key(row)
        if key != row.get("idempotency_key"):
            row["idempotency_key"] = key
            await self._sched.upsert(tenant, _key(row), row)

        # The quota, immediately before the send — see the campaign path above and quota.py. The
        # key here is the one already stored on the row, so a retry after a timeout consumes the
        # same unit rather than a second one.
        try:
            await self._quota.consume(tenant=tenant, idempotency_key=key)
        except Q.QuotaError as exc:
            await self._log.append(tenant, as_row(SendLog(
                tenant=tenant, subject_ref=subject, cls=cls, at=now,
                schedule_id=row.get("id", ""), branch_id=str(row.get("branch_id") or ""), outcome="suppressed", reason=str(exc))))
            # CLOSED AS SUPPRESSED, NOT FAILED. An exhausted quota is a decision, not an error:
            # retrying it every hour for the rest of the month would fill the reason counts with
            # noise and hide the peer failures they exist to surface. He buys a pack and the next
            # reminders go out; this one is a message that was not sent, and it says so.
            await self._close(tenant, row, "suppressed", str(exc), now)
            res.suppressed += 1
            return

        # THE RATING APP'S OWN ANCHOR — remembered BEFORE the send, not after, same reasoning as
        # the quota consume above: a timeout is not evidence that nothing was sent, and a reply
        # that arrives before this call returns must still resolve to something. Deterministic on
        # the visit id, so a retry of this exact schedule row remembers the SAME token rather than
        # orphaning the first one (RatingRequestStore.remember is a plain overwrite, harmless).
        flow_token = ""
        if is_rating:
            from app.core.rating_request import RatingRequestStore
            flow_token = f"rate:{row.get('visit_id', '')}"
            await RatingRequestStore(self._store).remember(
                flow_token=flow_token, tenant=tenant, subject_ref=subject,
                visit_id=str(row.get("visit_id") or ""), now=now)

        try:
            delivery_id = await self._sender.send(
                tenant=tenant, subject_ref=subject, template_name=rendered.template_name,
                variables=rendered.variables, cls=cls, idempotency_key=key,
                # WHICH NUMBER IT LEAVES FROM. The schedule already carries the branch the visit
                # happened at; this is the one line that turns it into the credentials the message
                # is actually sent with. `""` — every shop in the default mode — resolves to the
                # establishment inside the sender, exactly as before.
                sending_identity=_sending_identity(tenant, row),
                # EMPTY FOR EVERY KIND EXCEPT rating_request — the sender itself omits the wire
                # field entirely when flow_token is "", so this is harmless for every other send.
                flow_token=flow_token)
        except CeilingReached as exc:
            # WHATSAPP WILL NOT TAKE ANOTHER MESSAGE FROM THIS SHOP RIGHT NOW (spec §8.4.3).
            # Nothing left, so nothing is counted — and what happens next is the TEMPLATE's
            # decision, carried on the template itself rather than decided here.
            await self._quota.release(tenant=tenant, idempotency_key=key)
            # AND THE COUNT IS CORRECTED TO WHAT META JUST SAID. Our own count of the shop's room
            # disagreed with the ceiling — it thought there was room, and there is none — so the
            # rest of this pass defers on the count instead of asking again. `exhaust` rather than
            # the `settle` below: handing the slot back walks the next row into the same refusal.
            room.exhaust()
            policy = str(template.get("deferral") or "defer")
            res.ceiling += 1
            if policy == "drop":
                # Worthless tomorrow. "We recorded your visit" arriving 18 hours late is not a
                # late message, it is a strange one — and the shop is better served by silence.
                await self._log.append(tenant, as_row(SendLog(
                    tenant=tenant, subject_ref=subject, cls=cls, at=now,
                    schedule_id=row.get("id", ""), branch_id=str(row.get("branch_id") or ""), template_name=rendered.template_name,
                    outcome="suppressed", reason=f"سقف واتساب اليومي ({exc.code})")))
                await self._close(tenant, row, "suppressed",
                                  f"سقف واتساب اليومي ({exc.code})", now)
                res.suppressed += 1
                return
            # `defer` and `priority` both come back — priority is about ORDER within a day, and
            # once the day is closed there is no order left to win.
            await self._defer_to_tomorrow(tenant, row, now, exc.code)
            res.deferred += 1
            return
        except Exception:
            await self._quota.release(tenant=tenant, idempotency_key=key)
            raise

        # ── 5. record ─────────────────────────────────────────────────────────────────────────
        # RECORDED ONLY AFTER IT WENT. A message that failed reached nobody, and counting it would
        # push the shop toward a ceiling it never touched.
        #
        # And the same sentence decides the ceiling slot: it was a reservation until this line,
        # and this is where it becomes spent. Everything before it that ends the row hands it back.
        room.confirm()
        await self._reach.record(tenant, subject, now=now)
        await self._log.append(tenant, as_row(SendLog(
            tenant=tenant, subject_ref=subject, cls=cls, at=now,
            schedule_id=row.get("id", ""), branch_id=str(row.get("branch_id") or ""), template_name=rendered.template_name,
            outcome="sent", idempotency_key=key, delivery_id=delivery_id)))
        await self._close(tenant, row, "sent", "", now)

        # ── 5b. close what rode along ─────────────────────────────────────────────────────────
        # CLOSED, NEVER DELETED, and with the id of the message that carried them. An owner
        # reading «رسائلي» sees one message where he expected two and can follow it to the one
        # that went — whereas a row that simply disappears reads as the daily cap eating his
        # messages, which is the confusion `merge before counting` was written to avoid.
        #
        # AND ONLY AFTER THE SEND SUCCEEDED. Closing them at fold time would lose them for a
        # message that then hit the ceiling or a peer failure — one lost visit's reminder is a
        # customer nobody calls back.
        for folded in folding.folded:
            folded["merged_into"] = row.get("id", "")
            await self._close(tenant, folded, "merged", "دُمجت في رسالة واحدة", now)
            res.merged += 1
        res.sent += 1

        # ── 5c. the ladder, and it starts HERE or nowhere ─────────────────────────────────────
        #
        # AFTER THE SEND SUCCEEDED, never at schedule time. A ladder built when the first reminder
        # was scheduled would go on climbing after the message was suppressed, deferred or dropped
        # at the ceiling — pressing a customer about a message he never received.
        await self._ladder(tenant, row, subject, now=now, cls=cls)

    async def _claim(self, tenant: str, row: dict[str, Any], now: int) -> bool:
        """Move the row out of `pending` before anything external happens.

        SERIALISED WITH THE DATASTORE'S OWN `claim()` PRIMITIVE — fixed 2026-09-12, a real gap a
        QA audit found. The docstring here used to say the DataStore port had no CAS and adding
        one would be a change to base-services; that was stale — `DataStore.claim()` has existed,
        correctly implemented in both adapters, since the port itself was built for exactly this
        race, and simply was never wired in here. Two replicas racing the SAME row could both read
        `state == "pending"` before either wrote `"sending"`, both send, and both append their own
        SendLog row for one delivered message — inflating every cap `gate.evaluate` computes by
        counting ledger rows, and occasionally suppressing a later, legitimate message over a
        limit the customer never actually reached.

        A SEPARATE LOCK COLLECTION, NOT THE SCHEDULE ROW ITSELF — same shape as `SpendLock`/
        `OfferApplyLock`/`CustomerCounterLock` elsewhere on this platform: the schedule row keeps
        its own rich `state`/`claimed_at` shape (read by recovery and by every other method here)
        unchanged; the lock only decides WHO gets to read-modify-write it this instant.
        """
        lock_key = f"{tenant}|{_key(row)}"
        took = await self._store.claim(
            _CLAIM_LOCKS, lock_key, {"tenant": tenant, "row": _key(row)},
            ttl_seconds=CLAIM_LOCK_TTL_SECONDS, now=now)
        if not took:
            # Another replica is deciding this exact row's claim right now — not an error, just
            # this replica's loss of a race it need not retry: `due()` re-lists the row next tick
            # if it is genuinely still pending, or the lock's own short TTL clears in seconds if
            # the other replica's decision already finished.
            return False
        try:
            fresh = await self._sched.get(_key(row))
            if fresh is None:
                return False

            state = fresh.get("state")
            if state == "sending":
                # AN ABANDONED CLAIM IS RECLAIMABLE, AND ONLY AFTER THE LEASE. `due()` is what put
                # this row in front of us, and it only does that once the previous claim is old
                # enough to be certainly dead. Re-checking here rather than trusting the caller
                # keeps the rule in one place — and stops a second worker in the same tick from
                # taking a claim seconds old.
                if now - int(fresh.get("claimed_at") or 0) < CLAIM_LEASE_SECONDS:
                    return False
            elif state != "pending":
                return False

            fresh["state"] = "sending"
            # STAMPED, AND THIS IS THE FIELD THE WHOLE RECOVERY HANGS ON. Without it a row in
            # `sending` is indistinguishable from one claimed a second ago, so nothing can ever
            # safely reclaim it — which is exactly how the reminder used to be lost for good.
            fresh["claimed_at"] = now
            fresh["updated"] = now
            await self._sched.upsert(tenant, _key(fresh), fresh)
            row.update(fresh)
            return True
        finally:
            await self._store.delete(_CLAIM_LOCKS, lock_key)

    async def _ladder(self, tenant: str, row: dict[str, Any], subject: str, *,
                      now: int, cls: str) -> None:
        """Schedule what follows a reminder that went out (§5.6.1). NEVER RAISES.

        THE RUNGS COME FROM `core/ladder.py`, WHICH DECIDES AND DOES NOT ACT. This is the only
        caller, and it exists because the module was written and wired to nothing: the arithmetic
        was tested, the rules were right, and no customer would ever have received a second
        message. That is the same shape as the severed `service_id` next door — complete in the
        depth, cut at the door — and it is worth naming twice.

        ONLY AFTER A REMINDER. A follow-up, a review request or a campaign has no ladder: they are
        not "he did not come", which is the one thing a ladder answers.
        """
        if row.get("kind") != "reminder":
            return
        try:
            rule = await RuleStore(self._store).get(
                f"{tenant}|{subject}|{row.get('service_id', '')}") or {}
            eng = await self._eng.get(tenant, subject) or {}
            consent = await self._consent.state(tenant, subject)

            rungs = L.build(
                sent_at=now,
                interval_days=int(float(rule.get("interval_days") or 0)),
                # GRANTED, NOT "NOT REFUSED". `never_asked` is not consent — an offer needs a yes
                # (§8.5), and the ladder simply loses that rung rather than substituting one.
                marketing_consent=(consent == "granted"),
                first_rung_returns=int(rule.get("first_rung_returns") or 0),
                # NONE WHEN THERE IS NO RECORD, never 0.0. "Never measured" and "reads nothing"
                # are different facts, and a shop's first week is nothing but the former.
                engagement_score=(float(eng["score"]) if eng.get("score") is not None else None))

            for i, rung in enumerate(rungs):
                # ONE ROW PER RUNG, KEYED SO IT CANNOT COLLIDE with the reminder that produced it
                # nor with the other rung. The schedule's natural key is
                # (tenant, customer, service, kind) — two rungs of the same ladder would otherwise
                # be one row, and the second would silently replace the first.
                follow = dict(row)
                follow.pop("id", None)
                follow.pop("idempotency_key", None)
                follow["kind"] = f"ladder_{i + 1}"
                follow["state"] = "pending"
                follow["reason"] = ""
                follow["due_at"] = rung.due_at
                # A RUNG IS MARKETING ONLY IF IT CARRIES AN OFFER (د-8).
                #
                # `ladder.py` calls the second rung an OFFER, and this line believed it: it
                # flipped `cls` to marketing and changed NOTHING else — same `template_type`,
                # no `offer_value`, no expiry. So an ordinary service sentence went
                # out billed against the marketing share, counted against its cap, held by its
                # cooling rules — AND DROPPED ENTIRELY for everyone who never gave explicit
                # marketing consent. The second touch simply vanished, for most customers, and
                # nothing recorded that it had.
                #
                # Nothing in the product supplies a ladder offer today: offers are created by
                # campaigns and attached to the message that carries them. Until an owner can
                # set one, the rung is what its text actually is — a service reminder in a
                # different voice — and it reaches everybody rather than being charged to a
                # quota it does not use and refused for a consent it does not need.
                follow["cls"] = cls
                # THE TONE IS THE VARIATION. Same template type, a different voice — no new
                # template, no Meta review, and no crossing of the service/marketing wall.
                follow["tone_index"] = rung.tone_index
                follow["created"] = now
                follow["updated"] = now
                await self._sched.upsert(tenant, _key(follow), follow)
        except Exception:                                                   # noqa: BLE001
            # A LADDER THAT COULD NOT BE BUILT MUST NOT UNDO A MESSAGE THAT WENT. The reminder was
            # delivered and recorded; failing here would leave the tick raising after a successful
            # send, and the next pass would try to send it again.
            if self._t is not None:
                self._t.event("ladder_failed", tenant=tenant, service=row.get("service_id", ""))

    async def _close(self, tenant: str, row: dict[str, Any], state: str, reason: str,
                     now: int) -> None:
        row["state"] = state
        row["reason"] = reason
        row["updated"] = now
        await self._sched.upsert(tenant, _key(row), row)

    async def _defer_to_tomorrow(self, tenant: str, row: dict[str, Any], now: int,
                                 code: str) -> None:
        """Back to pending, tomorrow — not in an hour.

        The ceiling is a rolling 24-hour window, so a retry an hour from now walks into the same
        closed door and spends a tick doing it. The next morning is the first moment the answer
        can differ.

        THE IDEMPOTENCY KEY STAYS ON THE ROW. Tomorrow's attempt is the same message, and billing
        must count it once however many days it waits.
        """
        row["state"] = "pending"
        row["due_at"] = now + self._ceiling_defer
        row["reason"] = f"سقف واتساب اليومي ({code})"
        row["updated"] = now
        await self._sched.upsert(tenant, _key(row), row)

    async def _fail(self, tenant: str, row: dict[str, Any], error: str, now: int) -> None:
        """A row that threw goes back to pending with a short delay — a bounded number of times.

        Most failures here are a peer being briefly unavailable, and a schedule closed as `failed`
        is a reminder that silently never happens. So it retries on the next tick.

        BUT «MOST» IS NOT «ALL», AND THE REST USED TO RETRY FOR EVER. A number Meta refuses, a
        template rejected for this shop alone, a row whose data is malformed: the same inputs
        raise the same exception every hour until the shop closes. Nothing reached the send log,
        because as far as the log was concerned no attempt had been made; the row never left
        `pending`, so it appeared in no report; and one pass per hour was spent for as long as the
        establishment existed. The owner saw a customer who was never messaged and had nothing to
        ask about.

        The comfort this docstring used to offer — «a row that keeps failing shows up in the
        reason counts» — was about ONE tick's counts, which are not stored and which no screen
        reads. It was true and useless.

        SO THE ROW COUNTS ITS OWN TRIES, and when they run out it ends like every other refusal:
        a line in the send log carrying the last error, and a closed schedule. `MAX_ATTEMPTS`
        spans most of a day at one try an hour, which is far past any outage worth waiting
        through and far short of for ever.
        """
        attempts = int(row.get("attempts") or 0) + 1
        row["attempts"] = attempts
        if attempts >= MAX_ATTEMPTS:
            # GIVING UP IS AN ANSWER, AND IT IS RECORDED AS ONE. `suppressed` rather than a new
            # word, for the same reason every other refusal uses it: the log's vocabulary is what
            # every counter in the product reads.
            why = f"توقّفنا بعد {attempts} محاولات: {error}"
            await self._log.append(tenant, as_row(SendLog(
                tenant=tenant, subject_ref=row.get("subject_ref", ""),
                cls=row.get("cls", "service"), at=now, schedule_id=row.get("id", ""),
                branch_id=str(row.get("branch_id") or ""),
                outcome="suppressed", reason=why)))
            await self._close(tenant, row, "suppressed", why, now)
            return
        row["state"] = "pending"
        row["due_at"] = now + 3600
        row["reason"] = f"تعذّر الإرسال، سيُعاد: {error}"
        row["updated"] = now
        await self._sched.upsert(tenant, _key(row), row)


def _send_key(row: dict[str, Any]) -> str:
    """The idempotency key for ONE send occasion, derived rather than drawn (ز-2).

    THE KEY IS THE CROSSING GUARD, AND IT WAS ABSENT ON THE FIRST CROSSING. This line used to be
    `f"rem_{uuid.uuid4().hex}"`. A row that has never been sent carries no key, so two replicas
    winning the claim in the same second minted two different UUIDs — and the quota, the notifier
    and the send log all use the key to recognise a repeat. They saw two unrelated sends, because
    that is what they were handed. The customer read «حان موعد صيانتك» twice in the same minute
    and the shop was billed twice. A retry after a timeout was protected; the race never was.

    WHAT MAKES AN OCCASION. `_key(row)` names the reminder — tenant, customer, service, kind — and
    is stable for the row's whole life. `due_at` is what separates one send of it from the next:
    a deferral moves it, a follow-up rung sets a new one, and a recurring cycle earns its own.
    Two replicas racing over the SAME send agree on both, which is exactly the property the guard
    needs; a genuinely later send differs in `due_at` and correctly gets its own key.

    Hashed rather than concatenated only for length: a phone number and a service id inside a key
    that travels to Meta is more of the customer than the header needs to carry.
    """
    occasion = f"{_key(row)}|{int(row.get('due_at', 0))}"
    return "rem_" + hashlib.sha256(occasion.encode("utf-8")).hexdigest()[:32]


_key = key_of
