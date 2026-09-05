"""The three services this page reads, and the one thing it writes.

EVERY CLIENT HERE IS A THIN, BOUNDED READ. The page is public and unauthenticated, so each of these
runs on behalf of somebody we cannot identify — which makes every one of them a way to make us do
work if it is not bounded. Timeouts are short, page sizes are small, and nothing retries: the
composer has one deadline for the whole page, and a client that retried inside it would spend the
budget three times.

THE INTERNAL TOKEN IS OURS, NOT THE CUSTOMER'S. These calls are service-to-service; the customer
proves nothing and carries nothing. What limits them is that the reference in the URL already
determines exactly one tenant and one subject, and no client here accepts anything else.
"""
from __future__ import annotations

import urllib.error
import urllib.parse
from typing import Any

from app.adapters import internal_http


# The request itself is built in adapters/internal_http.py — the one place in this service that
# attaches the internal token. These two names stay because the clients below read well with them
# and because the failure policy that matters lives at each call site, not in the transport.
_post = internal_http.post_json
_get = internal_http.get_json


# ── tenant-service: who the shop is ────────────────────────────────────────────────────────────
class NullIdentity:
    driver = "null"

    async def get(self, tenant: str):
        from app.core.compose import Page  # noqa: F401  (kept for symmetry with the http client)
        return None

    async def logo_url(self, tenant: str) -> str:
        return ""


class HttpIdentity:
    """Reads tenant-service. Cached, because the shop's name does not change between two customers
    opening their pages a second apart — and an uncached read makes every page view a peer call."""
    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 3,
                 ttl_seconds: int = 300) -> None:
        self._url = url.rstrip("/")
        self._path = path
        self._token = token
        self._timeout = timeout
        self._ttl = ttl_seconds
        self._cache: dict[str, tuple[float, Any]] = {}

    async def get(self, tenant: str):
        import time
        now = time.time()
        hit = self._cache.get(tenant)
        if hit and now - hit[0] < self._ttl:
            return hit[1]
        path = self._path.replace("{id}", urllib.parse.quote(tenant, safe=""))
        data = _get(f"{self._url}{path}", self._token, self._timeout)
        shop = _Shop(name=str(data.get("name") or ""), branding=data.get("branding") or {})
        self._cache[tenant] = (now, shop)
        return shop

    async def logo_url(self, tenant: str) -> str:
        shop = await self.get(tenant)
        return str((getattr(shop, "branding", {}) or {}).get("logo_url") or "")


class _Shop:
    def __init__(self, name: str = "", branding: dict[str, Any] | None = None) -> None:
        self.name = name
        self.branding = branding or {}


# ── operations: the visits ─────────────────────────────────────────────────────────────────────
class NullOperations:
    driver = "null"

    async def visits_for(self, tenant: str, subject_ref: str) -> list[dict[str, Any]]:
        return []

    async def privacy_request(self, tenant: str, subject_ref: str, kind: str) -> bool:
        # FALSE, NEVER A CHEERFUL LIE. An unconfigured deployment must not tell a customer his
        # request was received when nothing recorded it — that is the one message he will act on
        # by doing nothing further.
        return False


class HttpOperations:
    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 3,
                 limit: int = 10) -> None:
        self._url = url.rstrip("/") + path
        self._token = token
        self._timeout = timeout
        # TEN, and the page shows ten. A customer's page is not a statement of account, and asking
        # for a hundred to display ten is a hundred rows crossing a network for nothing.
        self._limit = limit

    async def visits_for(self, tenant: str, subject_ref: str) -> list[dict[str, Any]]:
        data = _post(self._url, {"tenant": tenant, "subject_ref": subject_ref,
                                 "limit": self._limit}, self._token, self._timeout)
        return list(data.get("visits") or [])

    async def privacy_request(self, tenant: str, subject_ref: str, kind: str) -> bool:
        """Record that this customer asked his shop for his data — a copy of it, or its erasure.

        THE SHOP IS THE CONTROLLER and answers; we record. See operations' route for why nothing is
        erased here, and why the moment matters more than the wording: it is when the thirty-day
        clock in the regulation starts.
        """
        base = self._url.rsplit("/internal/", 1)[0]
        data = _post(f"{base}/internal/operations/privacy-request",
                     {"tenant": tenant, "subject_ref": subject_ref, "type": kind},
                     self._token, self._timeout)
        return bool(data.get("ok"))


