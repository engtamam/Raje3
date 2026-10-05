"""One customer's counters (`visit_count`/`last_visit`/`counted_visit_id`) are updated by one
caller at a time.

THE DEFECT THIS CLOSES (a QA audit found it, 2026-09-12). `record_visit`'s counter update, and the
crash-retry completion path right above it in the same file, are BOTH a read-modify-write against
`Customer` with no compare-and-set — `CustomerStore.save` is an unconditional upsert, exactly the
same missing-CAS root cause `offer_lock.py`'s own docstring documents for `apply_offer`. Two
genuinely distinct visits for the same customer (two operators, two branches, near-simultaneously)
can both read the same `visit_count`, both increment locally, and the later `save()` silently
overwrites the earlier increment — an undercount with no reconciliation sweep, unlike the
double-tap duplicate-visit race this same file explicitly designs for and can detect/merge.

SAME PRIMITIVE AS `OfferApplyLock`, A DIFFERENT KEY NAMESPACE — the cache (not the datastore) is
right here for the identical reason offer_lock.py's own docstring gives: this is a short-lived
mutual-exclusion claim around a few in-memory reads/writes, not data that needs to survive a
restart. Keyed on `(tenant, customer_id)` so two DIFFERENT customers' visits never contend with
each other — only two writes racing on the SAME customer do.
"""
from __future__ import annotations

import asyncio
from typing import Any

from app.core.operations import OperationError

# Long enough to cover a read + a save() round trip; short enough that a pod killed mid-write does
# not lock a customer's counters out of updates for long.
TTL_SECONDS = 10
# How long a contended claim keeps trying before it is refused, and how often it tries. Far longer
# than the guarded read + save takes; far shorter than the request timeout a caller waits under.
WAIT_SECONDS = 3.0
POLL_SECONDS = 0.02

BUSY = "جارٍ تحديث بيانات هذا العميل الآن — أعد المحاولة بعد لحظة."
UNAVAILABLE = "تعذّر قفل بيانات هذا العميل الآن — أعد المحاولة بعد لحظة."


class CustomerCounterBusy(OperationError):
    """Somebody else is updating this customer's visit counters right now, or we could not tell.

    INHERITS `OperationError`, same reasoning as `OfferApplyBusy`/loyalty's own `SpendBusy`: the
    callers here (`record_visit`, the crash-retry path) already let `OperationError` propagate to
    their own routes' existing error handling — a refusal outside that family is a refusal nobody
    actually catches.
    """


class CustomerCounterLock:
    """`async with CustomerCounterLock(cache, tenant, customer_id):` — held for the read-modify-
    write, released after.

    A CONTENDED CLAIM WAITS ITS TURN BEFORE IT IS REFUSED. The section this guards is one read and
    one save — milliseconds — and its caller (`record_visit`) has ALREADY WRITTEN THE VISIT when it
    asks. Refusing on the first busy claim therefore did not refuse a visit: it left a saved visit
    uncounted (`visit_count`/`last_visit` behind) and answered `recorded: false`, which also skipped
    the post-visit seams — no points, no reminder, no index for a visit that exists. Seeding a demo
    shop with ordinary concurrency undercounted 19 of 34 customers that way. Waiting a bounded
    moment for the other writer to finish turns that into what it should always have been: two
    visits, both counted. Only a lock still held after `wait_seconds` (a writer that died holding
    it, until its TTL) is refused.
    """

    def __init__(self, cache: Any, tenant: str, customer_id: str, *,
                ttl_seconds: int = TTL_SECONDS, wait_seconds: float = WAIT_SECONDS) -> None:
        self._cache = cache
        self._key = f"operations:customer-counters:{tenant}:{customer_id}"
        self._ttl = ttl_seconds
        self._wait = wait_seconds
        self._held = False

    async def __aenter__(self) -> "CustomerCounterLock":
        if self._cache is None:
            # NO CACHE AT ALL is a local run or a test with the port unwired — same posture as
            # `OfferApplyLock`: refusing every visit there would make the lock a bigger outage
            # than the race it prevents, and a process with no cache has no second caller to race
            # against.
            return self
        claim = getattr(self._cache, "set_if_absent", None)
        if claim is None:
            raise CustomerCounterBusy(UNAVAILABLE)
        deadline = asyncio.get_running_loop().time() + max(0.0, self._wait)
        while True:
            try:
                won = await claim(self._key, "1", self._ttl)
            except Exception as exc:                                        # noqa: BLE001
                raise CustomerCounterBusy(UNAVAILABLE) from exc
            if won:
                break
            if asyncio.get_running_loop().time() >= deadline:
                raise CustomerCounterBusy(BUSY)
            await asyncio.sleep(POLL_SECONDS)
        self._held = True
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if not self._held:
            return
        try:
            await self._cache.delete(self._key)
        except Exception:                                                   # noqa: BLE001
            # RELEASED BY THE TTL INSTEAD — same trade `OfferApplyLock` makes: a failed delete
            # costs this customer a few seconds of refusals; raising here would replace a
            # successful visit-count update with an error after it already happened.
            pass
