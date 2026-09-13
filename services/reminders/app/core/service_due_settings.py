"""«حان وقت الخدمة» / «لم يستجب»'s OWN settings — read from campaigns, at every send of
`svc_service_reminder`.

THE COMPUTATION STAYS HERE, THE SETTINGS DO NOT. `scheduling.py` still decides exactly when this
message is due, per service, per customer — untouched by this file. What moved to campaigns is only
the owner's own on/off switch for the goal — no reward choice (owner's own call, 2026-09-13: keep
this the old mechanism, an on/off switch and nothing else).

SAME `Null*`/`Http*` SHAPE AS EVERY OTHER PEER IN THIS PRODUCT (mirroring campaigns' own
`HttpLoyalty`/`NullLoyalty` in `adapters/peers/__init__.py`): a `Null*` that answers the SAFE
DEFAULT — `active=True` — so a deployment that never wired `CAMPAIGNS_SERVICE_URL` keeps sending
exactly the reminder it always has, and an `Http*` that asks campaigns for real, failing back to
that same safe default on any trouble. FAILS OPEN, DELIBERATELY: an unreachable campaigns service
must not silence a reminder every shop already relies on — the one thing it must never do is fail
CLOSED into suppressing today's working behaviour.
"""
from __future__ import annotations

import time
import urllib.error
import urllib.parse
from dataclasses import dataclass
from typing import Any

from app.adapters import internal_http

_get = internal_http.get_json

#: The untouched, byte-for-byte-unchanged-today default — see this module's own docstring.
DEFAULT_ACTIVE = True


@dataclass(frozen=True)
class ServiceDueSettings:
    active: bool = DEFAULT_ACTIVE


class NullServiceDueSettings:
    """No campaigns service wired — every shop keeps getting today's plain reminder."""

    driver = "null"

    async def load(self, tenant: str) -> ServiceDueSettings:
        return ServiceDueSettings()


class HttpServiceDueSettings:
    """Asks campaigns' `/internal/campaigns/service-due-settings`, cached per tenant like
    `HttpIdentity` above it — one owner-facing setting, re-read every few minutes rather than on
    every single send of a template that can fire hundreds of times an hour across a fleet.
    """

    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 5,
                 ttl_seconds: int = 300) -> None:
        self._url = url.rstrip("/") + path
        self._token = token
        self._timeout = timeout
        self._ttl = ttl_seconds
        self._cache: dict[str, tuple[float, ServiceDueSettings]] = {}

    async def load(self, tenant: str) -> ServiceDueSettings:
        now = time.time()
        hit = self._cache.get(tenant)
        if hit and now - hit[0] < self._ttl:
            return hit[1]
        try:
            q = urllib.parse.urlencode({"tenant": tenant})
            data: dict[str, Any] = _get(f"{self._url}?{q}", self._token, self._timeout)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            # FAILS OPEN — see this module's own docstring. Not cached: a transient outage must not
            # freeze the safe default in place for the whole TTL once the peer recovers.
            return ServiceDueSettings()
        settings = ServiceDueSettings(active=bool(data.get("active", DEFAULT_ACTIVE)))
        self._cache[tenant] = (now, settings)
        return settings
