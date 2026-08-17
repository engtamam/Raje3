"""The five cards an owner sees, and the state each one carries (spec §10.9).

THE OWNER PICKS A GOAL AND NEVER A TYPE. "Standing campaign" is our word; theirs is "bring back the
ones who stopped coming". So this file is the translation layer between what they press and what
the system does — and every field on a card is there because a screen needs it, not because a model
has it.

THE AWARENESS CARD IS THE ONE WITH A STORY. The original plan had the system send advice
automatically, matched to what a customer had taken and the season. It failed for an operational
reason that settles it: a thousand kinds of shop means a thousand pieces of advice we write and refresh
seasonally, and nobody can run that. The owner knows their trade — a barber knows what to say about
hair in summer, and we do not.

So awareness is a goal they press, with a lock after it. And the lock is DISPLAYED, not hidden:

    "متاح بعد 23 يوم"

grey, visible, with its reason on it. A card that disappears reads as a fault and generates a
support ticket; a card that explains itself reads as a rule and generates nothing.

THE LOCK IS PER ESTABLISHMENT, not per customer. One awareness campaign a month for the whole shop
satisfies the per-customer monthly cap in §8.4.2 automatically — no per-customer arithmetic, no
per-trade model, and one number an owner can hold in their head.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.models import GOAL_TEMPLATE, GOAL_TRIGGER, offers_something

DAY = 86400

# THE KINDS HE FILLS HIMSELF. `system` is ours — his name, the shop, a balance — and never a
# question. `catalogue` is a tap on his own service list rather than typing; the three typed ones
# have a shape we can check, which is the whole reason «خصم كبير» cannot be sent; and `owner` is
# the single free blank, where the sentence has nothing but his own words to put in it.
MANUAL_BLANKS = ("catalogue", "amount", "code", "date", "owner")

# What each card says. Two words and a line — the owner is choosing, not reading.
CARDS = {
    "win_back": {
        "title": "رجّع اللي غابوا",
        "line": "من تأخّر عن موعده المعتاد",
        "icon": "return",
    },
    "reward_loyal": {
        "title": "كافئ المخلصين",
        "line": "الأكثر زيارة عندك",
        "icon": "gift",
    },
    "announce": {
        "title": "أعلن جديدك",
        "line": "خبر أو عرض للجميع",
        "icon": "megaphone",
    },
    "occasion": {
        "title": "هنّئ في مناسبة",
        "line": "رسالة في يوم يخصّه",
        "icon": "cake",
    },
    "awareness": {
        "title": "وعِّ عملاءك",
        "line": "نصيحة تخصّ ما أخذوه",
        "icon": "info",
    },
    "service_offer": {
        "title": "عرض على خدمة",
        # THE LINE IS THE RULE, IN HIS WORDS. He is not told about a threshold or a cycle — he is
        # told who it reaches, and that sentence is the whole of what he needs to trust it.
        "line": "لمن قارب موعد خدمة معيّنة",
        "icon": "tag",
    },
}


@dataclass
class Card:
    goal: str
    title: str
    line: str
    icon: str
    # Whether it can be pressed right now.
    available: bool = True
    # Why not, in the owner's words, ON the card. Never in a tooltip, never in a modal after they
    # press it: a card that looks pressable and then refuses is worse than one that says so.
    unavailable_reason: str = ""
    # How it behaves, as a sentence rather than a type. "Runs every day" is a fact they can hold;
    # "standing" is a word they would have to learn.
    behaviour: str = ""
    # For a template type the tenant has not enabled — the one-tap fix, in place, rather than a
    # trip to the settings screen and back.
    needs_enabling: bool = False
    # Whether this goal PROMISES something — a discount, a reward, a reason to come back. Those
    # carry a mandatory end date (§10.9.1: «ينتهي — لا افتراض له»), and the screen has to know
    # which ones before it can ask for it. Derived here rather than listed in the console, where a
    # second copy would go stale the day a goal is added.
    offers: bool = False
    # WHICH BLANKS THIS GOAL'S MESSAGE HAS FOR HIM TO FILL, in the order they appear, and named
    # by KIND rather than by position (ط-4).
    #
    # Meta approves the WORDS. The only thing a shop decides is what goes in the numbered blanks,
    # so «write your line» was never a true description of anything: `mkt_offer` has an amount, a
    # service and a date, and no room for a sentence at all. The screen used to draw one free box
    # for every goal — and for four of the six the words he typed reached nobody.
    #
    # Empty means every blank is ours to fill, which is most of the engine's messages: a visit
    # confirmation asks him for nothing.
    blanks: list[str] = field(default_factory=list)


def cards(*, now: int, fills_by_type: dict[str, list[str]] | None = None, locks: dict[str, int] | None = None,
          enabled_types: set[str] | None = None) -> list[Card]:
    """The five cards, in the order an owner should see them.

    `locks` maps goal → locked_until. `enabled_types` is which template types the tenant has
    switched on (spec §10.8); a goal whose type is off is shown WITH a way to enable it rather than
    hidden — hiding it means an owner who wants it cannot find out it exists.
    """
    locks = locks or {}
    out: list[Card] = []
    for goal, meta in CARDS.items():
        card = Card(goal=goal, title=meta["title"], line=meta["line"], icon=meta["icon"],
                    behaviour=_behaviour(goal), offers=offers_something(goal))

        until = int(locks.get(goal) or 0)
        if until > now:
            days = max(1, (until - now + DAY - 1) // DAY)
            card.available = False
            # A NUMBER, not a date. "Available in 23 days" is arithmetic an owner does not have to
            # do; a date is arithmetic they do.
            card.unavailable_reason = f"متاح بعد {days} يوم"

        tmpl_type = GOAL_TEMPLATE.get(goal, ("", ""))[0]
        # THE BLANKS COME FROM THE TEMPLATE THIS SHOP WOULD ACTUALLY SEND, not from a table here.
        # A shop that rewrote the message itself has its own blanks, and a second list in this
        # file would describe the library's while the send used his.
        card.blanks = [k for k in (fills_by_type or {}).get(tmpl_type, [])
                       if k in MANUAL_BLANKS]
        if enabled_types is not None and tmpl_type not in enabled_types:
            card.needs_enabling = True
            card.available = False
            # THE FIX IS OFFERED IN PLACE. Sending them to the settings screen and back is where
            # people stop — not because the task is hard, but because they lost their place.
            card.unavailable_reason = "غير مفعّل — اضغط للتفعيل"

        out.append(card)
    return out


def _behaviour(goal: str) -> str:
    trigger = GOAL_TRIGGER.get(goal, "manual")
    if trigger == "standing":
        return "تعمل تلقائياً كل يوم"
    if trigger == "scheduled":
        return "تُرسَل في موعد تحدّده"
    if goal == "awareness":
        return "مرة واحدة، ثم تُقفَل شهراً"
    return "تُرسَل مرة واحدة"


def lock_after_send(goal: str, *, now: int, sent: int) -> int:
    """When this goal becomes available again, or 0 for no lock.

    ONLY IF SOMETHING WENT OUT. Locking after a run that reached nobody costs the owner a month
    for a send that never happened — and they would have no way to tell the difference.
    """
    if goal != "awareness" or sent <= 0:
        return 0
    return now + 30 * DAY


def resolve_goal(goal: str) -> dict[str, Any]:
    """Everything the system needs from a goal the owner pressed.

    One place, so a new goal is a row in CARDS and a row in GOAL_TEMPLATE — not a change in four
    files where the fourth is forgotten.
    """
    if goal not in CARDS:
        raise ValueError(f"unknown goal {goal!r} — one of {sorted(CARDS)}")
    template_type, cls = GOAL_TEMPLATE[goal]
    return {"goal": goal, "template_type": template_type, "cls": cls,
            "trigger": GOAL_TRIGGER.get(goal, "manual"), "behaviour": _behaviour(goal)}