# ── reminders: the switches ────────────────────────────────────────────────────────────────────
class NullLoyalty:
    driver = "null"

    async def balance_for(self, tenant: str, subject_ref: str) -> dict[str, Any]:
        return {}


class HttpLoyalty:
    """His points, read on his behalf.

    THE CUSTOMER HOLDS NO TOKEN — he opened a link from a WhatsApp message — so the page is
    composed here with portal's internal credential against loyalty's internal route. The
    alternative, minting an owner's token for a member of the public, is not a thing to be clever
    about.
    """

    driver = "http"

    def __init__(self, *, url: str, token: str, timeout: int = 3) -> None:
        self._url = url.rstrip("/")
        self._token = token
        self._timeout = timeout

    async def balance_for(self, tenant: str, subject_ref: str) -> dict[str, Any]:
        return _get(f"{self._url}/internal/loyalty/portal/balance"
                    f"?tenant={urllib.parse.quote(tenant, safe='')}"
                    f"&subject_ref={urllib.parse.quote(subject_ref, safe='')}",
                    self._token, self._timeout)


class NullReminders:
    driver = "null"

    async def prefs_for(self, tenant: str, subject_ref: str) -> dict[str, Any]:
        # THE SHAPE reminders ACTUALLY SERVES, and nothing else. This answered `{"stopped": {}}`,
        # a shape no route has ever returned, and the page read it as «nothing is switched off» —
        # which for marketing means «he agreed», about a customer nobody asked.
        return {"preferences": []}

    async def offers_for(self, tenant: str, subject_ref: str) -> dict[str, Any]:
        return {"offers": []}

    async def set_prefs(self, tenant: str, subject_ref: str, *, stopped: list[str],
                        merge: bool = False) -> bool:
        return False

    async def grant_marketing(self, tenant: str, subject_ref: str) -> bool:
        # FALSE, like every other write here. A null peer that reported a consent as recorded would
        # be the worst lie in this file: the screen would thank him and the record would be empty.
        return False


