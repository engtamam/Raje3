"""What a campaign is — one record for three modes, and why that is not a shortcut.

MANUAL, SCHEDULED AND STANDING DIFFER ONLY IN WHO FIRES THEM: a person now, a clock at a time, or a
daily evaluation. Everything else is identical — the same goal, the same audience rule, the same
template, the same gate.

Three tables would have meant three send paths, and the third is the one that gets forgotten. That
is not a hypothetical: the standing campaign is the one nobody watches. A manual send is fired by
an owner who is looking at the screen; a scheduled one goes out at a time they chose. The standing
rule runs unattended, every day, for a year — and if it had its own path, it would be the path
missing a check the day somebody added one to the other two.

THE OWNER NEVER SEES A MODE (spec §10.9). They pick a GOAL, and the goal decides: win-back is
standing because absence is continuous, an announcement is once because news is not.

THE RUN IS A SEPARATE RECORD, AND THAT IS THE SECOND decision worth defending. A standing campaign
that has fired forty times is forty questions an owner can ask — "why did nobody get it last
Tuesday?" — and a single row carrying `sent_count` cannot answer any of them. So each firing writes
its own row: when, how many matched, how many went, how many were refused and for what reason.

NOTHING IS EVER DELETED. A campaign whose runs are referenced by the send log must survive as a
name, or an owner reading their history six months later sees message rows pointing at nothing.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

CAMPAIGNS = "campaigns"
RUNS = "campaign_runs"

# What the owner picks. Not a taxonomy they learn — five cards with two words each (spec §10.9).
GOALS = ("win_back", "reward_loyal", "announce", "occasion", "awareness")

# Which template type each goal sends, and its regulatory class. The class is NOT the owner's
# choice: every campaign is promotional except awareness, and awareness is the one with a lock.
GOAL_TEMPLATE = {
    "win_back": ("mkt_winback", "marketing"),
    "reward_loyal": ("mkt_loyalty_activation", "marketing"),
    "announce": ("mkt_announcement", "marketing"),
    "occasion": ("mkt_personal_occasion", "marketing"),
    "awareness": ("awr_care_tip", "awareness"),
}

# Who fires it. Derived from the goal, never asked.
TRIGGERS = ("manual", "scheduled", "standing")

GOAL_TRIGGER = {
    "win_back": "standing",        # absence is continuous; a one-off win-back is a missed month
    "reward_loyal": "standing",
    "announce": "manual",          # news is not recurring
    "occasion": "scheduled",
    "awareness": "manual",         # pressed by the owner, then locked for a month (spec §10.9)
}

# draft → active → paused → done. A STANDING campaign is never done: it has no end, only a pause.
STATES = ("draft", "active", "paused", "done")


def _now() -> int:
    return int(time.time())


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


@dataclass
class Campaign:
    tenant: str
    goal: str
    id: str = field(default_factory=lambda: _id("cmp"))
    # The owner's single free-text field — the offer, the news, the advice. One at most, because
    # two is a form and a form left half-finished sends nothing (spec §8.4.2 section 6).
    owner_text: str = ""
    # Derived at creation from the goal and stored, not recomputed on read. If GOAL_TEMPLATE ever
    # changes, campaigns already running must keep sending what they were sending — a template
    # swapped underneath a live campaign is a message the owner never approved.
    template_type: str = ""
    cls: str = "marketing"
    trigger: str = "manual"
    state: str = "draft"
    # For `scheduled`: when to fire. For `standing`: unused.
    fire_at: int = 0
    # For `standing`: the last day it was evaluated, as an epoch. THE GUARD against a five-minute
    # cron evaluating a daily rule twelve times an hour — see core/tick.py. On the campaign rather
    # than in a side table, because a flag somewhere else is the flag that gets lost.
    last_evaluated: int = 0
    # Set when awareness fires. The card shows "available in N days" until it passes (spec §10.9).
    locked_until: int = 0
    created: int = field(default_factory=_now)
    updated: int = field(default_factory=_now)

    def __post_init__(self) -> None:
        if not self.template_type:
            t, c = GOAL_TEMPLATE.get(self.goal, ("mkt_announcement", "marketing"))
            self.template_type, self.cls = t, c
        if self.trigger == "manual" and self.goal in GOAL_TRIGGER:
            self.trigger = GOAL_TRIGGER[self.goal]

    @property
    def key(self) -> str:
        return f"{self.tenant}|{self.id}"

    @property
    def is_standing(self) -> bool:
        return self.trigger == "standing"

    def locked(self, now: int) -> bool:
        return self.locked_until > now


@dataclass
class Run:
    """One firing. Written even when it sends nothing.

    A standing campaign that matched nobody for a week is information — and silence looks identical
    to a broken cron, which is the failure this record exists to make visible.
    """
    tenant: str
    campaign_id: str
    at: int
    id: str = field(default_factory=lambda: _id("run"))
    matched: int = 0
    sent: int = 0
    suppressed: int = 0
    failed: int = 0
    # Reason → count, verbatim from reminders' gate. The totals alone turn every rule we wrote into
    # a suspected bug; "3 deferred for the daily cap" is a working system explaining itself.
    reasons: dict[str, int] = field(default_factory=dict)
    # Whether a person fired it or the clock did — the same campaign can be both over its life.
    fired_by: str = "system"

    @property
    def key(self) -> str:
        # Keyed by campaign AND time, so runs of one campaign sort together and a re-fire at the
        # same second cannot overwrite the previous one.
        return f"{self.tenant}|{self.campaign_id}|{self.at}|{self.id[-8:]}"


def as_row(obj: Any) -> dict[str, Any]:
    from dataclasses import asdict
    return asdict(obj)
