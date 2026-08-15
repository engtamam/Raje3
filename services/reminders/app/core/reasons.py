"""What makes a message go out — every one of them, in one list.

THE PROBLEM THIS SOLVES. "When does the system send?" had no answer anywhere. The visit confirmation
is decided in `scheduling.py`, the cycle reminder beside it, the ladder in `tick.py`, the points
notices in the loyalty service, the weekly report in insights, the standing campaigns in campaigns,
and the trial notice in operations. Seven files in five services, each holding a template name as a
literal — so adding a reason meant editing four services, nobody could list what a shop actually
sends, and the owner's screen could not offer a switch for something the product could not
enumerate.

SO A TRIGGER IS A THING NOW. Each one says: what happens in the world, which message answers it,
what class it is, and WHICH BLANKS IT CAN FILL. That last field is the one that pays for the rest:
it is what lets an owner write his own text without writing an unsendable one — the editor offers
the blanks his reason can supply and no others, so «رمز القسيمة» never appears while writing a
visit confirmation, and a template that would have failed at render is impossible to compose.

WHAT IS NOT HERE. The firing itself. This is a registry, not a scheduler: `scheduling.py` still
decides when a cycle is due, loyalty still decides when a balance changed. They ask this module
which template answers their event, and the answer stops being a literal in five places.

AND WHAT IS DELIBERATELY ABSENT. Five texts sat in the library with nothing to fire them — a
booking confirmation, an appointment reminder, a ready-for-pickup, a review request and a free-slot
offer. Three need a booking system this product does not have and has decided not to build yet; the
review request folds into the follow-up, which already asks «كل شيء تمام؟» and does not compete
with the one button that collects marketing consent. A registry that listed them would describe a
product that does not exist.
"""
from __future__ import annotations

from dataclasses import dataclass

# ── the blanks a reason can fill ──────────────────────────────────────────────────────────────
# Named for the OWNER, because these strings are what his editor shows on a chip. `customer` and
# `shop` are on every reason and are not listed per reason: slot 1 and slot 2 of every template
# in the library, always available, never a choice.
CUSTOMER = "customer"
SHOP = "shop"
SERVICE = "service"          # what he came for, or what is due
REWARD = "reward"            # what he redeemed
POINTS = "points"            # how many
BALANCE = "balance"          # what is left after
ACTION = "action"            # what just happened to his account, in our words
DIGEST = "digest"            # the week in one line, composed by us
OFFER_VALUE = "offer_value"  # «20%» or «50 ريال» — typed, never a sentence
COUPON = "coupon"            # a code, one per customer, machine-made
ENDS_AT = "ends_at"          # the last day, phrased by us
FREE_TEXT = "free_text"      # his own line — at most one per message (§8.4.2)
CODE = "code"                # a one-time code the customer is waiting for
MINUTES = "minutes"          # how long that code lives

ALWAYS = (CUSTOMER, SHOP)

# WHAT A BLANK IS CALLED ON HIS SCREEN. Here rather than in the console for the same reason the
# labels are: a name kept in the screen drifts from the thing it names, and a chip reading «الخدمة»
# over a blank we fill with a reward is a message he did not write.
SLOT_LABEL = {
    CUSTOMER: "اسم العميل",
    SHOP: "اسم محلّك",
    SERVICE: "الخدمة",
    REWARD: "المكافأة",
    POINTS: "النقاط",
    BALANCE: "الرصيد",
    ACTION: "ما تمّ",
    DIGEST: "ملخّص الأسبوع",
    OFFER_VALUE: "قيمة الخصم",
    COUPON: "رمز القسيمة",
    ENDS_AT: "ينتهي في",
    FREE_TEXT: "نصّك",
    CODE: "الرمز",
    MINUTES: "المدة",
}


@dataclass(frozen=True)
class Reason:
    """One reason a message exists."""

    id: str
    # What the OWNER calls it. Never a template name and never a class — he does not have those
    # words and does not need them (§10.8.1.2).
    label: str
    # When it fires, in his words. This is the sentence the screen shows under the label, and it
    # is here rather than in the screen so that the answer cannot drift from the behaviour.
    when: str
    cls: str
    # The default template type. The owner may point the reason at his own approved text instead
    # (#235); this is what it does until he does.
    template_type: str
    # Beyond the customer's name and the shop's — see ALWAYS.
    slots: tuple[str, ...] = ()
    # Which service decides this one has happened. Recorded so a silent reason can be traced to
    # the thing that should have fired it, rather than searched for across five repositories.
    source: str = "reminders"
    # ON FOR A SHOP THAT HAS SET NOTHING. The engine is what he bought; a product whose messages
    # all arrive switched off is a product that does nothing on the day it is installed.
    default_on: bool = True
    # Whether the owner may switch it off at all. Three may not: a privacy code is a legal right
    # with a statutory clock, and switching it off would be switching off somebody else's right.
    owner_can_switch: bool = True
    # Whether he may point it at his own text. The same three are closed, for the same reason.
    owner_can_retext: bool = True


