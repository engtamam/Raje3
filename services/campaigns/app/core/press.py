"""One press of «أطلق» is one campaign, however many times the button is pressed.

THE DEFECT. `POST /campaigns` built `Campaign(...)` with a fresh id on every request and fired it
inline. Every protection against sending a person the same thing twice is keyed on `campaign_id` —
`campaign_reached` and the send idempotency key — so two presses produced two
campaigns that could not see each other, and three hundred customers received the same offer twice
while the shop paid twice against its cap.

And the button invites it. The send happens inside the request: a campaign to a large audience
takes seconds with no visible progress, so the owner presses again. That is not a mistake on their
part — it is the only feedback the screen gives them.

THE KEY IS WHAT THE OWNER CHOSE, NOT WHAT WE GENERATED. Goal, their own words, the service, the
branch, the offer and its end date: two requests carrying all of that identically inside one press
window are one press. Nothing here is derived from the attempt — not the time, not a uuid — because
the attempt is exactly what is uncertain.

CLAIMED BEFORE THE CAMPAIGN EXISTS. The claim is written first, so the second press finds it even
while the first is still sending.

FIXED 2026-09-07 TO ACTUALLY BE ATOMIC — this used to read that claim with a plain `store.get()`
and write it back with a plain `store.put()`, a real check-then-act race a QA audit caught (two
genuinely simultaneous presses both read "unclaimed" before either wrote). The datastore port has
ALWAYS exposed `store.claim()`, a real atomic take-if-unheld-or-expired primitive built for exactly
this ("the one operation put cannot express" — see `ports/datastore.py`'s own docstring); this
module simply never called it. Now it does, so the decision and the write are one statement at the
store layer, not two round trips an attacker's timing (or an owner's own double-tap) can land
between.

THE WINDOW IS TEN MINUTES. Long enough to cover a slow send, an owner reloading the page, and a
retry from a flaky connection; short enough that running the same campaign again tomorrow — which
is a real thing shops do — is a new campaign and not a silent no-op.
"""
from __future__ import annotations

import hashlib
from typing import Any

PRESSES = "campaign_presses"

# Covers a slow send and a reload; well short of «I meant to run it again».
WINDOW_SECONDS = 600


class Press:
    """What the claim found: either this press is new, or it already happened."""

    def __init__(self, key: str, *, first: bool, campaign_id: str = "", in_flight: bool = False):
        self.key = key
        self.first = first                  # nothing had claimed it — go ahead and create
        self.campaign_id = campaign_id      # the campaign the earlier press produced
        self.in_flight = in_flight          # claimed, but that campaign is not written yet


def key_for(tenant: str, *, goal: str, owner_text: str, service_id: str, branch_id: str,
            reward_kind: str, reward_amount: int, expires_at: int, fire_at: int,
            package_id: str = "", window_start_hour: int = 0, window_end_hour: int = 24,
            window_weekdays: list[int] | None = None, milestone_threshold: int = 0,
            milestone_recurring: bool = False, reward_type: str = "discount",
            reward_points: int = 0) -> str:
    """A stable name for one intention. Every part of it is something the owner typed or chose.

    `package_id` DEFAULTS EMPTY, NOT OMITTED — two DIFFERENT `package_offer` presses (different
    packages) that otherwise share every other field (same blank owner_text, same branch, same
    reward_kind/reward_amount/dates — a real, plausible shape: an owner running the same wording
    on two packages the same week) would collide onto ONE press key without it, and the second
    press would be silently returned as "the same campaign, already sent" instead of creating its
    own.

    `reward_kind`/`reward_amount` REPLACE THE OLD `offer_value` STRING (2026-10-04) — same role in
    this key, now two structured parts instead of one free-text one.

    `window_*` JOINED FOR THE SAME REASON (2026-09-12) — an owner who launches the same offer
    twice, once for the whole day and once narrowed to evening hours, is not repeating himself; a
    key blind to the window would tell him he already sent the one he had not.

    `milestone_threshold` JOINED FOR THE SAME REASON (2026-09-27, "جماعي" goals) — a "100 عملاء"
    milestone and a "500 عملاء" one, launched back to back with every other field identical (blank
    owner_text, no branch, no window), are two different campaigns, not a retry of one.
    """
    raw = "|".join([tenant, goal, owner_text.strip(), service_id.strip(), branch_id.strip(),
                    reward_kind.strip(), str(int(reward_amount or 0)), str(int(expires_at or 0)),
                    str(int(fire_at or 0)), package_id.strip(), str(int(window_start_hour or 0)),
                    str(int(window_end_hour if window_end_hour is not None else 24)),
                    ",".join(str(w) for w in sorted(window_weekdays or [])),
                    str(int(milestone_threshold or 0)), "1" if milestone_recurring else "0",
                    reward_type.strip(), str(int(reward_points or 0))])
    return "prs_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


async def claim(store: Any, tenant: str, key: str, *, now: int) -> Press:
    """Take the press, or report who took it. Written BEFORE the campaign, deliberately.

    Routed through `store.claim()` (see the module docstring above) — `ttl_seconds=WINDOW_SECONDS`
    reproduces the old "still within the window" test exactly, but as one atomic store operation:
    unclaimed-or-expired takes it and returns `first=True`; held-and-fresh loses, and this then
    reads the row to report what the winner is doing (`settle()` below keeps the claim alive with
    its own fresh `expires`, so a second press within the window always finds it held, whether the
    first press is still sending or already settled)."""
    took = await store.claim(
        PRESSES, key, {"id": key, "tenant": tenant, "at": now, "campaign_id": ""},
        ttl_seconds=WINDOW_SECONDS, now=now)
    if took:
        return Press(key, first=True)

    row = await store.get(PRESSES, key) or {}
    cid = str(row.get("campaign_id") or "")
    return Press(key, first=False, campaign_id=cid, in_flight=not cid)


async def settle(store: Any, tenant: str, key: str, campaign_id: str, *, now: int) -> None:
    """Name the campaign the claim produced, so a later press can return it rather than refuse.

    Carries its own fresh `expires` (mirroring `claim()`'s), NOT dropped — without it, the very
    next press right after settling would find no `expires` field, read as an already-expired
    claim, and win a brand-new claim of its own: the exact double-campaign bug this whole module
    exists to prevent, just moved one step later."""
    await store.put(PRESSES, key, {"id": key, "tenant": tenant, "at": now,
                                   "campaign_id": campaign_id, "expires": now + WINDOW_SECONDS})
