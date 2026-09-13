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

from dataclasses import dataclass

import urllib.error
import urllib.parse
from datetime import datetime
from typing import Any

from app.core.riyadh import RIYADH
from app.adapters import internal_http

# The request itself is built in adapters/internal_http.py — the one place in this service that
# attaches the internal token. These two names stay because the clients below read well with them
# and because the failure policy that matters lives at each call site, not in the transport.
_post = internal_http.post_json
_get = internal_http.get_json


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

    async def pick_for_preview(self, tenant: str, template_type: str) -> dict[str, Any] | None:
        # LOCAL/TEST DEFAULT — every seeded type is already sendable here (see `statuses` below),
        # so there is nothing a preview-only fallback would ever add over `pick` itself.
        return await self.pick(tenant, template_type)

    async def enabled_types(self, tenant: str) -> set[str]:
        return {t.get("type", "") for t in self._lib}

    async def blocked_reasons(self, tenant: str) -> dict[str, str]:
        return {}

    async def statuses(self, tenant: str) -> dict[str, str]:
        # LOCAL/TEST DEFAULT — every seeded type reads "approved", matching the permissive
        # posture every other Null* peer here takes with nothing real wired.
        return {t.get("type", ""): "approved" for t in self._lib}


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

    async def _raw(self, tenant: str) -> dict[str, Any]:
        """The FULL answer — `templates` and `blocked` together, cached as one unit.

        THEY USED TO BE CACHED APART: this method kept only `rows`, so `blocked` — reminders' own
        per-type reason a goal is not sendable, «قيد مراجعة واتساب» vs «لا يوجد قالب فعّال» — was
        fetched and thrown away on every call. The goal card then had nothing to say but a single
        hardcoded «غير مفعّل — اضغط للتفعيل», WRONG in both halves: nothing is «مفعّل» for the owner
        to toggle (§10.8's own Messages.tsx docstring: the words «قالب» و«اعتماد» never reach him),
        and there is no press that does anything — the card is `disabled` the moment it needs
        enabling, so the very sentence promising a tap was never true.
        """
        import time
        now = time.time()
        hit = self._cache.get(tenant)
        if hit and now - hit[0] < self._ttl:
            return hit[1]
        q = urllib.parse.urlencode({"tenant": tenant})
        data = await _get(f"{self._url}?{q}", self._token, self._timeout)
        self._cache[tenant] = (now, data)
        return data

    async def pick(self, tenant: str, template_type: str) -> dict[str, Any] | None:
        """The row this shop would send for this type, or None.

        None is what makes «لا يوجد قالب مفعّل لهذا الهدف» true rather than decorative. Used by
        `create()` — the one place that must never see a not-yet-approved row as if it were
        sendable.
        """
        return dict((await self._raw(tenant)).get("templates") or {}).get(template_type)

    async def pick_for_preview(self, tenant: str, template_type: str) -> dict[str, Any] | None:
        """The row `/preview` shows, and it is allowed to be one Meta has not approved yet
        (2026-09-13): the sendable row if there is one, else reminders' own `preview_only`
        fallback — the exact words the send will use once approval lands, tagged so the screen
        can grey the launch button out without hiding the message itself. `None` only when
        neither exists, i.e. this type was never seeded at all.
        """
        raw = await self._raw(tenant)
        row = dict(raw.get("templates") or {}).get(template_type)
        if row is not None:
            return {**row, "meta_approved": True}
        preview_row = dict(raw.get("preview_only") or {}).get(template_type)
        if preview_row is not None:
            return {**preview_row, "meta_approved": False}
        return None

    async def enabled_types(self, tenant: str) -> set[str]:
        return set(dict((await self._raw(tenant)).get("templates") or {}))

    async def blocked_reasons(self, tenant: str) -> dict[str, str]:
        """reminders' OWN sentence for why a type is not sendable — never guessed here."""
        return dict((await self._raw(tenant)).get("blocked") or {})

    async def statuses(self, tenant: str) -> dict[str, str]:
        """One status word per type — pending | approved | rejected | paused | disabled |
        not_registered | not_seeded | unknown — reminders' own `rendering.type_status`, the same
        badge the admin panel's own template screen shows. `{}` when the peer's answer carried
        none (an old cached response from before this field existed, or an unreachable peer) —
        a caller reads a missing key as "unknown" on its own, same as every other status here."""
        return dict((await self._raw(tenant)).get("statuses") or {})


# ── the audience: built from operations' customers and reminders' learned intervals ────────────
class SourceRows(list):
    """The customer rows, plus whether operations had to stop before the end of its own book.

    A plain list carries the rows and loses the one fact the owner needs: that there were more.
    `audience.resolve` reads this attribute when present and defaults to False when it is not, so
    every existing caller and every fake in the suite keeps working — and for those the honest
    answer IS False, because a list built in a test is never a truncated read.
    """

    truncated = False


