"""What makes a message go out — every one of them, in one list.

THE PROBLEM THIS SOLVES. "When does the system send?" had no answer anywhere. The visit confirmation
is decided in `scheduling.py`, the cycle reminder beside it, the ladder in `tick.py`, the points
notices in the loyalty service, the weekly report in insights, the standing campaigns in campaigns,
and the trial notice in operations. Seven files in five services, each holding a template name as a
literal — so adding a trigger meant editing four services, nobody could list what a shop actually
sends, and the owner's screen could not offer a switch for something the product could not
enumerate.

SO A TRIGGER IS A THING NOW. Each one says: what happens in the world, which message answers it,
what class it is, and WHICH BLANKS IT CAN FILL. That last field is the one that pays for the rest:
it is what lets an owner write his own text without writing an unsendable one — the editor offers
the blanks his trigger can supply and no others, so «رمز القسيمة» never appears while writing a
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

# ── the blanks a trigger can fill ──────────────────────────────────────────────────────────────
# Named for the OWNER, because these strings are what his editor shows on a chip. `customer` and
# `shop` are on every trigger and are not listed per trigger: slot 1 and slot 2 of every template
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


@dataclass(frozen=True)
class Trigger:
    """One reason a message exists."""

    id: str
    # What the OWNER calls it. Never a template name and never a class — he does not have those
    # words and does not need them (§10.8.1.2).
    label: str
    # When it fires, in his words. This is the sentence the screen shows under the label, and it
    # is here rather than in the screen so that the answer cannot drift from the behaviour.
    when: str
    cls: str
    # The default template type. The owner may point the trigger at his own approved text instead
    # (#235); this is what it does until he does.
    template_type: str
    # Beyond the customer's name and the shop's — see ALWAYS.
    slots: tuple[str, ...] = ()
    # Which service decides this one has happened. Recorded so a silent trigger can be traced to
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


TRIGGERS: tuple[Trigger, ...] = (
    Trigger(
        id="visit_recorded",
        label="سُجّلت زيارة",
        when="بعد تسجيل الزيارة بعشر دقائق — حين يكون قد غادر",
        cls="service", template_type="svc_visit_confirmation",
    ),
    Trigger(
        id="visit_redeemed",
        label="زيارة استُبدلت فيها نقاط",
        when="مع تأكيد الزيارة نفسه، حين يستبدل نقاطه عند الصندوق",
        cls="service", template_type="svc_visit_redeemed",
        slots=(REWARD, POINTS, BALANCE),
    ),
    Trigger(
        id="service_due",
        label="حان وقت الخدمة",
        when="حين تحين دورة العميل نفسه لهذه الخدمة — دورةٌ يتعلّمها النظام منه",
        cls="service", template_type="svc_service_reminder",
        slots=(SERVICE,),
    ),
    Trigger(
        id="after_visit",
        label="الاطمئنان بعد الزيارة",
        when="بعد الزيارة بأيام — ويُلغى تلقائياً إن عاد قبل موعده",
        cls="service", template_type="svc_follow_up",
        slots=(SERVICE,),
    ),
    Trigger(
        id="no_response",
        label="لم يردّ على التذكير",
        when="رسالة أو رسالتان بعد التذكير الأول، بنبرة أخرى — ثم تتوقف",
        cls="service", template_type="svc_service_reminder",
        slots=(SERVICE,),
    ),
    Trigger(
        id="balance_changed",
        label="تغيّر رصيده بلا زيارة",
        when="حين يتغيّر رصيد نقاطه من غير زيارة — تعديلٌ منك، أو انتهاء صلاحية",
        cls="personal", template_type="per_account_notice",
        slots=(ACTION, BALANCE), source="loyalty",
    ),
    Trigger(
        id="points_expiring",
        label="نقاطه على وشك الانتهاء",
        when="قبل انتهاء صلاحية نقاطه بمهلة",
        cls="personal", template_type="per_points_expiring",
        slots=(POINTS, ENDS_AT), source="loyalty",
    ),
    Trigger(
        id="reward_within_reach",
        label="رصيده صار يكفي مكافأة",
        when="حين يبلغ رصيده أول مكافأة يستطيع استبدالها",
        cls="marketing", template_type="mkt_loyalty_activation",
        slots=(POINTS, REWARD), source="campaigns",
    ),
    Trigger(
        id="gone_missing",
        label="تجاوز دورته ولم يعد",
        when="حين يمضي على زيارته مرّة ونصف دورته المعتادة",
        cls="marketing", template_type="mkt_winback",
        slots=(OFFER_VALUE, ENDS_AT), source="campaigns",
    ),
    Trigger(
        id="loyal_customer",
        label="بلغ عدد زيارات",
        when="حين يبلغ عدد زياراته الحدّ الذي اخترته",
        cls="marketing", template_type="mkt_loyalty_activation",
        slots=(POINTS, REWARD), source="campaigns",
    ),
    Trigger(
        id="personal_occasion",
        label="حلّت مناسبته",
        when="في تاريخه — ميلاده، أو سنة على أول زيارة",
        cls="marketing", template_type="mkt_personal_occasion",
        slots=(OFFER_VALUE, ENDS_AT), source="campaigns",
    ),
    Trigger(
        id="weekly_digest",
        label="ملخّصك الأسبوعي",
        when="مرة كل أسبوع — تقريرك أنت، لا رسالة لعميلك",
        cls="personal", template_type="per_weekly_digest",
        slots=(DIGEST,), source="insights",
    ),
    Trigger(
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

BY_ID = {t.id: t for t in TRIGGERS}
BY_TEMPLATE_TYPE: dict[str, tuple[str, ...]] = {}
for _t in TRIGGERS:
    BY_TEMPLATE_TYPE.setdefault(_t.template_type, ())
    BY_TEMPLATE_TYPE[_t.template_type] += (_t.id,)


def get(trigger_id: str) -> Trigger | None:
    return BY_ID.get(trigger_id)


def slots_for(trigger_id: str) -> tuple[str, ...]:
    """Every blank this trigger can fill, including the two on every message.

    THE EDITOR'S WHOLE GUARD RAIL. An owner writing his own text is offered these and nothing else,
    so a template that asks for a value nobody can supply cannot be composed — which is the failure
    that would otherwise appear weeks later as a message that silently never goes out.
    """
    t = BY_ID.get(trigger_id)
    return ALWAYS + t.slots if t else ()


def public(t: Trigger) -> dict:
    """What a screen may read. The class and the template name are ours, not his (§10.8.1.2)."""
    return {"id": t.id, "label": t.label, "when": t.when,
            "slots": list(ALWAYS + t.slots),
            "can_switch": t.owner_can_switch, "can_retext": t.owner_can_retext,
            "default_on": t.default_on}


# Kept out of `public()` on purpose — see its docstring. This is for our own screens and gates.
def internal(t: Trigger) -> dict:
    return {**public(t), "cls": t.cls, "template_type": t.template_type, "source": t.source}
