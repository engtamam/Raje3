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
MAX_AUDIENCE = 5000


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
    truncated: bool = False

    @property
    def count(self) -> int:
        return len(self.candidates)


async def resolve(*, goal: str, tenant: str, now: int, customers, gate_check=None,
                  already_reached: set[str] | None = None,
                  window_days: int = 90, min_visits: int = 3) -> Audience:
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
                                min_visits=min_visits)
        if not matched:
            continue

        if gate_check is not None and not await gate_check(subject):
            # MATCHED BUT WOULD BE REFUSED. Counted, not hidden: the preview says "reaches 43"
            # and the owner is never surprised by a number that shrank between the screen and
            # the send.
            out.excluded += 1
            continue

        out.candidates.append(Candidate(subject_ref=subject, why=why))
        if len(out.candidates) >= MAX_AUDIENCE:
            # REPORTED, never silent. A truncation nobody is told about reads as "everyone was
            # reached", which is the single most misleading thing a campaign screen can say.
            out.truncated = True
            break

    return out


def _matches(goal: str, row: dict[str, Any], *, now: int, window_days: int,
             min_visits: int) -> tuple[bool, str]:
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

    if goal == "occasion":
        # The owner supplied the date; matching a customer to it is data we do not hold yet.
        # Returning False rather than everyone: a birthday campaign that reaches every customer is
        # worse than one that reaches nobody, because it goes out under the shop's name.
        return bool(row.get("occasion_today")), "مناسبته اليوم"

    return False, ""
