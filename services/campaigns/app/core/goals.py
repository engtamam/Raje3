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
from app.core.tick import DEFAULT_AWARENESS_LOCK_DAYS

DAY = 86400

# THE KINDS HE FILLS HIMSELF. `system` is ours — his name, the shop, a balance — and never a
# question. `catalogue` is a tap on his own service list rather than typing; the two typed ones
# have a shape we can check, which is the whole reason «خصم كبير» cannot be sent; and `owner` is
# the single free blank, where the sentence has nothing but his own words to put in it.
MANUAL_BLANKS = ("catalogue", "amount", "date", "owner")

# THE GROUPS A RAIL/FILTER CAN ORGANISE THE CARDS BY, in the order they should be offered — not
# a fourth thing to keep in sync by hand: every CARDS row below names one of these, and this is
# the one place their order and label live. Four buckets for seven goals today; a new goal picks
# an existing bucket or, if it truly needs one, adds a line here and the console's filter grows
# with it — no screen anywhere invents its own grouping.
GOAL_CATEGORIES = ["عروض وخصومات", "ولاء وعودة", "مناسبات", "إعلانات وتوعية"]

# What each card says. Two words and a line — the owner is choosing, not reading.
CARDS = {
    "win_back": {
        "title": "رجّع اللي غابوا",
        "line": "من تأخّر عن موعده المعتاد",
        "icon": "return",
        "category": "ولاء وعودة",
    },
    "reward_loyal": {
        "title": "كافئ المخلصين",
        "line": "الأكثر زيارة عندك",
        "icon": "gift",
        "category": "ولاء وعودة",
    },
    "announce": {
        "title": "أعلن جديدك",
        "line": "خبر أو عرض للجميع",
        "icon": "megaphone",
        "category": "إعلانات وتوعية",
    },
    "occasion": {
        "title": "هنّئ في مناسبة",
        "line": "رسالة في يوم يخصّه",
        "icon": "cake",
        "category": "مناسبات",
    },
    "awareness": {
        "title": "وعِّ عملاءك",
        "line": "نصيحة تخصّ ما أخذوه",
        "icon": "info",
        "category": "إعلانات وتوعية",
    },
    "service_offer": {
        "title": "عرض على خدمة",
        # THE LINE IS THE RULE, IN HIS WORDS. He is not told about a threshold or a cycle — he is
        # told who it reaches, and that sentence is the whole of what he needs to trust it.
        "line": "لمن قارب موعد خدمة معيّنة",
        "icon": "tag",
        "category": "عروض وخصومات",
    },
    "package_offer": {
        "title": "عرض على باقة",
        # NO CYCLE HERE, UNLIKE service_offer'S LINE — a package has no single rhythm to be "قارب
        # موعده" for (GOAL_TEMPLATE's own note), so the honest sentence is simply who it reaches:
        # everyone, the same as an announcement, with the message naming the package itself.
        "line": "روّج لباقة كاملة بسعرها الحقيقي",
        "icon": "tag",
        "category": "عروض وخصومات",
    },
}


@dataclass
class Card:
    goal: str
    title: str
    line: str
    icon: str
    # ONE OF `GOAL_CATEGORIES` — how a rail/filter groups this card, from CARDS' own row. Never
    # invented on a screen: a console that made up its own grouping would drift from this the
    # first time a goal moved buckets or a new one arrived in neither's list.
    category: str = ""
    # HOW MANY TIMES THIS GOAL HAS BEEN LAUNCHED, and how many customers it has actually reached
    # — from the side counter (`app.core.goal_stats`), never a screen-invented number. Zero for a
    # goal never used, which is the honest answer, not an absent field a console would have to
    # guess a fallback for.
    uses: int = 0
    reach: int = 0
    # Whether it can be pressed right now.
    available: bool = True
    # Why not, in the owner's words, ON the card. Never in a tooltip, never in a modal after they
    # press it: a card that looks pressable and then refuses is worse than one that says so.
    unavailable_reason: str = ""
    # How it behaves, as a sentence rather than a type. "Runs every day" is a fact they can hold;
    # "standing" is a word they would have to learn.
    behaviour: str = ""
    # KEPT SO THE CONSOLE CAN STYLE THE BADGE — but it names no action any more. It used to promise
    # «اضغط للتفعيل» on a card the same code marked `disabled`, which was never true: an owner never
    # sees the words «قالب» or «اعتماد» (Messages.tsx's own rule, §10.8), so there is no screen a tap
    # could open, and the button underneath the badge could not be pressed either way. What he
    # actually needs is WHY, in `unavailable_reason` below — reminders' own sentence, not a guess.
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
    # ONE WORD, THE SAME ONE THE ADMIN PANEL'S OWN TEMPLATE SCREEN SHOWS — approved | pending |
    # rejected | paused | disabled | not_registered | not_seeded | unknown (reminders'
    # `rendering.type_status`). Never guessed here: a card that is `available` can still be
    # "pending" (Meta has not caught up with THIS establishment's own account yet, even though
    # the type is seeded and usable in general) — the owner is entitled to see which, not just
    # whether he may press the card right now.
    template_status: str = "unknown"