REASONS: tuple[Reason, ...] = (
    Reason(
        id="visit_recorded",
        label="سُجّلت زيارة",
        when="بعد تسجيل الزيارة بعشر دقائق — حين يكون قد غادر",
        cls="service", template_type="svc_visit_confirmation",
    ),
    Reason(
        id="visit_redeemed",
        label="زيارة استُبدلت فيها نقاط",
        when="مع تأكيد الزيارة نفسه، حين يستبدل نقاطه عند الصندوق",
        cls="service", template_type="svc_visit_redeemed",
        slots=(REWARD, POINTS, BALANCE),
    ),
    Reason(
        id="service_due",
        label="حان وقت الخدمة",
        when="حين تحين دورة العميل نفسه لهذه الخدمة — دورةٌ يتعلّمها النظام منه",
        cls="service", template_type="svc_service_reminder",
        slots=(SERVICE,),
    ),
    Reason(
        id="after_visit",
        label="الاطمئنان بعد الزيارة",
        when="بعد الزيارة بأيام — ويُلغى تلقائياً إن عاد قبل موعده",
        cls="service", template_type="svc_follow_up",
        slots=(SERVICE,),
    ),
    Reason(
        id="no_response",
        label="لم يردّ على التذكير",
        when="رسالة أو رسالتان بعد التذكير الأول، بنبرة أخرى — ثم تتوقف",
        cls="service", template_type="svc_service_reminder",
        slots=(SERVICE,),
    ),
    Reason(
        id="balance_changed",
        label="تغيّر رصيده بلا زيارة",
        when="حين يستبدل نقاطه ولا تكون له زيارة مسجّلة تحمل الخبر",
        cls="personal", template_type="per_account_notice",
        slots=(ACTION, BALANCE), source="loyalty",
    ),
    Reason(
        id="points_expiring",
        label="نقاطه على وشك الانتهاء",
        when="قبل انتهاء صلاحية نقاطه بمهلة",
        cls="personal", template_type="per_points_expiring",
        slots=(POINTS, ENDS_AT), source="loyalty",
    ),
    Reason(
        id="reward_within_reach",
        label="رصيده صار يكفي مكافأة",
        when="حين يبلغ رصيده أول مكافأة يستطيع استبدالها",
        cls="marketing", template_type="mkt_loyalty_activation",
        slots=(POINTS, REWARD), source="campaigns",
    ),
    Reason(
        id="gone_missing",
        label="تجاوز دورته ولم يعد",
        when="حين يمضي على زيارته مرّة ونصف دورته المعتادة",
        cls="marketing", template_type="mkt_winback",
        slots=(OFFER_VALUE, ENDS_AT), source="campaigns",
    ),
    Reason(
        id="loyal_customer",
        label="بلغ عدد زيارات",
        when="حين يبلغ عدد زياراته الحدّ الذي اخترته",
        cls="marketing", template_type="mkt_loyalty_activation",
        slots=(POINTS, REWARD), source="campaigns",
    ),
    Reason(
        id="personal_occasion",
        label="حلّت مناسبته",
        when="في تاريخه — ميلاده، أو سنة على أول زيارة",
        cls="marketing", template_type="mkt_personal_occasion",
        slots=(OFFER_VALUE, ENDS_AT), source="campaigns",
    ),
    Reason(
        id="weekly_digest",
        label="ملخّصك الأسبوعي",
        when="مرة كل أسبوع — تقريرك أنت، لا رسالة لعميلك",
        cls="personal", template_type="per_weekly_digest",
        slots=(DIGEST,), source="insights",
    ),
    Reason(
        id="privacy_code",
        label="رمز طلب البيانات",
        when="حين يطلب عميلك نسخة من بياناته أو حذفها",
        cls="personal", template_type="per_dsar_code",
        slots=(CODE, MINUTES), source="portal",
        # A STATUTORY RIGHT WITH A CLOCK RUNNING (§14). Switching it off would be switching off
        # somebody else's right, and rewording it would reword a legal notice.
        owner_can_switch=False, owner_can_retext=False,
    ),
)

BY_ID = {t.id: t for t in REASONS}
BY_TEMPLATE_TYPE: dict[str, tuple[str, ...]] = {}
for _t in REASONS:
    BY_TEMPLATE_TYPE.setdefault(_t.template_type, ())
    BY_TEMPLATE_TYPE[_t.template_type] += (_t.id,)


def get(reason_id: str) -> Reason | None:
    return BY_ID.get(reason_id)


def slots_for(reason_id: str) -> tuple[str, ...]:
    """Every blank this reason can fill, including the two on every message.

    THE EDITOR'S WHOLE GUARD RAIL. An owner writing his own text is offered these and nothing else,
    so a template that asks for a value nobody can supply cannot be composed — which is the failure
    that would otherwise appear weeks later as a message that silently never goes out.
    """
    t = BY_ID.get(reason_id)
    return ALWAYS + t.slots if t else ()


