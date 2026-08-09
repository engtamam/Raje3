"""How much of today's sending ceiling this campaign may have.

    share = ceiling − what the automatic engine reserved − what has already been reached today

THE THREE TERMS COME FROM THREE PLACES, and that is the whole design rather than an accident:

  the CEILING   is Meta's, read live through notification-service. Never ours to invent.
  the RESERVE   is the shop's own traffic, computed by insights from the visits it already
                snapshots — the 95th percentile of the same weekday, so a car wash that fills on
                Thursday holds back more on Thursday.
  what is USED  is what reminders has already reached today, counted in PEOPLE, because the
                ceiling counts unique customers and not messages.

None of them is a number this service could compute, and every one of them is a number it needs
before it can promise an owner anything.

────────────────────────────────────────────────────────────────────────────────────────────────
AND ANY OF THE THREE MAY BE UNKNOWN

That is the case worth designing for, because it is the normal case on the day a shop connects.
A missing ceiling does not stop the campaign: Meta enforces its own limit at the door, and a
campaign that refuses to run because WE could not read a number is our outage wearing their
ceiling. What is lost is the PROMISE — we stop telling him "five days" when we cannot know.

So `known` travels with the number, and the screen shows an estimate only when it is one.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Share:
    """Today's campaign allowance, and whether it is a fact or a fallback."""

    per_day: int = 0
    known: bool = False
    ceiling: int = 0
    reserved: int = 0
    used: int = 0

    def to_dict(self) -> dict:
        return {"per_day": self.per_day, "known": self.known, "ceiling": self.ceiling,
                "reserved": self.reserved, "used": self.used}


def compute(*, ceiling: int, reserved: int, used: int, fallback: int) -> Share:
    """Today's share.

    `ceiling`  -1 unlimited, 0 unknown — the shape notification-service reports.
    `fallback` what to allow when the ceiling is unknown. NOT a pretend ceiling: it is the pass
               batch this service already used before any of this existed, so an unknown ceiling
               leaves behaviour exactly as it was rather than inventing a new one.
    """
    if ceiling < 0:
        # UNLIMITED IS KNOWN, and it is not infinity in practice: the pass batch still bounds one
        # run so a single campaign cannot monopolise a worker. What it means is that nothing is
        # held back for the ceiling's sake.
        return Share(per_day=fallback, known=True, ceiling=-1, reserved=reserved, used=used)
    if ceiling == 0:
        return Share(per_day=fallback, known=False, reserved=reserved, used=used)

    # THE RESERVE AND WHAT IS ALREADY USED BOTH COME OFF, and forgetting the second is the subtle
    # error: reserving 40 for the engine on a ceiling of 250 leaves 210 only at midnight. By the
    # afternoon the engine may have spent 30 of its own, and a campaign handed 210 then would push
    # the shop past its ceiling — the failure landing on whichever message went last, which will
    # be a customer's confirmation rather than the campaign that caused it.
    left = ceiling - max(0, reserved) - max(0, used)
    return Share(per_day=max(0, left), known=True, ceiling=ceiling,
                 reserved=reserved, used=used)
