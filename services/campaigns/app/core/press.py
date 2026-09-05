"""One press of «أطلق» is one campaign, however many times the button is pressed.

THE DEFECT. `POST /campaigns` built `Campaign(...)` with a fresh id on every request and fired it
inline. Every protection against sending a person the same thing twice is keyed on `campaign_id` —
`campaign_reached`, the send idempotency key, the awareness lock — so two presses produced two
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
while the first is still sending. That narrows the race from «the whole duration of the send» —
seconds, and the actual window an owner presses in — to the gap between one read and one write.
It does not eliminate it, and pretending otherwise would be the more dangerous claim: a datastore
with a compare-and-set would, and this one does not have one.

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
            offer_value: str, expires_at: int, fire_at: int, package_id: str = "") -> str:
    """A stable name for one intention. Every part of it is something the owner typed or chose.

    `package_id` DEFAULTS EMPTY, NOT OMITTED — two DIFFERENT `package_offer` presses (different
    packages) that otherwise share every other field (same blank owner_text, same branch, same
    offer_value/dates — a real, plausible shape: an owner running the same wording on two
    packages the same week) would collide onto ONE press key without it, and the second press
    would be silently returned as "the same campaign, already sent" instead of creating its own.
    """
    raw = "|".join([tenant, goal, owner_text.strip(), service_id.strip(), branch_id.strip(),
                    offer_value.strip(), str(int(expires_at or 0)), str(int(fire_at or 0)),
                    package_id.strip()])
    return "prs_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


async def claim(store: Any, tenant: str, key: str, *, now: int) -> Press:
    """Take the press, or report who took it. Written BEFORE the campaign, deliberately."""
    row = await store.get(PRESSES, key)
    if row and int(row.get("at") or 0) > now - WINDOW_SECONDS:
        cid = str(row.get("campaign_id") or "")
        return Press(key, first=False, campaign_id=cid, in_flight=not cid)

    await store.put(PRESSES, key, {"id": key, "tenant": tenant, "at": now, "campaign_id": ""})
    return Press(key, first=True)


async def settle(store: Any, tenant: str, key: str, campaign_id: str, *, now: int) -> None:
    """Name the campaign the claim produced, so a later press can return it rather than refuse."""
    await store.put(PRESSES, key, {"id": key, "tenant": tenant, "at": now,
                                   "campaign_id": campaign_id})
