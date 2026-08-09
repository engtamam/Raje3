"""When to tell an owner his trial is ending — and when to say nothing.

THE WHOLE POINT IS THAT HE CAN STILL ACT. A notice on the morning everything stopped is not a
warning, it is an apology; and one sent every day for a fortnight is a notice he mutes and then
misses the day it mattered.

────────────────────────────────────────────────────────────────────────────────────────────────
FALLING INTERVALS, NOT A SINGLE SHOT AND NOT A DRIP

    7 days out    there is time to decide, and to talk to whoever pays
    3 days out    close enough to act on
    1 day out     the last honest moment

Three notices over fourteen days. One notice a week out is read on a Tuesday and forgotten by the
Sunday it matters; a daily countdown is noise, and noise is what he silences.

EACH MILESTONE FIRES AT MOST ONCE, EVER. Not once per day — once. A cron that runs hourly, or that
is re-run after a failure, or that is deployed twice, must not produce three messages for the same
milestone. So what is recorded is the milestone reached, not the last time we sent something.

AND A MISSED MILESTONE IS NOT REPLAYED. If the cron was down for four days and he is now 2 days
out, he gets the 3-day notice and never the 7-day one — sending "your trial ends in 7 days" to
somebody with 2 left is worse than silence, because it is wrong in the direction that costs him
the decision.

────────────────────────────────────────────────────────────────────────────────────────────────
IT IS AN ACCOUNT FACT, NOT AN OFFER

The template is `per_account_notice` — personal class. An establishment's mandatory notices have
no off switch, because silencing them is silencing an outage that stops his shop (spec §8.4.2),
and that is the same argument that stops a customer silencing a service message.

WHICH MEANS THE TEXT MUST EARN IT. The moment it names a price or says "upgrade now", it is
MARKETING by its text (§8.4.1) — and then a notice about his own subscription sits behind quiet
hours, a monthly cap, and a consent he never thought to give himself. So: the date, the fact, and
where to go. No price, no plan name, no invitation.

────────────────────────────────────────────────────────────────────────────────────────────────
WHERE THE DATE COMES FROM, AND WHY NOT FROM BILLING

billing-service exposes no internal route carrying `trial_end`, and no way to list trialing
subscriptions: the internal surface is entitlements and usage. The user-tier list needs a signed
JWT, and a service cannot mint one without the signing key that must stay in identity-service.

So we do not read it — we RECORD it, at the moment our own subscribe path creates the
subscription and sees `trial_end` in the response. That is not a second copy of billing's state
pretending to be authoritative: billing remains the only thing that decides what he is entitled
to. This is a note of an event we witnessed, kept so we can schedule a message about it. If the
two ever disagree, the consequence is a notice at a slightly wrong hour — never an entitlement.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

TRIALS = "trial_watch"

# The service-class template that already exists. No new template is needed for this.
TEMPLATE = "per_account_notice"

DAY = 86400

# Falling, not uniform. Each is a milestone that fires once.
MILESTONES = (7, 3, 1)


def _now() -> int:
    return int(time.time())


@dataclass
class TrialWatch:
    """What we recorded when the subscription was created, plus what we have already said."""

    tenant: str
    trial_end: int
    subscription_id: str = ""
    # The milestones already sent, as days-out integers. A SET rather than a timestamp, because
    # the question is "have we said this one" and not "when did we last say something".
    sent: list[int] = field(default_factory=list)
    created: int = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.tenant, "tenant": self.tenant, "trial_end": self.trial_end,
                "subscription_id": self.subscription_id, "sent": sorted(self.sent),
                "created": self.created}


def due_milestone(trial_end: int, now: int, sent: list[int] | set[int]) -> int | None:
    """Which milestone to send RIGHT NOW, or None.

    Returns the closest milestone he has reached and not yet been told about. `None` covers every
    quiet case: too early, already told, and the trial already over.
    """
    remaining = trial_end - now
    if remaining <= 0:
        # OVER. The stop speaks for itself, and a warning about a thing that already happened
        # reads as a system that has not noticed.
        return None
    already = {int(m) for m in (sent or ())}
    days_left = remaining / DAY

    # A MILESTONE ALREADY SENT RETIRES EVERY LARGER ONE, PERMANENTLY. Without this the first
    # version, asked about a shop with 2 days left that had already had its 3-day notice, answered
    # SEVEN — because 2 <= 7 and 7 had not been sent. It would have told a customer with two days
    # remaining that his trial ends in a week, which is wrong in the direction that costs him the
    # decision. Caught by the test for the missed-milestone case, which is the same shape.
    ceiling = min(already) if already else None

    # Smallest first: at 2.5 days out he is owed the 3-day notice, not the 7-day one. A milestone
    # he passed while the cron was down is skipped rather than replayed.
    for milestone in sorted(MILESTONES):
        if milestone in already:
            continue
        if ceiling is not None and milestone >= ceiling:
            continue
        if days_left <= milestone:
            return milestone
    return None


def text(days: int, shop: str, ends_on: str) -> str:
    """The sentence. A fact about his account with a date and a destination — nothing else.

    NO PRICE AND NO PLAN NAME, and that is a constraint rather than a preference: this template is
    personal-class and unsilenceable, and the thing that decides a message's class is its TEXT.
    """
    if days == 1:
        when = "غداً"
    else:
        when = f"بعد {days} أيام"
    return (f"تنتهي فترة تجربتك في {shop} {when} ({ends_on}). "
            f"يمكنك تفعيل اشتراكك من لوحة التحكم لتستمر رسائلك بلا انقطاع.")


class TrialWatchStore:
    """Append-and-update, one row per tenant. Keyed by tenant because a shop has one trial."""

    def __init__(self, store: Any) -> None:
        self._s = store

    async def put(self, watch: TrialWatch) -> TrialWatch:
        await self._s.put(TRIALS, watch.tenant, watch.to_dict())
        return watch

    async def get(self, tenant: str) -> dict | None:
        return await self._s.get(TRIALS, tenant)

    async def due(self, *, now: int, limit: int = 500) -> list[tuple[dict, int]]:
        """Every tenant owed a notice right now, with the milestone owed.

        Bounded. An unbounded scan is a cron that gets slower every month until it stops finishing.
        """
        # scan_all, not find({}): the DataStore port REFUSES an empty `where` on find, deliberately
        # — an unfiltered find is a full table read wearing the shape of a query. This is a sweeper
        # and says so.
        rows = await self._s.scan_all(TRIALS, limit)
        out: list[tuple[dict, int]] = []
        for row in rows or []:
            milestone = due_milestone(int(row.get("trial_end") or 0), now, row.get("sent") or [])
            if milestone is not None:
                out.append((row, milestone))
        return out

    async def mark_sent(self, tenant: str, milestone: int) -> None:
        """Record the milestone BEFORE the send is attempted is wrong, and after it is right.

        A crash between the two sends one notice twice, which is survivable. Marking first and
        crashing sends nothing at all and records that we did — which is the failure nobody finds,
        because the row says the customer was told.
        """
        row = await self._s.get(TRIALS, tenant)
        if row is None:
            return
        sent = set(row.get("sent") or [])
        sent.add(int(milestone))
        row["sent"] = sorted(sent)
        await self._s.put(TRIALS, tenant, row)
