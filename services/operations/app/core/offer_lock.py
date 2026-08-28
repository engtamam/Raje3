"""One visit's offer is applied by one caller at a time.

THE DEFECT THIS CLOSES. `Operations.apply_offer` is a read-modify-write: read the visit, check
`v.offer_ref`, ask reminders which offer applies, write it back. The datastore's only write is an
unconditional upsert (`VisitStore.save`) — no compare-and-set, no version, nothing conditional
anywhere in the platform's datastore port.

So two `POST /till/offer/apply` calls for the SAME visit landing in the same second — a fast
double-tap, a retried request racing the original, or two different tills both closing the same
sale — both read `v.offer_ref == ""`, both ask reminders and get back the SAME offer (nothing has
been saved onto any visit yet by either racer), and both `save()`. The second write silently wins;
both HTTP responses report `applied: true`, and if the two racing calls happen to name two
DIFFERENT visits of the same customer, the same offer ends up stamped "used" on both — each side
believing, independently and wrongly, that it alone spent it.

SAME DEFECT FAMILY, SAME FIX loyalty's own `SpendLock` already closed for a redemption racing
across the field phone and the till — see that module's own docstring for the fuller reasoning on
why a lock rather than a retry, and why the cache rather than the datastore. This is that same
primitive, ported (this codebase shares no library across services — see any core/pii.py's own
note on why an identical idea is pasted rather than imported), keyed on `(tenant, visit_id)`
instead of `(tenant, subject_ref)`, because it is the VISIT — not the customer's whole balance —
that must not be double-claimed here.
"""
from __future__ import annotations

from typing import Any

from app.core.operations import OperationError

# Longer than a peer read (reminders' choose) plus one datastore write can take, short enough that
# a pod killed mid-apply does not lock a visit out of its own offer for long.
TTL_SECONDS = 15

BUSY = "جارٍ تطبيق العرض على هذه الزيارة الآن — أعد المحاولة بعد لحظة."
UNAVAILABLE = "تعذّر التحقق من حالة هذه الزيارة الآن — أعد المحاولة بعد لحظة."


class OfferApplyBusy(OperationError):
    """Somebody else is applying this visit's offer right now, or we could not find out.

    INHERITS `OperationError`, DELIBERATELY — same reasoning `SpendBusy` inheriting `LoyaltyError`
    documents in loyalty's own spend_lock.py: `apply_offer_at_the_counter` (api/v1/till.py) already
    catches `OperationError` and returns `{"applied": False, "reason": str(e)}`, read aloud to a
    customer standing at the counter — a refusal that is not of the family its one handler catches
    is a refusal that was never actually written.
    """


class OfferApplyLock:
    """`async with OfferApplyLock(cache, tenant, visit_id):` — held for the apply, released after."""

    def __init__(self, cache: Any, tenant: str, visit_id: str, *,
                ttl_seconds: int = TTL_SECONDS) -> None:
        self._cache = cache
        self._key = f"operations:offer-apply:{tenant}:{visit_id}"
        self._ttl = ttl_seconds
        self._held = False

    async def __aenter__(self) -> "OfferApplyLock":
        if self._cache is None:
            # NO CACHE AT ALL is a local run or a test with the port unwired. Refusing every apply
            # there would make the lock a bigger outage than the race it prevents, and a process
            # with no cache is a process with no second caller to race against.
            return self
        claim = getattr(self._cache, "set_if_absent", None)
        if claim is None:
            raise OfferApplyBusy(UNAVAILABLE)
        try:
            won = await claim(self._key, "1", self._ttl)
        except Exception as exc:                                            # noqa: BLE001
            raise OfferApplyBusy(UNAVAILABLE) from exc
        if not won:
            raise OfferApplyBusy(BUSY)
        self._held = True
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if not self._held:
            return
        try:
            await self._cache.delete(self._key)
        except Exception:                                                   # noqa: BLE001
            # RELEASED BY THE TTL INSTEAD. A failed delete costs one visit a few seconds of
            # refusals; raising here would replace a successful apply with an error after the
            # offer was already stamped, which is the worse of the two by a distance.
            pass
