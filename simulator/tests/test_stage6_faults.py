"""Stage 6 proof: the SAME, unmodified `RegisterReferralAction` (stage 5) run against a REAL
services/operations whose `referrals` peer is deliberately broken three different ways — none of
it faked inside operations' own process, all of it a real network condition operations' own code
has to survive: `ReferralsPeerUnavailable` (core/referral_redemption.py /
adapters/referrals_desk.py) turning a real connectivity failure into a clean, well-worded refusal
instead of a 500 or a hang.
"""
from __future__ import annotations

import asyncio
import time

from simulator.apps.operations.actions import RegisterReferralAction
from simulator.apps.operations.faults import fake_referrals_peer
from simulator.apps.operations.service import spawn
from simulator.common.engine import run_one
from simulator.common.faults import unreachable_url

TENANT = "sim-stage6"
PEER_REFUSAL = "تعذّر التحقق من الكود الآن"


def run(coro):
    return asyncio.run(coro)


def _register(base_url: str, *, code_suffix: str) -> RegisterReferralAction:
    return RegisterReferralAction(base_url=base_url, tenant=TENANT, code=f"UNKNOWN{code_suffix}",
                                  beneficiary_phone="0511111111")


def test_a_dependency_that_is_genuinely_unreachable_is_refused_cleanly_not_a_crash():
    async def _go():
        async with spawn(extra_env={"REFERRALS_SERVICE_URL": unreachable_url()}) as svc:
            return await run_one(_register(svc.base_url, code_suffix="A"))

    result = run(_go())
    assert result.error is None, result.error  # never an unhandled crash
    assert result.ok is False
    assert PEER_REFUSAL in (result.detail or "")


def test_a_dependency_slower_than_the_real_timeout_is_refused_cleanly_not_a_hang():
    async def _go():
        async with fake_referrals_peer(mode="slow") as peer:
            async with spawn(extra_env={"REFERRALS_SERVICE_URL": peer.base_url}) as svc:
                started = time.monotonic()
                result = await run_one(_register(svc.base_url, code_suffix="B"))
                elapsed = time.monotonic() - started
                return result, elapsed

    result, elapsed = run(_go())
    assert result.error is None, result.error
    assert result.ok is False
    assert PEER_REFUSAL in (result.detail or "")
    # ReferralsDesk's own fixed 5s timeout must actually have been hit and given up on — not hung
    # indefinitely, and not suspiciously instant either (which would mean the slow peer never
    # actually got called at all).
    assert 4.5 < elapsed < 9.0, f"expected ~5s (the real timeout), took {elapsed:.1f}s"


def test_a_dependency_returning_garbled_json_is_refused_cleanly_not_a_crash():
    async def _go():
        async with fake_referrals_peer(mode="garbled") as peer:
            async with spawn(extra_env={"REFERRALS_SERVICE_URL": peer.base_url}) as svc:
                return await run_one(_register(svc.base_url, code_suffix="C"))

    result = run(_go())
    assert result.error is None, result.error
    assert result.ok is False
    assert PEER_REFUSAL in (result.detail or "")


def test_a_healthy_peer_never_produces_the_peer_unavailable_refusal():
    """Control case: the SAME action, the SAME fixture, talking instead of failing — proving the
    three failures above are genuinely about the peer being broken, not something that always
    fires regardless of peer health (whatever business refusal a healthy peer's own made-up
    answer leads to — e.g. the referrer isn't a real customer here — must be a DIFFERENT message
    from the peer-unavailable one, never confused with it)."""
    async def _go():
        async with fake_referrals_peer(mode="healthy") as peer:
            async with spawn(extra_env={"REFERRALS_SERVICE_URL": peer.base_url}) as svc:
                return await run_one(_register(svc.base_url, code_suffix="D"))

    result = run(_go())
    assert result.error is None, result.error
    assert PEER_REFUSAL not in (result.detail or "")
