"""FlowBookingBackend — the platform's AvailabilityProvider + BookingProvider (notification-
service's booking_flow.py, v0.18.54+), backed by REAL peers. The WhatsApp Flow (fixed, structured
screens) counterpart to booking_assignment.py's RealBookingProvider (the free-text AI channel) —
both ultimately call the SAME bookings-service engine (assignment.py); this module only translates
the platform's fixed {options, calendar, slots, reserve} questions into calls RealBookingProvider
already knows how to make. One engine, every channel — never a second policy that can drift.

ONE HTTP ENDPOINT, FOUR OPS. The platform's own HttpBookingBackend adapter (services/notification-
service/app/adapters/booking/http.py) POSTs {"op": "options"|"calendar"|"slots"|"reserve",
"tenant", "customer", ...} to a single configured URL; `api/internal.py`'s
`/internal/whatsapp-flow/booking` route is what answers on our side, dispatching each op to this
class's matching method.

`customer`, THROUGHOUT: the Flow's own seed data (platform v0.18.54's parity fix with reschedule/
loyalty). WE choose that value when WE send the flow-triggering interactive message — and we
choose it to BE the customer's own phone number (`from_number`), the same identity every other
channel in this service already keys on, never a second identity scheme. Empty means the sender
never seeded one; every method here degrades to "cannot proceed" rather than guessing who is asking.

THE STAFF STEP SKIPS ITSELF (v0.18.53's conditional-step contract — see platform's booking_flow.py
docstring). `options(dimension="staff", ...)` returns `[]` the instant the chosen service is not
`named` mode, and the platform's engine advances past that step silently — no "any available"
placeholder needed. Matches the console's own BookingDialog.tsx behaviour and the
decision on this feature: `auto` services never ask who, `named` services always do.

SINGLE-BRANCH SHOPS ONLY, FOR NOW — a documented limitation, not a guess. Resolving WHICH branch a
central-number shop's WhatsApp Flow booking is for needs its own Flow step (the same ambiguity
core/branch_directory.py already exists to resolve for the free-text channel); adding that step is
a separate, later pass. A shop with more than one open branch simply cannot complete a Flow booking
yet — `options`/`calendar`/`slots` all return empty rather than guessing a branch, and `reserve`
refuses with a reason a customer can read.

LOYALTY-IN-BOOKING, NEVER STANDALONE REDEMPTION (restated here because it is
the whole reason this exists in this file and not a separate loyalty Flow). core/points.py's own
module docstring already records why a bare "redeem your points" tool was removed from the AI text
channel: a redemption with no booking behind it is a reward the shop hands over with no visit to
show for it if the customer never comes in. So `options(dimension="reward", ...)` below is the
ONLY place points can ever be spent from a WhatsApp Flow — it rides INSIDE this same booking, using
the exact mechanism `booking_flow.py`'s own docstring calls "LOYALTY-IN-BOOKING": the chosen reward
becomes `selection["reward"]` and travels to `reserve()`, which books AND redeems atomically via
`hold_and_confirm`'s existing `intended_reward_id` (Phase 4's own field — nothing new on the write
side). SKIPS ITSELF (same v0.18.53 contract as the staff step) whenever the customer cannot be
identified, has no loyalty programme, or has nothing affordable without manager approval — a
customer with nothing to redeem never sees the step at all.
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import json
import urllib.error
import urllib.request
from typing import Any

from app.core.booking_assignment import BookingAssignmentError, RealBookingProvider, _Peer
from app.core.riyadh import RIYADH

# booking_flow.py's CALENDAR screen wants Meta's own weekday abbreviations, Sun-first
# ("include_days": [...] "Sun".."Sat"); bookings-service's own weekly working-hours are keyed
# 0=Monday..6=Sunday (date.weekday()'s own numbering — see availability.py's own note). One fixed
# translation table, not re-derived per call.
_WEEKDAY_NAME_BY_INDEX = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}

_CALENDAR_HORIZON_DAYS = 14   # matches assignment.py's own search_days default — one horizon


def _fmt_time(starts_at: int) -> str:
    return _dt.datetime.fromtimestamp(starts_at, tz=RIYADH).strftime("%H:%M")


class FlowBookingBackend:
    driver = "flow"

    def __init__(self, *, real: RealBookingProvider, catalog: Any, branch_directory: Any,
                day_slots: _Peer, working_hours_url: str, working_hours_path: str,
                token: str, timeout: int, customer_lookup: Any = None,
                points_summary: Any = None) -> None:
        self._real = real
        self._catalog = catalog
        self._branches = branch_directory
        self._day_slots = day_slots
        self._wh_url = working_hours_url.rstrip("/") + working_hours_path
        self._token = token
        self._timeout = timeout
        # OPTIONAL — see module docstring, "LOYALTY-IN-BOOKING". None (never wired) means the
        # reward step always skips, same fail-safe posture as an unreachable peer; never a crash.
        self._customer_lookup = customer_lookup
        self._points_summary = points_summary

    async def _branch_id(self, tenant: str) -> str:
        """The one open branch, or "" — see module docstring, "SINGLE-BRANCH SHOPS ONLY"."""
        branches = await self._branches.list_open(tenant)
        return str(branches[0].get("id") or "") if len(branches) == 1 else ""

    async def _service_row(self, tenant: str, service_id: str) -> dict[str, Any] | None:
        rows = await self._catalog.list_active(tenant)
        return next((r for r in rows if str(r.get("id")) == service_id), None)

    async def _working_hours(self, tenant: str) -> dict[str, Any]:
        # A plain GET with a query string — the one peer call in this module that is not the
        # {"op": ...} POST shape, because it reaches bookings-service's own pre-existing
        # `/internal/working-hours` route directly (built for the console, reused here) rather
        # than a Phase-5-specific endpoint.
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        return await asyncio.to_thread(self._working_hours_sync, tenant)

    def _working_hours_sync(self, tenant: str) -> dict[str, Any]:
        import urllib.parse
        url = self._wh_url + "?" + urllib.parse.urlencode({"tenant": tenant})
        req = urllib.request.Request(
            url, method="GET", headers={"X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    return {}
                data = json.loads(resp.read() or b"{}")
        except (urllib.error.URLError, OSError, ValueError):
            return {}
        return dict(data.get("weekly") or {})

    # ── AvailabilityProvider ─────────────────────────────────────────────────────────────────

    async def options(self, *, tenant: str, dimension: str, chosen: dict[str, Any],
                      customer: str = "") -> list[dict[str, Any]]:
        if dimension == "service":
            rows = await self._catalog.list_active(tenant)
            return [{"id": str(r["id"]), "title": str(r.get("name") or "")} for r in rows
                   if r.get("id")]

        if dimension == "staff":
            service_id = str(chosen.get("service") or "")
            svc = await self._service_row(tenant, service_id) if service_id else None
            if svc is None or svc.get("assignment_mode") != "named":
                # SKIP — auto (or an unresolved/unknown service) never asks who. See module
                # docstring on v0.18.53's conditional-step contract.
                return []
            branch_id = await self._branch_id(tenant)
            if not branch_id:
                return []   # no single resolvable branch — see "SINGLE-BRANCH SHOPS ONLY"
            try:
                pool = await self._real._eligible_pool(tenant, branch_id, service_id)   # noqa: SLF001 — same-feature internal reuse
            except BookingAssignmentError:
                return []
            ops = self._real._branch_operators.call({"tenant": tenant, "branch_id": branch_id})   # noqa: SLF001
            names = {str(o.get("id")): str(o.get("name") or "")
                    for o in (ops or {}).get("operators") or []}
            return [{"id": op_id, "title": names.get(op_id) or op_id} for op_id in pool]

        if dimension == "reward":
            # SKIPS ITSELF FAR MORE OFTEN THAN NOT — see module docstring, "LOYALTY-IN-BOOKING".
            # Every early return here is the SAME outcome (no step shown), for different reasons;
            # none of them is an error, so none of them logs or refuses anything.
            if self._customer_lookup is None or self._points_summary is None or not customer:
                return []
            resolved = await self._customer_lookup.resolve(tenant, customer)
            subject_ref = str(resolved.get("subject_ref") or "") if resolved.get("found") else ""
            if not subject_ref:
                return []
            offers = await self._points_summary.offers(tenant=tenant, subject_ref=subject_ref)
            return [{"id": str(o.get("reward_id") or ""),
                    "title": f"{o.get('reward_name') or ''} — {int(o.get('points_cost') or 0)} نقطة"}
                   for o in offers if o.get("reward_id")]

        return []

    async def calendar(self, *, tenant: str, chosen: dict[str, Any],
                       customer: str = "") -> dict[str, Any]:
        today = _dt.datetime.now(tz=RIYADH).date()
        weekly = await self._working_hours(tenant)
        include_days = [_WEEKDAY_NAME_BY_INDEX[i] for i in range(7)
                        if not bool((weekly.get(str(i)) or {}).get("closed"))]
        return {
            "min_date": today.isoformat(),
            "max_date": (today + _dt.timedelta(days=_CALENDAR_HORIZON_DAYS - 1)).isoformat(),
            # Per-day exceptions (a branch holiday, a Ramadan short day) are not yet surfaced to
            # the Flow — a shop's weekly pattern already narrows most of the picker; a customer who
            # picks a date the shop happens to be closed on that ONE day still gets a correct,
            # empty TIME screen from `slots()` below rather than a wrong booking. Not a guess —
            # documented as the same known gap this module's SINGLE-BRANCH note already sets a
            # precedent for: a real limitation, stated, not silently over-promised.
            "unavailable_dates": [],
            "include_days": include_days,
        }

    async def slots(self, *, tenant: str, chosen: dict[str, Any], date: str,
                    customer: str = "") -> list[dict[str, Any]]:
        service_id = str(chosen.get("service") or "")
        if not service_id or not date:
            return []
        branch_id = await self._branch_id(tenant)
        if not branch_id:
            return []
        staff = str(chosen.get("staff") or "")
        try:
            if staff:
                # THE CHOSEN NAME WINS — still re-validated against the real eligible pool (never
                # trusted blindly) rather than searched across everyone.
                pool = await self._real._eligible_pool(tenant, branch_id, service_id)   # noqa: SLF001
                if staff not in pool:
                    return []
                pool = [staff]
            else:
                pool = await self._real._eligible_pool(tenant, branch_id, service_id)   # noqa: SLF001
        except BookingAssignmentError:
            return []

        try:
            day = _dt.date.fromisoformat(date)
        except ValueError:
            return []
        day_start = int(_dt.datetime.combine(day, _dt.time(0, 0), tzinfo=RIYADH).timestamp())
        day_end = day_start + 86400

        result = self._day_slots.call({
            "tenant": tenant, "branch_id": branch_id, "operator_ids": pool,
            "service_ids": [service_id], "day_start": day_start, "day_end": day_end})
        times = (result or {}).get("starts_at") or []
        # id = the epoch start time itself, echoed back at reserve() — opaque to the customer
        # (they see only the formatted title), and WHO ends up with it is decided at reserve()
        # time by the shop's own algorithm (see assignment.day_slots_any's own docstring on why
        # this never picks an operator here).
        return [{"id": str(int(t)), "title": _fmt_time(int(t))} for t in times]

    # ── BookingProvider ──────────────────────────────────────────────────────────────────────

    async def reserve(self, *, tenant: str, selection: dict[str, Any], idempotency_key: str,
                      customer: str = "") -> dict[str, Any]:
        if not customer:
            # SHOULD NEVER HAPPEN FOR OUR OWN SENDS (we always seed `customer` — see module
            # docstring) — refused rather than guessed if it somehow does.
            return {"ok": False, "reason": "تعذّر تحديد هويتك. أعد فتح المحادثة من جديد من فضلك."}
        service_id = str(selection.get("service") or "")
        time_id = str(selection.get("time") or "")
        if not service_id or not time_id:
            return {"ok": False, "reason": "الاختيار غير مكتمل."}
        try:
            starts_at = int(time_id)
        except ValueError:
            return {"ok": False, "reason": "الوقت المختار غير صالح."}
        branch_id = await self._branch_id(tenant)
        if not branch_id:
            return {"ok": False, "reason": "تعذّر تحديد الفرع لهذا الحجز."}

        try:
            result = await self._real.hold_and_confirm(
                tenant=tenant, subject_ref="", service_id=service_id, starts_at=starts_at,
                idempotency_key=idempotency_key, branch_id=branch_id, from_number=customer,
                preferred_operator_id=str(selection.get("staff") or ""),
                # LOYALTY-IN-BOOKING — see module docstring. INTENT ONLY (RealBookingProvider's
                # own comment on this field): the actual spend still waits for attend(), so a
                # no-show never costs the shop a reward it never delivered.
                intended_reward_id=str(selection.get("reward") or ""))
        except BookingAssignmentError as exc:
            return {"ok": False, "reason": str(exc)}
        return {"ok": True, "ref": str(result.get("id") or "")}


def build(settings: Any, *, real: RealBookingProvider, catalog: Any,
         branch_directory: Any, customer_lookup: Any = None,
         points_summary: Any = None) -> "FlowBookingBackend":
    """Requires `real`/`catalog`/`branch_directory` — the SAME instances the container already
    built for BOOKING_PROVIDER_DRIVER="real" and the AI channel's own catalogue/branch lookups
    (container.py's `service_catalog`/`branch_directory`), never a second copy of their peers.
    Fails fast, matching `booking_assignment.build`'s own posture, if the one extra peer this
    module needs (bookings-service's day-slots-any route) is not reachable because
    BOOKINGS_SERVICE_URL is unset — WHATSAPP_FLOW_BOOKING_ENABLED already requires
    BOOKING_PROVIDER_DRIVER="real" at the container level, so this should never actually be hit
    with an empty URL in practice.

    `customer_lookup`/`points_summary` are OPTIONAL — the container's own instances
    (`CL.build`/`P.build`, already constructed for the AI text channel), reused rather than
    duplicated. Omitted (both default None) means the reward step always skips — see
    FlowBookingBackend's own docstring, "LOYALTY-IN-BOOKING" — never a crash from a missing peer.
    """
    if not settings.BOOKINGS_SERVICE_URL:
        raise ValueError("WHATSAPP_FLOW_BOOKING_ENABLED=true requires BOOKINGS_SERVICE_URL set")
    token = settings.INTERNAL_SERVICE_TOKEN
    timeout = settings.PEER_TIMEOUT_SECONDS
    return FlowBookingBackend(
        real=real, catalog=catalog, branch_directory=branch_directory,
        customer_lookup=customer_lookup, points_summary=points_summary,
        day_slots=_Peer(url=settings.BOOKINGS_SERVICE_URL,
                        path=settings.BOOKINGS_DAY_SLOTS_ANY_REAL_PATH,
                        token=token, timeout=timeout),
        working_hours_url=settings.BOOKINGS_SERVICE_URL,
        working_hours_path=settings.BOOKINGS_WORKING_HOURS_PATH,
        token=token, timeout=timeout)
