"""Cache contract."""
from __future__ import annotations

import os

import pytest

from app.adapters.cache.memory import MemoryCache
from tests.contracts.util import run
from app.adapters.cache.redis import RedisCache

#: THE REAL DRIVER, HELD TO THE SAME PROMISE — whenever a server is there to hold it against.
#:
#: WITHOUT THIS PARAMETER THE CONTRACT ONLY EVER PROVED THAT THE IN-MEMORY DRIVER AGREES WITH
#: ITSELF. The fleet runs redis for this port; the memory driver exists for tests and for a
#: single-process bring-up. So the one that carries real traffic was the one nothing held.
#:
#:   docker run -d -p 6379:6379 redis:7-alpine
#:   REDIS_TEST_URL=redis://127.0.0.1:6379/0 pytest tests/contracts
_REDIS_URL = os.environ.get("REDIS_TEST_URL", "")


_PARAMS = [pytest.param(lambda: MemoryCache(), id="memory")]
if _REDIS_URL:
    _PARAMS.append(pytest.param(lambda: RedisCache(_REDIS_URL), id="redis"))


@pytest.fixture(params=_PARAMS)
def cache(request):
    c = request.param()
    # A SHARED SERVER BETWEEN PARAMETERS IS A TEST THAT PASSES BECAUSE OF THE ONE BEFORE IT. The
    # memory driver starts empty by construction; redis does not, and the whole matrix points at
    # one database.
    if hasattr(c, "_client"):
        run(c._client.flushdb())
    yield c
    run(c.close())


def test_set_get(cache):
    run(cache.set("k", "v"))
    assert run(cache.get("k")) == "v"


def test_missing_returns_none(cache):
    assert run(cache.get("absent")) is None


def test_delete(cache):
    run(cache.set("k", "v"))
    assert run(cache.delete("k")) is True
    assert run(cache.get("k")) is None


def test_ttl_value_present_immediately(cache):
    run(cache.set("k", "v", ttl_seconds=100))
    assert run(cache.get("k")) == "v"


def test_health(cache):
    assert run(cache.health()) is True
