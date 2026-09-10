"""What المساعد الذكي عبر واتساب actually does for a shop owner — one catalog, written as VALUE,
not mechanism. Same discipline as bookings-service's own `core/features.py` (the first pilot of
the "features, not services" architecture, 2026-09-11 CTO decision) — see that file's own
docstring for the four tests a candidate feature has to pass.
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
        title="يتكلم بأسلوب محلّك أنت",
        detail="تكتب ملاحظاتك له، ويستخدمها يخدم عملاءك بمعلومات ما يعرفها من أي مكان ثاني",
        icon="message-circle",
        tone=TONE_VIOLET,
        # `build_system_prompt` (core/conversation.py:193-332) — the persona is a FUNCTION of the
        # shop's real name and the owner's own free-text notes, never a fixed script; notes are
        # appended LAST (after every rule, so nothing in them can talk the model out of a rule)
        # and redacted a second time independently of the write-time redaction already applied.
    ),
    Feature(
        id="whatsapp.books_without_double_booking",
        title="يحجز من المحادثة بلا تعارض",
        detail="يتحقق من الموعد لحظة ما يقترحه ولحظة ما يتأكد، فما يصير حجز مكرر أبداً",
        icon="calendar",
        tone=TONE_BLUE,
        # `propose_booking`/`execute_confirmed_proposal` (core/tools.py:48, 571-611) — the model
        # can only PROPOSE; a real availability re-check happens both at proposal time and again at
        # confirm time, behind a short-TTL execution lock that closes a real double-tap/redelivery
        # race, plus an idempotency key on the actual write.
    ),
    Feature(
        id="whatsapp.fair_staff_assignment",
        title="يوزّع حجوزات الشات على فريقك بعدالة",
        detail="نفس محرك توزيع الحجوزات اللي يستخدمه جدولك بالضبط، بلا فرق",
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
        title="يقترح الإضافة المناسبة بذوق",
        detail="باقة أو خدمة تكمّل طلبه، مرة وحدة بلطف، بلا إلحاح وبلا اختراع سعر",
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
        title="يخصّص اقتراحه بصمت",
        detail="يستخدم عادة العميل ليقرر وش يقترح له، بلا ما يقول له صراحة إنه يراقب زياراته",
        icon="star",
        tone=TONE_VIOLET,
        # `personalization` persona section (core/conversation.py:280-294) — what this service
        # learns about one customer (a service he returns to, one he stopped booking) shapes WHICH
        # suggestion the model reaches for, never a sentence it says back to him — an explicit,
        # regex-backstopped ban on "لاحظنا إنك..."-style disclosure.
    ),
    Feature(
        id="whatsapp.escalates_when_frustrated",
        title="يسلّمه لموظف بشري وقت الحاجة",
        detail="شكوى، طلب صريح، أو نفس السؤال يتكرر — يوصل لفريقك فوراً بلا ما ينتظر",
        icon="shield-check",
        tone=TONE_TEAL,
        # `detect_frustration`/`_requests_human` (core/frustration.py:23-52,
        # core/conversation.py:174+) — two cheap, no-LLM-call signals (repeated unconfirmed
        # proposals, or the same question asked again) plus a mandatory first-message triage gate
        # for "شكوى/اقتراح" that bypasses the model entirely — all route to the same human handoff.
    ),
    Feature(
        id="whatsapp.stops_pushing",
        title="يوقف عن الإلحاح إذا رفض العميل",
        detail="يرفض عرضين ترويجيين بنفس المحادثة، يتوقف عن البيع ويكمل يخدمه عادي",
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
