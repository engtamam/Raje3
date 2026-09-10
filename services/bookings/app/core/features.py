"""What الحجوزات actually does for a shop owner — one catalog, written as VALUE, not mechanism.

WHY THIS FILE EXISTS AT ALL. The app's real capabilities were never anywhere a shop owner could
read them as a list: `licence.py` only knows a boolean (`feature.bookings`), and the console's own
`apps.ts` carries one description line per app, never a breakdown. An owner deciding whether to
buy has no way to see what he is actually paying for beyond "appointment scheduling" — the exact
gap `docs/خطة-تنفيذ-الحجوزات.md`'s own ten build stages closed in code but never in a sentence he
could read (2026-09-11 product decision: "بطاقة التطبيق تكون ذكية وتظهر مميزات كثير حقيقي").

EVERY ENTRY HERE IS A REAL MECHANISM, cited to the exact code that does it — never a marketing
adjective invented for this file. `title`/`detail` are the owner-facing sentence, and REWRITTEN
2026-09-11 to answer the owner's own question directly — «ايش بيستفيد؟ كيف يرفع مبيعاته أو يخليه
يكسب؟» — never a description of how the code behaves ("يحمي بيانات العميل" says nothing he can
act on; "يحميك من خسارة موعد فاضي" does). The docstring on each `Feature(...)` call is the
engineering truth the sentence is grounded in, so the two can never drift silently apart.

`shared_with`/`owned_by` are the hooks the "features, not services" architecture (2026-09-11 CTO
decision) needs: a feature is not necessarily this app's own code — the reminders line below is
IMPLEMENTED in `services/reminders`, and بوكينغز only GRANTS access to it (its own
`subscribed_write` ORs `bookings_licence` — see that service's `api/subscribed.py`). Represented
here so "الحجوزات" and "تسجيل زيارة" can show the identical sentence for the identical capability,
from one authored source, once each app's own catalog references it.

WHY THIS FILE, NOT A DATABASE ROW. Same reasoning as `deploy/seed/plans.json` for prices: content
that changes by us editing code and shipping a review, never by a runtime write nobody reviews.
"""
from __future__ import annotations

from dataclasses import dataclass

# The five colour categories a feature's icon may carry — chosen to MATCH what the icon depicts
# (money/points amber, people/rewards violet, timing/connectivity blue, a message reaching the
# customer rose, a safety/verified guarantee teal), never rotated blindly. The console owns the
# actual hex values; this only names which bucket a feature belongs in, so the console's palette
# and this catalog can never disagree about which feature is which colour.
TONE_TEAL = "teal"
TONE_VIOLET = "violet"
TONE_AMBER = "amber"
TONE_ROSE = "rose"
TONE_BLUE = "blue"
TONES = frozenset({TONE_TEAL, TONE_VIOLET, TONE_AMBER, TONE_ROSE, TONE_BLUE})


@dataclass(frozen=True)
class Feature:
    """One real, separately-nameable capability — see this module's own docstring for the four
    tests a candidate has to pass before it earns an entry here (real code behind it, a shop owner
    recognises it as value, explainable by mechanism not adjective, nameable on its own)."""

    id: str
    title: str
    detail: str
    icon: str
    tone: str
    # OTHER APP IDS THAT ALSO GRANT THIS EXACT FEATURE — same id, same title/detail, rendered
    # identically wherever it appears; see `services/operations/app/apps.py`-style app ids
    # ("visit", "bookings", …) once the console side of this reads it.
    shared_with: tuple[str, ...] = ()
    # WHICH SERVICE'S CODE THIS FEATURE ACTUALLY LIVES IN, when it is not this app's own — absent
    # (empty string) means "implemented right here, in bookings-service itself".
    owned_by: str = ""

    def __post_init__(self) -> None:
        if self.tone not in TONES:
            raise ValueError(f"unknown tone {self.tone!r} on feature {self.id!r}")