def cards(*, now: int, fills_by_type: dict[str, list[str]] | None = None, locks: dict[str, int] | None = None,
          enabled_types: set[str] | None = None, blocked_reasons: dict[str, str] | None = None,
          statuses: dict[str, str] | None = None,
          stats: dict[str, dict[str, int]] | None = None) -> list[Card]:
    """The five cards, in the order an owner should see them.

    `locks` maps goal → locked_until. `enabled_types` is which template types this tenant can
    actually send right now (spec §10.8); a goal whose type is not in it is shown, never hidden —
    hiding it means an owner who wants it cannot find out it exists — but locked, WITH THE REAL
    REASON reminders computed (`blocked_reasons`, keyed by template type): under review at Meta, or
    never seeded. Guessing a reason here would be a second, possibly wrong, version of a fact one
    call away.

    `statuses` is the badge itself — one word per template type (`rendering.type_status`), shown
    on every card whether it is available or not, so an owner can see "pending" without having to
    press a locked card to learn why.
    """
    locks = locks or {}
    statuses = statuses or {}
    stats = stats or {}
    out: list[Card] = []
    for goal, meta in CARDS.items():
        goal_stats = stats.get(goal) or {}
        card = Card(goal=goal, title=meta["title"], line=meta["line"], icon=meta["icon"],
                    category=meta.get("category", ""),
                    uses=int(goal_stats.get("uses") or 0), reach=int(goal_stats.get("reach") or 0),
                    behaviour=_behaviour(goal), offers=offers_something(goal))

        until = int(locks.get(goal) or 0)
        if until > now:
            days = max(1, (until - now + DAY - 1) // DAY)
            card.available = False
            # A NUMBER, not a date. "Available in 23 days" is arithmetic an owner does not have to
            # do; a date is arithmetic they do.
            card.unavailable_reason = f"متاح بعد {days} يوم"

        tmpl_type = GOAL_TEMPLATE.get(goal, ("", ""))[0]
        card.template_status = statuses.get(tmpl_type, "unknown")
        # THE BLANKS COME FROM THE TEMPLATE THIS SHOP WOULD ACTUALLY SEND, not from a table here.
        # A shop that rewrote the message itself has its own blanks, and a second list in this
        # file would describe the library's while the send used his.
        card.blanks = [k for k in (fills_by_type or {}).get(tmpl_type, [])
                       if k in MANUAL_BLANKS]
        if enabled_types is not None and tmpl_type not in enabled_types:
            card.needs_enabling = True
            card.available = False
            # REMINDERS' OWN SENTENCE — BUT NEVER ITS OWN WORDS FOR THE TEMPLATE. It already tells
            # the two truths apart — «قوالب …
            # قيد مراجعة واتساب» resolves itself in hours and needs nothing from him; «لا يوجد قالب
            # فعّال» is ours to fix, not his. The one line this used to hardcode («غير مفعّل — اضغط
            # للتفعيل») was wrong on both counts: nothing here is a switch he owns, and the card is
            # `disabled` below regardless, so the tap it promised never did anything.
            reason = (blocked_reasons or {}).get(tmpl_type, "")
            # `tmpl_type` ITSELF NEVER REACHES THE CARD. reminders' sentence is written for its own
            # logs and names the internal template type verbatim ("قوالب mkt_winback ما زالت قيد
            # مراجعة واتساب") — an internal identifier, not a word an owner has ever been shown
            # anywhere else in the product. Swapped for the card's own title, which already IS the
            # owner-facing name for exactly this goal.
            if reason and tmpl_type:
                reason = reason.replace(tmpl_type, card.title)
            card.unavailable_reason = reason or "هذا الهدف غير متاح حالياً — نعمل على تفعيله."

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


def lock_after_send(goal: str, *, now: int, sent: int,
                    lock_days: int = DEFAULT_AWARENESS_LOCK_DAYS) -> int:
    """When this goal becomes available again, or 0 for no lock.

    ONLY IF SOMETHING WENT OUT. Locking after a run that reached nobody costs the owner a month
    for a send that never happened — and they would have no way to tell the difference.

    `lock_days` DEFAULTS TO THE SAME CONSTANT THE STANDING/TICK PATH USES — fixed 2026-09-12, a
    real gap a QA audit found: this manual-create path hardcoded `30 * DAY` directly, while
    `tick.py`'s own standing-campaign path already reads the configurable `AWARENESS_LOCK_DAYS`
    setting. Both agreed only by coincidence (the setting's own default is also 30) — the day an
    operator changed AWARENESS_LOCK_DAYS, the two paths would have silently disagreed about when
    the SAME lock reopens. The caller (the manual-create route) now passes the same setting
    tick.py's own container wiring already reads.
    """
    if goal != "awareness" or sent <= 0:
        return 0
    return now + int(lock_days) * DAY


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
