"""THE REAL BUG: `execute_confirmed_proposal`'s "consumed" guard was a plain read-then-write, so a
QA audit found two genuinely simultaneous calls for the SAME proposal_id (a redelivered wamid
before its own dedup settled, or WhatsApp itself replaying a button tap) could both read
`consumed=False` before either had written it, and both proceed into a REAL booking-provider call.
"""
from __future__ import annotations

import asyncio
import time

from app.adapters.datastore.memory import MemoryDataStore
from app.core import tools as T
from app.core.points import NullPointsSummary
from app.ports.booking_provider import Slot

from tests.unit.test_booking_management import _FakeManagementProvider, _seed

TENANT = "t1"
ALLOWED = frozenset({"propose_cancel_booking"})


class _FakeAuditor:
    async def record(self, *a, **kw):
        pass


class _SlowProvider(_FakeManagementProvider):
    """Yields inside `cancel_booking` — the real peer call `_execute_confirmed_proposal` makes —
    so two `asyncio.gather`ed calls genuinely interleave around it, same technique every other race
    test in this session uses."""

    async def cancel_booking(self, **kw):
        await asyncio.sleep(0)
        return await super().cancel_booking(**kw)


def test_two_simultaneous_confirms_of_the_same_proposal_only_one_executes():
    async def run():
        store = MemoryDataStore()
        provider = _SlowProvider()
        now = int(time.time())
        _seed(provider, booking_id="bkg1", from_number="+9665", customer_id="cust1",
             starts_at=now + 3600)
        proposal = await T.validate_and_render(
            tenant=TENANT, subject_ref="sub1", conversation_id="c1",
            tool="propose_cancel_booking", args={"booking_id": "bkg1"}, allowed_tools=ALLOWED,
            store=store, booking_provider=provider, points_summary=NullPointsSummary(),
            proposal_ttl_seconds=1800, now=now, from_number="+9665")

        results = await asyncio.gather(
            T.execute_confirmed_proposal(
                tenant=TENANT, proposal_id=proposal.proposal_id, store=store,
                booking_provider=provider, auditor=_FakeAuditor(), idempotency_key="btn_x",
                now=now, from_number="+9665"),
            T.execute_confirmed_proposal(
                tenant=TENANT, proposal_id=proposal.proposal_id, store=store,
                booking_provider=provider, auditor=_FakeAuditor(), idempotency_key="btn_x",
                now=now, from_number="+9665"),
            return_exceptions=True)
        return results

    results = asyncio.run(run())
    succeeded = [r for r in results if isinstance(r, dict)]
    refused = [r for r in results if isinstance(r, T.ToolValidationError)]
    assert len(succeeded) == 1, (
        f"two concurrent confirms both executed the real cancel — {results!r}, the exact "
        "double-execution bug this lock exists to prevent")
    assert len(refused) == 1
    assert "in progress" in str(refused[0])
