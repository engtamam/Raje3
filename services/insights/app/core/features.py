"""What صفقات (renamed from فرصي, 2026-09-11 — same app, same key, new name) actually does for a
shop owner — one catalog, written as VALUE, not mechanism.
Same discipline as bookings-service's own `core/features.py` (the first pilot of the "features,
not services" architecture, 2026-09-11 CTO decision) — see that file's own docstring for the four
tests a candidate feature has to pass, and the owner's own framing that redirected every title in
this fleet toward money on 2026-09-11: «ايش بيستفيد؟ كيف يرفع مبيعاته أو يخليه يكسب؟».
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


INSIGHTS_FEATURES: tuple[Feature, ...] = (
    # MOVED TO FIRST (2026-09-11, owner's own instruction) — the daily "what do I do right now"
    # card is the single most actionable thing this app says; it now leads the shelf instead of
    # closing it.
    Feature(
        id="insights.tells_you_exactly_what_to_do",
        title="يقولك بالضبط وش تسوي اليوم",
        detail="من بين كل مؤشراتك، يختار لك خطوة وحدة أهم شي تسويها الآن — لا قائمة مؤشرات تايهة",
        icon="shield-check",
        tone=TONE_VIOLET,
        # `core/next_step.py` — a real priority queue over named rules (visits/messages/at-risk/
        # loyalty/services/staff), never a random pick: exactly one primary card and at most one
        # secondary from a DIFFERENT category, with a real cooldown so a rule that keeps matching
        # without being acted on stops repeating itself once it becomes wallpaper.
    ),
    Feature(
        id="insights.finds_real_bundles",
        title="يلقى لك صفقات جاهزة تبيعها",
        detail="يعرف أي خدمتين عملاءك فعلاً ياخذونها مع بعض، وتسوّي منهم باقة تربح أكثر بلا تخمين",
        icon="star",
        tone=TONE_AMBER,
        # `core/associations.py` — the product's own IP: lift measured on TWO axes (within one
        # receipt AND across a customer's own visits over time), which is what filters out a
        # "family receipt" (three people, one bill) from a REAL relationship worth building a
        # bundle on. Never shows the arithmetic — a verdict and a plain count only.
    ),
    Feature(
        id="insights.catches_missed_upsell",
        # REWORDED (2026-09-11, owner's own note): «فايتاك» read as slang, not a professional
        # sentence on a page that sells a paid app. Same value stated plainly instead.
        title="يكشف لك صفقة ناقصة عند عميلك",
        detail="عميل أخذ نص الصفقة بس، يعطيك اسمه فوراً عشان تكمّل البيع بدل ما يفوتك",
        icon="gift",
        tone=TONE_ROSE,
        # `core/bundles.py::build`/`associations.py::missed_opportunities` — customers who hold one
        # side of a real (or temporal) pair and not the other, turned into an actionable card with
        # a real customer COUNT (never a percentage of a base he hasn't seen), and never a price —
        # that decision stays his, always.
    ),
    Feature(
        id="insights.proves_your_messages_work",
        title="يثبت لك إن رسائلك ترجّع عملاء فعلاً",
        detail="يقارن مين رجع من اللي وصلته رسالة بمين ما وصلته، بالأرقام لا بالتخمين",
        icon="check-circle",
        tone=TONE_TEAL,
        # `core/indicators.py::holdout_comparison`/`returned_after_reminder` — the one number in
        # this product that is not our word for our own work: measured against a real held-back
        # tenth of the shop's own customers, and refuses to speak at all ("لم يكتمل القياس") rather
        # than claim a result from too small a sample.
    ),
    Feature(
        id="insights.weekly_shop_pulse",
        title="ملخص محلك كل أسبوع، بلا ما تحسب شي",
        detail="زياراتك، عملاؤك الجدد، اللي بيغادرونك، وأهم فرصة ضايعة — برسالة وحدة على واتساب",
        icon="clock",
        tone=TONE_BLUE,
        # `core/digest.py` — most owners never open a dashboard, so this is the highest-leverage
        # surface the app has: at most eight lines, degrades to complete SILENCE on a week with
        # nothing real to say (never "0 visits, 0 customers" — a verdict on his week dressed as data).
    ),
)


def public_features() -> list[dict[str, str | list[str]]]:
    return [
        {
            "id": f.id, "title": f.title, "detail": f.detail, "icon": f.icon, "tone": f.tone,
            "shared_with": list(f.shared_with), "owned_by": f.owned_by,
        }
        for f in INSIGHTS_FEATURES
    ]