# ── from a scheduled row back to the reason that made it ────────────────────────────────────
# The row records `kind` (what the scheduler called it) and `template_type` (what it will send).
# Neither alone is enough: two reasons share `svc_service_reminder` — the cycle reminder and the
# ladder rung that follows it — and they are separate switches because an owner who wants
# reminders may not want to be reminded of the reminder.
_BY_KIND = {
    "visit_confirmation": "visit_recorded",
    "reminder": "service_due",
    "follow_up": "after_visit",
}


def for_row(kind: str, template_type: str) -> str:
    """Which reason produced this schedule. Empty when we cannot tell.

    EMPTY IS NOT A FAILURE HERE. An unrecognised row keeps sending — a switch we cannot attribute
    must not silence a message the shop is expecting, and the alternative (guess a reason) would
    apply somebody else's switch to it.
    """
    if kind.startswith("ladder_"):
        return "no_response"
    if kind in _BY_KIND:
        return _BY_KIND[kind]
    ids = BY_TEMPLATE_TYPE.get(template_type, ())
    return ids[0] if len(ids) == 1 else ""


def candidates(kind: str, template_type: str) -> tuple[str, ...]:
    """Every reason this message could belong to — for the paths that only know a template type.

    A PEER SEND CARRIES NO `kind`. loyalty, insights and campaigns hand us a template type and a
    class, and one type can serve two reasons (`mkt_loyalty_activation` answers both "his balance
    reaches a reward" and "he became a regular"). So the switch is honoured only when EVERY
    reason that could have produced this message is off — silencing on a guess would switch off a
    message the owner never touched.
    """
    one = for_row(kind, template_type)
    if one:
        return (one,)
    return BY_TEMPLATE_TYPE.get(template_type, ())


# ── what a preview puts in each blank ────────────────────────────────────────────────────────
# EXAMPLE VALUES, AND THEY ARE NOT DECORATION. The owner is choosing between three wordings; a
# preview showing «أهلاً {{1}}» asks him to imagine the message rather than read it. Values that
# look like a real customer's are also the ones Meta's own review requires at submission.
SAMPLE = {
    CUSTOMER: "محمد",
    SERVICE: "غيار الزيت",
    REWARD: "غسيل مجاني",
    POINTS: "40",
    BALANCE: "60",
    ACTION: "استبدال نقاطك",
    DIGEST: "3 زيارات هذا الأسبوع",
    OFFER_VALUE: "20%",
    COUPON: "RJ-4F2K",
    ENDS_AT: "21 أغسطس",
    FREE_TEXT: "افتتحنا فرعاً جديداً",
    CODE: "4821",
    MINUTES: "15",
}


def sample_slots(template: dict, *, establishment: str) -> dict[str, str]:
    """Fill a library template's numbered slots with example values, by each slot's own source.

    THE PREVIEW GOES THROUGH THE SAME `render()` THE SEND USES. A screen that formatted the body
    itself would show a message that renders here and fails there — and the one place that must
    never lie is the place he decides what his customers read.
    """
    fills = list(template.get("fills") or [])
    variables = list(template.get("variables") or [])
    by_source = {"system": "", "catalogue": SAMPLE[SERVICE], "owner": SAMPLE[FREE_TEXT],
                 "amount": SAMPLE[OFFER_VALUE], "code": SAMPLE[COUPON], "date": SAMPLE[ENDS_AT]}
    # Slot 3 of the library's own numbering is «الخدمة أو المحتوى», 4 «تفصيل», 5 «الرصيد» — the
    # positional meanings the texts were written against (deploy/seed/templates.json).
    by_number = {1: SAMPLE[CUSTOMER], 2: establishment, 3: SAMPLE[SERVICE],
                 4: SAMPLE[POINTS], 5: SAMPLE[BALANCE]}
    out: dict[str, str] = {}
    for i, number in enumerate(variables):
        source = fills[i] if i < len(fills) else "system"
        value = by_source.get(source) or ""
        if not value:
            value = by_number.get(number, SAMPLE[FREE_TEXT])
        out[str(number)] = value
    return out


def public(t: Reason) -> dict:
    """What a screen may read. The class and the template name are ours, not his (§10.8.1.2)."""
    return {"id": t.id, "label": t.label, "when": t.when,
            # ID AND LABEL TOGETHER. The editor stores the id and shows the label; sending only
            # ids would make the screen invent names, and only labels would make it guess ids.
            "slots": [{"id": k, "label": SLOT_LABEL.get(k, k), "sample": SAMPLE.get(k, "")}
                      for k in ALWAYS + t.slots],
            "can_switch": t.owner_can_switch, "can_retext": t.owner_can_retext,
            "default_on": t.default_on}


# Kept out of `public()` on purpose — see its docstring. This is for our own screens and gates.
def internal(t: Reason) -> dict:
    return {**public(t), "cls": t.cls, "template_type": t.template_type, "source": t.source}
