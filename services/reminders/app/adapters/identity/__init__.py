"""Who the establishment is — read from tenant-service, never stored here.

WHY THIS FILE EXISTS AT ALL. Every message this service sends renders `{{2}}` as the shop's name.
Until now that came from a `tenant_cache` collection nothing ever wrote, so it rendered EMPTY — a
message reading "your appointment at  is due", going out under a name that was not there. Meta
would have accepted it; the customer would have read it.

THE NAME LIVES IN tenant-service AND ONLY THERE. It serves `/internal/tenants/{id}`, whose record
carries `name` and a free-form `branding` dict. Copying it into our datastore would be a second
copy of the one string every customer of that shop reads in every message — and the first time the
two disagree is a message going out under a name that is not the one on the sign.

CACHED, WITH A SHORT TTL AND A LONG FALLBACK. Two different needs:

  The TTL is short because a shop that fixes a typo in its name should see it in the next message,
  not next week.

  The FALLBACK is unbounded because the tick runs unattended: if tenant-service is down at 3am, a
  reminder with yesterday's correct name is right, and a reminder with a blank name is a message
  the owner has to apologise for. Stale beats empty, and empty is the only outcome we refuse.

AND A MESSAGE IS NOT SENT WITH AN EMPTY NAME. If there is no cached value and the peer is
unreachable, the send is DEFERRED rather than rendered — see `Establishment.usable`.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Establishment:
    """What this service needs about a shop, and nothing else."""
    tenant: str
    name: str = ""
    # Which of the three wordings its templates use. OURS, not the platform's — it lives inside
    # their free-form branding dict under a key we own rather than in a table we invent.
    tone: str = "brief"
    branding: dict[str, Any] = field(default_factory=dict)
    fetched_at: int = 0

    @property
    def usable(self) -> bool:
        """Whether a message may be rendered from this.

        A blank name is the one thing that must stop a send. Everything else degrades: a missing
        tone falls back to `brief`, a missing colour is only a page's problem.
        """
        return bool(self.name.strip())


class NullIdentity:
    """Answers nothing, and says so. Correct for tests; refused in production by the boot guard,
    where it would mean every message rendering an empty shop name."""
    driver = "null"

    async def get(self, tenant: str) -> Establishment:
        return Establishment(tenant=tenant)


class HttpIdentity:
    """Reads tenant-service. stdlib urllib, like every other internal client here."""
    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 5,
                 ttl_seconds: int = 300) -> None:
        self._url = url.rstrip("/")
        self._path = path
        self._token = token
        self._timeout = timeout
        self._ttl = ttl_seconds
        self._cache: dict[str, Establishment] = {}

    async def get(self, tenant: str) -> Establishment:
        now = int(time.time())
        cached = self._cache.get(tenant)
        if cached is not None and now - cached.fetched_at < self._ttl:
            return cached
        try:
            fresh = self._fetch(tenant, now)
        except Exception:                                                   # noqa: BLE001
            # STALE BEATS EMPTY. A reminder carrying yesterday's correct name is right; one
            # carrying a blank name is a message the owner has to apologise for. If there is no
            # cached value either, `usable` is False and the caller defers rather than sends.
            return cached or Establishment(tenant=tenant)
        self._cache[tenant] = fresh
        return fresh

    def _fetch(self, tenant: str, now: int) -> Establishment:
        path = self._path.replace("{id}", tenant).replace("{}", tenant)
        req = urllib.request.Request(
            f"{self._url}{path}", headers={"X-Internal-Token": self._token})
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:    # nosec B310
            data = json.loads(resp.read() or b"{}")
        branding = data.get("branding") or {}
        return Establishment(
            tenant=tenant,
            # `display_name` in branding wins over the provisioned `name`: the first is what the
            # shop calls itself, the second is what whoever signed them up typed.
            name=str(branding.get("display_name") or data.get("name") or "").strip(),
            tone=str(branding.get("tone") or "brief"),
            branding=branding,
            fetched_at=now)


def build_identity(settings) -> Any:
    driver = (getattr(settings, "IDENTITY_DRIVER", "") or "null").lower()
    if driver == "null":
        return NullIdentity()
    return HttpIdentity(url=settings.TENANT_SERVICE_URL,
                        path=settings.TENANT_READ_PATH,
                        token=settings.INTERNAL_SERVICE_TOKEN,
                        timeout=settings.PEER_TIMEOUT_SECONDS,
                        ttl_seconds=settings.IDENTITY_CACHE_TTL_SECONDS)
