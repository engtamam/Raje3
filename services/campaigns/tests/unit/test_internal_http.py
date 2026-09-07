"""`internal_http.send`/`read` must not block the event loop.

THE DEFECT THIS CLOSES. Every peer call in this service goes through `send`/`read`, which called
`urllib.request.urlopen` directly inside an `async def` with no thread offload — the exact pattern
the JWKS verifier's own docstring already names as a production incident (a single slow fetch froze
the whole pod, `/healthz`/`/readyz` included, because this service's event loop is single-worker).
These tests do not just assert the returned value is correct — a synchronous implementation would
pass that too — they prove the event loop stays free to run OTHER coroutines while a slow "peer"
call is in flight, which is the one thing a synchronous `urlopen` cannot do.
"""
from __future__ import annotations

import asyncio
import io
import time
from unittest.mock import patch

from app.adapters import internal_http


class _SlowResp(io.BytesIO):
    """Answers like `urlopen`'s context manager, but only after blocking the calling thread."""

    def __init__(self, status: int, body: bytes, delay: float) -> None:
        super().__init__(body)
        self.status = status
        self._delay = delay

    def __enter__(self):
        time.sleep(self._delay)          # a real blocking call — what a slow peer looks like
        return self

    def __exit__(self, *a):
        return False


def _slow_urlopen(delay: float):
    def _open(req, timeout=0):
        return _SlowResp(200, b'{"ok": true}', delay)
    return _open


def test_send_offloads_the_blocking_call_so_the_loop_keeps_ticking():
    """While `send` waits on a 200ms "peer", a concurrently scheduled coroutine still runs on time —
    which is only possible if the blocking `urlopen` is off the event loop's own thread."""
    ticks: list[float] = []

    async def ticker():
        start = time.monotonic()
        for _ in range(4):
            await asyncio.sleep(0.02)
            ticks.append(time.monotonic() - start)

    async def scenario():
        with patch("urllib.request.urlopen", _slow_urlopen(0.2)):
            await asyncio.gather(
                internal_http.send("http://peer.invalid/x", timeout=5),
                ticker(),
            )

    asyncio.run(scenario())
    # Four 20ms ticks land close to their own schedule (well under the 200ms the blocking call
    # would have held the loop for, had it not been offloaded to a thread).
    assert ticks[-1] < 0.15, (
        "the event loop stalled — send() is blocking it instead of running in a thread")


def test_read_also_offloads_and_returns_only_the_body():
    async def scenario():
        with patch("urllib.request.urlopen", _slow_urlopen(0.05)):
            return await internal_http.read("http://peer.invalid/x", 5)

    body = asyncio.run(scenario())
    assert body == b'{"ok": true}'


def test_get_json_and_post_json_run_off_the_loop_too():
    """The two contracts every peer client actually calls — proved together since `get_json` and
    `post_json` are thin wrappers over `read`, not a second transport."""
    async def scenario():
        with patch("urllib.request.urlopen", _slow_urlopen(0.05)):
            got = await internal_http.get_json("http://peer.invalid/x", "tok", 5)
            posted = await internal_http.post_json(
                "http://peer.invalid/x", {"a": 1}, "tok", 5)
        return got, posted

    got, posted = asyncio.run(scenario())
    assert got == {"ok": True}
    assert posted == {"ok": True}
