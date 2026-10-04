"""A controllable, real, standalone stand-in for services/referrals' own internal API — used ONLY
by stage 6's fault tests, to exercise services/operations' REAL peer-failure handling
(`ReferralsPeerUnavailable` in core/referral_redemption.py / adapters/referrals_desk.py) against
genuine network behaviour (a real slow response, a real malformed body), never a Python mock
patched into operations' own process.

`FAULT_MODE` (env var) picks the behaviour every request gets:
  - "healthy" (default): a normal, well-shaped response, immediately.
  - "slow": sleeps past ReferralsDesk's own 5-second timeout before answering (a real timeout, a
    real socket left open that long — not a simulated delay inside operations' own test process).
  - "garbled": answers 200 with a body that is NOT valid JSON — a real malformed peer response.
"""
from __future__ import annotations

import asyncio
import os

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

app = FastAPI()

_SLOW_SECONDS = 7.0  # comfortably past ReferralsDesk's own fixed 5-second timeout


def _mode() -> str:
    return os.environ.get("FAULT_MODE", "healthy")


@app.get("/healthz")
async def healthz() -> dict:
    # ALWAYS healthy, regardless of FAULT_MODE — stage 4's own run_service needs this to answer
    # fast so the fixture itself boots; the fault is in the DOMAIN routes below, not in whether
    # the process is up at all (a truly "down" peer is modelled by never spawning this at all,
    # see common/faults.py::unreachable_url).
    return {"status": "ok"}


@app.get("/internal/referrals/lookup/{code}")
async def lookup_code(code: str):
    mode = _mode()
    if mode == "slow":
        await asyncio.sleep(_SLOW_SECONDS)
    if mode == "garbled":
        return PlainTextResponse("{not valid json at all", status_code=200)
    return {"phone": "+966500000999"}


@app.get("/internal/referrals/campaigns/active")
async def active_campaign(tenant: str):
    mode = _mode()
    if mode == "slow":
        await asyncio.sleep(_SLOW_SECONDS)
    if mode == "garbled":
        return PlainTextResponse("{not valid json at all", status_code=200)
    return {
        "id": "camp_fake", "tenant": tenant, "mode": "lifetime", "min_spend_minor": 0,
        "usage_cap_period": "", "usage_cap_limit": 0, "x_times_limit": 0, "cap_scope": "campaign",
        "reward_type": "fixed_points", "reward_params": {"points": 10},
        "new_customer_reward_type": "discount_percent", "new_customer_reward_params": {"percent": 5},
        "active": True,
    }
