"""The peers this service talks to, and the one it never bypasses.

EVERY MESSAGE GOES THROUGH REMINDERS' GATE. There is no loyalty-shaped shortcut to
notification-service, for the same reason campaigns has none: a second send path is a second set of
rules, and the second one is always the one missing a check the day somebody adds one to the first.

The redemption receipt is EXEMPT from the quiet hours and from the message cap — but the exemption
is a property the gate already knows about the `per_account_notice` type (spec §8.4.1), not a
bypass we implement here. That distinction is the whole design: we ask, and it decides.

The shop's name comes from tenant-service, never a second copy, and a stale name beats an empty one
— the same rule the other services landed on after a message went out with a blank establishment.
"""
from __future__ import annotations

import asyncio
import urllib.error
import urllib.parse
from typing import Any

from app.adapters import internal_http


# The request itself is built in adapters/internal_http.py — the one place in this service that
# attaches the internal token. These two names stay because the clients below read well with them
# and because the failure policy that matters lives at each call site, not in the transport.
#
# BOTH OFF THE EVENT LOOP — fixed 2026-09-12, a real gap a QA audit found: `internal_http.post_json`/
# `get_json` are thin synchronous wrappers over a blocking `urllib.request.urlopen`, and every
# caller below is `async def` but called them directly with no `asyncio.to_thread` — a slow/down
# billing or reminders peer used to freeze this pod's whole event loop for every tenant, not just
# the one request. Wrapped ONCE, here, so every call site below stays a plain `await _post(...)`/
# `await _get(...)` rather than repeating `asyncio.to_thread` at each one.
async def _post(url: str, body: dict[str, Any], token: str, timeout: float, *,
               method: str = "POST") -> dict[str, Any]:
    return await asyncio.to_thread(internal_http.post_json, url, body, token, timeout,
                                   method=method)


async def _get(url: str, token: str, timeout: float) -> dict[str, Any]:
    return await asyncio.to_thread(internal_http.get_json, url, token, timeout)


# ── sending, through the gate ──────────────────────────────────────────────────────────────────
class NullSender:
    """Records what it would have sent. Correct in tests; refused in production by config.py,
    where it would mean a programme that deducts points and never tells anybody."""
    driver = "null"

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send(self, **kw: Any) -> dict[str, Any]:
        self.sent.append(kw)
        return {"sent": True}


class HttpSender:
    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 8,
                 merge_path: str = "/internal/reminders/redemption") -> None:
        self._url = url.rstrip("/") + path
        # WHERE A REDEMPTION ASKS TO JOIN A MESSAGE ALREADY WAITING, rather than send its own.
        self._merge_url = url.rstrip("/") + merge_path
        self._token = token
        self._timeout = timeout

    async def merge_redemption(self, *, tenant: str, subject_ref: str, reward_name: str,
                               cost: int, remaining: int) -> bool:
        """Try to fold this redemption into the confirmation that has not gone out yet (§9.6).

        True means it joined and NOTHING ELSE SHOULD BE SENT. False means there was nothing to join
        — a redemption without a visit — and the caller falls back to its own receipt, because a
        customer who spends points and hears nothing is worse served than one who gets two
        messages.

        UNREACHABLE COUNTS AS FALSE. A peer that is down must not silence a receipt; the fallback
        is the safe direction.
        """
        try:
            out = await _post(self._merge_url, {
                "tenant": tenant, "subject_ref": subject_ref, "reward_name": reward_name,
                "cost": int(cost), "remaining": int(remaining),
            }, self._token, self._timeout)
            return bool(out.get("merged"))
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            return False

    async def send(self, *, tenant: str, subject_ref: str, template_type: str, cls: str,
                   owner_text: str, idempotency_key: str) -> dict[str, Any]:
        """Hand one message to reminders. It decides whether it goes.

        Returns `{"sent": bool, "reason": str}`, and the reason is theirs verbatim — two
        vocabularies for one refusal is how an owner comes to believe there are two problems.
        """
        try:
            return await _post(self._url, {
                "tenant": tenant, "subject_ref": subject_ref,
                "template_type": template_type, "class": cls,
                "owner_text": owner_text, "idempotency_key": idempotency_key,
            }, self._token, self._timeout)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()[:200]
            return {"sent": False, "reason": f"رفض الإرسال ({exc.code}): {body}"}
        except (urllib.error.URLError, OSError) as exc:
            return {"sent": False, "reason": f"تعذّر الوصول لخدمة التذكيرات: {exc}"}


