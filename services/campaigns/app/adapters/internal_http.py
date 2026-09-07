"""The one place this service builds an outbound request carrying the internal token.

WHY THIS EXISTS. The token header was set by hand at every internal call site — in three different
idioms (a headers dict literal, a dict the caller mutated when the token was non-empty, and
`req.add_header`) spread across `adapters/` and `core/`. Three spellings of one decision means three
places to keep in step, and the next thing every internal call has to carry — a caller identity the
callee can actually verify — would have to be written into each of them separately. It is written
here once instead.

WHAT THIS DELIBERATELY DOES NOT DO. It does not catch anything, does not retry, and does not judge a
status code. Every call site here has its own answer to a peer that fails, and those answers are not
interchangeable: the audit sink must never raise, the consent gate turns an error into UNKNOWN
rather than a verdict, the audience client raises on purpose because half an audience is worse than
none, and the licence check reads any failure as "no". Unifying that here would quietly replace four
considered policies with one. So this builds the request, sends it, and hands back what came back —
the exception included, for the caller to answer in its own terms.

`urlopen` is called on a URL assembled from CONFIG, never from a request body, which is what makes
the `# nosec B310` below true rather than merely asserted: no caller can point an internally
authenticated call at a host of their choosing.

`urlopen` ITSELF IS SYNCHRONOUS, AND EVERY CALLER HERE IS `async def`. `send`/`read` below run the
blocking socket call inside `asyncio.to_thread`, the same offload `adapters/object_store/local.py`
already uses for its own blocking filesystem calls — a pod running this service is single-worker,
so a peer call left un-offloaded doesn't just slow its own request, it freezes every other
in-flight request on the pod, `/healthz`/`/readyz` included, for the full round trip. That exact
failure mode is already documented as a production incident for the JWKS verifier
(`adapters/token_verifier/jwks.py`) — this file is what every OTHER peer call goes through, so the
same fix belongs here, once, rather than repeated at each call site.
"""
from __future__ import annotations

import asyncio
import json
import urllib.request
from typing import Any

JSON = "application/json"


def request(url: str, *, method: str | None = None, body: bytes | None = None,
            content_type: str = "", token: str = "", omit_blank_token: bool = False,
            ) -> urllib.request.Request:
    """Build one internally authenticated request. THE only place the token header is attached.

    `omit_blank_token` is the one difference between call sites that had to survive being brought
    together. The audit sink and the consent gate leave the header OFF entirely when no token is
    configured — they are wired in local runs where the peer does not ask for one — while the peer
    clients and the licence check send the header regardless, empty value and all, and let the
    callee refuse. Sending a blank header where none was sent before, or dropping one that was
    always sent, are both changes to what goes on the wire, so the caller keeps saying which it is.
    """
    headers: dict[str, str] = {}
    if content_type:
        headers["Content-Type"] = content_type
    if token or not omit_blank_token:
        headers["X-Internal-Token"] = token
    return urllib.request.Request(url, data=body, method=method, headers=headers)


def _send_sync(url: str, *, timeout: float, **kw: Any) -> tuple[int, bytes]:
    with urllib.request.urlopen(request(url, **kw),
                                timeout=timeout) as resp:          # nosec B310 - config-only host
        return resp.status, resp.read()


async def send(url: str, *, timeout: float, **kw: Any) -> tuple[int, bytes]:
    """Send, and return `(status, raw body)` for callers that judge the status themselves.

    Offloaded to a worker thread — see the module docstring — so a slow peer blocks only the
    awaiting caller, not the whole pod's event loop.
    """
    return await asyncio.to_thread(_send_sync, url, timeout=timeout, **kw)


def _read_sync(url: str, timeout: float, **kw: Any) -> bytes:
    with urllib.request.urlopen(request(url, **kw),
                                timeout=timeout) as resp:          # nosec B310 - config-only host
        return resp.read()


async def read(url: str, timeout: float, **kw: Any) -> bytes:
    """Send, and read ONLY the body.

    Deliberately does not touch `resp.status`: the peer clients never did, `urlopen` has already
    raised on 4xx/5xx by the time this returns, and the fakes those clients are tested against
    implement `read()` and nothing else. Reading a status here would be a new demand on every
    response object in the suite for a value no caller ever asked for.

    Offloaded to a worker thread — see the module docstring — same as `send`.
    """
    return await asyncio.to_thread(_read_sync, url, timeout, **kw)


async def get_json(url: str, token: str, timeout: float) -> dict[str, Any]:
    """A GET whose answer is JSON. The failure stays the caller's to answer."""
    return json.loads(await read(url, timeout, token=token) or b"{}")


async def post_json(url: str, body: dict[str, Any], token: str, timeout: float, *,
                    method: str = "POST") -> dict[str, Any]:
    """A JSON body sent under the internal token, same contract as `get_json`.

    `method` is POST unless the peer's contract says otherwise — portal saves a customer's message
    preferences with a PUT, which is the same request in every other respect and has no business
    being a second hand-rolled one.
    """
    return json.loads(await read(url, timeout, method=method, body=json.dumps(body).encode(),
                                 content_type=JSON, token=token) or b"{}")
