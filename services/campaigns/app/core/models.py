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
GOALS = ("win_back", "reward_loyal", "announce", "occasion", "awareness", "service_offer")

# Which template type each goal sends, and its regulatory class. The class is NOT the owner's
# choice: every campaign is promotional except awareness, and awareness is the one with a lock.
GOAL_TEMPLATE = {
    "win_back": ("mkt_winback", "marketing"),
    "reward_loyal": ("mkt_loyalty_activation", "marketing"),
    "announce": ("mkt_announcement", "marketing"),
    "occasion": ("mkt_personal_occasion", "marketing"),
    "awareness": ("awr_care_tip", "awareness"),
    "seasonal_care": ("awr_seasonal_care", "awareness"),
    # NOT MARKETING, AND THE CLASS IS THE WHOLE REASON THIS IS SEPARATE FROM `announce`. A hazard
    # notice reaches people who never consented to offers, because it is not an offer — it is the
    # shop telling somebody that a thing they are using may hurt them. Filing it as marketing
    # would silence it for exactly the customers most likely to be affected: the ones who opted
    # out of being sold to.
    "safety": ("wrn_safety_notice", "warning"),
    # AN OFFER ON ONE SERVICE — and it sends the OFFER template, not the announcement.
    #
    # It borrowed «جديد في {{2}}: {{3}}» for as long as it existed, so a discount reached the
    # customer wearing an announcement's words and the number was stuffed into the owner's one
    # free line. `mkt_offer` declares the slots this goal actually has: a typed value, the service
    # it covers, and the day it stops. The audience rule (§10.9.1) is unchanged — what changed is
    # that the message now says what the campaign is.
    "service_offer": ("mkt_offer", "marketing"),
}

# WHICH GOALS PUT SOMETHING ON THE TABLE, and therefore must carry an end date.
#
# Not every campaign is an offer. A care tip gives nothing away and expires by being read;
# demanding a date for it would be a field with no meaning that somebody fills in with a guess.
#
# `occasion` DOES belong here, and its absence was ح-7: its own template — `mkt_personal_occasion`
# — declares `offer_value` and `ends_at` (reasons.py's `personal_occasion` reason), the exact same
# typed slots `win_back` and `reward_loyal` carry. A goal whose template needs an amount and a date
# but whose card claims `offers=False` never asks for either — `Launch.tsx` never draws the value
# and date fields, so the console posts a campaign to a template that requires them and
# `preview.py` refuses every single one. The whole goal was unreachable, and the owner had no way
# to fix a refusal born from a field the screen never showed.
#
# An offer without an end is a price change nobody decided on, and it is also the only thing the
# counter can be asked to honour.
OFFER_GOALS = ("service_offer", "win_back", "reward_loyal", "occasion")


def offers_something(goal: str) -> bool:
    return goal in OFFER_GOALS

# Who fires it. Derived from the goal, never asked.
TRIGGERS = ("manual", "scheduled", "standing")

GOAL_TRIGGER = {
    "win_back": "standing",        # absence is continuous; a one-off win-back is a missed month
    "reward_loyal": "standing",
    # MANUAL, AND DELIBERATELY NOT STANDING. An offer is a decision the owner makes about this
    # week — a standing one would keep discounting the same service for ever, to a rota of people
    # crossing 70% of their cycle, with nobody ever deciding to stop.
    "service_offer": "manual",
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
    # WHICH SERVICE THIS OFFER IS ABOUT — `service_offer` only, and required for it.
    #
    # It is what the cycle lock measures against: a customer who took THIS service two days ago is
    # held out, and one who is 70% of the way through his own rhythm for it is exactly who the
    # offer should reach. Without it the goal would be an announcement wearing a targeted name,
    # and the reach number would read as proof it worked.
    service_id: str = ""
    # WHICH BRANCH'S CUSTOMERS — empty means the whole establishment (spec 12.2).
    #
    # A BRANCH IS A DESCRIPTION ON AN EVENT, NEVER A DIVISION OF THE ACCOUNT. The customer, the
    # balance and the opt-out all stay unified; this only narrows WHO A GIVEN CAMPAIGN REACHES, by
    # the last branch each customer actually walked into. A shop in Riyadh announcing its Riyadh
    # evening does not want to reach the man who moved to Jeddah last month — and he moved himself,
    # by visiting, with nobody configuring anything.
    #
    # STORED, because the send resolves the audience again at fire time. A branch that lived only
    # in the preview would show the owner a Jeddah count and then message the whole chain.
    branch_id: str = ""
    # WHAT THE OFFER APPLIES TO, as something a screen can act on rather than read.
    #
    # `owner_text` is the sentence the customer receives, and it must stay free: it is what
    # persuades, and it is the field Meta already approved a shell around. But a sentence cannot be
    # ENFORCED — the operator at the counter reads "20% off" and decides for himself what that
    # covers, and two operators decide differently on the same day.
    #
    # So the scope sits beside the words: empty means the whole shop, a list means these services.
    # The text convinces; the scope applies. Neither replaces the other.
    #
    # SERVICES, NOT PRODUCTS. This product has no product catalogue — only services — and a scope
    # that named products would be a promise nothing behind it could keep.
    scope_service_ids: list[str] = field(default_factory=list)
    # For `scheduled`: when to fire. For `standing`: unused.
    fire_at: int = 0
    # WHEN THE OFFER STOPS BEING TRUE — stored, and required for every goal that offers something.
    #
    # It used to be a preview-only number: the console sent it, the spread planner used it once to
    # answer "can everyone be reached before then", and it was thrown away. So the message went out
    # with no end anybody could name — an owner running "20% off" had no date, the operator at the
    # counter had nothing to check against, and the customer's own page could not count anything
    # down. A discount with no end is a permanent price nobody decided on.
    #
    # AND IT IS WHAT MAKES THE OFFER EXCLUSIVE MEAN SOMETHING. Whoever received the message holds
    # it until this moment and no longer; whoever did not receive it never held it. The send log
    # says who, and this says until when — no second table, and nothing to argue about at the till.
    expires_at: int = 0
    # ── the discount itself, typed ────────────────────────────────────────────────────────────
    # «20%» or «50 ريال». It travelled inside `owner_text` — one free line carrying a number, a
    # scope and a promise all at once — so the send could not validate it, could not put it in a
    # template slot declared `amount`, and could not phrase it the same way twice. A shop wrote
    # «خصم كبير» and the customer read a promise nobody could be held to.
    offer_value: str = ""
    # The same services as `scope_service_ids`, by name — carried so the send can say «خصم على
    # غسيل خارجي» instead of an id. Names live in operations; this is the copy the message needs
    # at the moment it is written, and it is deliberately a snapshot: renaming a service later
    # must not rewrite an offer a customer already received.
    scope_service_names: list[str] = field(default_factory=list)
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