# ── the shop's name ────────────────────────────────────────────────────────────────────────────
class NullIdentity:
    driver = "null"

    def __init__(self, name: str = "المنشأة") -> None:
        self._name = name

    async def name(self, tenant: str) -> str:
        return self._name


class HttpIdentity:
    """Reads the establishment's name from tenant-service, and caches it.

    STALE BEATS EMPTY. When tenant-service is unreachable we serve the last name we saw rather than
    an empty string, because an empty establishment name in a customer's message is the one failure
    the owner cannot explain to the person who received it.
    """
    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 5,
                 ttl: int = 300) -> None:
        self._url = url.rstrip("/")
        self._path = path
        self._token = token
        self._timeout = timeout
        self._ttl = ttl
        self._cache: dict[str, tuple[float, str]] = {}

    async def name(self, tenant: str) -> str:
        import time
        hit = self._cache.get(tenant)
        now = time.time()
        if hit and now - hit[0] < self._ttl:
            return hit[1]
        path = self._path.replace("{id}", urllib.parse.quote(tenant, safe=""))
        try:
            data = await _get(f"{self._url}{path}", self._token, self._timeout)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            return hit[1] if hit else ""
        branding = data.get("branding") or {}
        name = str(data.get("name") or "")
        if name:
            self._cache[tenant] = (now, name)
            return name
        return hit[1] if hit else ""


# ── recording a visit, when a service reward is redeemed ───────────────────────────────────────
class NullVisits:
    driver = "null"

    def __init__(self) -> None:
        self.recorded: list[dict[str, Any]] = []

    async def record(self, **kw: Any) -> dict[str, Any]:
        self.recorded.append(kw)
        return {"ok": True}


class NullServicesPricing:
    """Local/test placeholder — answers `True` (permissive), same posture every other `Null*`
    peer here takes when nothing real is wired. A test that needs the refusal path constructs its
    own fake with an explicit answer rather than relying on this default."""
    driver = "null"

    async def __call__(self, tenant: str) -> bool:
        return True


class HttpServicesPricing:
    """Asks operations whether every one of a tenant's ACTIVE services is priced — the live check
    behind `invoice` mode (spec §9.3, `/settings/mode`'s own route), retiring the old till-only
    gate. Same shape as `HttpStaffEligibility` (bookings' own client for the same peer).

    FAILS CLOSED. Unlike most peer reads here (`{}`/`[]` on failure, "we don't know, proceed as if
    there is nothing to add"), this one gates whether points get calculated CORRECTLY going
    forward — an owner switching to `invoice` mode during a brief operations outage would otherwise
    silently enable a mode that then undercounts every visit with no error anywhere to notice it
    by. Refusing the switch and asking him to try again is the safer of the two wrong answers.
    """
    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def __call__(self, tenant: str) -> bool:
        try:
            out = await _post(self._url, {"tenant": tenant}, self._token, self._timeout)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return False
        return bool(out.get("all_priced"))


class HttpVisits:
    """Tells operations that a free service was performed (spec §9.4, reward type `service`).

    Without this, a free wash is points deducted and nothing else: no visit, so the reminder cycle
    is not restarted and the customer is reminded to come for a wash he just had. It is the join
    everybody forgets, which is why it has its own adapter rather than living inline.
    """
    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def record(self, *, tenant: str, subject_ref: str, service_id: str,
                     actor: str, source: str) -> dict[str, Any]:
        try:
            return await _post(self._url, {
                "tenant": tenant, "subject_ref": subject_ref, "service_id": service_id,
                "actor": actor, "source": source, "free": True,
            }, self._token, self._timeout)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError) as exc:
            # NOT fatal to the redemption. The points are already spent and the customer has his
            # reward; failing here would mean refusing a reward that was handed over. Reported so
            # the gap is visible rather than silent.
            return {"ok": False, "reason": str(exc)[:200]}


