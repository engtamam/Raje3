"""Assembling the page from three services that may not all be there.

THE PAGE IS A COMPOSITION, and that is its whole risk. The shop's identity comes from
tenant-service, the visits from operations, the preferences from reminders. Any of the three can be
slow, restarting, or rolling out — and the customer opening the link knows none of that. They know
the shop sent them a link and the link is broken.

SO NOTHING HERE IS ALLOWED TO FAIL THE PAGE.

  identity missing   -> the page still renders, with the shop's name absent rather than the page
                        absent. This is the only section whose loss is visible as a gap, and even
                        then a page saying nothing is better than a 500 that says the shop is
                        broken.
  visits missing     -> a quiet line saying the history could not be loaded. The switches still
                        work, which is what most people opened the link for anyway.
  preferences missing-> the switches say so honestly and render read-only. Showing them as
                        togglable and then failing the save is worse than admitting it up front.

A DEADLINE FOR THE WHOLE PAGE, NOT PER CALL. Three calls with a five-second timeout each is a
fifteen-second page, which is a page nobody sees. The budget belongs to the person waiting, so the
sections race a single clock and whatever has not arrived when it runs out is simply absent.

AND THEY RUN CONCURRENTLY. Sequentially, the slowest peer sets the floor for the page; in parallel
it sets the ceiling. Same three calls, a third of the wait.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

# The five classes, in the order a customer should see them: what they are most likely to want
# kept, first. Not the regulatory order — that one is ours, and this list is theirs.
CLASS_ORDER = ("service", "personal", "awareness", "warning", "marketing")

LABELS = {
    "service": "رسائل الخدمة",
    "personal": "رسائل تخصّك",
    "awareness": "نصائح ومعلومات",
    "warning": "تنبيهات السلامة",
    "marketing": "العروض والخصومات",
}

HINTS = {
    "service": "تأكيد زيارتك، والتذكير بموعد صيانتك القادم.",
    "personal": "رصيد نقاطك وإشعارات حسابك.",
    "awareness": "نصيحة تخصّ ما تستخدمه، مرة في الشهر على الأكثر.",
    "warning": "تنبيه يخصّ سلامتك أو ما تملكه. نادر.",
    "marketing": "العروض الجديدة. أربع رسائل شهرياً على الأكثر.",
}


@dataclass
class Section:
    """One part of the page, and whether it is really there.

    `available` is separate from emptiness on purpose: "you have no visits yet" and "we could not
    load your visits" are different sentences, and showing the first when the second is true is a
    lie the customer has no way to detect.

    AND `failed` IS SEPARATE FROM BOTH. `available=False` was carrying two meanings at once —
    «this shop runs no such thing», which is a fact and renders nothing, and «the read threw»,
    which is ours and must say so. The renderer could only see one of them, so a failed offers
    read produced the same page as a customer who was simply never sent an offer: he opened a link
    from a message that promised him something, found no offer on it, and concluded the message
    was not real.
    """
    available: bool = False
    data: Any = None
    #: The read raised or the peer refused. Never true for a shop that just has none of these.
    failed: bool = False


@dataclass
class Page:
    reference: str
    tenant: str
    shop_name: str = ""
    brand_colour: str = ""
    visits: Section = field(default_factory=Section)
    prefs: Section = field(default_factory=Section)
    # HIS OFFERS — the reason most people open this link at all.
    #
    # It is a section like the others, which means it CANNOT fail the page: a customer who came to
    # read an offer and found a 500 concludes the shop's message was a trick. An unavailable offers
    # section says so; it does not pretend he has none.
    offers: Section = field(default_factory=Section)
    # HIS POINTS — the one number he cannot get anywhere else.
    #
    # A balance he never sees does not bring him back, and a reward he does not know he can afford
    # is never asked for. Absent entirely for a shop without the loyalty feature: an empty points
    # box on a customer's page is a shop advertising something it does not run.
    points: Section = field(default_factory=Section)

    @property
    def has_identity(self) -> bool:
        return bool(self.shop_name.strip())


class Composer:
    def __init__(self, *, identity, operations, reminders, loyalty=None,
                 deadline_seconds: float = 3.0) -> None:
        self._identity = identity
        self._operations = operations
        self._reminders = reminders
        # OPTIONAL. A deployment without loyalty composes a page with four sections rather than
        # failing — the same rule every other peer here follows.
        self._loyalty = loyalty
        self._deadline = deadline_seconds

    async def build(self, tenant: str, subject_ref: str) -> Page:
        """Fetch all three concurrently, under one clock. NEVER RAISES."""
        page = Page(reference=f"{tenant}.{subject_ref}", tenant=tenant)

        async def _identity():
            return await self._identity.get(tenant)

        async def _visits():
            return await self._operations.visits_for(tenant, subject_ref)

        async def _prefs():
            return await self._reminders.prefs_for(tenant, subject_ref)

        async def _offers():
            return await self._reminders.offers_for(tenant, subject_ref)

        async def _points():
            if self._loyalty is None:
                return None
            return await self._loyalty.balance_for(tenant, subject_ref)

        # `gather` with return_exceptions, then a single wait_for around the lot. A per-call
        # timeout would let slow peers add up; this way the page is late once, at most.
        try:
            results = await asyncio.wait_for(
                asyncio.gather(_identity(), _visits(), _prefs(), _offers(), _points(),
                               return_exceptions=True),
                timeout=self._deadline)
        except asyncio.TimeoutError:
            # Everything missed the clock. The page still renders — a shell with no shop name and
            # two unavailable sections is a page that says "we could not load this right now",
            # which is honest, and it is not a 500 that says the shop is broken.
            return page

        ident, visits, prefs, offers, points = results

        if not isinstance(ident, BaseException) and ident is not None:
            page.shop_name = getattr(ident, "name", "") or ""
            page.brand_colour = (getattr(ident, "branding", {}) or {}).get("accent", "")

        if not isinstance(visits, BaseException) and visits is not None:
            page.visits = Section(available=True, data=list(visits))

        if not isinstance(prefs, BaseException) and prefs is not None:
            page.prefs = Section(available=True, data=_normalise_prefs(prefs))

        if not isinstance(offers, BaseException) and offers is not None:
            page.offers = Section(available=True, data=_normalise_offers(offers))
        elif isinstance(offers, BaseException):
            # OURS, AND THE PAGE SAYS SO. Silence here reads to him as «the offer was a trick».
            page.offers = Section(available=False, failed=True)

        # A SHOP WITHOUT REWARDS IS NOT AN OUTAGE. `to_next_reward` is 0 and the list is empty for
        # a shop that runs no programme; the section stays unavailable so the page renders nothing
        # rather than a balance of zero nobody can spend.
        if not isinstance(points, BaseException) and isinstance(points, dict) and points:
            page.points = Section(available=True, data=points)

        return page


def _normalise_offers(raw: Any) -> list[dict[str, Any]]:
    """His live offers, newest first, with nothing expired among them.

    FILTERED HERE AS WELL AS AT THE PEER. The peer already drops expired ones, and this drops them
    again — not from distrust but because of WHEN this page is read: a link sits in a chat for
    days, and the second reading can fall on the other side of an expiry the first did not.

    THE END TIME TRAVELS, NEVER A DURATION. "Three days left" computed here would be wrong by the
    time it is rendered and frozen wrong for as long as the page is open; the countdown needs the
    moment itself.
    """
    import time as _time

    rows = raw.get("offers") if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        return []
    now = int(_time.time())
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        text = str(r.get("text") or "").strip()
        expires = int(r.get("expires_at") or 0)
        # An offer with no end is not an offer: nothing can count down to a deadline that does not
        # exist, and a discount with no end is a price change nobody decided on.
        if not text or not expires or expires <= now:
            continue
        out.append({"text": text, "expires_at": expires,
                    "sent_at": int(r.get("sent_at") or 0),
                    # Which services it covers. Empty means the whole shop, which is a real answer
                    # and not a missing one — the page says so in words rather than showing a gap.
                    "services": [str(s) for s in (r.get("services") or []) if s],
                    # SCOPED BUT UNNAMEABLE IS ITS OWN ANSWER. Empty services used to mean «the
                    # whole shop», and the page said so — which turned an offer on one service
                    # into a promise covering everything the moment the names were missing.
                    "scoped": bool(r.get("scoped")),
                    # THE CODE HE READS OUT AT THE COUNTER. It is the only handle the till has on
                    # this offer, and a customer holding an offer he cannot name is a customer
                    # arguing with an operator who has nothing to check.
                    "code": str(r.get("code") or "")})
    return sorted(out, key=lambda o: o["expires_at"])


def _normalise_prefs(raw: Any) -> list[dict[str, Any]]:
    """The five switches in the customer's order, whatever shape the peer returned.

    Defensive because this is rendered without a schema check on the other side: a peer that grows
    a sixth class must not put an unlabelled toggle on a customer's page, and one that drops a
    class must not make a switch disappear from under someone who was about to press it.
    """
    stopped: dict[str, bool] = {}
    if isinstance(raw, dict):
        stopped = raw.get("stopped") or {}
        if not stopped and isinstance(raw.get("preferences"), list):
            stopped = {p.get("class"): not p.get("enabled", True)
                       for p in raw["preferences"] if isinstance(p, dict) and p.get("class")}
    elif isinstance(raw, list):
        stopped = {p.get("class"): not p.get("enabled", True)
                   for p in raw if isinstance(p, dict) and p.get("class")}
    return [{"class": c, "label": LABELS[c], "hint": HINTS[c],
             "enabled": not bool(stopped.get(c, False))} for c in CLASS_ORDER]
