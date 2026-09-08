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

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


INTERNAL_TOKEN = os.environ["INTERNAL_SERVICE_TOKEN"]


@pytest.fixture(scope="session")
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


def pytest_pyfunc_call(pyfuncitem):
    """Run a coroutine test on a real loop, with no plugin to install.

    pytest-asyncio is not in this environment, and pytest's answer to a coroutine it cannot drive
    is to fail the test with "async def functions are not natively supported" — a red line that
    looks like a broken behaviour and is in fact an assertion nobody has ever evaluated. A
    permanently red test is read as noise within a week, which is how the ones beside it stop
    being read too. Copied from services/loyalty/tests/conftest.py, which hit exactly this.
    """
    import asyncio
    import inspect

    fn = pyfuncitem.obj
    if not inspect.iscoroutinefunction(fn):
        return None
    kwargs = {name: pyfuncitem.funcargs[name] for name in pyfuncitem._fixtureinfo.argnames}
    asyncio.run(fn(**kwargs))
    return True


# ── ONE EVENT LOOP FOR THE WHOLE SESSION ──────────────────────────────────────────────────────
# `asyncio.run()` opens and closes a loop per call, and each one allocates a self-pipe socket pair.
# Past several hundred of them a Windows run stops — no CPU, no traceback, no failing test, and the
# honest reading («it is just slow») is available every time. A gate that cannot finish is not a
# gate. The semantics these tests rely on are unchanged: each call still runs one coroutine to
# completion on a loop nobody else is using.
import asyncio as _asyncio  # noqa: E402

_LOOP = _asyncio.new_event_loop()


def _run_on_the_one_loop(coro, *, debug=None):
    if debug is not None:
        _LOOP.set_debug(debug)
    return _LOOP.run_until_complete(coro)


_asyncio.run = _run_on_the_one_loop
