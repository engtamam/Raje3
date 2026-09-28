"""THE REAL BUG: `request_withdrawal` reads "any open request?" (no lock) and reads/claims
CONFIRMED commissions, all before writing anything — a QA audit found two genuinely simultaneous
requests can both pass the "no open request" check and both claim the SAME confirmed commissions
into two separate withdrawal requests, doubling what the affiliate is owed on paper.

Same technique as bookings' `test_two_operators_cannot_take_the_same_slot.py` and campaigns'
`test_press_claim_is_actually_atomic.py`: a thin store wrapper that yields on the reads
`request_withdrawal` actually makes, so two `asyncio.gather`ed calls genuinely interleave.
"""
from __future__ import annotations

import asyncio

import pytest
from app.adapters.datastore.memory import MemoryDataStore
from app.core.models import ACTIVE, AFFILIATES, COMMISSIONS, CONFIRMED, CONVERSION, Affiliate, Commission
from app.core.payouts import PayoutError, PayoutService

AFF = "aff-1"


class _SlowStore:
    def __init__(self, inner: MemoryDataStore) -> None:
        self._inner = inner

    async def get(self, *a, **kw):
        await asyncio.sleep(0)
        return await self._inner.get(*a, **kw)

    async def find(self, *a, **kw):
        await asyncio.sleep(0)
        return await self._inner.find(*a, **kw)

    def __getattr__(self, name):
        return getattr(self._inner, name)


async def _seed(store) -> None:
    await store.put(AFFILIATES, AFF, Affiliate(
        id=AFF, person_id="p1", phone="+966501234567", name="م",
        role="affiliate_manager", status=ACTIVE,
        payout_channel="bank_iban", payout_account_ref="SA0000000000000000000000").to_dict())
    await store.put(COMMISSIONS, "c1", Commission(
        id="c1", tenant="t1", affiliate_id=AFF, kind=CONVERSION,
        amount_halalas=100_000, status=CONFIRMED).to_dict())


@pytest.mark.anyio
async def test_two_simultaneous_withdrawal_requests_do_not_both_claim_the_same_commission():
    store = _SlowStore(MemoryDataStore())
    await _seed(store)
    svc = PayoutService(store=store, min_withdrawal_halalas=0)

    results = await asyncio.gather(
        svc.request_withdrawal(AFF), svc.request_withdrawal(AFF), return_exceptions=True)
    created = [r for r in results if not isinstance(r, Exception)]
    refused = [r for r in results if isinstance(r, PayoutError)]

    assert len(created) == 1, (
        f"two concurrent withdrawal requests both succeeded — got {len(created)} withdrawal "
        "requests both claiming the same confirmed commission")
    assert len(refused) == 1
    assert refused[0].reason == "already_pending"
