"""The staff-rating alert's own decision: has this operator's recent run of ratings genuinely
dropped, and if so, tell whoever may see his branch — never a general-purpose policy engine, one
specific product decision the owner made explicitly (2026-09-12): the last 10 rated visits, never
fewer than 5 of them counted, average below 4.5.

WHY A ROLLING WINDOW OF RATINGS, NOT A CALENDAR PERIOD. The same reasoning `notify_recipients.py`
already documents for branch scope applies here to TIME: a slow operator's "last 10" might span
three months and a busy one's a single week, and a calendar window (e.g. "this week") would
either miss the slow operator's real pattern for months or over-react to one bad rating in a quiet
week for him. Matches Uber's own driver-rating design (average of the last 500 RIDES, not a
calendar period) — a rolling count of actual opinions, not a clock.

WHY A MINIMUM SAMPLE SIZE. A brand-new operator's first one or two ratings are not a pattern, and
alerting on them teaches an owner to stop reading these alerts. Five is the floor below which this
policy says nothing at all, favourable or not.

WHY THIS FIRES PER QUALIFYING RATING, NOT ONCE PER "STATE CHANGE". Tracking "was he already below
threshold" would need a second stored fact this service has nowhere to keep durably tied to this
decision, and — more importantly — each new low rating while he is already below the line is
itself new, real information an owner watching his shop's reputation would want, not noise to be
suppressed. `InAppNotifier.send`'s own idempotency key includes the triggering visit's id, so a
retried webhook for the SAME rating still cannot double-send; a genuinely NEW low rating is a
genuinely new alert.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.notify_recipients import managers_for_branch
from app.core.stores import AccountSettingsStore, VisitStore

WINDOW = 10
MIN_SAMPLES = 5
THRESHOLD = 4.5

TEMPLATE_KEY = "operations.staff_rating_dropped"

# THE FIVE LOCALES THE TEMPLATE IS REGISTERED IN (deploy/seed/notification-templates.json) — same
# list `operator-i18n.tsx`'s own OPERATOR_LOCALES declares. A recipient's OWN preference
# (AccountSettingsStore, the platform-wide `/api/v1/account/me/locale` — the CURRENT authority for
# every account, owner or hired staff alike, see api/v1/__init__.py's own note superseding
# `Operator.locale`) is used when it names one of these; anything else — never set, or a value from
# before this list existed — falls back to Arabic, same fallback chain operator-i18n.tsx's own `t()`
# already uses for a screen not yet translated into a locale.
_TEMPLATE_LOCALES = frozenset({"ar", "en", "ur", "ha", "fil"})
_DEFAULT_LOCALE = "ar"


@dataclass(frozen=True)
class RatingDropVerdict:
    should_alert: bool
    average: float
    sample_size: int


def evaluate(ratings: list[int]) -> RatingDropVerdict:
    """`ratings` is already the last `WINDOW` (or fewer) ratings, newest first — the caller's job
    (`VisitStore.ratings(..., limit=WINDOW)` already sorts and caps it, so this function itself
    never re-reads or re-trims)."""
    n = len(ratings)
    if n < MIN_SAMPLES:
        return RatingDropVerdict(should_alert=False, average=0.0, sample_size=n)
    average = sum(ratings) / n
    return RatingDropVerdict(should_alert=average < THRESHOLD, average=average, sample_size=n)


async def check_and_notify(container, *, tenant: str, operator_id: str, operator_name: str,
                           branch_id: str, triggering_visit_id: str) -> None:
    """Call after a rating is SAVED (see `api/internal.py::record_visit_rating`), never before —
    the newly-saved rating must already be part of what `ratings()` reads back, or the window this
    checks is one rating stale.

    A TILL SALE OR ANY VISIT WITH NO OPERATOR NEVER REACHES THIS — same exclusion
    `Operations.staff_performance` already applies for the same reason: there is no "operator whose
    rating dropped" to name.
    """
    if not operator_id:
        return
    store = container.datastore
    rows, _ = await VisitStore(store).ratings(tenant, operator_id=operator_id, limit=WINDOW)
    verdict = evaluate([v.rating for v in rows])
    if not verdict.should_alert:
        return
    recipients = await managers_for_branch(
        store=store, authz=container.authz_desk, tenant=tenant, branch_id=branch_id)
    settings = AccountSettingsStore(store)
    for recipient in recipients:
        locale = await _locale_for(settings, tenant, recipient)
        # BEST-EFFORT, LIKE EVERY OTHER SEND IN THIS FILE'S OWN NEIGHBOURHOOD (loyalty_desk's
        # rating_bonus, this same route's own credit call above it) — a lost alert does not undo
        # the rating just saved, and does not block the customer's own "thank you" reply either.
        await container.inapp_notifier.send(
            tenant=tenant, user_id=recipient, template_key=TEMPLATE_KEY,
            variables={"name": operator_name, "average": f"{verdict.average:.1f}"},
            idempotency_key=f"rating_drop:{tenant}:{operator_id}:{triggering_visit_id}:{recipient}",
            locale=locale)


async def _locale_for(settings: AccountSettingsStore, tenant: str, subject: str) -> str:
    row = await settings.get_by_subject(tenant, subject)
    locale = str((row or {}).get("locale") or "")
    return locale if locale in _TEMPLATE_LOCALES else _DEFAULT_LOCALE
