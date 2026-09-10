"""What برنامج النقاط actually does for a shop owner — one catalog, written as VALUE, not
mechanism. Same discipline, same wire shape, as bookings-service's own `core/features.py` (the
first pilot of the "features, not services" architecture, 2026-09-11 CTO decision) — see that
file's own docstring for the four tests a candidate feature has to pass before it earns an entry
here, and `services/reminders/app/core/features.py`'s docstring for how a feature genuinely
shared across app boundaries is kept from drifting (`ci/check_shared_features_match.py`).

NOTHING HERE IS SHARED WITH ANOTHER APP. The one tempting candidate — "نبّهه لما رصيده يكفي
مكافأة" — was checked directly against the code and found to NOT be this service's own trigger:
`core/notify.py::to_next_reward` only computes the raw number this service is asked for; the
actual "balance just crossed into affordability → send a nudge" decision is campaigns-service's
own (`services/reminders/app/core/reasons.py`'s `reward_within_reach`, `source="campaigns"`). That
belongs in campaigns' own future catalog, not claimed here.
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


LOYALTY_FEATURES: tuple[Feature, ...] = (
    Feature(
        id="loyalty.earn_per_visit",
        title="نقطة على كل زيارة تلقائياً",
        detail="تُحسب وتُضاف لحالها، بلا أي خطوة من موظفك",
        icon="star",
        tone=TONE_AMBER,
        # `Earner.from_visit` (core/earn.py:37-107) — ONE ledger entry per visit (never one per
        # service — a customer experienced one visit, and a statement showing three lines for one
        # wash reads as a mistake), idempotent on the visit id (the event bus is at-most-once BY
        # CONTRACT, so a redelivery must never double-award), and a `catch_up()` sweep
        # (core/earn.py:109-142) fills any visit the event never brought at all.
    ),
    Feature(
        id="loyalty.only_affordable_rewards",
        title="ما نحرجه بجايزة ما يقدر ياخذها",
        detail="نعرض له بس الجوايز اللي رصيده الحالي يكفي لها",
        icon="gift",
        tone=TONE_VIOLET,
        # `Rewards.affordable` (core/rewards.py:114-127) — not the full menu with the
        # unaffordable greyed out: showing a reward he cannot have is a worse moment than his not
        # knowing it exists, and the operator holding the phone is the one who has to manage it.
    ),
    Feature(
        id="loyalty.manager_approval",
        title="مكافآت كبيرة تحتاج اعتماد مدير",
        detail="تحدد أنت الحد، وأي مكافأة فوقه ما تُسلَّم إلا باسم مدير حقيقي",
        icon="shield-check",
        tone=TONE_BLUE,
        # `needs_approval`/`Redeemer._redeem_locked` (core/redeem.py:34-45, 92-130) — a real,
        # owner-set threshold, and a real second identity: the approver must differ from the
        # operator doing the redeeming (case-insensitive compare), so a reward expensive enough to
        # matter is never self-approved by whoever is handing it out.
    ),
    Feature(
        id="loyalty.expiry_warning",
        title="يحذّر عميلك قبل ما تضيع نقاطه",
        detail="يوصله تنبيه قبل انتهاء رصيده بأسبوعين، مو يفاجأ بضياعه",
        icon="clock",
        tone=TONE_ROSE,
        # `Expiry` (core/expiry.py:53-90) — measured from the customer's own LAST MOVEMENT, not
        # per point, so an active customer's whole clock resets on every visit and only a genuinely
        # lapsed one ever loses anything; the warning is sent as a SERVICE message (never marketing
        # — a customer who opted out of offers must still be told he is about to lose real points).
    ),
    Feature(
        id="loyalty.fraud_receipt",
        title="يكشف لك أي تلاعب بالنقاط",
        detail="لو موظف استخدم نقاط عميل من غير علمه، يوصله إشعار فوري يفضحها",
        icon="shield-check",
        tone=TONE_TEAL,
        # `core/notify.py`'s own stated purpose (module docstring) — the redemption receipt is not
        # for information, it is to be UN-FORGEABLE: an operator spending a customer's balance on
        # himself or a friend is caught within seconds, because the customer whose balance it was
        # is the one person who reliably notices. Exempt from quiet hours and the message cap
        # (a personal message, not marketing) so it always actually arrives.
    ),
)


def public_features() -> list[dict[str, str | list[str]]]:
    return [
        {
            "id": f.id, "title": f.title, "detail": f.detail, "icon": f.icon, "tone": f.tone,
            "shared_with": list(f.shared_with), "owned_by": f.owned_by,
        }
        for f in LOYALTY_FEATURES
    ]