class NullAudience:
    driver = "null"

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self._rows = rows or []

    async def customers(self, tenant: str, *, service_id: str = "",
                        service_ids: list[str] | None = None,
                        branch_id: str = "") -> list[dict[str, Any]]:
        # The fake narrows too, so a test that targets a branch exercises the narrowing rather
        # than passing because everything came back.
        if not branch_id:
            return list(self._rows)
        return [r for r in self._rows if r.get("last_branch_id") == branch_id]

    async def allows(self, tenant: str, subject_ref: str, cls: str) -> bool:
        return True

    async def redeemed(self, tenant: str, reached: list[dict[str, Any]]) -> int:
        return 0


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
            data = await _get(f"{self._room}?tenant={urllib.parse.quote(tenant)}",
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
                reserved = int((await _get(f"{self._reserve}?tenant={urllib.parse.quote(tenant)}",
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
                 rhythms_path: str = "", redeemed_path: str = "") -> None:
        self._customers = operations_url.rstrip("/") + customers_path
        self._eligibility = reminders_url.rstrip("/") + eligibility_path
        self._rhythms = (reminders_url.rstrip("/") + rhythms_path) if rhythms_path else ""
        self._redeemed = (operations_url.rstrip("/") + redeemed_path) if redeemed_path else ""
        self._token = token
        self._timeout = timeout

    async def customers(self, tenant: str, *, service_id: str = "",
                        service_ids: list[str] | None = None,
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

        SEVERAL SERVICES, ONE ROW EACH (2026-09-13): `service_ids` (a multi-select offer) asks
        reminders once per service and MERGES every answer onto the same row's `services` dict —
        never one read per service silently overwriting the last, which is what a naive loop
        reassigning `r["services"] = {...}` would do.
        """
        # THE BRANCH IS SENT, NOT APPLIED HERE. operations filters before its own 5000 cap; a
        # narrowing done on this side would silently drop the branch's older customers.
        data = await _post(self._customers,
                           {"tenant": tenant, "limit": 5000, "branch_id": branch_id},
                           self._token, self._timeout)
        # A LIST THAT CARRIES WHETHER IT IS THE WHOLE LIST. operations now says whether its own
        # read stopped early, and that fact has to survive the trip to `audience.resolve` or the
        # preview goes on reporting «reaches 4,300» for a shop whose book it only half saw. A
        # plain list cannot carry it and changing the callable's signature would touch ten call
        # sites and every fake in the suite — where the honest answer is always False anyway.
        rows = SourceRows(data.get("customers") or [])
        rows.truncated = bool(data.get("truncated"))
        ids = list(dict.fromkeys((service_ids or []) + ([service_id] if service_id else [])))
        if not rows or not self._rhythms or not ids:
            return rows
        by_subject: dict[str, dict[str, Any]] = {r.get("subject_ref") or "": r for r in rows}
        for sid in ids:
            try:
                learned = (await _post(self._rhythms,
                                       {"tenant": tenant, "service_id": sid, "limit": 5000},
                                       self._token, self._timeout)).get("rhythms") or {}
            except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
                continue
            for subject, mine in learned.items():
                r = by_subject.get(subject)
                if r is None:
                    continue
                # THE FIRST SERVICE ASKED ALSO SETS THE ROW'S TOP-LEVEL `interval_days` — kept for
                # every OTHER goal's matcher, which reads it unqualified (a single-service offer
                # is the common case and the only one those matchers ever look at).
                if "interval_days" not in r or sid == ids[0]:
                    r["interval_days"] = mine.get("interval_days") or 0
                # THE PER-SERVICE SHAPE `_too_early` READS — MERGED, not replaced, across every
                # service asked for.
                r.setdefault("services", {})[sid] = {
                    "last_visit": mine.get("last_visit") or 0,
                    "interval_days": mine.get("interval_days") or 0,
                }
        return rows

    async def allows(self, tenant: str, subject_ref: str, cls: str) -> bool:
        """Would reminders' gate let this through right now?

        Asked BEFORE the send so the preview's count is the count that goes out. A failure here is
        treated as "yes": the gate will refuse it again at send time anyway, and excluding someone
        because a peer blinked would silently shrink an audience with no reason the owner can see.
        """
        try:
            data = await _post(self._eligibility,
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

    async def redeemed(self, tenant: str, reached: list[dict[str, Any]]) -> int:
        """How many of the people this campaign reached came back and spent an offer (ط-3).

        THE QUESTION NOBODY COULD ANSWER. «كم واحداً رجع وصرف؟» is the one number a shop paid for
        this feature to produce, and every piece of it already existed: `campaign_reached` names
        exactly who a campaign sent to and when, and operations records every offer spend on the
        visit it happened on (§5.6.2). Nothing joined the two.

        `reached` IS `campaign_reached`, SHAPED FOR THE ASK — `{"subject_ref": ..., "since": at}`
        for each recipient, `since` being the moment THIS campaign reached them. operations
        resolves the pseudonyms to customers (the join it already serves reminders) and counts
        whoever holds a visit with a spent offer at or after their own `since` — never before it,
        or a discount redeemed from a DIFFERENT, earlier campaign would inflate this one's number.

        FAILS TO ZERO, NOT TO AN EXCEPTION. This is a report card, read well after the campaign
        ran; a shop that opens it while operations is restarting should see «0» and reload, not a
        500 in a place that used to just show a number.
        """
        if not reached or not self._redeemed:
            return 0
        try:
            data = await _post(self._redeemed, {"tenant": tenant, "reached": reached},
                               self._token, self._timeout)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return 0
        return int(data.get("redeemed") or 0)


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
                   offer_value: str = "",
                   service_names: list[str] | None = None,
                   branch_id: str = "",
                   flow_token: str = "",
                   flow_action_data: dict[str, Any] | None = None,
                   button_item_id: str = "",
                   button_kind: str = "service") -> dict[str, Any]:
        """Hand one message to reminders. It decides.

        Returns `{"sent": bool, "reason": str}` — and the reason is theirs, carried into the run
        report verbatim. Two vocabularies for one refusal is how an owner ends up believing there
        are two problems.
        """
        body: dict[str, Any] = {
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
            # THE TYPED PARTS. A discount is «20%» or «50 ريال», and the covered services
            # travel as WORDS because reminders holds ids and cannot name anything.
            "offer_value": offer_value,
            "service_names": list(service_names or []),
        }
        # THE BOOKING FLOW'S OWN FIELDS (core/shape.py) — omitted from the body entirely when this
        # send opens nothing, which is every send from a shop without the appointment book. Same
        # "no meaningless field on an ordinary send" rule reminders' own sender follows for this
        # exact pair, and the same shape insights' peer client uses for the weekly report.
        if flow_token:
            body["flow_token"] = flow_token
            if flow_action_data:
                body["flow_action_data"] = dict(flow_action_data)
        # THE SINGLE-ITEM QUICK-REPLY BUTTON (core/shape.py, 2026-09-13) — same "omitted when
        # meaningless" rule as every other optional field above.
        if button_item_id:
            body["button_item_id"] = button_item_id
            if button_kind != "service":
                body["button_kind"] = button_kind
        try:
            return await _post(self._url, body, self._token, self._timeout)
        except urllib.error.HTTPError as exc:
            # NOT named `body`: that name now holds the request we just sent, and reusing it for
            # the peer's refusal would put our own payload into the owner's run report.
            detail = exc.read().decode()[:200]
            return {"sent": False, "reason": f"رفض الإرسال ({exc.code}): {detail}"}


# ── the shop's name, for the preview ───────────────────────────────────────────────────────────
# ── packages: is the package_offer goal's own package still active/in-schedule right now ────────
# A THIN, DIRECT CALL TO operations' core/scheduling.py — never a second copy of the rule. Asked at
# TWO moments, mirroring HttpAudience.allows()'s own "ask again independently, never trust the
# earlier answer" shape: once at campaign creation (a clear refusal while the owner is looking at
# the screen), and once more at every dispatch.fire() pass (a campaign created weeks ago, or a
# standing/scheduled one, must not advertise a package that has since been turned off or fallen
# outside its own schedule).
class NullPackageOfferable:
    driver = "null"

    async def offerable(self, tenant: str, package_id: str, at: int) -> bool:
        return True


class HttpPackageOfferable:
    driver = "http"

    def __init__(self, *, operations_url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = operations_url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def offerable(self, tenant: str, package_id: str, at: int) -> bool:
        """`False` on ANY failure — an unreachable peer or an unknown package both mean "do not
        advertise it", the same fail-closed posture as every other paid-surface gate here."""
        try:
            out = await _post(self._url, {"tenant": tenant, "package_id": package_id, "at": int(at)},
                              self._token, self._timeout)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return False
        return bool(out.get("offerable"))


# ── the WhatsApp AI assistant's own kill switch (2026-09-13) ────────────────────────────────────
class NullAiToggle:
    driver = "null"

    async def enabled(self, tenant: str) -> bool:
        return True


class HttpAiToggle:
    """Asks operations' `/internal/operations/shop-name` — THE SAME ROUTE whatsapp-assistant's own
    `shop_identity.py` already calls — for the one field this service needs: `ai_enabled`. Never a
    second endpoint for a second switch.

    FAILS OPEN (True) on any read trouble — an outage must not silently strip every single-item
    quick-reply button for a shop that never touched this setting, which is every shop today.
    """

    driver = "http"

    def __init__(self, *, operations_url: str, path: str, token: str, timeout: int = 5) -> None:
        self._url = operations_url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def enabled(self, tenant: str) -> bool:
        if not tenant:
            return True
        try:
            data = await _post(self._url, {"tenant": tenant}, self._token, self._timeout)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return True
        return bool(data.get("ai_enabled", True))


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
        data = await _get(f"{self._url}{path}", self._token, self._timeout)
        branding = data.get("branding") or {}
        name = str(data.get("name") or "")
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


class NullLoyalty:
    """No points move. `award()` reports a shape identical to a real refusal (`earned: 0`) rather
    than raising, so a caller that has not been taught about a driver still gets an answer it can
    read the same way it reads a genuine "already credited" or "licence not included"."""

    driver = "null"

    async def award(self, *, tenant: str, subject_ref: str, points: int, idempotency_key: str,
                    reason: str = "", actor: str = "campaigns",
                    branch_id: str = "") -> dict[str, Any]:
        return {"earned": 0, "reason": "NOT_CONFIGURED"}


class HttpLoyalty:
    """A points credit with no visit behind it — a campaign's own gift (2026-09-13). No goal calls
    this yet; built so the capability exists once one does, rather than a template design waiting
    on a backend that does not.

    RAISES NOTHING. loyalty's own `/internal/loyalty/award` already answers "not credited" as data
    (a lapsed licence, a duplicate key) rather than an error — an unreachable peer answers the same
    shape rather than a caller having to tell three failure modes apart.
    """

    driver = "http"

    def __init__(self, *, loyalty_url: str, award_path: str, token: str, timeout: int = 8) -> None:
        self._award = loyalty_url.rstrip("/") + award_path
        self._token = token
        self._timeout = timeout

    async def award(self, *, tenant: str, subject_ref: str, points: int, idempotency_key: str,
                    reason: str = "", actor: str = "campaigns",
                    branch_id: str = "") -> dict[str, Any]:
        try:
            return await _post(
                self._award,
                {"tenant": tenant, "subject_ref": subject_ref, "points": points,
                 "idempotency_key": idempotency_key, "reason": reason, "actor": actor,
                 "branch_id": branch_id},
                self._token, self._timeout)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError) as exc:
            return {"earned": 0, "reason": f"UNREACHABLE: {exc}"}


def build_peers(settings) -> dict[str, Any]:
    if (getattr(settings, "PEERS_DRIVER", "") or "null").lower() == "null":
        return {"templates": NullTemplates(), "audience": NullAudience(),
                "sender": NullSender(), "identity": NullIdentity(),
                "package_offerable": NullPackageOfferable(), "loyalty": NullLoyalty(),
                "window": Window(start_hour=settings.SEND_WINDOW_START_HOUR,
                                 end_hour=settings.SEND_WINDOW_END_HOUR)}
    t = settings.PEER_TIMEOUT_SECONDS
    return {
        "templates": HttpTemplates(url=settings.REMINDERS_SERVICE_URL,
                                   path=settings.REMINDERS_SENDABLE_PATH,
                                   token=settings.INTERNAL_SERVICE_TOKEN, timeout=t,
                                   ttl_seconds=settings.TEMPLATES_CACHE_TTL_SECONDS),
        "audience": HttpAudience(operations_url=settings.OPERATIONS_SERVICE_URL,
                                 customers_path=settings.CUSTOMERS_PATH,
                                 reminders_url=settings.REMINDERS_SERVICE_URL,
                                 eligibility_path=settings.ELIGIBILITY_PATH,
                                 rhythms_path=settings.REMINDERS_RHYTHMS_PATH,
                                 redeemed_path=settings.OFFERS_REDEEMED_PATH,
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
        "package_offerable": HttpPackageOfferable(
            operations_url=settings.OPERATIONS_SERVICE_URL,
            path=settings.PACKAGE_OFFERABLE_PATH,
            token=settings.INTERNAL_SERVICE_TOKEN, timeout=t),
        "window": Window(start_hour=settings.SEND_WINDOW_START_HOUR,
                         end_hour=settings.SEND_WINDOW_END_HOUR),
        # OPTIONAL, LIKE `INSIGHTS_SERVICE_URL` ABOVE — a deployment that never set
        # `LOYALTY_SERVICE_URL` gets the null answer rather than a boot-time refusal, because
        # nothing calls `award()` yet either.
        "loyalty": (HttpLoyalty(loyalty_url=settings.LOYALTY_SERVICE_URL,
                                award_path=settings.LOYALTY_AWARD_PATH,
                                token=settings.INTERNAL_SERVICE_TOKEN, timeout=t)
                    if settings.LOYALTY_SERVICE_URL else NullLoyalty()),
    }
