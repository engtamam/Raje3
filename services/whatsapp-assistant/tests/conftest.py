"""Shared test setup — see services/reminders/tests/conftest.py for the full rationale behind the
single-event-loop `asyncio.run` shim (imitated verbatim: this platform has no pytest-asyncio, and
without this shim every `async def` test silently never runs)."""
from __future__ import annotations

import asyncio
import os

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
    import inspect

    fn = pyfuncitem.obj
    if not inspect.iscoroutinefunction(fn):
        return None
    kwargs = {name: pyfuncitem.funcargs[name] for name in pyfuncitem._fixtureinfo.argnames}
    asyncio.run(fn(**kwargs))
    return True


_LOOP = asyncio.new_event_loop()


def _run_on_the_one_loop(coro, *, debug=None):
    if debug is not None:
        _LOOP.set_debug(debug)
    return _LOOP.run_until_complete(coro)


asyncio.run = _run_on_the_one_loop
