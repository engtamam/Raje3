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

import uuid
from dataclasses import dataclass, field
from typing import Any

from app.core import engagement as E
from app.core import gate as G
from app.core import quota as Q
from app.core import ceiling as C
from app.core import coupons as COUPONS
from app.core import ladder as L
from app.core import reasons as TR
from app.core import merge as M
from app.core import ceiling_notice as CN
from app.core.reach import Reach

# How long a message waits after WhatsApp refused it for the ceiling. A DEFAULT: the right delay
# depends on when in the rolling window the refusal happened, and the only wrong answer is "an
# hour", which walks back into the same closed door. Deployments set CEILING_DEFER_SECONDS.
_DEFAULT_CEILING_DEFER = 12 * 3600
from app.core import rendering as R
from app.core.models import SendLog, as_row
from app.adapters.message_sender import CeilingReached, Unsendable
from app.core.consent import Consent
from app.core.stores import (EngagementStore, PrefsStore, RuleStore, ScheduleStore,
                             SendLogStore)


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

    def known(self) -> bool:
        return self.left >= 0

    def take(self) -> bool:
        """Spend one slot. False when there is none left."""
        if not self.known():
            return True
        if self.left <= 0:
            return False
        self.left -= 1
        return True


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


class Tick:
    def __init__(self, *, store, sender, limits: G.Limits, eng_cfg: E.EngagementConfig,
                 batch: int = 100, telemetry=None, quota=None, approved=None,
                 reach_window: int = 0, ceiling_defer_seconds: int = 0, ceiling=None,
                 holdout_enabled: bool = False, holdout_share: int = 10) -> None:
        self._store = store
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

    async def run(self, tenant: str, *, now: int, library: list[dict[str, Any]],
                  service_names: dict[str, str], establishment: str,
                  customer_names: dict[str, str] | None = None,
                  tone: str = "brief", choices: Any = None) -> TickResult:
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
        # The reach window is only meaningful for a day, and a table nobody prunes turns a bounded
        # read into an unbounded one — the exact failure the read exists to avoid.
        if due:
            await self._reach.prune(now=now)

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
                                tone=tone, approved=approved, room=room, choices=choices)
            except Unsendable as exc:
                # PERMANENT, not transient. There is nobody to send to — erased, or never there.
                # Retrying would ask operations about a forgotten customer on every tick forever,
                # which is both useless and the opposite of what they asked for.
                await self._close(tenant, row, "suppressed", f"لا يوجد مستقبِل: {exc}", now)
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
                       establishment: str, tone: str = "brief",
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
        # READ ONLY FOR MARKETING. Every other class is allowed without a grant, so asking the
        # store on every service reminder would be a read per message for an answer nobody uses.
        consent = (await self._consent.state(tenant, subject)) if cls == "marketing"             else "never_asked"
        decision = G.evaluate(
            cls=cls, template_type=row.get("template_type", ""), now=now, limits=self._limits,
            prefs_stopped=prefs.get("stopped") or {},
            engagement_score=float(eng.get("score") or 0.0),
            engagement_at=int(eng.get("scored_at") or 0),
            recent_sends=recent, eng_cfg=self._eng_cfg,
            marketing_consent=consent,
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
            template = R.choose(template_type=row.get("template_type", ""), tone=tone,
                                library=library, approved=approved,
                                own=_own_template(choices, ids))
            # SLOT BY SLOT, FROM THE TEMPLATE'S OWN DECLARATION. The previous version put the
            # owner's single sentence into slots 3 AND 4 through all three source dicts, so a
            # four-variable template said the same thing twice; and it passed slot 1 empty, which
            # greeted every customer «عميلنا العزيز» although we hold their names. A typed slot
            # (a discount, a coupon code, an end date) had no value to take at all.
            # THE COUPON, DERIVED HERE AND NOWHERE ELSE. Same send, same code — a retry after a
            # timeout must not hand the customer a second one, and a random code would need a
            # write on the send path for no gain.
            coupon = (COUPONS.code_for(str(row.get("idempotency_key") or ""))
                      if int(row.get("offer_expires_at") or 0) else "")
            values = R.campaign_slots(
                template,
                establishment=establishment,
                owner_text=row.get("owner_text", ""),
                service_text=R.merged_service_text(
                    [service_names.get(s, s) for s in (row.get("offer_services") or [])]),
                offer_value=str(row.get("offer_value", "")),
                coupon_code=coupon,
                expires_at=int(row.get("offer_expires_at") or 0))
            # ONE DICT, PASSED AS ALL THREE. `campaign_slots` has already answered per source, so
            # handing the renderer three different maps would be deciding the same thing twice and
            # inviting them to disagree.
            rendered = R.render(template=template, system=values, catalogue=values, owner=values)
        except R.RenderError as exc:
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
            await self._sender.send(
                tenant=tenant, subject_ref=subject, template_name=rendered.template_name,
                variables=rendered.variables, cls=cls, idempotency_key=key,
                # WHICH NUMBER IT LEAVES FROM. The schedule already carries the branch the visit
                # happened at; this is the one line that turns it into the credentials the message
                # is actually sent with. `""` — every shop in the default mode — resolves to the
                # establishment inside the sender, exactly as before.
                sending_identity=_sending_identity(tenant, row))
        except Unsendable as exc:
            # GIVE THE UNIT BACK. The consume had to come first to be atomic, so a send that did
            # not happen leaves a unit spent — and an erased recipient is not something the shop
            # should pay for.
            await self._quota.release(tenant=tenant, idempotency_key=key)
            return {"sent": False, "reason": f"لا يوجد مستقبِل: {exc}"}
        except CeilingReached as exc:
            # A campaign message is always deferrable — see the 8.4.3 table, where every mkt_* is
            # `defer`. It goes when the ceiling opens; nobody is waiting for an offer.
            await self._quota.release(tenant=tenant, idempotency_key=key)
            return {"sent": False, "reason": f"سقف واتساب اليومي ({exc.code}) — سترسل تلقائياً"}
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
            outcome="sent", idempotency_key=key,
            offer_text=row.get("offer_text", ""),
            offer_expires_at=int(row.get("offer_expires_at") or 0),
            offer_services=list(row.get("offer_services") or []),
            # RECORDED WITH THE OFFER IT BELONGS TO. The customer will read it back to an operator
            # who has to find this row from that string alone.
            offer_code=coupon)))
        return {"sent": True, "reason": ""}

    async def _one(self, tenant: str, row: dict[str, Any], *, now: int, res: TickResult,
                   library: list[dict[str, Any]], service_names: dict[str, str],
                   establishment: str, customer_name: str, tone: str,
                   approved: set[str] | None = None, room: Room | None = None,
                   choices: Any = None) -> None:
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
            await self._close(tenant, row, "suppressed", "أوقفتَ هذا النوع من الرسائل", now)
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
        # READ ONLY FOR MARKETING. Every other class is allowed without a grant, so asking the
        # store on every service reminder would be a read per message for an answer nobody uses.
        consent = (await self._consent.state(tenant, subject)) if cls == "marketing"             else "never_asked"
        decision = G.evaluate(
            cls=cls, template_type=row.get("template_type", ""), now=now, limits=self._limits,
            prefs_stopped=prefs.get("stopped") or {},
            engagement_score=float(eng.get("score") or 0.0),
            engagement_at=int(eng.get("scored_at") or 0),
            recent_sends=recent, eng_cfg=self._eng_cfg,
            marketing_consent=consent,
            tenant=tenant, subject_ref=subject,
            holdout_enabled=self._holdout_enabled, holdout_share=self._holdout_share,
            class_enabled=any(t.get("type") == row.get("template_type") for t in library))

        if not decision.allowed:
            if decision.retry_at:
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
                policy = ""
                for t in library:
                    if t.get("type") == row.get("template_type"):
                        policy = str(t.get("deferral") or "defer")
                        break
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
        template = R.choose(template_type=row.get("template_type", ""), tone=tone,
                            library=library, approved=approved,
                            # HIS OWN TEXT ON THIS PATH TOO. Two render sites is two chances to
                            # wire one of them and believe the feature works: an owner who
                            # customised his visit confirmation would see it on some messages and
                            # ours on others, which reads as a product that cannot make up its mind.
                            own=_own_template(choices, [reason] if reason else []))
        service_text = R.merged_service_text(
            [service_names.get(s, s) for s in
             [row.get("service_id", "")] + list(row.get("also_services") or [])])
        # THE REDEMPTION, IF ONE JOINED THIS MESSAGE (§9.6). A confirmation waits ten minutes on
        # purpose, and that is exactly the window in which a redemption happens at the counter —
        # so it rides along instead of becoming a second message. Slots 3, 4 and 5 of
        # `svc_visit_redeemed`: what he took, what it cost, what is left.
        #
        # 3 AND 4 ARE SHARED SLOTS. On every other template they hold the service text; on this
        # one the reward's name and its cost. Same numbering, different template — which is the
        # whole reason this is a template VARIANT rather than an optional sentence: WhatsApp has
        # no optional part, and a visit without a redemption has nothing true to put in them.
        redeemed = row.get("redeemed_name", "")
        rendered = R.render(
            template=template,
            system={"1": customer_name, "2": establishment,
                    "3": redeemed or service_text,
                    "4": str(row.get("redeemed_cost", "")) if redeemed else service_text,
                    "5": str(row.get("redeemed_remaining", ""))},
            catalogue={"3": service_text, "4": service_text},
            owner={"3": row.get("owner_text", ""), "4": row.get("owner_text", "")})

        # ── 4. send ───────────────────────────────────────────────────────────────────────────
        # The key is generated and stored BEFORE the call and reused on every retry: a timeout is
        # not evidence that nothing was sent, and the customer must not pay for our uncertainty.
        key = row.get("idempotency_key") or f"rem_{uuid.uuid4().hex}"
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

        try:
            await self._sender.send(
                tenant=tenant, subject_ref=subject, template_name=rendered.template_name,
                variables=rendered.variables, cls=cls, idempotency_key=key,
                # WHICH NUMBER IT LEAVES FROM. The schedule already carries the branch the visit
                # happened at; this is the one line that turns it into the credentials the message
                # is actually sent with. `""` — every shop in the default mode — resolves to the
                # establishment inside the sender, exactly as before.
                sending_identity=_sending_identity(tenant, row))
        except CeilingReached as exc:
            # WHATSAPP WILL NOT TAKE ANOTHER MESSAGE FROM THIS SHOP RIGHT NOW (spec §8.4.3).
            # Nothing left, so nothing is counted — and what happens next is the TEMPLATE's
            # decision, carried on the template itself rather than decided here.
            await self._quota.release(tenant=tenant, idempotency_key=key)
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
        await self._reach.record(tenant, subject, now=now)
        await self._log.append(tenant, as_row(SendLog(
            tenant=tenant, subject_ref=subject, cls=cls, at=now,
            schedule_id=row.get("id", ""), branch_id=str(row.get("branch_id") or ""), template_name=rendered.template_name,
            outcome="sent", idempotency_key=key)))
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

        Read-then-write rather than a compare-and-set: the DataStore port has no CAS, and adding
        one would be a change to base-services. The window is small and the consequence of losing
        the race is bounded by the idempotency key at the sender — which is the belt this braces.
        """
        fresh = await self._sched.get(_key(row))
        if fresh is None or fresh.get("state") != "pending":
            return False
        fresh["state"] = "sending"
        fresh["updated"] = now
        await self._sched.upsert(tenant, _key(fresh), fresh)
        row.update(fresh)
        return True

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
                follow["cls"] = "marketing" if rung.marketing else cls
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
        """A row that threw goes back to pending with a short delay, not to a dead state.

        Most failures here are a peer being briefly unavailable, and a schedule closed as `failed`
        is a reminder that silently never happens. It retries on the next tick; a row that keeps
        failing shows up in the reason counts, which is where an operator will actually see it.
        """
        row["state"] = "pending"
        row["due_at"] = now + 3600
        row["reason"] = f"تعذّر الإرسال، سيُعاد: {error}"
        row["updated"] = now
        await self._sched.upsert(tenant, _key(row), row)


def _key(row: dict[str, Any]) -> str:
    return (f"{row.get('tenant','')}|{row.get('subject_ref','')}|"
            f"{row.get('service_id','')}|{row.get('kind','')}")
