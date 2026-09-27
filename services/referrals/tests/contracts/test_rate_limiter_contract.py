"""RateLimiter contract."""
from __future__ import annotations

import os

import pytest

from app.adapters.rate_limiter.memory import MemoryRateLimiter
from tests.contracts.util import run
from app.adapters.rate_limiter.redis import RedisRateLimiter

#: THE REAL DRIVER, HELD TO THE SAME PROMISE — whenever a server is there to hold it against.
#:
#: WITHOUT THIS PARAMETER THE CONTRACT ONLY EVER PROVED THAT THE IN-MEMORY DRIVER AGREES WITH
#: ITSELF. The fleet runs redis for this port; the memory driver exists for tests and for a
#: single-process bring-up. So the one that carries real traffic was the one nothing held.
#:
#:   docker run -d -p 6379:6379 redis:7-alpine
#:   REDIS_TEST_URL=redis://127.0.0.1:6379/0 pytest tests/contracts
_REDIS_URL = os.environ.get("REDIS_TEST_URL", "")


_PARAMS = [pytest.param(lambda: MemoryRateLimiter(max_requests=3, window_seconds=60),
                        id="memory")]
if _REDIS_URL:
    _PARAMS.append(pytest.param(lambda: RedisRateLimiter(_REDIS_URL, 3, 60), id="redis"))


@pytest.fixture(params=_PARAMS)
def limiter(request):
    limiter = request.param()
    # EVERY KEY FROM THE PASS BEFORE IS A BUDGET ALREADY SPENT. Without this the second test reads
    # the first one's counters and fails for a reason that has nothing to do with the limiter.
    if hasattr(limiter, "_client"):
        run(limiter._client.flushdb())
    yield limiter
    run(limiter.close())


def test_allows_up_to_max_then_blocks(limiter):
    assert [run(limiter.allow("k")) for _ in range(4)] == [True, True, True, False]


def test_per_key_independent(limiter):
    for _ in range(3):
        run(limiter.allow("a"))
    assert run(limiter.allow("a")) is False
    assert run(limiter.allow("b")) is True  # different key, own budget


def test_reset_restores(limiter):
    for _ in range(3):
        run(limiter.allow("k"))
    run(limiter.reset("k"))
    assert run(limiter.allow("k")) is True
