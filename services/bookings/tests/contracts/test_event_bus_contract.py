"""EventBus contract."""
from __future__ import annotations

import os

import pytest

from app.adapters.event_bus.memory import MemoryEventBus
from app.ports.event_bus import Event
from tests.contracts.util import run
from app.adapters.event_bus.redis import RedisEventBus

#: THE REAL DRIVER, HELD TO THE SAME PROMISE — whenever a server is there to hold it against.
#:
#: WITHOUT THIS PARAMETER THE CONTRACT ONLY EVER PROVED THAT THE IN-MEMORY DRIVER AGREES WITH
#: ITSELF. The fleet runs redis for this port; the memory driver exists for tests and for a
#: single-process bring-up. So the one that carries real traffic was the one nothing held.
#:
#:   docker run -d -p 6379:6379 redis:7-alpine
#:   REDIS_TEST_URL=redis://127.0.0.1:6379/0 pytest tests/contracts
_REDIS_URL = os.environ.get("REDIS_TEST_URL", "")


_PARAMS = [pytest.param(lambda: MemoryEventBus(), id="memory")]
if _REDIS_URL:
    _PARAMS.append(pytest.param(lambda: RedisEventBus(_REDIS_URL), id="redis"))


@pytest.fixture(params=_PARAMS)
def bus(request):
    b = request.param()
    if hasattr(b, "_client"):
        run(b._client.flushdb())
    yield b
    run(b.close())


def test_subscribe_then_publish_delivers(bus):
    received: list[Event] = []

    async def handler(ev: Event) -> None:
        received.append(ev)

    async def scenario() -> None:
        await bus.subscribe("topic.a", handler)
        await bus.publish("topic.a", Event(type="x", payload={"n": 1}))

    run(scenario())
    assert len(received) == 1
    assert received[0].payload == {"n": 1}


def test_no_subscriber_is_noop(bus):
    run(bus.publish("topic.none", Event(type="x", payload={})))


def test_handler_error_isolated(bus):
    async def bad(_ev: Event) -> None:
        raise RuntimeError("boom")

    async def scenario() -> None:
        await bus.subscribe("t", bad)
        await bus.publish("t", Event(type="x", payload={}))  # must not raise

    run(scenario())
