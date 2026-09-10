"""What الحملات actually does for a shop owner — one catalog, written as VALUE, not mechanism.
Same discipline as bookings-service's own `core/features.py` (the first pilot of the "features,
not services" architecture, 2026-09-11 CTO decision) — see that file's own docstring for the four
tests a candidate feature has to pass.

TWO TEMPTING CANDIDATES, CHECKED DIRECTLY AND EXCLUDED — same discipline as loyalty's own catalog:
- "مجموعة تحكم لإثبات الأثر" (holdout testing) is NOT this service's own code — no `holdout.py`,
  no split logic anywhere in `core/`. It is entirely `services/reminders/app/core/holdout.py`;
  campaigns' own `audience.resolve()` only calls INTO it via a `gate_check` predicate reminders
  supplies.
- "يقيس مين رجع بسببك" (attribution/return measurement) is NOT this service's own code either —
  `core/report.py` reports SEND-TIME delivery outcomes only (matched/sent/suppressed/failed). The
  real "did they come back because of this" number (`holdout_comparison`/`returned_after_reminder`)
  is `services/insights/app/core/indicators.py`'s own work, surfaced through فرصي's own future
  catalog, not claimed here even though this app's own `apps.ts`-style description used to imply it.

REWRITTEN 2026-09-11, SAME DAY AS BOOKINGS' OWN — the first pass named what the code DOES; the
owner's own words asked what he GETS from it («ايش بيستفيد؟»). Every title now answers with money,
a loss avoided, or a customer who comes back.
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


CAMPAIGNS_FEATURES: tuple[Feature, ...] = (
    Feature(
        id="campaigns.smart_targeting",
        title="يرجّع لك زباينك القدام",
        detail="يعرف مين ابتعد عنك فعلاً حسب عادته هو، فيصل عرضك بالوقت الصح ويرجع",
        icon="users",
        tone=TONE_VIOLET,
        # `audience.resolve`'s own `win_back` rule (core/audience.py:1-140) — no visit for longer
        # than THAT customer's OWN learned interval (never a fixed 60 days for every shop): a
        # weekly-visit customer is absent after three weeks, a six-month workshop customer is not
        # absent until six months. The owner never types a segment — four goal cards, and this
        # decides who each one actually reaches.
    ),
    Feature(
        id="campaigns.wont_pitch_too_early",
        title="ما يحرق عليك عرضك",
        detail="ما يعرض عليه خدمة أخذها قريب، فيوصل عرضك مؤثر لما فعلاً يحتاجه",
        icon="clock",
        tone=TONE_BLUE,
        # `_too_early` (core/audience.py:94-113) — a real cycle-lock: an offer on a service reaches
        # a customer only once he is at least 70% through his OWN learned cycle for it. Below that
        # the need has not formed and the offer is noise; a customer never seen for that service is
        # never excluded by it (silence would wrongly lock out every new customer).
    ),
    Feature(
        id="campaigns.paced_sending",
        title="يوصّل عرضك لكل عملائك، بلا استثناء",
        detail="يحسب أيام الإرسال قبل ما تضغط، ويحذّرك لو عرضك بينتهي قبل ما يوصل الكل",
        icon="cloud",
        tone=TONE_TEAL,
        # `spread.plan` (core/spread.py:72+) — divides only the campaign's OWN share of the daily
        # WhatsApp ceiling (never the automatic-message reserve — a confirmation for tonight's
        # walk-in is not the campaign's to spend), spreads at-risk customers first so nobody waits
        # for no reason, and REFUSES at launch — never sending to whoever fits — when an offer's
        # own end date cannot reach the whole audience in time.
    ),
    Feature(
        id="campaigns.no_double_launch",
        title="يحميك من دفع فلوسك مرتين",
        detail="لو ضغطت \"أطلق\" مرتين بالغلط، ما ترسل الحملة مرتين وتدفع مرتين على عملاء بلا داعي",
        icon="check-circle",
        tone=TONE_ROSE,
        # `Press` (core/press.py) — the claim key is built from what the OWNER chose (goal, text,
        # service, branch, offer, end date), never from the attempt itself, and claimed atomically
        # BEFORE the campaign exists — so a double-tap, or a reload during a slow send to a large
        # audience, can never create two campaigns that pay twice against the shop's own ceiling.
    ),
    Feature(
        id="campaigns.booking_in_message",
        title="يحوّل رسالتك لحجز فوري",
        detail="لو عندك تطبيق الحجوزات، عميلك يحجز من نفس الرسالة بلا ما يتصل أو ينسى",
        icon="calendar",
        tone=TONE_AMBER,
        # `shape.py` — NOT a shared-feature entry (this is campaigns' OWN decision, not another
        # app's engine granted through this one): for the three "come back" message types
        # (win-back, occasion, offer), a shop that ALSO owns الحجوزات gets a real in-WhatsApp
        # booking Flow under the message instead of plain text — decided purely by entitlement,
        # never by the campaign's own goal or a per-send switch, since an entitlement can change
        # after a campaign is already authored.
    ),
)


def public_features() -> list[dict[str, str | list[str]]]:
    return [
        {
            "id": f.id, "title": f.title, "detail": f.detail, "icon": f.icon, "tone": f.tone,
            "shared_with": list(f.shared_with), "owned_by": f.owned_by,
        }
        for f in CAMPAIGNS_FEATURES
    ]
