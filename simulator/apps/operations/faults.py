"""App-specific fault definitions for services/operations (see the README's own taxonomy: generic
faults live in `common/faults.py`; a fault that needs to know the SHAPE of a real dependency's API
belongs next to the app that depends on it). services/operations' one real external dependency
this simulator can currently fault is its `referrals` peer (`REFERRALS_SERVICE_URL`) — see
`core/referral_redemption.py`'s own `ReferralsPeerUnavailable` handling, the thing being exercised.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from simulator.common.environment import ServiceHandle, run_service
from simulator.shared.service_env import base_env

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "fake_referrals_peer"


@asynccontextmanager
async def fake_referrals_peer(*, mode: str) -> AsyncIterator[ServiceHandle]:
    """A REAL, running, controllable stand-in for services/referrals' own internal API — `mode`
    is one of "healthy"/"slow"/"garbled" (see the fixture's own module docstring for what each
    one actually does over the wire). Point `REFERRALS_SERVICE_URL` at `.base_url` when spawning
    services/operations to exercise its real peer-failure handling against real network
    behaviour, never a Python-level mock patched into operations' own process."""
    env = {**base_env(), "FAULT_MODE": mode}
    async with run_service(f"fake-referrals-peer-{mode}", app_import="app.main:app",
                           cwd=_FIXTURE_DIR, env=env) as svc:
        yield svc
