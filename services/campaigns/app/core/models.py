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

from app.core.riyadh import local as riyadh_local

CAMPAIGNS = "campaigns"
RUNS = "campaign_runs"

# What the owner picks. Not a taxonomy they learn — four cards with two words each (spec §10.9).
#
# `community_milestone` (2026-09-27) HAS NO CARD YET, same as `service_due` — real, wired,
# CI-checked machinery (GOAL_TEMPLATE/GOAL_TRIGGER/GOAL_MECHANIC rows below, a real resolver in
# `core/milestone.py`, a real `tick.py` branch), reachable only through this file and direct tests
# until the console/mobile phase gives it a launch screen. See `core/mechanics.py`'s own docstring
# for why this is a SIBLING mechanic to the one every other goal uses, not a branch inside it.
GOALS = ("win_back", "reward_loyal", "announce", "occasion", "service_offer",
        "package_offer", "service_due", "community_milestone")

# Which template type each goal sends, and its regulatory class. The class is NOT the owner's
# choice: every campaign here is promotional (marketing).
GOAL_TEMPLATE = {
    "win_back": ("mkt_winback", "marketing"),
    "reward_loyal": ("mkt_loyalty_activation", "marketing"),
    "announce": ("mkt_announcement", "marketing"),
    "occasion": ("mkt_personal_occasion", "marketing"),
    # AN OFFER ON ONE SERVICE — and it sends the OFFER template, not the announcement.
    #
    # It borrowed «جديد في {{2}}: {{3}}» for as long as it existed, so a discount reached the
    # customer wearing an announcement's words and the number was stuffed into the owner's one
    # free line. `mkt_offer` declares the slots this goal actually has: a typed value, the service
    # it covers, and the day it stops. The audience rule (§10.9.1) is unchanged — what changed is
    # that the message now says what the campaign is.
    "service_offer": ("mkt_offer", "marketing"),
    # A PACKAGE, NOT A SERVICE — but the SAME template. `mkt_offer`'s "catalogue" fill is a tap on
    # what he sells, not specifically a service; a package is exactly as much "what he sells" as a
    # service is, and reusing the template means Meta approved this wording once, for both.
    #
    # NO CYCLE LOCK, DELIBERATELY (unlike service_offer). A package spans several services with no
    # single rhythm to be 70% through — audience.resolve()'s own lock only ever engages when
    # `service_id` is set (core/audience.py), and a package_offer campaign never sets it, so this
    # falls through to the same plain whole-shop/branch audience an announcement uses. Inventing a
    # cross-service cycle for this would be a real, separate design question this feature does not
    # answer by guessing.
    "package_offer": ("mkt_offer", "marketing"),
    # "حان وقت الخدمة" — reclassified `marketing` this session (CST's own rule: reminding of a
    # service is a promotional message, not a service one). UNLIKE EVERY OTHER GOAL HERE, this one
    # sends no message of its own: reminders' `scheduling.py` computes the precise per-service cycle
    # and schedules the row directly, at visit time, and keeps doing so untouched. What lives here
    # is SETTINGS ONLY — on/off, and which of two rewards it hands out — read by reminders at send
    # time (services/reminders' own new peer client) rather than fired by this service's own
    # tick/dispatch. See the one settings record's own note below (`SERVICE_DUE_SETTINGS_ID`).
    "service_due": ("svc_service_reminder", "marketing"),
    # A SHARED-COHORT REVEAL, NOT A PER-CUSTOMER SEND — the template still needs Meta approval and
    # a "catalogue"/"reward" fill like any offer template; nothing about the "جماعي" mechanic
    # changes what a WhatsApp template IS, only how the recipient list is built (core/milestone.py).
    "community_milestone": ("mkt_community_milestone", "marketing"),
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
#
# `community_milestone` JOINED (2026-09-27, reversing the v1-simplest launch decision on the
# owner's own direct instruction: "نفس المحرك ينطبق عليها بالكامل") — the SAME two fields every
# other offer goal already has, reused verbatim rather than invented twice: `fire_at` is when
# counting STARTS (0 = immediately, the same "no future date means now" every other goal's
# `fire_at` already means), `expires_at` is the challenge's own deadline — reached without
# crossing the threshold, the campaign expires without ever revealing anyone (see
# core/milestone.py's own docstring on the window check, and core/tick.py's own milestone branch
# on the expiry-vs-recurrence decision).
OFFER_GOALS = ("service_offer", "package_offer", "win_back", "reward_loyal", "occasion",
              "community_milestone")


def offers_something(goal: str) -> bool:
    return goal in OFFER_GOALS


# Same range Python's own `date.weekday()` returns — see `Campaign.window_weekdays`'s own note.
_WEEKDAY_RANGE = range(0, 7)


def validate_window(*, start_hour: int, end_hour: int, weekdays: list[int] | None) -> str:
    """One Arabic sentence naming what is wrong with a campaign's own time window, or "" when the
    combination is coherent — same shape and same calling convention as
    `operations/core/scheduling.py::validate_recurrence`, checked at write time so a malformed
    window is refused before it is ever stored, never discovered the first time a dispatch pass
    silently skips every single one of its passes forever.
    """
    if not (0 <= start_hour <= 24):
        return "ساعة البداية يجب أن تكون بين 0 و24"
    if not (0 <= end_hour <= 24):
        return "ساعة النهاية يجب أن تكون بين 0 و24"
    if end_hour <= start_hour:
        return "ساعة النهاية يجب أن تكون بعد ساعة البداية"
    if weekdays and any(w not in _WEEKDAY_RANGE for w in weekdays):
        return "أحد الأيام المختارة غير صحيح"
    return ""


#: `reward_loyal`'s own audience thresholds, adjustable per campaign (2026-09-13 — the owner's own
#: correction: "الأكثر زيارة عندك" should never be a fixed 90-day/3-visit rule baked into the
#: code, it should be a decision he makes per campaign, live). Named the SAME as `audience.resolve`'s
#: own `window_days`/`min_visits` parameters but campaign-scoped and reward_loyal-specific — win_back's
#: own use of `window_days` (its fallback cycle length) is a completely different question and must
#: never read these.
LOYALTY_WINDOW_DAYS_RANGE = (7, 365)
LOYALTY_MIN_VISITS_RANGE = (1, 50)


def validate_loyalty_window(*, window_days: int, min_visits: int) -> str:
    """One Arabic sentence naming what is wrong with «كافئ المخلصين»'s own audience thresholds, or
    "" when both are coherent — same shape as `validate_window` above."""
    lo, hi = LOYALTY_WINDOW_DAYS_RANGE
    if not (lo <= window_days <= hi):
        return f"مدة الزيارة الأخيرة يجب أن تكون بين {lo} و{hi} يوماً"
    lo, hi = LOYALTY_MIN_VISITS_RANGE
    if not (lo <= min_visits <= hi):
        return f"أقل عدد زيارات يجب أن يكون بين {lo} و{hi}"
    return ""


#: What one of these campaigns may give (2026-09-13, started as the `occasion`-goal pilot,
#: extended to `win_back` once that pilot proved out). `discount` keeps today's behaviour exactly,
#: which is why it is every campaign's default; `gift` and `points` are the two new doors, each
#: requiring the one field it cannot compose a sentence without.
REWARD_TYPES = ("discount", "gift", "points")

#: WHICH GOALS THIS CHOICE APPLIES TO. Every other goal's `reward_type`/`reward_points` are a
#: no-op — accepted, never rejected (a console sending the spare default must not fail a campaign
#: over it), but ignored, same posture `fire_at`'s own comment states for `occasion`-only fields.
#: Started with `occasion` alone, then `win_back` once that proved out, then `service_offer`/
#: `package_offer` (both fire `mkt_offer` — see `GOAL_TEMPLATE` — so one template rewrite reaches
#: both goals at once). `reward_loyal` and `announce` stay out: `reward_loyal` is already built
#: around redeeming an EXISTING points balance for a catalogue item, a different mechanic than
#: choosing a reward at creation; `announce` offers nothing today and has no `offer_value`/
#: `scope_service_ids` for a reward to be built from in the first place. `service_due` stays out
#: too, by the owner's own explicit call (2026-09-13): that goal is an on/off switch only, never a
#: reward choice — see `service_due_settings.py`'s own docstring.
#:
#: A SET LITERAL, DELIBERATELY, NOT A TUPLE — `ci/check_template_fills.py::campaign_types()`
#: regexes this whole file, unscoped, for a two-quoted-string pair inside parentheses to find
#: `GOAL_TEMPLATE`'s own goal-to-class entries; a tuple of two strings here reads as a second,
#: bogus entry of that same shape and corrupts that check. Curly braces do not match it.
REWARD_ENABLED_GOALS = {"occasion", "win_back", "service_offer", "package_offer",
                        "community_milestone"}

#: THE NARROWEST SANE SHARED TARGET — a "milestone" of 1 is an ordinary single-customer send with
#: extra steps, and a target of 0 or less can never be crossed by an increasing counter, which
#: would be a campaign that can NEVER fire, silently, forever.
MIN_MILESTONE_THRESHOLD = 2


def validate_milestone_threshold(threshold: int) -> str:
    """One Arabic sentence naming what is wrong with a `community_milestone` campaign's own shared
    target, or "" when it is coherent — same shape and calling convention as
    `validate_window`/`validate_loyalty_window`/`validate_reward` above."""
    if threshold < MIN_MILESTONE_THRESHOLD:
        return f"الهدف الجماعي يجب أن يكون {MIN_MILESTONE_THRESHOLD} على الأقل"
    return ""


def validate_milestone_recurrence(*, recurring: bool, fire_at: int, expires_at: int) -> str:
    """One Arabic sentence naming what is wrong with a recurring milestone's own start/end, or ""
    when it is coherent. A NON-recurring milestone needs nothing here — `expires_at` alone (via
    `OFFER_GOALS`'s own ordinary "an offer without an end" check) is enough for a one-shot
    challenge. RECURRING NEEDS BOTH DATES EXPLICIT, because the period the next round repeats is
    `expires_at - fire_at` — a recurring challenge with no real start has no real period to repeat,
    and guessing one (from `Campaign.created`, say) would make two owners who launched the "same"
    weekly challenge on different days silently repeat on different schedules.
    """
    if not recurring:
        return ""
    if not fire_at or not expires_at:
        return "التكرار يحتاج تاريخ بداية ونهاية واضحين لكل جولة"
    if fire_at >= expires_at:
        return "تاريخ البداية يجب أن يكون قبل تاريخ النهاية"
    return ""


def validate_reward(*, reward_type: str, reward_points: int, scope_service_ids: list,
                    offer_value: str) -> str:
    """One Arabic sentence naming what is wrong with a campaign's own reward, or "" when it is
    coherent — same shape and calling convention as `validate_window`/`validate_loyalty_window`
    above. Checked at write time, for the same reason those two are: a reward with a missing field
    must be refused before it is ever stored, never discovered the first time a send tries to
    compose a sentence around a hole.
    """
    if reward_type not in REWARD_TYPES:
        return f"نوع المكافأة غير معروف — اختر واحداً من {REWARD_TYPES}"
    if reward_type == "gift" and not scope_service_ids:
        return "الهدية تحتاج خدمة محدَّدة من كتالوجك — اختر واحدة على الأقل"
    if reward_type == "points" and reward_points <= 0:
        return "عدد نقاط الهدية يجب أن يكون أكبر من صفر"
    if reward_type == "discount" and not offer_value:
        return "حدّد قيمة الخصم — نسبة مثل 20% أو مبلغاً مثل 50 ريال"
    return ""


def in_window(*, start_hour: int, end_hour: int, weekdays: list[int] | None, now: int) -> bool:
    """Is `now` (Riyadh local) inside this window right now?

    PLAIN VALUES, NOT A `Campaign` — every caller in this service (dispatch.py, tick.py) holds a
    campaign as a raw stored dict, never a real dataclass instance; asking for one here would
    just be reconstructed on the spot from a partial `.get(...)` sweep, which is the shape this
    avoids.

    A CAMPAIGN THAT NEVER SET A WINDOW (the `0, 24`/`[]` defaults) IS ALWAYS INSIDE IT — an owner
    who never touches this field gets exactly the behaviour every campaign already had before
    this existed. `end_hour == 24` reads as midnight, the true end of the Riyadh calendar day,
    never a wrap past it — there is no "24:00 to 02:00" window; that shape is simply not
    representable, the same honest limitation `operations/scheduling.py`'s own yearly-window wrap
    logic exists specifically to handle for DAYS, not hours (this file does not attempt the hour
    equivalent — a window that must cross midnight is two campaigns, not one, until a real need
    for the wrap is reported).
    """
    local = riyadh_local(now)
    if weekdays and local.weekday() not in weekdays:
        return False
    return start_hour <= local.hour < end_hour

# Who fires it. Derived from the goal, never asked.
#
# "milestone" (2026-09-27) IS ITS OWN TRIGGER, NOT "standing" — a standing campaign is throttled to
# once a Riyadh calendar day (`tick.same_day`'s whole reason for existing); a milestone campaign
# must be checked EVERY tick (a shared counter can cross its threshold at any minute), and it is
# only ever "done" once its one-shot reveal has fully drained — a genuinely different shape
# `tick.py`'s own `milestone` branch handles on its own terms, never squeezed into `standing`'s
# once-a-day guard or `scheduled`'s "finished means done" shortcut.
TRIGGERS = ("manual", "scheduled", "standing", "milestone")

GOAL_TRIGGER = {
    "win_back": "standing",        # absence is continuous; a one-off win-back is a missed month
    "reward_loyal": "standing",
    # MANUAL, AND DELIBERATELY NOT STANDING. An offer is a decision the owner makes about this
    # week — a standing one would keep discounting the same service for ever, to a rota of people
    # crossing 70% of their cycle, with nobody ever deciding to stop.
    "service_offer": "manual",
    "package_offer": "manual",     # same reasoning: a package offer is this week's decision
    "announce": "manual",          # news is not recurring
    "occasion": "scheduled",
    # STANDING, LIKE `win_back`/`reward_loyal` — the same "always on unless paused" shape, since
    # this goal's one record IS the settings, never a thing that finishes. NOTHING ACTUALLY READS
    # THIS ENTRY FOR `service_due` TODAY: it has no card in `goals.py::CARDS` (no launch screen, no
    # audience, no `dispatch.fire()` of its own — reminders' own `scheduling.py` decides the timing
    # entirely on its own, untouched by this service's tick), so `resolve_goal()`/`_behaviour()`
    # never look this goal up. Set anyway, deliberately, rather than left absent: the day a screen
    # or a report DOES ask "how does this goal behave", the honest answer is here rather than a
    # `KeyError` or a silent `.get(..., "manual")` default that would describe it wrong.
    "service_due": "standing",
    "community_milestone": "milestone",
}

# HOW A GOAL DECIDES WHO IT REACHES — held for EVERY real goal, the same way GOAL_TEMPLATE/
# GOAL_TRIGGER already are, including `service_due` (no card, no audience, no mechanic that ever
# actually runs — kept anyway for the same "the honest answer is here, not a KeyError" reason
# GOAL_TRIGGER's own comment gives it). "فردي" is the one mechanic every launchable goal used until
# 2026-09-27: one candidate row, matched independently, via `core/audience.py::resolve`. "جماعي" is
# the first sibling — a shared counter crossing a fixed threshold, then a batch reveal to the whole
# earned cohort at once (`core/milestone.py`). See `core/mechanics.py` for the registry that turns
# this word into a real resolver function, and `ci/check_campaign_mechanics.py` for the gate that
# keeps every goal here honestly wired to one.
MECHANICS = ("فردي", "جماعي")

GOAL_MECHANIC = {
    "win_back": "فردي",
    "reward_loyal": "فردي",
    "announce": "فردي",
    "occasion": "فردي",
    "service_offer": "فردي",
    "package_offer": "فردي",
    "service_due": "فردي",
    "community_milestone": "جماعي",
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
    # WHICH PACKAGE THIS OFFER IS ABOUT — `package_offer` only, mutually exclusive with
    # `service_id` (a campaign is about one or the other, never both). NOT read by the cycle lock
    # — see GOAL_TEMPLATE's own note on `package_offer` for why a package has no single rhythm to
    # be checked against. It exists so dispatch.fire() can re-ask, at every pass, whether this
    # exact package is still active and in its own schedule (core/scheduling.py, operations) —
    # never trusted from the moment the campaign was created, the same "ask again, never assume"
    # rule HttpAudience.allows() already applies to the audience gate.
    package_id: str = ""
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
    # ── which of three rewards this campaign gives (`occasion` pilot, 2026-09-13) ─────────────
    # "discount" is every campaign's default, and it is the ONLY one that ever existed before this
    # — a campaign created before this field did, or a goal this feature has not reached yet, reads
    # exactly as it always has. See `validate_reward` above for what each of the other two requires
    # and `rendering.campaign_slots`'s own "reward" branch for the composed sentence each produces.
    reward_type: str = "discount"
    # THE POINTS A "points" REWARD CREDITS — meaningless for the other two, same "0 is not yet
    # decided" convention as every other optional numeric field on this dataclass.
    reward_points: int = 0
    # The same services as `scope_service_ids`, by name — carried so the send can say «خصم على
    # غسيل خارجي» instead of an id. Names live in operations; this is the copy the message needs
    # at the moment it is written, and it is deliberately a snapshot: renaming a service later
    # must not rewrite an offer a customer already received.
    scope_service_names: list[str] = field(default_factory=list)
    # For `standing`: the last day it was evaluated, as an epoch. THE GUARD against a five-minute
    # cron evaluating a daily rule twelve times an hour — see core/tick.py. On the campaign rather
    # than in a side table, because a flag somewhere else is the flag that gets lost.
    last_evaluated: int = 0
    # ── THE OWNER'S OWN WINDOW, FOR AN OFFER CAMPAIGN ONLY (2026-09-12) ───────────────────────────
    #
    # EVERY GOAL MAY SET ONE, NOT ONLY `OFFER_GOALS` (revised 2026-09-12 — the owner's own
    # correction: «أعلن جديدك» wanting to go out only Thursday/Friday for a weekend opening is as
    # real a want as an offer's own hours). Always optional — `0, 24, []` (no window) is every
    # campaign's default whether it offers something or not. Read at every dispatch pass
    # (`dispatch.py::Dispatcher.fire`) exactly like `package_id`'s own re-check — never trusted as
    # a one-time decision made at creation.
    #
    # `window_start_hour`/`window_end_hour` — Riyadh local hours, `[start, 24)` when `end == 24`
    # (midnight, "until end of day" — not a magic sentinel, an honest boundary: there is no 24:00
    # to wrap past). `0, 24` (the default) means "the whole day", i.e. no window at all — an owner
    # who never touches this field gets exactly today's behaviour, unchanged.
    window_start_hour: int = 0
    window_end_hour: int = 24
    # `[]` means every day. Same encoding operations/core/scheduling.py's `recurrence_weekdays`
    # already uses (`date.weekday()`: Monday=0 .. Sunday=6) — a second, disagreeing convention for
    # "which days" is the mistake this campaign is not worth making twice in one product.
    window_weekdays: list[int] = field(default_factory=list)
    # «كافئ المخلصين»'s OWN AUDIENCE THRESHOLDS (2026-09-13) — meaningless for every other goal,
    # defaults matching `audience.resolve`'s own pre-existing hardcoded values so a campaign that
    # never touches these gets exactly today's behaviour. See `validate_loyalty_window`'s own note
    # on why these are named/scoped separately from `win_back`'s unrelated use of `window_days`.
    loyalty_window_days: int = 90
    loyalty_min_visits: int = 3
    # `community_milestone` ONLY — the fixed shared target (2026-09-27, v1: fixed at creation, no
    # reset, no re-arming; see `core/milestone.py`'s own docstring for why). Meaningless for every
    # other goal, `0` for every campaign that predates this field, same "not yet decided" convention
    # every other optional numeric field on this dataclass already uses.
    milestone_threshold: int = 0
    # `community_milestone` ONLY — restarts a fresh round (same `fire_at`→`expires_at` period,
    # counter reset to 0) the moment one round's own `expires_at` passes, whether it fired or not.
    # `False` (every other goal's default) means a one-shot challenge — reaches `done` at its
    # deadline (expired, never crossed the threshold) or once its reveal fully drains (crossed and
    # sent), exactly like every other offer goal's own end.
    milestone_recurring: bool = False
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
