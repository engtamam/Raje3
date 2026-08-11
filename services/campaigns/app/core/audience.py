"""Who a campaign reaches — computed from the goal, never typed by the owner.

THE OWNER NEVER SEES THE WORD SEGMENT (spec §10.9). They press "bring back the ones who stopped
coming", and this file decides what that means. Every goal is an audience rule we own, and owning
it is what lets the screen stay four cards instead of a query builder.

THE RULES:

  win_back      no visit for longer than that customer's OWN learned interval — not a fixed 60
                days. A car wash customer who comes weekly is absent after three weeks; a workshop
                customer is not absent until six months. One number for both would send the wrong
                message to whichever is not the average.
  reward_loyal  the most visits in a window.
  announce      everyone who accepts marketing.
  occasion      a date the owner supplied.
  awareness     everyone who accepts awareness — locked to one send a month per shop.

TWO PROPERTIES THAT MATTER MORE THAN THE RULES:

1. THE COUNT SHOWN IN THE PREVIEW IS PRODUCED BY THIS CODE, and the send uses the same function.
   A preview that promises 47 and delivers 31 teaches the owner our numbers are decoration — and
   the only reliable way to keep them equal is to have one implementation, not two that agree
   today.

2. A STANDING CAMPAIGN MUST NOT RE-SEND TO SOMEONE IT ALREADY REACHED. The dedup is the RUN
   HISTORY, not a flag on the customer: a flag would have to be cleared by something, and whatever
   clears it is the bug. Asking "did any run of this campaign already reach this subject?" needs no
   cleanup and is correct after a restore.

BOUNDED, ALWAYS. This reads other services' data on behalf of an owner pressing a button; an
unbounded audience is a way to make the platform do unbounded work.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DAY = 86400

# The ceiling on one campaign's audience. Not a technical limit — a product one: an establishment
# with more than this many customers in one send is a case we want to look at before it goes out,
# and a silent truncation would be worse than a refusal.
#
# A DEFAULT, because "how large is too large to send unreviewed" is a judgement that changes with
# the size of the shops we serve, and the day it needs changing is the day a real customer is
# blocked by it. CAMPAIGN_MAX_AUDIENCE overrides it.
DEFAULT_MAX_AUDIENCE = 5000


@dataclass
class Candidate:
    subject_ref: str
    # Why they matched, carried through to the preview so an owner can sanity-check the rule
    # without us explaining it: "last visit 94 days ago, usual 60".
    why: str = ""


@dataclass
class Audience:
    candidates: list[Candidate] = field(default_factory=list)
    # Everyone the rule matched but the gate would refuse — stopped classes, minimal engagement,
    # over a cap. Counted separately so the preview can show the HONEST number.
    excluded: int = 0
    # HELD OUT BY THE CYCLE LOCK — they took this service too recently (spec §10.9.1). Counted
    # apart from `excluded` because it is the one exclusion with a REASON the owner should read:
    # a number that drops without explanation looks like a fault, and the same number beside its
    # cause looks like a system that understands his shop.
    too_recent: int = 0
    truncated: bool = False

    @property
    def count(self) -> int:
        return len(self.candidates)


# HOW FAR THROUGH HIS OWN CYCLE HE MUST BE before an offer on that service may reach him.
#
# 0.7 rather than a half: below it the need has not formed and the offer is noise; at it the need
# has begun to press, and the offer PULLS FORWARD a visit that was coming — which is the only real
# effect a campaign has. It does not create a need, it moves one.
#
# AND IT IS HIS OWN CYCLE, never a number of ours: the adaptive engine learns a rhythm per customer
# per service, so a man who changes his oil every 60 days and one who takes 120 are each measured
# against themselves rather than against one date for the whole shop.
CYCLE_THRESHOLD = 0.7


def _too_early(row: dict[str, Any], *, now: int, service_id: str,
               threshold: float, window_days: int) -> tuple[bool, str]:
    """Is this customer still early in his cycle for THIS service?

    NEVER SEEN IT: not early, and he is exactly who an offer on it is for. Silence would exclude
    every new customer from every service campaign, which is the opposite of the intent.
    """
    per_service = row.get("services") or {}
    mine = per_service.get(service_id) or {}
    last = int(mine.get("last_visit") or 0)
    if not last:
        return False, "لم يأخذ هذه الخدمة من قبل"
    cycle = float(mine.get("interval_days") or row.get("interval_days") or window_days)
    if cycle <= 0:
        # A service with no rhythm — a one-off repair. Nothing to be early in.
        return False, ""
    elapsed = (now - last) / DAY
    if elapsed < cycle * threshold:
        return True, f"أخذها قبل {int(elapsed)} يوماً، ودورته {int(cycle)}"
    return False, f"مضى {int(elapsed)} يوماً من دورته {int(cycle)}"


async def resolve(*, goal: str, tenant: str, now: int, customers, gate_check=None,
                  already_reached: set[str] | None = None,
                  window_days: int = 90, min_visits: int = 3,
                  service_id: str = "", cycle_threshold: float = CYCLE_THRESHOLD,
                  max_audience: int = DEFAULT_MAX_AUDIENCE) -> Audience:
    """Who this campaign reaches, right now.

    `customers` is an async callable returning rows with `subject_ref`, `last_visit`,
    `interval_days` and `visit_count` — passed in rather than fetched so this stays pure enough to
    test across its whole space, and so the same function serves the preview and the send.

    `gate_check` is an async predicate: would reminders let this message through? Applied HERE so
    the preview's count is the count that actually goes out. Absent, nothing is excluded — which is
    correct for a test and wrong in production, so the caller always supplies it.
    """
    rows = await customers(tenant)
    reached = already_reached or set()
    out = Audience()

    for row in rows:
        subject = row.get("subject_ref") or ""
        if not subject or subject in reached:
            continue

        matched, why = _matches(goal, row, now=now, window_days=window_days,
                                min_visits=min_visits, service_id=service_id)
        if not matched:
            continue

        # ── the cycle lock ────────────────────────────────────────────────────────────────────
        # An offer on a service, sent to somebody who took it yesterday, is the message that loses
        # the permission: he does not read a good intention, he reads a shop that does not know he
        # was there. And it costs the owner money — a discount on a visit that was coming anyway
        # is a sale sold cheaper, not a customer won.
        if service_id:
            early, _ = _too_early(row, now=now, service_id=service_id,
                                  threshold=cycle_threshold, window_days=window_days)
            if early:
                out.too_recent += 1
                continue

        if gate_check is not None and not await gate_check(subject):
            # MATCHED BUT WOULD BE REFUSED. Counted, not hidden: the preview says "reaches 43"
            # and the owner is never surprised by a number that shrank between the screen and
            # the send.
            out.excluded += 1
            continue

        out.candidates.append(Candidate(subject_ref=subject, why=why))
        if len(out.candidates) >= max_audience:
            # REPORTED, never silent. A truncation nobody is told about reads as "everyone was
            # reached", which is the single most misleading thing a campaign screen can say.
            out.truncated = True
            break

    return out


def _matches(goal: str, row: dict[str, Any], *, now: int, window_days: int,
             min_visits: int, service_id: str = "") -> tuple[bool, str]:
    last = int(row.get("last_visit") or 0)
    visits = int(row.get("visit_count") or 0)

    if goal == "win_back":
        if not last:
            return False, ""
        # THE CUSTOMER'S OWN RHYTHM, not a fixed number. `interval_days` is what reminders learned
        # for them; falling back to the window only when nothing has been learned yet.
        usual = float(row.get("interval_days") or window_days)
        elapsed = (now - last) / DAY
        # 1.5x their own cycle: late enough to be absence rather than lateness, early enough that
        # the shop is still the one they think of. A multiplier rather than added days, because
        # "two weeks late" means something different at a car wash and at a workshop.
        if elapsed >= usual * 1.5:
            return True, f"آخر زيارة قبل {int(elapsed)} يوماً، ومعدّله {int(usual)}"
        return False, ""

    if goal == "reward_loyal":
        if visits >= min_visits and last and (now - last) / DAY <= window_days:
            return True, f"{visits} زيارات خلال {window_days} يوماً"
        return False, ""

    if goal in ("announce", "awareness"):
        # Everyone the gate allows. The rule is deliberately empty — narrowing an announcement is
        # the owner's job through a different goal, not a hidden filter here.
        return True, "كل العملاء"

    if goal == "service_offer":
        # AN OFFER ON ONE SERVICE. The rule here is deliberately wide — everyone the gate allows —
        # because the narrowing that matters is the cycle lock in `resolve`, and putting it here
        # too would make one decision live in two places.
        #
        # A campaign of this goal WITHOUT a service is refused rather than widened to the whole
        # shop: it would be an announcement sent under a name that promises targeting, and the
        # owner would read the reach number as proof it worked.
        if not service_id:
            return False, ""
        return True, "من قارب موعد هذه الخدمة"

    if goal == "occasion":
        # The owner supplied the date; matching a customer to it is data we do not hold yet.
        # Returning False rather than everyone: a birthday campaign that reaches every customer is
        # worse than one that reaches nobody, because it goes out under the shop's name.
        return bool(row.get("occasion_today")), "مناسبته اليوم"

    return False, ""
