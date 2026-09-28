"""What the owner sees (spec §9.10) — and the one indicator that is a warning.

GRANTED VERSUS CONSUMED IS ALSO THE OUTSTANDING OBLIGATION. It reads as an engagement metric and it
is really a balance sheet line: everything granted and not yet spent is a promise the shop still
owes. That is why it is the first number rather than a footnote.

EXPIRED-UNREDEEMED IS THE WARNING ONE. A high figure does not mean customers are lazy; it means the
thresholds are out of their reach. The programme is then doing the opposite of its job — reminding
people of something they will never get. No other indicator here reveals that, because every other
one only counts what happened.

COMPUTED FROM THE LEDGER, never from a counter kept alongside it. A tally maintained on the side
would drift exactly like the materialised balance can, and unlike the balance it would have no
`reconcile` to catch it.
"""
from __future__ import annotations

from typing import Any

from app.adapters.datastore.drain import drain
from app.core.models import ENTRIES, REDEMPTIONS


# A TRUE FIX HERE IS AN INCREMENTAL AGGREGATE UPDATED WHERE `Ledger.post`/`Redeemer.redeem` WRITE,
# not a recompute on every report read. Deliberately left as a full read for now: doing it right
# means those write paths maintain a running tally alongside the ledger they already write, and a
# bug there would corrupt a number this same module exists to keep honest (see "COMPUTED FROM THE
# LEDGER, never from a counter kept alongside it" above) — not a change to make without touching
# `post`/`redeem`'s correctness-critical write paths, which was explicitly out of scope for this
# pass. Revisit if report reads become a measured hot path.
#
# BUT A SINGLE UNPAGED find() WAS A SEPARATE BUG, NOT THE SAME TRADE-OFF — fixed 2026-09-12 (a
# QA audit found it): `limit=100000` with the cursor discarded meant a tenant past 100k ledger
# rows got every number here silently computed from only the OLDEST 100k — granted, consumed,
# expired, outstanding, expired_share all wrong, with nothing saying so. `drain()` is the same
# primitive `Ledger.reconcile` already uses for exactly this collection, and it REFUSES rather
# than truncates once a tenant is too large to read at once — this module's own quoted worry
# ("a bug there would corrupt a number this module exists to keep honest") is exactly why an
# honest refusal beats a silently wrong report.
async def build(store: Any, tenant: str) -> dict:
    rows = await drain(store, ENTRIES, {"tenant": tenant}, sort=("created_at", "asc"))

    # ONE PASS, NOT FIVE. `rows` can be up to `limit` (100000) entries, and the four sums plus the
    # `customers` set below used to each walk the whole list separately — five full passes over
    # the same data for numbers a single running accumulation gives just as well.
    granted = consumed = expired = adjusted = 0
    customers: set[Any] = set()
    for r in rows:
        delta = int(r["delta"])
        reason = r.get("reason")
        if reason == "earn":
            granted += delta
        elif reason == "redeem":
            consumed -= delta
        elif reason == "expire":
            expired -= delta
        elif reason == "adjust":
            adjusted += delta
        customers.add(r.get("subject_ref"))

    reds = await drain(store, REDEMPTIONS, {"tenant": tenant}, sort=("created_at", "asc"))
    by_type: dict[str, int] = {}
    by_reward: dict[str, int] = {}
    for r in reds:
        by_type[r.get("reward_type", "")] = by_type.get(r.get("reward_type", ""), 0) + 1
        # By NAME as it was at the time, not by id: a reward renamed halfway through the year is
        # two names in the owner's history, and merging them under one id would hide a rename he
        # made deliberately.
        by_reward[r.get("reward_name", "")] = by_reward.get(r.get("reward_name", ""), 0) + 1

    return {
        # The obligation still standing. First, because it is the number with money behind it.
        "outstanding": granted - consumed - expired + adjusted,
        "granted": granted,
        "consumed": consumed,
        "expired_unredeemed": expired,
        # The warning: how much of everything granted died unspent. A high share means the
        # thresholds are beyond his customers' reach, and the programme is annoying them rather
        # than holding them.
        "expired_share": round(expired / (granted + max(adjusted, 0)), 3)
                        if (granted + max(adjusted, 0)) else 0.0,
        "redemptions": len(reds),
        "by_type": by_type,
        "top_rewards": sorted(by_reward.items(), key=lambda kv: -kv[1])[:5],
        "customers": len(customers),
    }
