"""The four services a campaign reads or hands work to.

CAMPAIGNS OWNS ALMOST NOTHING. The templates are operations', the audience is built from
operations' visits and reminders' engagement, the shop's name is tenant-service's, and the send is
reminders'. What this service owns is the campaign, the run, and the decision — which is exactly
the right amount.

EVERY CLIENT HERE IS BOUNDED AND FAILS LOUD. Unlike the portal, which renders for a customer and
must degrade, a campaign that cannot resolve its audience must NOT send to a partial one: half an
audience is a campaign the owner will run again tomorrow, reaching the other half a day late and
the first half twice.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

RIYADH = timezone(timedelta(hours=3))


def _post(url: str, body: dict[str, Any], token: str, timeout: int) -> dict[str, Any]:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "X-Internal-Token": token})
    with urllib.request.urlopen(req, timeout=timeout) as resp:              # nosec B310
        return json.loads(resp.read() or b"{}")


def _get(url: str, token: str, timeout: int) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"X-Internal-Token": token})
    with urllib.request.urlopen(req, timeout=timeout) as resp:              # nosec B310
        return json.loads(resp.read() or b"{}")


# ── templates: operations' library, filtered to what this tenant enabled ───────────────────────
class NullTemplates:
    driver = "null"

    def __init__(self, library: list[dict[str, Any]] | None = None) -> None:
        self._lib = library or []

    async def pick(self, tenant: str, template_type: str) -> dict[str, Any] | None:
        for t in self._lib:
            if t.get("type") == template_type:
                return t
        return None

    async def enabled_types(self, tenant: str) -> set[str]:
        return {t.get("type", "") for t in self._lib}


class HttpTemplates:
    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 5,
                 ttl_seconds: int = 300) -> None:
        self._url = url.rstrip("/") + path
        self._token = token
        self._timeout = timeout
        self._ttl = ttl_seconds
        self._cache: tuple[float, list[dict[str, Any]]] | None = None

    def _library(self) -> list[dict[str, Any]]:
        import time
        now = time.time()
        if self._cache and now - self._cache[0] < self._ttl:
            return self._cache[1]
        data = _get(self._url, self._token, self._timeout)
        lib = list(data.get("templates") or [])
        self._cache = (now, lib)
        return lib

    async def pick(self, tenant: str, template_type: str) -> dict[str, Any] | None:
        """The tenant's tone of this template type, and only if it is active.

        An INACTIVE template is not picked, which is what makes "this goal is not enabled" true
        rather than decorative — a campaign built on a switched-off template would be approved by
        Meta and refused by our own library at send time.
        """
        for t in self._library():
            if t.get("type") == template_type and t.get("active", True):
                return t
        return None

    async def enabled_types(self, tenant: str) -> set[str]:
        return {t.get("type", "") for t in self._library() if t.get("active", True)}


# ── the audience: built from operations' customers and reminders' learned intervals ────────────
class NullAudience:
    driver = "null"

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self._rows = rows or []

    async def customers(self, tenant: str) -> list[dict[str, Any]]:
        return list(self._rows)

    async def allows(self, tenant: str, subject_ref: str, cls: str) -> bool:
        return True


class HttpAudience:
    driver = "http"

    def __init__(self, *, operations_url: str, customers_path: str, reminders_url: str,
                 eligibility_path: str, token: str, timeout: int = 8) -> None:
        self._customers = operations_url.rstrip("/") + customers_path
        self._eligibility = reminders_url.rstrip("/") + eligibility_path
        self._token = token
        self._timeout = timeout

    async def customers(self, tenant: str) -> list[dict[str, Any]]:
        """Everyone, with their last visit and their learned interval.

        RAISES on failure rather than returning an empty list. Half an audience is a campaign the
        owner runs again tomorrow — reaching the other half a day late and the first half twice.
        """
        data = _post(self._customers, {"tenant": tenant, "limit": 5000},
                     self._token, self._timeout)
        return list(data.get("customers") or [])

    async def allows(self, tenant: str, subject_ref: str, cls: str) -> bool:
        """Would reminders' gate let this through right now?

        Asked BEFORE the send so the preview's count is the count that goes out. A failure here is
        treated as "yes": the gate will refuse it again at send time anyway, and excluding someone
        because a peer blinked would silently shrink an audience with no reason the owner can see.
        """
        try:
            data = _post(self._eligibility,
                         {"tenant": tenant, "subject_ref": subject_ref, "class": cls},
                         self._token, self._timeout)
            return bool(data.get("allowed", True))
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return True


# ── the send: reminders, always ────────────────────────────────────────────────────────────────
class NullSender:
    driver = "null"

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send(self, **kw: Any) -> dict[str, Any]:
        self.sent.append(kw)
        return {"sent": True}


class HttpSender:
    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def send(self, *, tenant: str, subject_ref: str, template_type: str, cls: str,
                   owner_text: str, idempotency_key: str) -> dict[str, Any]:
        """Hand one message to reminders. It decides.

        Returns `{"sent": bool, "reason": str}` — and the reason is theirs, carried into the run
        report verbatim. Two vocabularies for one refusal is how an owner ends up believing there
        are two problems.
        """
        try:
            return _post(self._url, {
                "tenant": tenant, "subject_ref": subject_ref,
                "template_type": template_type, "class": cls,
                "owner_text": owner_text, "idempotency_key": idempotency_key,
            }, self._token, self._timeout)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()[:200]
            return {"sent": False, "reason": f"رفض الإرسال ({exc.code}): {body}"}


# ── the shop's name, for the preview ───────────────────────────────────────────────────────────
class NullIdentity:
    driver = "null"

    async def name(self, tenant: str) -> str:
        return ""


class HttpIdentity:
    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 5,
                 ttl_seconds: int = 300) -> None:
        self._url = url.rstrip("/")
        self._path = path
        self._token = token
        self._timeout = timeout
        self._ttl = ttl_seconds
        self._cache: dict[str, tuple[float, str]] = {}

    async def name(self, tenant: str) -> str:
        import time
        now = time.time()
        hit = self._cache.get(tenant)
        if hit and now - hit[0] < self._ttl:
            return hit[1]
        path = self._path.replace("{id}", urllib.parse.quote(tenant, safe=""))
        data = _get(f"{self._url}{path}", self._token, self._timeout)
        branding = data.get("branding") or {}
        name = str(branding.get("display_name") or data.get("name") or "")
        self._cache[tenant] = (now, name)
        return name


# ── the window, for the "when" sentence ────────────────────────────────────────────────────────
class Window:
    """Is it inside the permitted sending hours right now?

    A LOCAL COPY OF ONE FACT, not a second gate. reminders decides whether a message goes; this
    only decides which sentence the preview shows. Asking the peer for a sentence would put a
    network call on a screen that has to render instantly, and getting it wrong costs a wrong
    sentence rather than a wrong send.
    """

    def __init__(self, *, start_hour: int = 7, end_hour: int = 22) -> None:
        self._start = start_hour
        self._end = end_hour

    def inside_window(self, now: int) -> bool:
        return self._start <= datetime.fromtimestamp(now, RIYADH).hour < self._end


def build_peers(settings) -> dict[str, Any]:
    if (getattr(settings, "PEERS_DRIVER", "") or "null").lower() == "null":
        return {"templates": NullTemplates(), "audience": NullAudience(),
                "sender": NullSender(), "identity": NullIdentity(),
                "window": Window(start_hour=settings.SEND_WINDOW_START_HOUR,
                                 end_hour=settings.SEND_WINDOW_END_HOUR)}
    t = settings.PEER_TIMEOUT_SECONDS
    return {
        "templates": HttpTemplates(url=settings.OPERATIONS_SERVICE_URL,
                                   path=settings.TEMPLATES_PATH,
                                   token=settings.INTERNAL_SERVICE_TOKEN, timeout=t),
        "audience": HttpAudience(operations_url=settings.OPERATIONS_SERVICE_URL,
                                 customers_path=settings.CUSTOMERS_PATH,
                                 reminders_url=settings.REMINDERS_SERVICE_URL,
                                 eligibility_path=settings.ELIGIBILITY_PATH,
                                 token=settings.INTERNAL_SERVICE_TOKEN, timeout=t),
        "sender": HttpSender(url=settings.REMINDERS_SERVICE_URL, path=settings.SEND_PATH,
                             token=settings.INTERNAL_SERVICE_TOKEN, timeout=t),
        "identity": HttpIdentity(url=settings.TENANT_SERVICE_URL,
                                 path=settings.TENANT_READ_PATH,
                                 token=settings.INTERNAL_SERVICE_TOKEN, timeout=t),
        "window": Window(start_hour=settings.SEND_WINDOW_START_HOUR,
                         end_hour=settings.SEND_WINDOW_END_HOUR),
    }
