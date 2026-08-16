"""One customer's balance is spent by one caller at a time.

THE DEFECT THIS CLOSES. `Ledger.post` is a read-modify-write: read the balance, check the overdraft,
write the entry, write the balance. The datastore's only write is an unconditional upsert — no
compare-and-set, no version, nothing conditional anywhere in the platform's port. And this product
deliberately opens TWO redemption doors: the field phone (`/api/v1/loyalty/redeem`) and the
integrated till (`/internal/loyalty/redeem`).

So a customer with 100 points, at branch A's till while a cashier at branch B redeems for him in
the same second, gets BOTH rewards: two different idempotency keys, two different sources, both
reads see 100, both pass the overdraft check, both hand something over. The shop gives away twice
what the customer paid for. The ledger then sums to -100 while the materialised balance says 0, and
`reconcile` later «repairs» it to a negative number no screen can explain to anybody.

WHY A LOCK AND NOT A RETRY. The two callers are not racing to write the same value — they are each
spending a scarce thing. Optimistic retry needs a conditional write to detect the loss, and there
is none. Serialising the SPEND is the smallest correct answer available at this layer.

WHY THE CACHE AND NOT THE DATASTORE. Redis `SET NX` is genuinely atomic across pods; the datastore's
upsert is not atomic against anything. The memory driver is per-process — and that is honest rather
than a gap: the chart refuses `replicas > 1` unless every stateful port is shared, so a deployment
on the memory cache has exactly one pod, where a per-process claim IS the whole lock. The redis path
is what keeps this true on the day the fleet is allowed to scale.

IT EXPIRES. A pod killed mid-redemption must not lock a customer out of his own points for ever, so
the claim carries a TTL a few seconds longer than any redemption can take. The cost of a stale claim
is one refusal a customer retries; the cost of no TTL is a balance nobody can spend again.

AND A LOCK WE CANNOT TAKE IS A REFUSAL, NOT A PASS. If the cache is unreachable we do not know
whether somebody else is spending, and «we could not check» must not render as «nobody is».
"""
from __future__ import annotations

from typing import Any

# Longer than any redemption can take (a peer read, two writes and a receipt), short enough that a
# customer whose cashier's pod died is not locked out of a purchase he is standing there making.
TTL_SECONDS = 15

BUSY = ("جارٍ تنفيذ عملية أخرى على نقاط هذا العميل — أعد المحاولة بعد لحظة.")
UNAVAILABLE = ("تعذّر التحقق من نقاط هذا العميل الآن — أعد المحاولة بعد لحظة.")


class SpendBusy(Exception):
    """Somebody else holds this customer's balance right now, or we could not find out."""


class SpendLock:
    """`async with SpendLock(cache, tenant, subject_ref):` — held for the spend, released after."""

    def __init__(self, cache: Any, tenant: str, subject_ref: str, *,
                 ttl_seconds: int = TTL_SECONDS) -> None:
        self._cache = cache
        self._key = f"loyalty:spend:{tenant}:{subject_ref}"
        self._ttl = ttl_seconds
        self._held = False

    async def __aenter__(self) -> SpendLock:
        if self._cache is None:
            # NO CACHE AT ALL is a local run or a test with the port unwired. Refusing every
            # redemption there would make the lock a bigger outage than the race it prevents, and
            # a process with no cache is a process with no second caller.
            return self
        claim = getattr(self._cache, "set_if_absent", None)
        if claim is None:
            # An adapter without the primitive cannot serialise anything, and pretending otherwise
            # is the silent-success shape this whole file exists to answer.
            raise SpendBusy(UNAVAILABLE)
        try:
            won = await claim(self._key, "1", self._ttl)
        except Exception as exc:                                            # noqa: BLE001
            raise SpendBusy(UNAVAILABLE) from exc
        if not won:
            raise SpendBusy(BUSY)
        self._held = True
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if not self._held:
            return
        try:
            await self._cache.delete(self._key)
        except Exception:                                                   # noqa: BLE001
            # RELEASED BY THE TTL INSTEAD. A failed delete costs one customer a few seconds of
            # refusals; raising here would replace a successful redemption with an error after the
            # points were already spent, which is the worse of the two by a distance.
            pass
