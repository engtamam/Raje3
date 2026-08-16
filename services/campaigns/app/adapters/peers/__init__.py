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
from dataclasses import dataclass

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
    """What THIS shop can actually send — asked of reminders, per tenant.

    IT USED TO THROW THE TENANT AWAY. This client took `tenant` in both methods, fetched the
    platform library from operations once, cached it PROCESS-WIDE, and answered from the first row
    of the matching type. Every establishment on the pod got the same answer — and three facts that
    differ per establishment were missing from a docstring that promised them:

      · THE TONE, so the preview showed one wording and the customer received another.
      · META'S APPROVAL, which is per (tenant, name). A goal card read «متاح» for a shop whose
        library was still under review; he launched, and every recipient failed at the delivery
        layer for a reason he could do nothing about.
      · HIS OWN RE-WRITTEN TEXT, which the preview never showed him.

    THE CACHE IS PER TENANT NOW, and that is not a detail: a process-wide cache of a per-tenant
    answer is the same defect wearing a performance argument.
    """

    driver = "http"

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 5,
                 ttl_seconds: int = 300) -> None:
        self._url = url.rstrip("/") + path
        self._token = token
        self._timeout = timeout
        self._ttl = ttl_seconds
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}

    def _resolved(self, tenant: str) -> dict[str, Any]:
        import time
        now = time.time()
        hit = self._cache.get(tenant)
        if hit and now - hit[0] < self._ttl:
            return hit[1]
        q = urllib.parse.urlencode({"tenant": tenant})
        data = _get(f"{self._url}?{q}", self._token, self._timeout)
        rows = dict(data.get("templates") or {})
        self._cache[tenant] = (now, rows)
        return rows

    async def pick(self, tenant: str, template_type: str) -> dict[str, Any] | None:
        """The row this shop would send for this type, or None.

        None is what makes «لا يوجد قالب مفعّل لهذا الهدف» true rather than decorative.
        """
        return self._resolved(tenant).get(template_type)

    async def enabled_types(self, tenant: str) -> set[str]:
        return set(self._resolved(tenant))


# ── the audience: built from operations' customers and reminders' learned intervals ────────────
class NullAudience:
    driver = "null"

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self._rows = rows or []

    async def customers(self, tenant: str, *, service_id: str = "",
                        branch_id: str = "") -> list[dict[str, Any]]:
        # The fake narrows too, so a test that targets a branch exercises the narrowing rather
        # than passing because everything came back.
        if not branch_id:
            return list(self._rows)
        return [r for r in self._rows if r.get("last_branch_id") == branch_id]

    async def allows(self, tenant: str, subject_ref: str, cls: str) -> bool:
        return True


class HttpRoom:
    """Today's ceiling and what the engine has already spent — from the two services that own them.

    THIS PEER DID NOT EXIST, AND THAT IS THE WHOLE DEFECT. `build_peers` returned five keys;
    `container.py` asked for `ceiling` and `engine`, got None for both, and fell back to "the
    ceiling is unknown". So `share.known` was False on every request the product has ever served,
    the spread sentence never rendered once, and the engine's reserve was never subtracted from
    anything. Everything reported success; the feature simply was not there.

    FAILS SOFT, BOTH HALVES. An unreadable ceiling is «we do not know», which the share treats as
    "promise nothing and send as before" — and an unreadable reserve contributes zero rather than
    holding a campaign back on a number nobody could fetch. A campaign refused because insights
    was restarting would be a worse answer than a campaign that runs.
    """

    driver = "http"

    def __init__(self, *, reminders_url: str, room_path: str, insights_url: str,
                 reserve_path: str, token: str, timeout: int = 8) -> None:
        self._room = reminders_url.rstrip("/") + room_path
        self._reserve = (insights_url.rstrip("/") + reserve_path) if insights_url else ""
        self._token = token
        self._timeout = timeout

    async def read(self, tenant: str) -> Any:
        """The ceiling, in notification-service's own shape: -1 unlimited, 0 unknown."""
        try:
            data = _get(f"{self._room}?tenant={urllib.parse.quote(tenant)}",
                        self._token, self._timeout)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return _RoomRead()
        return _RoomRead(limit=int(data.get("limit") or 0), tier=str(data.get("tier") or ""),
                         used=int(data.get("used") or 0))

    async def engine_load(self, tenant: str) -> dict[str, int]:
        """`reserved` from insights, `used` from the same room read — one number each, no guesses."""
        reserved = 0
        if self._reserve:
            try:
                reserved = int((_get(f"{self._reserve}?tenant={urllib.parse.quote(tenant)}",
                                     self._token, self._timeout)).get("reserved") or 0)
            except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
                reserved = 0
        used = (await self.read(tenant)).used
        return {"reserved": reserved, "used": used}