class HttpVisitFeed:
    """Visits recorded after a watermark — the RELIABLE path from a visit to points.

    Separate from `HttpVisits` above, which tells operations that a free service was performed.
    One writes, one reads; sharing a name would be the kind of confusion that ends with a recovery
    pass posting visits.
    """
    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 8,
                 page: int = 200) -> None:
        self._url = (url.rstrip("/") + path) if url else ""
        self._token = token
        self._timeout = timeout
        self._page = page

    @property
    def configured(self) -> bool:
        return bool(self._url)

    async def since(self, tenant: str, mark: int) -> dict[str, Any]:
        """`{visits, watermark, more}` — and `{}` when we could not ask.

        `{}` IS NOT «no visits». The caller must not advance its cursor on an unreadable answer:
        the window would be skipped and nobody could ever go back to it.
        """
        if not self._url:
            return {}
        try:
            return await _post(self._url, {"tenant": tenant, "since": int(mark), "limit": self._page},
                         self._token, self._timeout)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return {}


    async def tenants(self, limit: int = 500) -> list[str]:
        """Which establishments have visits AT ALL — the recovery's work list (د-19).

        NOT OUR BALANCE ROWS. Those are written by the first point ever awarded, so a shop whose
        very first visit event was the dropped one has no balance, is not in the list, and is
        therefore invisible to the repair FOR EVER — the exact case the repair exists for, and its
        first customers are the ones who lost their points.

        The visits themselves name their tenant, and the peer's sweeper answers with no tenant
        filter for precisely this reason. `[]` on an unreadable peer: the caller merges this with
        what it already knows, so a failed read narrows the pass rather than emptying it.
        """
        if not self._url:
            return []
        try:
            page = await _post(self._url, {"tenant": "", "since": 0, "limit": int(limit)},
                         self._token, self._timeout)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return []
        seen: list[str] = []
        for visit in page.get("visits") or []:
            tenant = str(visit.get("tenant") or "")
            if tenant and tenant not in seen:
                seen.append(tenant)
        return seen


class NullVisitFeed:
    driver = "null"
    configured = False

    async def since(self, tenant: str, mark: int) -> dict[str, Any]:
        return {}

    async def tenants(self, limit: int = 500) -> list[str]:
        return []


def build_peers(settings) -> dict[str, Any]:
    driver = (getattr(settings, "PEERS_DRIVER", "") or "null").lower()
    if driver == "null":
        return {"sender": NullSender(), "identity": NullIdentity(), "visits": NullVisits(),
                "visit_feed": NullVisitFeed(), "services_pricing": NullServicesPricing()}
    return {
        "sender": HttpSender(url=settings.REMINDERS_SERVICE_URL,
                             path=settings.REMINDERS_SEND_PATH,
                             token=settings.INTERNAL_SERVICE_TOKEN,
                             timeout=settings.PEER_TIMEOUT_SECONDS),
        "identity": HttpIdentity(url=settings.TENANT_SERVICE_URL,
                                 path=settings.TENANT_LOOKUP_PATH,
                                 token=settings.INTERNAL_SERVICE_TOKEN,
                                 timeout=settings.PEER_TIMEOUT_SECONDS),
        "visits": HttpVisits(url=settings.OPERATIONS_SERVICE_URL,
                             path=settings.OPERATIONS_VISIT_PATH,
                             token=settings.INTERNAL_SERVICE_TOKEN,
                             timeout=settings.PEER_TIMEOUT_SECONDS),
        # THE RECOVERY'S OWN READER. The config key naming this route has existed since the
        # service was written and nothing read it — which is why `Earner.catch_up` had no caller
        # and the bus was, in practice, the only path from a visit to a point.
        "visit_feed": HttpVisitFeed(url=settings.OPERATIONS_SERVICE_URL,
                                    path=settings.OPERATIONS_VISITS_SINCE_PATH,
                                    token=settings.INTERNAL_SERVICE_TOKEN,
                                    timeout=settings.PEER_TIMEOUT_SECONDS),
        "services_pricing": HttpServicesPricing(url=settings.OPERATIONS_SERVICE_URL,
                                               path=settings.OPERATIONS_SERVICES_PRICED_PATH,
                                               token=settings.INTERNAL_SERVICE_TOKEN,
                                               timeout=settings.PEER_TIMEOUT_SECONDS),
    }
