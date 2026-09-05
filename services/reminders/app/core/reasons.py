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

AND WHAT IS STILL DELIBERATELY ABSENT. Four texts sat in the library with nothing to fire them — an
appointment reminder, a ready-for-pickup, a review request and a free-slot offer. `booking_confirmed`
below is the FIRST of the five to be wired, now that a booking system exists
(docs/خطة-تنفيذ-الحجوزات.md); the appointment reminder and the free-slot offer follow it in that
product's own Stage 8, once there is a scheduled tick that knows a booking's time is approaching —
this registry only answers "which template", never "when". The review request folds into the
follow-up, which already asks «كل شيء تمام؟» and does not compete with the one button that collects
marketing consent. A registry that listed the rest before their triggers exist would describe a
product that does not exist yet.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core import links as L

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
APPT_TIME = "appt_time"      # a booking's day and hour, phrased by us — never the raw epoch
# THE TWO THAT ARE ADDRESSES, NOT WORDS. Every slot above is text we hold or a number we computed;
# these two are places a thumb has to reach, so core/links.py composes them from the fleet's public
# base and refuses when it is unset. They are on ALWAYS because both are true of every message: a
# customer may open his page from any of them, and marketing may not go out without a way to stop.
LINK = "link"                # his page: <base>/p/<ref>
STOP_LINK = "stop_link"      # one tap to stop marketing — a requirement, not a courtesy
INVITE = "invite"            # the last line of every utility text: the only way consent is given

# WHAT EVERY MESSAGE CARRIES, WHATEVER ITS REASON.
#
# `LINK` IS NOT ON THIS LIST, and that is a decision rather than an omission. It addresses the
# customer page, which portal has deleted outright — so a template offering it would invite
# somebody to open «صفحتك» and land on nothing at all. The constant and its composer stay in case a
# future page is ever built, but nothing may fill a template with it until then.
#
# `INVITE` replaces it as the address a utility message carries, because it resolves to a door that
# IS open — and it is the only door marketing consent can ever come through.
ALWAYS = (CUSTOMER, SHOP, INVITE, STOP_LINK)

# THE ADDRESS A MESSAGE OWES ITS READER, AND WHICH ONE DEPENDS ONLY ON THE CLASS.
MARKETING = "marketing"


def mandatory_tail(cls: str) -> str:
    """The blank that must be LAST in any message of this class, ours or the owner's own.

    MARKETING OWES A ONE-TAP STOP (§8.3) — it is a requirement rather than a courtesy, and a
    promotional message without it is one we cannot lawfully send. EVERYTHING ELSE OWES THE
    INVITATION, because it is the only door marketing consent can ever come through: a utility
    message that does not carry it is a dead end, and a shop whose every message is a dead end can
    never run a campaign at all.

    WHY THIS IS A FUNCTION AND NOT A TABLE IN EACH READER. `ci/gen_templates.py` enforces it over
    OUR library, the owner's own drafts are checked against it here, and the submission path fills
    it. Three readers, one sentence — and the day a fourth class of message exists, it is one edit
    rather than three that agree by luck.
    """
    return STOP_LINK if cls == MARKETING else INVITE


#: WHY IT IS THERE, in one line on his screen beside the locked chip. «إلزامي» with no reason reads
#: as our bureaucracy, and an owner who believes a rule is ours argues with it; one who knows whose
#: rule it is works with it. Kept here rather than in the console for the same reason the labels
#: are: a sentence living in the screen drifts from the thing it explains.
MANDATORY_NOTE = {
    STOP_LINK: "إلزامي نظاماً — نظام حماية البيانات يوجب أن يستطيع العميل الإيقاف بضغطة.",
    INVITE: "إلزامي — هو الباب الوحيد لموافقة العميل على عروضك.",
}

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
    APPT_TIME: "موعد الحجز",
    LINK: "رابط صفحته",
    STOP_LINK: "رابط الإيقاف",
    INVITE: "دعوة تفعيل المزايا",
}


# WHAT A CLASS IS CALLED ON HIS SCREEN. The five are the regulator's own division (§8.4, §8.6),
# and they are not a technical detail he can be spared: the class decides whether a message needs
# his customer's consent, whether it may go out between 10pm and 7am, what it counts against, and
# what Meta charges for it. A list of thirteen identical-looking rows hides all four.
CLASS_LABEL = {
    "service": "خدمية",
    "personal": "شخصية",
    "awareness": "توعوية",
    "warning": "تحذيرية",
    "marketing": "تسويقية",
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
        id="booking_confirmed",
        label="تأكيد حجز",
        when="بعد إنشاء الحجز بمهلة قصيرة تحتمل التراجع (نظام الحجوزات، `BOOKING_CONFIRM_DELAY_SECONDS`)",
        cls="service", template_type="svc_booking_confirmation",
        slots=(APPT_TIME,), source="bookings",
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
    "booking_confirmation": "booking_confirmed",
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
    APPT_TIME: "الأحد 9:00 مساءً",
    # THE TWO ADDRESSES, AND THEY NEEDED SAMPLES AS MUCH AS ANY WORD.
    #
    # `public()` builds the owner's chips from `SAMPLE.get(k, "")`, and neither of these was
    # in the table — so both chips rendered with an EMPTY example on the one screen where he
    # decides what his customers read. And `_examples()` in submission.py feeds the same table
    # to Meta's reviewer, who refuses a template whose placeholder has no example value.
}