BOOKINGS_FEATURES: tuple[Feature, ...] = (
    Feature(
        id="bookings.instant_slot",
        title="ما يفوّتك حجز وأنت مشغول",
        detail="بضغطة وحدة يطلع لك أقرب وقت فاضي، فيحجز العميل عندك — لا يقفل ويحجز عند غيرك",
        icon="clock",
        tone=TONE_BLUE,
        # `BookingOperations.nearest_slot` (app/core/operations.py:732-800) — the pure derivation
        # in `app/core/availability.py::nearest_slot`, fed the shop's real working hours, this
        # operator's own hours override (never wider than the shop's — `_effective_schedule`,
        # operations.py:278-316), and his real busy intervals from actual bookings. Refuses up
        # front for an operator who cannot perform the service, so a probe never leaks a slot he
        # could never actually be booked into.
    ),
    Feature(
        id="bookings.fair_distribution",
        title="يشغّل فريقك كله، لا موظف واحد بس",
        detail="يوزّع الحجوزات بعدل بينهم، فتستفيد من طاقة محلك كاملة لا نص طاقتها",
        icon="users",
        tone=TONE_VIOLET,
        # `BookingOperations.nearest_slots_any` (operations.py:802-868) + `app/core/
        # assignment.py::order_candidates` — a real, tenant-picked ranking, not a fixed rule: the
        # shop chooses "nearest" (unranked, first slot wins), "least_loaded" (fewest existing
        # bookings in the search window — modelled on Vagaro's "Most Open Schedule"), or
        # "manual_order" (an owner-defined operator priority). The algorithm only ever REORDERS
        # candidates, never changes which slot is actually offered (operations.py:818-821) — a
        # shop's ranking choice can bias who gets picked, never break availability.
    ),
    Feature(
        id="bookings.no_show_warning",
        title="يحميك من موعد فاضي يكلّفك فلوس",
        detail='يقلّك "هذا عادة يتغيب" قبل ما يحجز، فتطلب عربون وتضمن وقت موظفك',
        icon="alert-triangle",
        tone=TONE_AMBER,
        # `BookingOperations.no_show_risk` (operations.py:635-658) — a real percentage, not a
        # guess: of this customer's last `risk_window` (default 5, tenant-tunable) CLOSED
        # appointments (attended/no-show only — booked/cancelled excluded, neither is an
        # attendance outcome), how many she missed. Flagged "risky" only once BOTH a minimum
        # sample size AND the tenant's own threshold percentage (default 60%) are met — the
        # minimum sample is derived from that same threshold (ceil division), never a second
        # hardcoded number. Never auto-refuses a booking; staff decide what to do with the number.
    ),
    Feature(
        id="bookings.visit_auto_open",
        title="يسجّل لك المبيعة تلقائياً",
        detail="لحظة يوصل العميل تنفتح زيارته وتدخل بمبيعاتك، بلا ما تنسى تسجّلها بنفسك",
        icon="check-badge",
        tone=TONE_TEAL,
        # `BookingOperations.attend` (operations.py:560-614) — marking a booking attended is the
        # SOLE path that creates a real Visit row, via a peer call into `operations`' own
        # `record_visit` (never writing a Visit directly — this service does not own that shape).
        # Ordered deliberately: the peer call happens BEFORE the booking's own status flips to
        # attended, so a booking can never claim "attended" while no visit actually exists. A
        # pending loyalty-reward intent set at booking time is also spent at this exact moment,
        # best-effort (a failed redemption never undoes an attendance that already succeeded).
    ),
    Feature(
        id="bookings.safe_reschedule",
        title="يحفظ حجزك من الضياع",
        detail="لو موظفتين عدّلوا نفس الموعد بنفس اللحظة، يحفظه صح — ما يضيع عليك حجز أبداً",
        icon="move",
        tone=TONE_VIOLET,
        # `BookingOperations.reschedule`/`_claim_and_save`/`_refuse_if_conflicting`
        # (operations.py:446-464, 912-965) — the drag-and-drop on the calendar IS this call
        # (§6.1.1). Re-validates the new operator's eligibility on every reschedule (a real gap
        # fixed 2026-09-07 — it used to skip this entirely), takes a real distributed claim lock
        # keyed on (branch, operator, time-bucket) before committing, uses optimistic concurrency
        # so a stale copy can never silently overwrite a newer edit, and scans the adjacent
        # calendar day's bucket too so a late booking spilling past midnight is still caught as a
        # real conflict (another 2026-09-07 fix).
    ),
    Feature(
        id="bookings.right_staff_only",
        title="يحميك من خطأ يكلّفك رضا عميلك",
        detail="خدمة تحتاج تدريب خاص، ما ياخذها إلا اللي يتقنها — تحافظ على جودة شغلك وسمعتك",
        icon="shield-check",
        tone=TONE_BLUE,
        # `_refuse_if_ineligible`/`_refuse_if_ineligible_for_booking` (operations.py:242-276) —
        # enforced at EVERY write path a booking can take (create, reschedule, edit_services), not
        # only at the "أقرب موعد" suggestion — a client that skips the suggestion and posts
        # directly is refused exactly the same way. A shop that never restricted a service sees no
        # refusal at all (fail-open by default, never fail-closed on a rule nobody set).
    ),
    Feature(
        id="reminders.learns_each_customer",
        title="يرجّع لك عميلك بلا ما تتعب",
        detail="يعرف امتى كل عميل يرجع عادة، ويذكّره بوقته — حجز إضافي بلا أي مجهود منك",
        icon="bell",
        tone=TONE_ROSE,
        # NOT THIS SERVICE'S OWN CODE — the reminders engine (per-customer learned visit rhythm,
        # engagement-tier scoring) lives in `services/reminders/app/core/adaptive.py`/
        # `engagement.py`. bookings only grants access to it: `reminders`' own `subscribed_write`
        # (services/reminders/app/api/subscribed.py) is an OR across `feature.visit`/
        # `feature.bookings` — a shop owning EITHER app gets the exact same engine.
        #
        # THE CANONICAL TEXT LIVES IN `services/reminders/app/core/features.py::SHARED_FEATURES`
        # (reminders owns the real code) — this copy exists only because services in this fleet do
        # not import each other's code, and `ci/check_shared_features_match.py` fails the build the
        # moment this drifts from that canonical wording by so much as one character. Editing this
        # entry without editing reminders' own copy the same way is a build failure, not a review
        # miss.
        shared_with=("visit",),
        owned_by="reminders",
    ),
)


def public_features() -> list[dict[str, str | list[str]]]:
    """The wire shape `GET /api/v1/bookings/features` actually returns — flat, no internal
    docstrings, no engineering citations. Kept as one function (not inlined at the route) so a
    future internal-only consumer (a different service composing several apps' catalogs together)
    can call this directly instead of going back through HTTP."""
    return [
        {
            "id": f.id, "title": f.title, "detail": f.detail, "icon": f.icon, "tone": f.tone,
            "shared_with": list(f.shared_with), "owned_by": f.owned_by,
        }
        for f in BOOKINGS_FEATURES
    ]
