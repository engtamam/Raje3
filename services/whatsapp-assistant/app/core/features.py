"""What المساعد الذكي عبر واتساب actually does for a shop owner — one catalog, written as VALUE,
not mechanism. Same discipline as bookings-service's own `core/features.py` (the first pilot of
the "features, not services" architecture, 2026-09-11 CTO decision) — see that file's own
docstring for the four tests a candidate feature has to pass.

REWRITTEN 2026-09-11, SAME DAY — the first pass named the MECHANISM ("ما يكشف إنه يراقب") instead
of the MONEY. The owner's own words: «ايش بيستفيد؟ كيف يرفع مبيعاته أو يخليه يكسب؟». Every title
below now answers exactly that — more revenue, a loss avoided, or a customer who comes back —
never a description of how the code behaves internally.
"""
from __future__ import annotations

from dataclasses import dataclass

TONE_TEAL = "teal"
TONE_VIOLET = "violet"
TONE_AMBER = "amber"
TONE_ROSE = "rose"
TONE_BLUE = "blue"
TONES = frozenset({TONE_TEAL, TONE_VIOLET, TONE_AMBER, TONE_ROSE, TONE_BLUE})


@dataclass(frozen=True)
class Feature:
    id: str
    title: str
    detail: str
    icon: str
    tone: str
    shared_with: tuple[str, ...] = ()
    owned_by: str = ""

    def __post_init__(self) -> None:
        if self.tone not in TONES:
            raise ValueError(f"unknown tone {self.tone!r} on feature {self.id!r}")


WHATSAPP_FEATURES: tuple[Feature, ...] = (
    Feature(
        id="whatsapp.speaks_your_shop_tone",
        title="يبيع بصوت محلّك، لا بصوت آلة",
        detail="يرد بأسلوبك أنت ويعرف تفاصيل محلك من ملاحظاتك، فيثق فيه عميلك ويشتري أسرع",
        icon="message-circle",
        tone=TONE_VIOLET,
        # `build_system_prompt` (core/conversation.py:193-332) — the persona is a FUNCTION of the
        # shop's real name and the owner's own free-text notes, never a fixed script; notes are
        # appended LAST (after every rule, so nothing in them can talk the model out of a rule)
        # and redacted a second time independently of the write-time redaction already applied.
    ),
    Feature(
        id="whatsapp.books_without_double_booking",
        title="يقفل الحجز فوراً، قبل ما يروح لمنافس",
        detail="يحجز له من نفس المحادثة بلا خطأ ولا تعارض مواعيد يحرجك قدامه",
        icon="calendar",
        tone=TONE_BLUE,
        # `propose_booking`/`execute_confirmed_proposal` (core/tools.py:48, 571-611) — the model
        # can only PROPOSE; a real availability re-check happens both at proposal time and again at
        # confirm time, behind a short-TTL execution lock that closes a real double-tap/redelivery
        # race, plus an idempotency key on the actual write.
    ),
    Feature(
        id="whatsapp.fair_staff_assignment",
        title="يشغّل فريقك كله، لا موظف واحد بس",
        detail="يوزّع حجوزات الشات بعدل بين موظفينك، فتستفيد من طاقة محلك كاملة لا نص طاقتها",
        icon="users",
        tone=TONE_AMBER,
        # `core/booking_assignment.py::RealBookingProvider` — reuses the SAME merge-and-rank
        # engine the console's "أي متاح" picker uses (not a second, divergent algorithm), narrowed
        # by real per-service staff eligibility, with a customer's named-operator preference
        # honoured only when it does not override a shop that deliberately spreads a service
        # evenly across its team.
    ),
    Feature(
        id="whatsapp.smart_upsell",
        title="يرفع فاتورة كل عميل، بلا ما توظّف بائع",
        detail="يقترح له خدمة أو باقة تكمّل طلبه بذوق، فتبيع أكثر من نفس المحادثة",
        icon="gift",
        tone=TONE_ROSE,
        # The `upsell`/`growth` persona sections (core/conversation.py:254-278) — bounded by
        # structural filters the model cannot see around (context_builder.py's own eligible-
        # package list: active, scheduled soon, priced at or above the separate services), never a
        # cheaper package than what the customer already chose, and each angle offered at most once
        # per conversation.
    ),
    Feature(
        id="whatsapp.remembers_without_saying",
        title="يقنعه يرجع من أول رسالة",
        detail="يعرف وش يناسب كل عميل بالضبط ويقترحه بالوقت الصح، فيزيد رجوعه لمحلك",
        icon="star",
        tone=TONE_VIOLET,
        # `personalization` persona section (core/conversation.py:280-294) — what this service
        # learns about one customer (a service he returns to, one he stopped booking) shapes WHICH
        # suggestion the model reaches for, never a sentence it says back to him — an explicit,
        # regex-backstopped ban on "لاحظنا إنك..."-style disclosure.
    ),
    Feature(
        id="whatsapp.escalates_when_frustrated",
        title="ما يخسّرك عميل غاضب",
        detail="أي شكوى أو إلحاح توصل لفريقك فوراً، قبل لا يروح يشتكي أو يروح لمنافسك",
        icon="shield-check",
        tone=TONE_TEAL,
        # `detect_frustration`/`_requests_human` (core/frustration.py:23-52,
        # core/conversation.py:174+) — two cheap, no-LLM-call signals (repeated unconfirmed
        # proposals, or the same question asked again) plus a mandatory first-message triage gate
        # for "شكوى/اقتراح" that bypasses the model entirely — all route to the same human handoff.
    ),
    Feature(
        id="whatsapp.stops_pushing",
        title="ما ينفّر عميلك بالإلحاح",
        detail="لو رفض عرضين، يوقف عن البيع عليه ويخليه مرتاح — عميل مرتاح يرجع، عميل مزعوج لا",
        icon="check-circle",
        tone=TONE_BLUE,
        # `is_decline` (core/soft_decline.py:30-38) — after `soft_decline_threshold` short,
        # dismissive replies in one session, every PROMOTIONAL tool goes quiet for the rest of
        # it; direct requests (booking, cancel, reschedule) are never affected — only the pitching.
    ),
)


def public_features() -> list[dict[str, str | list[str]]]:
    return [
        {
            "id": f.id, "title": f.title, "detail": f.detail, "icon": f.icon, "tone": f.tone,
            "shared_with": list(f.shared_with), "owned_by": f.owned_by,
        }
        for f in WHATSAPP_FEATURES
    ]
