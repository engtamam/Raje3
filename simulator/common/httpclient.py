"""ONE pooled `httpx.AsyncClient` reused per (event loop, base URL) — instead of every Action
opening (and closing) a brand-new TCP connection for EVERY single HTTP call, which is what was
actually exhausting local ephemeral ports on Windows under real load (the platform-scale shared-
server experiment's own failure — see the README's own note on it): a load/noise/population run
already fires hundreds of individual short-lived connections against ONE spawned service within
seconds, and `httpx.AsyncClient()` used as a fresh context manager per call never reuses any of
them (no keep-alive, TIME_WAIT pile-up on the exact same port range every OTHER connection in the
same burst is also competing for).

KEYED BY THE RUNNING EVENT LOOP ITSELF (a `WeakKeyDictionary`, not `id(loop)`), never a plain
module-level singleton: an `httpx.AsyncClient` is bound to the loop that created it, and every
test in this simulator calls `asyncio.run(...)`, which hands it a BRAND NEW loop — reusing a
client from a prior, now-closed loop would fail hard on its next real request. Tying the cache to
the loop object's own identity (not a recycled integer id, which Python can and does reuse once an
old loop is garbage-collected) means the WHOLE per-loop cache is dropped for free the moment that
loop itself is, with no explicit teardown hook needed anywhere in this simulator's own scenario or
fixture code.
"""
from __future__ import annotations

import asyncio
import weakref
from urllib.parse import urlsplit

import httpx

_registry: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, dict[str, httpx.AsyncClient]]" \
    = weakref.WeakKeyDictionary()


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def _client_for(url: str) -> httpx.AsyncClient:
    loop = asyncio.get_running_loop()
    per_loop = _registry.setdefault(loop, {})
    origin = _origin(url)
    client = per_loop.get(origin)
    if client is None:
        # Generous pool limits — a load/population/noise scenario deliberately drives MANY
        # genuinely concurrent callers at once against the same spawned service; a small default
        # pool would just turn "pooled" into a new, self-inflicted bottleneck.
        client = httpx.AsyncClient(
            limits=httpx.Limits(max_keepalive_connections=200, max_connections=400))
        per_loop[origin] = client
    return client


async def request(method: str, url: str, **kwargs) -> httpx.Response:
    """Drop-in replacement for `async with httpx.AsyncClient() as client: await client.request(...)`
    — same call shape, same return type, the only difference is the underlying connection is
    reused rather than opened and torn down fresh every time."""
    client = _client_for(url)
    return await client.request(method, url, **kwargs)
