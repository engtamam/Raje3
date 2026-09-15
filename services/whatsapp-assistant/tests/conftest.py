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


def push_headers(body: bytes, *, ts: int | None = None) -> dict[str, str]:
    """A genuine job-service push signature over `body` (the exact bytes a test will send),
    verifiable against `INTERNAL_SERVICE_TOKEN` — the default secret `require_push_signature`
    falls back to when no dedicated `PUSH_SIGNING_SECRET` is configured, exactly as it is not in
    this test environment. Any route gated by `require_push_signature` needs these on top of the
    ordinary `X-Internal-Token` header."""
    import hashlib
    import hmac
    import time

    from app.core.push_verify import SIGNATURE_HEADER, TIMESTAMP_HEADER

    t = ts if ts is not None else int(time.time())
    signed = f"{t}.".encode("utf-8") + body
    sig = hmac.new(INTERNAL_TOKEN.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return {SIGNATURE_HEADER: sig, TIMESTAMP_HEADER: str(t)}


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