# ── the two samples that are ADDRESSES, composed rather than typed ────────────────────────────
#
# WRITTEN AS LITERALS FIRST, AND A GATE REFUSED THEM: `check_a_link_a_customer_taps_is_absolute`
# bans a bare `/p/` path anywhere but `core/links.py`, and it was right to. A hand-typed example is
# a second definition of the URL shape — it drifts the day a path changes, and the drifted copy is
# the one Meta's reviewer reads and the one the owner sees on his own screen.
#
# Composed from the same functions the send path uses, so the example cannot be wrong about a shape
# the product actually produces.
_SAMPLE_BASE = "https://my.raje3.sa"
_SAMPLE_REF = L.reference_for("nakheel", "sub_rj7k2m")

SAMPLE[STOP_LINK] = L.stop_link(_SAMPLE_BASE, _SAMPLE_REF)
SAMPLE[INVITE] = f"ولك عندنا مزايا خاصة — فعّلها من هنا: {L.grant_link(_SAMPLE_BASE, _SAMPLE_REF)}"


def sample_slots(template: dict, *, establishment: str) -> dict[str, str]:
    """Fill a library template's numbered slots with example values, by each slot's own source.

    THE PREVIEW GOES THROUGH THE SAME `render()` THE SEND USES. A screen that formatted the body
    itself would show a message that renders here and fails there — and the one place that must
    never lie is the place he decides what his customers read.
    """
    fills = list(template.get("fills") or [])
    variables = list(template.get("variables") or [])
    by_source = {"system": "", "catalogue": SAMPLE[SERVICE], "owner": SAMPLE[FREE_TEXT],
                 "amount": SAMPLE[OFFER_VALUE], "code": SAMPLE[COUPON], "date": SAMPLE[ENDS_AT],
                 # BY SOURCE, NEVER BY POSITION. The address lands on slot 3 in a visit
                 # confirmation and on slot 6 in an offer, so the numbered fallback below
                 # would have drawn «غيار الزيت» where the owner expects to see a link.
                 "invite": SAMPLE[INVITE], "stop_link": SAMPLE[STOP_LINK]}
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
    """What a screen may read. The TEMPLATE NAME is ours, not his (§10.8.1.2) — the class is not.

    THAT IS A REVERSAL, AND IT IS DELIBERATE. This used to withhold both on the same reasoning:
    an owner does not have our words and does not need them. True of a template name, which is an
    identifier at Meta and means nothing to him. Not true of the class.

    The class is the one fact that decides whether a message needs his customer's explicit consent,
    whether it may go out inside the quiet window (10pm–7am, §8.6), what it counts against, and
    what Meta charges him for it. Withholding it left «متى نرسل» a flat list of thirteen sentences
    that look alike and behave nothing alike — and the owner, who carries the fine, could not tell
    which was which.
    """
    return {"id": t.id, "label": t.label, "when": t.when,
            # HIS WORD FOR IT, NOT OURS. `cls` is the key the screen colours by; `cls_label` is what
            # it prints. Sending only the key would make the screen invent the Arabic, which is how
            # a name drifts from the thing it names.
            "cls": t.cls, "cls_label": CLASS_LABEL.get(t.cls, t.cls),
            # ID AND LABEL TOGETHER. The editor stores the id and shows the label; sending only
            # ids would make the screen invent names, and only labels would make it guess ids.
            # THE PALETTE HE MAY ADD FROM — and the mandatory address is NOT in it. The server puts
            # that one at the end of every text (custom_templates.with_mandatory_tail); offering it
            # as a chip would let him place a second one mid-sentence, which the draft path then
            # refuses. A palette whose choices can be refused is a palette that teaches by error.
            "slots": [{"id": k, "label": SLOT_LABEL.get(k, k), "sample": SAMPLE.get(k, "")}
                      for k in ALWAYS + t.slots if k != mandatory_tail(t.cls)],
            # AND THE ONE HE CANNOT REMOVE, sent so the editor can show it LOCKED rather than
            # absent. An owner who does not see it in his text believes it is not in his text —
            # and the first he learns otherwise is a customer's reply, or a regulator's letter.
            # The screen never derives WHICH address it is: that rule has one owner, above.
            "mandatory": {"id": mandatory_tail(t.cls),
                          "label": SLOT_LABEL.get(mandatory_tail(t.cls), ""),
                          "sample": SAMPLE.get(mandatory_tail(t.cls), ""),
                          "note": MANDATORY_NOTE[mandatory_tail(t.cls)]},
            "can_switch": t.owner_can_switch, "can_retext": t.owner_can_retext,
            "default_on": t.default_on}


# Kept out of `public()` on purpose — see its docstring. This is for our own screens and gates.
def internal(t: Reason) -> dict:
    return {**public(t), "cls": t.cls, "template_type": t.template_type, "source": t.source}
