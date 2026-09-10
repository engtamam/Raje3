"""FlowVisitBackend — this service's half of visit-registration over WhatsApp (a second channel
alongside the console's own شاشة تسجيل الزيارة; see services/operations' `api/internal.py::
internal_visit_from_whatsapp` docstring for the full write-side design).

THE REAL ENGINE, CONFIRMED (platform v0.19.16/v0.19.17, both verified live before this was
written) — the SAME `BookingEngine` class `booking`/`delivery` already use, registered a third
time under `name="visit"`, with a `FlowDefinition` that needs neither `date` nor `time` (v0.19.17
dropped that requirement) and whose `service` step sets `"multi": true` (v0.19.16's CheckboxGroup).
So this backend speaks the SAME `{options, calendar, slots, reserve}` port as
`flow_booking_backend.py` — this module only ever implements `options`/`reserve` because the
visit Flow's own definition (`deploy/services/notification-service.values.yaml`'s
`WHATSAPP_VISIT_DEFINITION`) has no `date`/`time` steps, so `calendar()`/`slots()` are simply
never called (see `booking_flow.py`'s own `_render`: it only reaches those for a definition that
declares them).

NO SEPARATE "identify" OP — dropped from an earlier draft of this module once the real engine's
shape was confirmed: `BookingEngine` has no such op, and none is needed. Staff identity is proven
TWICE already, by the trigger and inside `reserve()` (see below), never by a dedicated round trip.

`customer`, THROUGHOUT: the STAFF SENDER's own WhatsApp number — not an end customer's, unlike
every other Flow backend in this service (see `flow_booking_backend.py`'s own note on the same
field meaning something different there). This Flow is opened BY a staff member's own inbound
message (`core/visit_trigger.py`'s own `flow_action_data={"customer": from_number}`), so the
Flow's seed `customer` naturally carries whoever's thread it is: the operator, RE-resolved via
`core/operator_identity.py` inside `reserve()` — never trusted from `selection`, the same "the
write re-checks, never only the suggestion" posture every real write in this fleet already holds
(and the same reason `flow_visit_backend`'s sibling never trusts a `staff` selection blindly
either).

THE VISITED CUSTOMER'S OWN IDENTITY — "phone" — ARRIVES AS FREE TEXT (v0.19.17's TextInput step),
because unlike a booking (where the texting customer IS the customer), here the operator has to
TYPE who the visit is for. `services/operations`' own `record_visit()` resolves that phone into a
real (or newly created) customer row — this module never does that itself, same "one write path,
every channel" discipline `flow_booking_backend.py` already holds toward `RealBookingProvider`.

MULTI-SELECT SERVICES — THE OPEN QUESTION FROM AN EARLIER DRAFT, NOW RESOLVED. `options(dimension
="service")` answers the exact same catalogue list `flow_booking_backend.py`'s own `service` step
does; `reserve()` reads `selection["service"]` as a LIST (v0.19.16), matching Visit.tsx's own
tick-several-services UX for the first time on this channel.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any


def _service_ids(selection_or_chosen: dict[str, Any]) -> list[str]:
    """Same normalisation as `flow_booking_backend.py`'s own helper — a plain string (unlikely
    here, since the visit Flow's own definition always sets `"multi": true` on this step, but
    never assumed) or a CheckboxGroup list, always returned as a list of non-blank ids."""
    value = selection_or_chosen.get("service")
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if v]
    return [str(value)] if value else []


class FlowVisitBackend:
    driver = "flow"

    def __init__(self, *, catalog: Any, operator_identity: Any, visits_url: str,
                visits_path: str, token: str, timeout: int = 8) -> None:
        self._catalog = catalog
        self._operators = operator_identity
        self._visits_url = visits_url.rstrip("/") + visits_path
        self._token = token
        self._timeout = timeout

    async def options(self, *, tenant: str, dimension: str, chosen: dict[str, Any],
                      customer: str = "") -> list[dict[str, Any]]:
        if dimension != "service":
            return []
        services = await self._catalog.list_active(tenant)
        return [{"id": str(s.get("id")), "title": str(s.get("name") or "")} for s in services
               if s.get("id")]

    async def reserve(self, *, tenant: str, selection: dict[str, Any], idempotency_key: str,
                      customer: str = "") -> dict[str, Any]:
        if not customer:
            # SHOULD NEVER HAPPEN FOR OUR OWN SENDS (`visit_trigger.py` always seeds `customer`)
            # — refused rather than guessed if it somehow does, same posture
            # `flow_booking_backend.py::reserve` already holds for the identical case.
            return {"ok": False, "reason": "تعذّر تحديد هويتك. أعد فتح المحادثة من جديد من فضلك."}
        phone = str(selection.get("phone") or "").strip()
        if not phone:
            return {"ok": False, "reason": "أدخل رقم جوال العميل"}
        service_ids = _service_ids(selection)
        if not service_ids:
            return {"ok": False, "reason": "اختر خدمة واحدة على الأقل"}
        # RESOLVED HERE, NOT TRUSTED FROM `selection` — see module docstring.
        operator_id = await self._operators.resolve(tenant=tenant, from_number=customer)
        body = {
            "tenant": tenant, "phone": phone, "service_ids": service_ids,
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
