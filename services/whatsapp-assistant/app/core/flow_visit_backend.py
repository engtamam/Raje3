"""FlowVisitBackend — this service's half of visit-registration over WhatsApp (a second channel
alongside the console's own شاشة تسجيل الزيارة; see services/operations' `api/internal.py::
internal_visit_from_whatsapp` docstring for the full design, and this repo's own approved plan at
.claude/plans/stateless-wondering-fox.md).

THE ENGINE ON THE OTHER SIDE IS NOT YET BUILT (platform/, base-services' own piece — requested,
not shipped as of this module). This backend's op contract is written to be engine-agnostic on
purpose: `identify`/`options`/`reserve`, the smallest set that answers "who is this about",
"what services", "record it" — whichever concrete Flow engine ends up calling it (a trimmed
`BookingEngine` with no date/time steps, or a small dedicated one) only needs to speak this
contract, mirroring how `flow_booking_backend.py`'s own `{options, calendar, slots, reserve}`
already answers `platform`'s `booking_flow.py`.

`customer`, THROUGHOUT: the STAFF SENDER's own WhatsApp number — not an end customer's, unlike
every other Flow backend in this service. This Flow is opened BY a staff member's own inbound
message (see app/core/inbound_ingest.py's own trigger check), so the Flow's seed `customer` field
naturally carries whoever's thread it is: the operator, resolved via `core/operator_identity.py`
at `reserve()` time — never trusted from `selection`, the same "the write re-checks, never only
the suggestion" posture every other real write in this fleet already holds.

MULTI-SELECT SERVICES IS A REAL OPEN QUESTION, STATED HERE RATHER THAN HIDDEN. Visit.tsx lets an
operator tick several services in one visit; a single-choice Flow selection step (the shape every
existing engine's `options()` answers today) cannot reproduce that directly — the two options are
a repeatable "add another service?" loop (several short screens) or a genuinely new multi-select
Flow component, and which one the eventual engine uses decides this module's own `options()`
return shape (one id per call today; would need to change for a checkbox-style component). Left as
a single-selection contract for now, matching every existing engine, and flagged for whoever builds
the real engine to resolve deliberately rather than by accident.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any


class FlowVisitBackend:
    driver = "flow"

    def __init__(self, *, catalog: Any, operator_identity: Any, visits_url: str,
                visits_path: str, token: str, timeout: int = 8) -> None:
        self._catalog = catalog
        self._operators = operator_identity
        self._visits_url = visits_url.rstrip("/") + visits_path
        self._token = token
        self._timeout = timeout

    async def identify(self, *, tenant: str, customer: str) -> dict[str, Any]:
        """Who is texting, in the one sentence the CONFIRM screen needs — not a lookup of the
        VISIT's own subject (that happens once, inside `reserve()`, from `phone`/`plate` in
        `selection`, exactly like the console's own screen resolves a car or a number): this is
        the STAFF SENDER himself, so a Flow session opened by someone no longer on the roster
        (removed after the message was sent, a forwarded/shared session) answers honestly rather
        than silently recording under a stale identity."""
        operator_id = await self._operators.resolve(tenant=tenant, from_number=customer)
        return {"known": bool(operator_id)}

    async def options(self, *, tenant: str, dimension: str, chosen: dict[str, Any],
                      customer: str = "") -> list[dict[str, Any]]:
        if dimension != "service":
            return []
        services = await self._catalog.list_active(tenant)
        return [{"id": s.id, "title": s.name} for s in services]

    async def reserve(self, *, tenant: str, selection: dict[str, Any], idempotency_key: str,
                      customer: str = "") -> dict[str, Any]:
        if not customer:
            return {"ok": False, "reason": "لا يمكن تحديد من يسجّل — أعد فتح الفلو"}
        phone = str(selection.get("phone") or "").strip()
        if not phone:
            return {"ok": False, "reason": "أدخل رقم جوال العميل"}
        service_id = str(selection.get("service") or "").strip()
        if not service_id:
            return {"ok": False, "reason": "اختر خدمة واحدة على الأقل"}
        # RESOLVED HERE, NOT TRUSTED FROM `selection` — see module docstring.
        operator_id = await self._operators.resolve(tenant=tenant, from_number=customer)
        body = {
            "tenant": tenant, "phone": phone, "service_ids": [service_id],
            "name": str(selection.get("name") or ""), "plate": str(selection.get("plate") or ""),
            "operator_id": operator_id, "idempotency_key": idempotency_key,
        }
        try:
            # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
            out = await asyncio.to_thread(self._post_sync, body)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError) as exc:
            return {"ok": False, "reason": f"تعذّر تسجيل الزيارة: {exc}"}
        if not out.get("recorded"):
            return {"ok": False, "reason": str(out.get("reason") or "تعذّر تسجيل الزيارة")}
        return {"ok": True, "ref": str(out.get("visit_id") or "")}

    def _post_sync(self, body: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            self._visits_url, data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
            return json.loads(resp.read() or b"{}")


def build(settings: Any, *, catalog: Any, operator_identity: Any) -> FlowVisitBackend:
    return FlowVisitBackend(
        catalog=catalog, operator_identity=operator_identity,
        visits_url=settings.OPERATIONS_SERVICE_URL,
        visits_path=settings.OPERATIONS_VISIT_FROM_WHATSAPP_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN, timeout=settings.PEER_TIMEOUT_SECONDS)
