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

    SIX TESTS IN THIS SUITE HAD NEVER RUN ONCE. They are written `async def` with
    `@pytest.mark.asyncio`, pytest-asyncio is not in this environment, and pytest's answer to a
    coroutine it cannot drive is to fail the test with "async def functions are not natively
    supported" — six red lines that look like six broken behaviours and are in fact six assertions
    nobody has ever evaluated. A permanently red test is read as noise within a week, which is how
    the ones beside it stop being read too.

    So the runner lives here rather than in a dependency: the rest of the suite drives coroutines
    through a local `run()` helper, and this makes the two styles equivalent instead of making one
    of them a lie.
    """
    import asyncio
    import inspect

    fn = pyfuncitem.obj
    if not inspect.iscoroutinefunction(fn):
        return None
    kwargs = {name: pyfuncitem.funcargs[name] for name in pyfuncitem._fixtureinfo.argnames}
    asyncio.run(fn(**kwargs))
    return True
