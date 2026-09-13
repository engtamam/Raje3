"""The follow-up ladder — what happens when he does not come at his time (spec §5.6.1).

ONE REMINDER IS NOT ENOUGH AND THREE IS NAGGING. So the ladder is two or three rungs depending on
what the customer has consented to, and then it STOPS. A ladder with no end is how a WhatsApp
number gets blocked, and a blocked number does not lose the last message — it loses the channel,
for every customer of that shop, for ever.

VARIATION, NOT ESCALATION — and this is the decision the whole file turns on.

    without marketing consent          with marketing consent
    ------------------------------     ------------------------------
    reminder                           reminder
    a second reminder, WORDED ANEW     an OFFER
    stop                               a third reminder

THE WORDING NO LONGER CHANGES BY SWITCHING TONE. The library used to carry three formality TONES
for every type (brief, warm, formal) and a rung could ask for a different one — safe, because all
three addressed the same customer the same grammatical way. The library now carries two tones
(masculine, feminine), and they are not a formality ladder: they differ in WHO is grammatically
addressed — masculine vs. feminine — so hopping to the other one mid-ladder would mean a shop that
picked «masculine» suddenly addressing its own customer as a woman on the second message. That is worse
than repetition. So every rung now stays on the shop's OWN chosen tone (`tone_index=1`); a repeated
sentence costs nothing this file was built to prevent, but a misgendered one costs the customer's
trust.

AND WHOEVER DID NOT CONSENT TO MARKETING IS REMINDED TWICE AND LEFT. No offer reaches him under
any circumstances (§8.5); the ladder loses a rung rather than breaking.

THE DELAY COMES FROM HIS OWN CYCLE. 15% of the LEARNED interval between rungs, never a fixed number
of days: fifteen percent of ninety days is not fifteen percent of ten, and a fixed delay makes a car
wash nag and a workshop forget.

THE LOCK THAT PROTECTS THE SHOP'S MARGIN — the most important rule here.

A customer who came back on the FIRST reminder twice has his ladder locked at rung one and never
sees an offer. A discount that reaches whoever is late teaches the pattern inside two cycles, and
he starts being late on purpose: the algorithm burns margin while "working perfectly", the shop
sees more returns and less profit, and nothing connects the two. The offer is for whoever does not
come back without one — not for whoever comes back anyway.

THE DORMANT ARE LEFT AT RUNG ONE. Engagement decides: pressing somebody who does not read us is
pure annoyance with nothing on the other side.

AND EVERY RUNG GOES THROUGH THE GATE LIKE ANY OTHER MESSAGE — the 20-hour gap, the daily cap, the
merge across visits (§5.8.1), the quiet hours. THE LADDER PROPOSES; THE GATE DECIDES. Nothing here
sends anything, which is why this file is pure arithmetic and can be read in one sitting.
"""
from __future__ import annotations

from dataclasses import dataclass

DAY = 86400

# The share of the customer's own learned cycle that separates two rungs (§5.6.1).
STEP_SHARE = 0.15

# Never less than this between two rungs, whatever the cycle says. A three-day cycle would
# otherwise put two messages a few hours apart, which the gate would suppress anyway — and a
# proposal the gate always refuses is a rung that exists only in a log.
MIN_STEP_DAYS = 2

# Nor more than this. A 730-day cycle (a battery, a ceramic coat) would otherwise wait a third of
# a year for its second rung, by which time the reminder is about a different visit entirely.
MAX_STEP_DAYS = 30

# How many times returning on the FIRST rung locks the ladder. Twice, not once: one early return
# is a customer who happened to be passing, and locking on a single coincidence would deny an
# offer to somebody who never needed reminding twice by chance.
LOCK_AFTER_FIRST_RETURNS = 2

# Below this engagement score the customer is dormant and the ladder stops at rung one.
DORMANT_BELOW = 1.0

# The rungs, by what each one IS. The tone rotates so no two consecutive rungs read alike.
REMINDER = "reminder"
OFFER = "offer"


@dataclass(frozen=True)
class Rung:
    """One proposed message: what it is, when, and in which tone."""
    kind: str                  # REMINDER or OFFER
    due_at: int
    tone_index: int            # which of the library's tones for this type — always 1 now, see above
    # `marketing` decides which cap and which consent apply, and it is set HERE rather than at send
    # time so an owner asking "why was this suppressed" gets a stable answer.
    marketing: bool = False


def step_seconds(interval_days: int) -> int:
    """The gap between two rungs, from this customer's own cycle."""
    raw = (interval_days or 0) * STEP_SHARE
    clamped = max(MIN_STEP_DAYS, min(MAX_STEP_DAYS, raw))
    return int(clamped * DAY)


def is_locked(first_rung_returns: int) -> bool:
    """Has this customer earned the lock that protects the margin?"""
    return first_rung_returns >= LOCK_AFTER_FIRST_RETURNS


def build(*, sent_at: int, interval_days: int, marketing_consent: bool,
          first_rung_returns: int = 0, engagement_score: float | None = None) -> list[Rung]:
    """The rungs AFTER the first reminder, which has already gone out at `sent_at`.

    Returns an empty list when the ladder stops there — the dormant, and the locked without
    consent. The caller schedules what comes back and nothing else; a rung that is not returned is
    not "skipped", it does not exist.
    """
    step = step_seconds(interval_days)

    # THE DORMANT ARE LEFT AT RUNG ONE, before consent is even consulted: whether he would accept
    # an offer is irrelevant when he does not read us at all.
    #
    # AND `None` IS NOT ZERO — the distinction the engagement score itself is built on. A customer
    # with no record is one we have never measured, not one who ignores us: a shop's first week
    # produces nothing but such customers, and treating unknown as dormant would have meant the
    # ladder never started for anybody, ever. Found by a test that expected a rung and got none.
    if engagement_score is not None and engagement_score < DORMANT_BELOW:
        return []

    locked = is_locked(first_rung_returns)

    if not marketing_consent:
        # TWO RUNGS, THEN LEFT. The second is the same reminder in a different tone — one message
        # more, no new template, and no offer ever.
        #
        # AND THE LOCK APPLIES HERE TOO, which is not obvious: it locks at rung one, and the reason
        # is the same whether or not an offer was available — somebody who returns on the first
        # message does not need a second.
        if locked:
            return []
        return [Rung(kind=REMINDER, due_at=sent_at + step, tone_index=1)]

    if locked:
        # HE CONSENTED, AND HE STILL SEES NO OFFER. This is the rule that costs the most to write
        # down and saves the most: the offer is for whoever does not come back without one.
        return [Rung(kind=REMINDER, due_at=sent_at + step, tone_index=1)]

    return [
        Rung(kind=OFFER, due_at=sent_at + step, tone_index=1, marketing=True),
        # NOT tone_index=2 ANY MORE — see the module docstring. With only two tones in the
        # library, and the two a gender split rather than a formality ladder, index 2 would
        # switch this shop's customer to the OTHER grammatical gender for one message and back.
        Rung(kind=REMINDER, due_at=sent_at + 2 * step, tone_index=1),
    ]
