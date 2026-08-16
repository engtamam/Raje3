"""ك-9: `urlopen` inside an `async def` must not block the event loop.

Both peers run on the hottest write paths in the fleet: every till's licence check, and a loyalty
balance read while a customer stands at the till. A blocking call there freezes the WHOLE worker —
other shops' tills and the field screen stall on one slow peer — which is exactly the outage the
licence module's own docstring says a "could not ask" answer must never cause. Proven here by
measuring whether an independent coroutine keeps ticking WHILE the "network" call is in flight; a
synchronous `urlopen` in an `async def` starves it for the whole call.
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import patch

import pytest

from app.adapters.loyalty_desk import LoyaltyDesk
from app.core.licence import HttpApiLicence

BLOCK_SECONDS = 0.25


class _SlowResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self.status = 200

    def read(self):
        return self._payload

    def __enter__(self):
        time.sleep(BLOCK_SECONDS)          # the "network" call, done synchronously on purpose
        return self

    def __exit__(self, *a):
        return False


async def _heartbeat(ticks: list[float], stop: asyncio.Event) -> None:
    while not stop.is_set():
        ticks.append(time.monotonic())
        await asyncio.sleep(0.01)


async def _run_alongside(coro) -> list[float]:
    ticks: list[float] = []
    stop = asyncio.Event()
    hb = asyncio.ensure_future(_heartbeat(ticks, stop))
    await coro
    stop.set()
    await hb
    return ticks


@pytest.mark.anyio
async def test_the_licence_check_does_not_freeze_the_event_loop():
    licence = HttpApiLicence(billing_url="http://billing", check_path="/check", token="t")
    with patch("app.core.licence.urllib.request.urlopen",
              return_value=_SlowResponse(b'{"allowed": true}')):
        ticks = await _run_alongside(licence.allowed("t_1"))
    # A STARVED LOOP TICKS AT MOST ONCE across the whole blocking window; a threaded call lets
    # the heartbeat run many times while it waits.
    assert len(ticks) >= 5


@pytest.mark.anyio
async def test_the_loyalty_balance_read_does_not_freeze_the_event_loop():
    desk = LoyaltyDesk(base_url="http://loyalty", token="t")
    with patch("app.adapters.loyalty_desk.urllib.request.urlopen",
              return_value=_SlowResponse(b'{"points": 10}')):
        ticks = await _run_alongside(desk.balance(tenant="t_1", subject_ref="sub_1"))
    assert len(ticks) >= 5