@dataclass(frozen=True)
class _RoomRead:
    """What `share.compute` reads off a ceiling: the limit, and nothing it has to interpret."""

    limit: int = 0
    tier: str = ""
    used: int = 0

class HttpAudience:
    driver = "http"

    def __init__(self, *, operations_url: str, customers_path: str, reminders_url: str,
                 eligibility_path: str, token: str, timeout: int = 8,
                 rhythms_path: str = "") -> None:
        self._customers = operations_url.rstrip("/") + customers_path
        self._eligibility = reminders_url.rstrip("/") + eligibility_path
        self._rhythms = (reminders_url.rstrip("/") + rhythms_path) if rhythms_path else ""
        self._token = token
        self._timeout = timeout

    async def customers(self, tenant: str, *, service_id: str = "",
                        branch_id: str = "") -> list[dict[str, Any]]:
        """Everyone, with their last visit and their learned interval.

        RAISES on failure rather than returning an empty list. Half an audience is a campaign the
        owner runs again tomorrow — reaching the other half a day late and the first half twice.

        TWO SERVICES, ONE ROW. operations holds who they are and when they last came; reminders
        holds the RHYTHM it learned for each of them. The join was documented in operations' own
        route («campaigns joins the learned interval from reminders») and never written, so every
        audience rule fell through to a 90-day default for every customer alike — the per-customer
        cycle the product sells, computed and unread.

        THE RHYTHM IS THE SOFT HALF. Its absence costs precision, not the campaign: an unreachable
        reminders leaves the rows exactly as they were before this existed, and the rule falls back
        to the window default it used all along.
        """
        # THE BRANCH IS SENT, NOT APPLIED HERE. operations filters before its own 5000 cap; a
        # narrowing done on this side would silently drop the branch's older customers.
        data = _post(self._customers,
                     {"tenant": tenant, "limit": 5000, "branch_id": branch_id},
                     self._token, self._timeout)
        rows = list(data.get("customers") or [])
        if not rows or not self._rhythms:
            return rows
        try:
            learned = (_post(self._rhythms,
                             {"tenant": tenant, "service_id": service_id, "limit": 5000},
                             self._token, self._timeout)).get("rhythms") or {}
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return rows
        for r in rows:
            mine = learned.get(r.get("subject_ref") or "")
            if not mine:
                continue
            r["interval_days"] = mine.get("interval_days") or 0
            # THE PER-SERVICE SHAPE `_too_early` READS. Written only when the caller named a
            # service — a rhythm for "anything" is not this service's cycle, and putting it under
            # the service key would make an unrelated visit look like this one.
            if service_id:
                r["services"] = {service_id: {"last_visit": mine.get("last_visit") or 0,
                                              "interval_days": mine.get("interval_days") or 0}}
        return rows

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
            if "allowed" not in data:
                # THE SAME CALL AS THE TRANSPORT FAILURE BELOW, SAID OUT LOUD. An answer with no
                # verdict in it is a contract break rather than a refusal, and this is a PREVIEW —
                # the gate runs again at send time and is the one that decides. Written as an
                # explicit branch and not as `.get("allowed", True)`, because a default hides which
                # of the two situations produced the «yes».
                return True
            return bool(data["allowed"])
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
                   owner_text: str, idempotency_key: str,
                   offer_expires_at: int = 0,
                   offer_services: list[str] | None = None,
                   offer_value: str = "", coupon_code: str = "",
                   service_names: list[str] | None = None,
                   branch_id: str = "") -> dict[str, Any]:
        """Hand one message to reminders. It decides.

        Returns `{"sent": bool, "reason": str}` — and the reason is theirs, carried into the run
        report verbatim. Two vocabularies for one refusal is how an owner ends up believing there
        are two problems.
        """
        try:
            return _post(self._url, {
                "tenant": tenant, "subject_ref": subject_ref,
                "template_type": template_type, "class": cls,
                # WHICH NUMBER IT LEAVES FROM, and which branch the send log records. A chain with
                # a number per branch sent every campaign message from the central one until this
                # field travelled — see reminders' CampaignSendIn.branch_id.
                "branch_id": branch_id,
                "owner_text": owner_text, "idempotency_key": idempotency_key,
                # Carried so the send log can record the entitlement AND its end. Zero for every
                # message that offers nothing, which is most of them.
                "offer_expires_at": offer_expires_at,
                "offer_services": list(offer_services or []),
                # THE TYPED PARTS. A discount is «20%» or «50 ريال», a coupon code is machine-made,
                # and the covered services travel as WORDS because reminders holds ids and cannot
                # name anything.
                "offer_value": offer_value,
                "coupon_code": coupon_code,
                "service_names": list(service_names or []),
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
        "templates": HttpTemplates(url=settings.REMINDERS_SERVICE_URL,
                                   path=settings.REMINDERS_SENDABLE_PATH,
                                   token=settings.INTERNAL_SERVICE_TOKEN, timeout=t),
        "audience": HttpAudience(operations_url=settings.OPERATIONS_SERVICE_URL,
                                 customers_path=settings.CUSTOMERS_PATH,
                                 reminders_url=settings.REMINDERS_SERVICE_URL,
                                 eligibility_path=settings.ELIGIBILITY_PATH,
                                 rhythms_path=settings.REMINDERS_RHYTHMS_PATH,
                                 token=settings.INTERNAL_SERVICE_TOKEN, timeout=t),
        "sender": HttpSender(url=settings.REMINDERS_SERVICE_URL, path=settings.SEND_PATH,
                             token=settings.INTERNAL_SERVICE_TOKEN, timeout=t),
        # THE TWO KEYS THE CONTAINER ASKS FOR BY NAME. One object answers both because the two
        # numbers come from one read of reminders plus one of insights — and because two objects
        # would be two chances to wire only one of them, which is how this got lost the first time.
        "ceiling": HttpRoom(reminders_url=settings.REMINDERS_SERVICE_URL,
                            room_path=settings.REMINDERS_ROOM_PATH,
                            insights_url=settings.INSIGHTS_SERVICE_URL,
                            reserve_path=settings.INSIGHTS_RESERVE_PATH,
                            token=settings.INTERNAL_SERVICE_TOKEN, timeout=t),
        "engine": HttpRoom(reminders_url=settings.REMINDERS_SERVICE_URL,
                           room_path=settings.REMINDERS_ROOM_PATH,
                           insights_url=settings.INSIGHTS_SERVICE_URL,
                           reserve_path=settings.INSIGHTS_RESERVE_PATH,
                           token=settings.INTERNAL_SERVICE_TOKEN, timeout=t),
        "identity": HttpIdentity(url=settings.TENANT_SERVICE_URL,
                                 path=settings.TENANT_READ_PATH,
                                 token=settings.INTERNAL_SERVICE_TOKEN, timeout=t),
        "window": Window(start_hour=settings.SEND_WINDOW_START_HOUR,
                         end_hour=settings.SEND_WINDOW_END_HOUR),
    }