class HttpReminders:
    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 3) -> None:
        self._url = url.rstrip("/")
        self._path = path
        self._token = token
        self._timeout = timeout

    def _ref_path(self, tenant: str, subject_ref: str) -> str:
        ref = urllib.parse.quote(f"{tenant}.{subject_ref}", safe="")
        return self._path.replace("{ref}", ref).replace("{}", ref)

    async def prefs_for(self, tenant: str, subject_ref: str) -> dict[str, Any]:
        return _get(f"{self._url}{self._ref_path(tenant, subject_ref)}",
                    self._token, self._timeout)

    async def offers_for(self, tenant: str, subject_ref: str) -> dict[str, Any]:
        """The offers this customer is holding — the reason most people open the link.

        A SEPARATE ROUTE FROM THE SWITCHES, on purpose. They fail differently and they are read at
        different moments; folding them into one response would mean a customer who came to read
        an offer loses it because the preferences store was slow.
        """
        return _get(f"{self._url}/internal/portal/offers"
                    f"?tenant={urllib.parse.quote(tenant, safe='')}"
                    f"&subject_ref={urllib.parse.quote(subject_ref, safe='')}",
                    self._token, self._timeout)

    async def set_prefs(self, tenant: str, subject_ref: str, *, stopped: list[str],
                        merge: bool = False) -> bool:
        """Write the switches. Returns whether the PEER said it saved.

        `merge` exists for the one-tap unsubscribe: /stop adds marketing to whatever is already
        stopped rather than replacing the set. Replacing would silently re-enable everything else
        the customer had switched off — a stop that turns four things back on is the opposite of
        what they pressed.
        """
        if merge:
            current = {}
            try:
                current = await self.prefs_for(tenant, subject_ref)
            except Exception:                                               # noqa: BLE001
                # A read that fails must not make the stop replace their other choices. Falling
                # back to "stop only what was asked" is the safe direction: it under-stops rather
                # than re-enabling.
                current = {}
            existing = [p["class"] for p in (current.get("preferences") or [])
                        if isinstance(p, dict) and not p.get("enabled", True)]
            stopped = sorted(set(existing) | set(stopped))
        url = f"{self._url}{self._ref_path(tenant, subject_ref)}"
        try:
            body = _post(url, {"stopped": stopped}, self._token, self._timeout, method="PUT")
            return bool(body.get("saved"))
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            # FALSE, NOT AN EXCEPTION. The caller renders the page without a confirmation, which is
            # the honest outcome: a customer told their choice was saved who keeps receiving
            # messages does not try again — they block the number.
            return False

    async def grant_marketing(self, tenant: str, subject_ref: str) -> bool:
        """Marketing on, everything else untouched. Returns whether the PEER recorded it.

        WHY THIS GOES THROUGH THE PREFERENCES PUT rather than a consent route of its own: that PUT
        is already the one implementation that writes a consent RECORD — the statement, its
        version, the source, audited write-ahead (reminders' api/v1/prefs.py). A second door into
        the same decision would be a second definition of what «he agreed» means, and the two would
        drift on the day one of them was edited.

        THE STOPPED SET IS READ FIRST, for the mirror of the reason `/stop` merges: a bare
        `stopped=[]` would switch back ON every class he had deliberately switched off, so a tap
        meaning «yes to offers» would also undo «no to reminders».

        AND A READ THAT FAILS REFUSES THE GRANT rather than guessing an empty set. Under-granting
        costs one more tap; re-enabling what somebody silenced costs the number.
        """
        try:
            current = await self.prefs_for(tenant, subject_ref)
        except Exception:                                                   # noqa: BLE001
            return False
        prefs = current.get("preferences")
        # SILENCE IS NOT AGREEMENT. An empty answer is indistinguishable from «he stopped nothing»,
        # and acting on it is the same guess the paragraph above refuses.
        if not isinstance(prefs, list) or not prefs:
            return False
        stopped = sorted({str(p.get("class") or "") for p in prefs
                          if isinstance(p, dict) and not p.get("enabled", True)}
                         - {"marketing", ""})
        # SAME CALL AS `set_prefs`, deliberately — `urllib.request`/`json` were never imported in
        # this file (every other client here goes through `_post`/`_get`), so this method raised
        # NameError on every real invocation. Never caught by a test that mocks `_post`.
        url = f"{self._url}{self._ref_path(tenant, subject_ref)}"
        try:
            body = _post(url, {"stopped": stopped}, self._token, self._timeout, method="PUT")
            return bool(body.get("saved"))
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return False


def build_peers(settings) -> tuple[Any, Any, Any, Any]:
    """FOUR NOW, and loyalty is the fourth. Returned rather than reached for so that a deployment
    with LOYALTY_SERVICE_URL unset composes a page without a points section instead of failing —
    every peer here follows that rule and this one is not the exception."""
    if (getattr(settings, "PEERS_DRIVER", "") or "null").lower() == "null":
        return NullIdentity(), NullOperations(), NullReminders(), NullLoyalty()
    t = settings.PEER_TIMEOUT_SECONDS
    return (
        HttpIdentity(url=settings.TENANT_SERVICE_URL, path=settings.TENANT_READ_PATH,
                     token=settings.INTERNAL_SERVICE_TOKEN, timeout=t,
                     ttl_seconds=settings.IDENTITY_CACHE_TTL_SECONDS),
        HttpOperations(url=settings.OPERATIONS_SERVICE_URL,
                       path=settings.OPERATIONS_VISITS_PATH,
                       token=settings.INTERNAL_SERVICE_TOKEN, timeout=t),
        HttpReminders(url=settings.REMINDERS_SERVICE_URL, path=settings.REMINDERS_PREFS_PATH,
                      token=settings.INTERNAL_SERVICE_TOKEN, timeout=t),
        (HttpLoyalty(url=settings.LOYALTY_SERVICE_URL,
                     token=settings.INTERNAL_SERVICE_TOKEN, timeout=t)
         if getattr(settings, "LOYALTY_SERVICE_URL", "") else NullLoyalty()),
    )
