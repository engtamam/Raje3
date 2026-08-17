"""Shared test setup.

Sets a valid environment BEFORE the app is imported so config validation passes,
then exposes a TestClient. ENV=test keeps logging silent and disables prod-only
behavior (HSTS, hidden docs).
"""
from __future__ import annotations

import os

# Must be set before any `app.*` import triggers config validation.
os.environ.setdefault("ENV", "test")
os.environ.setdefault("INTERNAL_SERVICE_TOKEN", "t" * 40)
os.environ.setdefault("BODY_LIMIT_BYTES", "2048")
os.environ.setdefault("REQUEST_TIMEOUT_MS", "30000")

import asyncio  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

# ── ONE EVENT LOOP FOR THE WHOLE SESSION ──────────────────────────────────────────────────────
# THE SUITE COULD NOT FINISH ON WINDOWS, and it did not fail — it STOPPED. Fifty-six test files
# define `def run(c): return asyncio.run(c)`, so a full run opens roughly nine hundred event
# loops in one process. Each one allocates a self-pipe socket pair, and somewhere past the eight
# hundredth the process blocked: no CPU, no traceback, no failing test — the run simply sat there
# for ever at 93%. The position moved with the test COUNT and not with the tests, which is what
# named it: deselecting the file it stopped in only moved the stop to the next file along.
#
# A GATE THAT CANNOT FINISH IS NOT A GATE. The block looks exactly like a slow machine, so the
# honest reading — «the suite is green, it just takes a while» — was available every time, and the
# real reading is that nothing after the eight hundredth test was ever run.
#
# So `asyncio.run` is answered here by a loop that is created once and closed at exit. The
# semantics tests rely on are unchanged: each call still runs a coroutine to completion on a loop
# nobody else is using, because these tests are synchronous and never overlap.
_LOOP = asyncio.new_event_loop()


def _run_on_the_one_loop(coro, *, debug=None):
    if debug is not None:
        _LOOP.set_debug(debug)
    return _LOOP.run_until_complete(coro)


asyncio.run = _run_on_the_one_loop


INTERNAL_TOKEN = os.environ["INTERNAL_SERVICE_TOKEN"]


@pytest.fixture(scope="session")
def client() -> TestClient:
    from app.main import app

    return TestClient(app)
