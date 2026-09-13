"""One number per customer: are they still alive with us? (spec 8.4.2 section 3)

WHY NOT A COUNTER. The first design was "five consecutive ignored messages and we stop". It is the
obvious rule and it is backwards: it punishes the customer we message MOST. A shop that sends
weekly hits five ignores in five weeks from someone perfectly happy; a shop that sends quarterly
never reaches five from someone who has plainly gone. The counter measures our behaviour and calls
it theirs.

WHAT THE INDUSTRY DOES, AND WHAT WE TOOK FROM IT. Deliverability practice sunsets on TIME without
engagement — three to six months, sooner for high-frequency senders — and moves the recipient to an
inactive state rather than deleting them. Segmentation practice weights recent behaviour more
heavily than old. Both are the same instinct as the adaptive interval next door, so this uses the
same shape: a decaying score, not a window and not a counter.

THE ARITHMETIC:

    score = Σ points × 2^(-age / half_life)

A visit is 10, a button tap 3, a read 1, and an ignored message 0. Points halve every 60 days. So
someone who visited last week outranks someone who read six messages last year, which is correct:
one of them is a customer.

DECAYED ON READ, NEVER BY A SWEEP. A nightly job that halves every score is a job that can fail,
skip a night, or run twice — and each of those is silently wrong in a different direction, with no
symptom until an owner asks why a customer stopped getting messages. Decay-on-read cannot drift,
because the value is a pure function of the stored score, its timestamp, and now.

AND ZERO IS NOT A STOP. Below the threshold a customer keeps receiving SERVICE messages — they are
a customer, not a subscriber. What lapses is our right to advertise to them, not their relationship
with the shop. That distinction is the whole difference between a sunset policy and a blocklist.
"""
from __future__ import annotations

from dataclasses import dataclass

DAY = 86400


@dataclass(frozen=True)
class EngagementConfig:
    """Points, half-life, and the two thresholds.

    A visit is worth ten reads because it is the only signal that means anything commercially. A
    read means the message was opened; a visit means the message worked — or that the relationship
    is alive regardless of the message, which is the same answer for our purposes.
    """
    visit_points: float = 10.0
    click_points: float = 3.0
    read_points: float = 1.0
    half_life_days: float = 60.0
    # THE THRESHOLDS ARE DERIVED FROM THE HALF-LIFE, not chosen to look round. An earlier draft
    # said 10 and 3, which read well and was arithmetically wrong: with a visit worth 10 points and
    # a 60-day half-life, a score of 10 is only reachable on the DAY of a visit — a customer who
    # came in three weeks ago scores 7.9 and would have been demoted. The bug was invisible in
    # prose and obvious the moment a test asked "is a customer from last month engaged?".
    #
    # 5.0 is one visit within the half-life: came in within about two months. 1.5 is roughly five
    # months since anything at all, which lines up with the three-to-six-month sunset the
    # deliverability literature converged on.
    full_threshold: float = 5.0
    minimal_threshold: float = 1.5


# What a customer may receive, by tier. Returned as a string rather than a bool pair because the
# gate logs it verbatim in the suppression reason, and "tier: minimal" is an answer an owner can
# act on where "False" is not.
TIER_FULL = "full"
TIER_REDUCED = "reduced"
TIER_MINIMAL = "minimal"


def decayed(score: float, *, scored_at: int, now: int, cfg: EngagementConfig) -> float:
    """The stored score, aged to now. Pure — same inputs, same answer, forever."""
    if score <= 0 or scored_at <= 0 or now <= scored_at:
        return max(0.0, score)
    elapsed_days = (now - scored_at) / DAY
    return round(score * (0.5 ** (elapsed_days / cfg.half_life_days)), 3)


def add(score: float, *, scored_at: int, points: float, now: int,
        cfg: EngagementConfig) -> tuple[float, int]:
    """Age the existing score, add new points, and restamp.

    Returns `(score, scored_at)`. Ageing BEFORE adding is what makes the arithmetic associative:
    add-then-age would apply today's decay to points earned today, so the same events in the same
    order would yield a different number depending on when the sweep happened to run.
    """
    base = decayed(score, scored_at=scored_at, now=now, cfg=cfg)
    return round(base + points, 3), now


def tier(score: float, *, scored_at: int, now: int, cfg: EngagementConfig) -> str:
    s = decayed(score, scored_at=scored_at, now=now, cfg=cfg)
    if s >= cfg.full_threshold:
        return TIER_FULL
    if s >= cfg.minimal_threshold:
        return TIER_REDUCED
    return TIER_MINIMAL


def allows(cls: str, current_tier: str) -> tuple[bool, str]:
    """Whether this tier may receive this class — and the reason if not.

    SERVICE AND PERSONAL ARE NEVER GATED BY ENGAGEMENT. A visit confirmation is a reply to
    something the customer just did; withholding it because they have not read our marketing would
    be absurd, and would break the product for the exact customer who is standing in the shop.

    MARKETING ALONE IS GATED HERE. The regulator's category governs what we may send at 11pm;
    this governs whether an inattentive customer needs to hear from us at all, and unsolicited
    advertising to someone who has ignored us for four months serves nobody.
    """
    if cls in ("service", "personal", "warning"):
        return True, ""
    if current_tier == TIER_MINIMAL:
        return False, (f"engagement tier is minimal — no visit, read or tap for months — so "
                       f"{cls} messages are paused. Service messages continue, and one visit "
                       f"restores everything immediately.")
    # FULL and REDUCED both pass here. The difference between them is not permission but PACE:
    # `monthly_cap` below halves the marketing allowance for a reduced customer. Encoding that as
    # a refusal instead would mean two places decide whether a message may go out, and the second
    # one would eventually disagree with the first.
    return True, ""


def monthly_cap(cls: str, current_tier: str, base_cap: int) -> int:
    """The monthly allowance for this class, adjusted for how engaged the customer is.

    A customer we have barely heard from gets HALF the marketing, not none. That is the middle
    state the counter design had no way to express: it could only stop, so a quiet customer either
    kept receiving everything until they blocked us, or was cut off entirely. Halving buys months
    of the relationship at a fraction of the annoyance.
    """
    if cls != "marketing" or current_tier != TIER_REDUCED:
        return base_cap
    return max(1, base_cap // 2)


def points_for(event: str, cfg: EngagementConfig) -> float:
    return {"visit": cfg.visit_points, "click": cfg.click_points,
            "read": cfg.read_points}.get(event, 0.0)
