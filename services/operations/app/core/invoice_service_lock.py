"""One (tenant, product_id) pair gets at most one auto-created catalogue row at a time.

THE DEFECT THIS CLOSES (a QA audit found it, 2026-09-12). `invoices.resolve`'s auto-create branch
is a check-then-create with no compare-and-set in between: it reads `by_ext.get(product_id)`
against a catalogue snapshot taken at the START of the request, and if nothing matches it creates a
new `Service` row. Two invoices for the same brand-new product arriving close together — two till
terminals posting near-simultaneously, or two batch requests each carrying one item for the same
tenant — both read "not found" against their own snapshot and both create a row, and the owner ends
up with two identical services splitting one product's history between them, discovered only when
he notices the same name twice in his own catalogue.

SAME PRIMITIVE AS `CustomerCounterLock`/`OfferApplyLock`, A DIFFERENT KEY NAMESPACE — a short-lived
mutual-exclusion claim in the cache, not the datastore, around the handful of reads/writes that
decide whether this product is genuinely new. Keyed on `(tenant, product_id)` so two DIFFERENT
products never contend with each other — only two writers racing to create the SAME one do.
"""
from __future__ import annotations

from typing import Any

from app.core.operations import OperationError

# Long enough to cover a read + a save() round trip; short enough that a pod killed mid-write does
# not lock a brand-new product out of being created for long.
TTL_SECONDS = 10

BUSY = "جارٍ إضافة هذه الخدمة الآن — أعد المحاولة بعد لحظة."
UNAVAILABLE = "تعذّر قفل إضافة الخدمة الآن — أعد المحاولة بعد لحظة."


class InvoiceServiceCreateBusy(OperationError):
    """Somebody else is deciding whether to create this exact (tenant, product_id) service right
    now, or we could not tell.

    INHERITS `OperationError`, same reasoning as `CustomerCounterBusy`: the one caller here
    (`invoices.resolve`, reached from `record_visits_batch`) already lets `OperationError`
    propagate to that route's existing per-item error handling — a refusal outside that family is
    a refusal nobody actually catches.
    """


class InvoiceServiceCreateLock:
    """`async with InvoiceServiceCreateLock(cache, tenant, product_id):` — held across the
    re-check-then-create, released after."""

    def __init__(self, cache: Any, tenant: str, product_id: str, *,
                ttl_seconds: int = TTL_SECONDS) -> None:
        self._cache = cache
        self._key = f"operations:invoice-service-create:{tenant}:{product_id}"
        self._ttl = ttl_seconds
        self._held = False

    async def __aenter__(self) -> "InvoiceServiceCreateLock":
        if self._cache is None:
            # NO CACHE AT ALL is a local run or a test with the port unwired — same posture as
            # `CustomerCounterLock`: refusing every invoice there would make the lock a bigger
            # outage than the race it prevents, and a process with no cache has no second caller
            # to race against.
            return self
        claim = getattr(self._cache, "set_if_absent", None)
        if claim is None:
            raise InvoiceServiceCreateBusy(UNAVAILABLE)
        try:
            won = await claim(self._key, "1", self._ttl)
        except Exception as exc:                                            # noqa: BLE001
            raise InvoiceServiceCreateBusy(UNAVAILABLE) from exc
        if not won:
            raise InvoiceServiceCreateBusy(BUSY)
        self._held = True
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if not self._held:
            return
        try:
            await self._cache.delete(self._key)
        except Exception:                                                   # noqa: BLE001
            # RELEASED BY THE TTL INSTEAD — same trade `CustomerCounterLock` makes: a failed
            # delete costs this one product a few seconds of refusals; raising here would replace
            # a successful catalogue write with an error after it already happened.
            pass
