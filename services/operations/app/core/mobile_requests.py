"""Mobile/on-the-go service requests — a shop whose SERVICE travels to the customer (a mobile car
wash, a home visit, a mobile detailer) rather than the customer coming in, collected entirely
through the WhatsApp bot and reviewed by the shop itself before anything is promised.

DELIBERATELY NOT `bookings`'s own engine. `bookings` auto-confirms on creation and REQUIRES a
named staff member (services/bookings/app/core/operations.py's own `create()` refuses without
one — "الفرع والموظفة والعميلة مطلوبون") — the exact opposite of what this needs: a request sits
PENDING until a human at the shop reviews it, and there is no staff/capacity concept here at all,
only "can we get there and when". So this is its own small state machine, living in operations
(which already owns Visit creation — the one piece the two genuinely share) rather than a second
copy of bookings' own, larger engine bent to fit a shape it was not built for.

REUSED, NOT REBUILT:
  * the shop's own service catalogue — `ServiceStore`, unchanged, the same one «خدماتي» writes;
  * `record_visit()` itself, called DIRECTLY (we are already inside operations — no network hop
    bookings' own `attend()` needs) for the loyalty/insights side effects a completed request
    earns exactly like an ordinary visit;
  * the shop's weekly working hours — read live from bookings (`BookingsDesk.working_hours()`,
    the same call staff.py already makes) by the WhatsApp conversation, not duplicated here.

OWNER'S OWN WORDS (2026-09-15) ON WHY REVIEW IS A REAL GATE, NOT AUTO-ACCEPT: "الحجز يتسجل
ولكن ما يكون مقبول او مرفوض يتم مراجعته واعتماده من المحل نفسه" — and once accepted, "بعد القبول
او الرفض احنا مالنا دخل اللي يسير تواصل بينهم خارج المنصة": coordinating the actual visit is
entirely the shop's and the customer's own business from that point on. Our own involvement
resumes only once — completed or not.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from app.core.signup import canonical_phone

MOBILE_REQUESTS = "mobile_service_requests"

PENDING = "pending"
ACCEPTED = "accepted"
REJECTED = "rejected"
COMPLETED = "completed"
NO_SHOW = "no_show"
# TERMINAL, ONE-WAY — same discipline as bookings' own STATUS set (operations.py:36-37 there):
# nothing here reopens once decided or closed.
TERMINAL = frozenset({REJECTED, COMPLETED, NO_SHOW})


class MobileRequestError(Exception):
    """A refusal the caller (an API route) can show verbatim."""


def _now() -> int:
    return int(time.time())


def maps_link(lat: float, lng: float) -> str:
    """A clickable Google Maps pin from raw coordinates — the one small piece that genuinely did
    not exist anywhere in this codebase (confirmed live: the console only has the REVERSE, a
    pasted-link parser in `apps/console/src/googleMapsLink.ts`). `q=lat,lng` opens the exact pin
    on both the mobile app and the web, no API key needed — the format Google's own docs give for
    a bare coordinate link."""
    return f"https://www.google.com/maps?q={lat},{lng}"


@dataclass
class MobileServiceRequest:
    id: str
    tenant: str
    # THE PHONE IN THE CLEAR — same posture as `Customer.phone` (core/models.py's own module
    # docstring): this service is the one place in the platform that holds it, deliberately, and
    # a mobile-service request is exactly the kind of row an owner needs to call back on.
    phone: str
    customer_name: str
    service_ids: list[str]
    # THE CUSTOMER'S OWN WORDS, NEVER A PARSED TIMESTAMP — there is no slot-booking system behind
    # this (module docstring), so "بعد صلاة العصر" or "الخميس الصبح" is a legitimate, honest answer
    # a shop reviewing the request reads and decides against for itself. A parsed/guessed datetime
    # here would be a confidence neither we nor the shop actually has.
    requested_time_text: str
    lat: float
    lng: float
    status: str
    created: int
    # WHO DECIDED, AND WHEN — "" / 0 until a human actually acts (accept/reject), same as
    # `CouponTenantOverride`'s own `updated` field never being backdated.
    decided_at: int = 0
    decided_by: str = ""
    reject_reason: str = ""
    # SET ONLY ON COMPLETION — the real Visit this request turned into, so a shop looking at an
    # old request can always find what it actually earned (loyalty, insights) rather than a dead
    # end once `record_visit()` has run.
    visit_id: str = ""
    note: str = ""

    @property
    def maps_url(self) -> str:
        return maps_link(self.lat, self.lng)

    def public(self) -> dict[str, Any]:
        row = asdict(self)
        row["maps_url"] = self.maps_url
        return row


@dataclass
class NoShowRisk:
    considered: int
    no_shows: int
    risky: bool
    threshold_percent: int

    def public(self) -> dict[str, Any]:
        return asdict(self)


class MobileRequestService:
    """Everything a mobile-service request needs, other than `record_visit()` itself (injected as
    `operations`, the same `core/operations.py::Operations` instance every other visit-creation
    path already shares)."""

    def __init__(self, *, store: Any, operations: Any, default_cc: str,
                risk_window: int = 20, risk_threshold_percent: int = 40) -> None:
        self._s = store
        self._ops = operations
        self._cc = default_cc
        # SAME SHAPE AS bookings' OWN `no_show_risk()` (services/bookings/app/core/operations.py)
        # — a small window of the customer's own RECENT closed requests, never the whole history:
        # someone who no-showed twice three years ago and has been reliable since must not still
        # read as risky. Deliberately re-implemented here rather than called cross-service — this
        # is a ~15-line formula over OUR OWN rows, and a network hop to ask bookings about a
        # customer bookings has never heard of buys nothing.
        self._risk_window = risk_window
        self._risk_threshold_percent = risk_threshold_percent

    # ── creation — the WhatsApp bot's own door ─────────────────────────────────────────────────
    async def create(self, *, tenant: str, phone: str, customer_name: str,
                     service_ids: list[str], requested_time_text: str,
                     lat: float, lng: float) -> MobileServiceRequest:
        phone = canonical_phone(phone, default_cc=self._cc)
        if not phone:
            raise MobileRequestError("رقم الجوال غير صحيح.")
        if not service_ids:
            raise MobileRequestError("اختر خدمة واحدة على الأقل.")
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise MobileRequestError("الموقع المُرسَل غير صالح.")
        now = _now()
        row = MobileServiceRequest(
            id=f"mreq_{uuid.uuid4().hex}", tenant=tenant, phone=phone,
            customer_name=customer_name[:128], service_ids=list(service_ids),
            requested_time_text=requested_time_text[:300], lat=float(lat), lng=float(lng),
            status=PENDING, created=now)
        await self._s.put(MOBILE_REQUESTS, f"{tenant}|{row.id}",
                          {"tenant_key": tenant, **asdict(row)})
        return row

    async def get(self, tenant: str, request_id: str) -> MobileServiceRequest | None:
        raw = await self._s.get(MOBILE_REQUESTS, f"{tenant}|{request_id}")
        if not raw:
            return None
        return MobileServiceRequest(**{k: v for k, v in raw.items() if k != "tenant_key"})

    async def list(self, tenant: str, *, status: str = "", limit: int = 200,
                  ) -> list[MobileServiceRequest]:
        where: dict[str, Any] = {"tenant": tenant}
        if status:
            where["status"] = status
        rows, _ = await self._s.find(MOBILE_REQUESTS, where, limit=limit,
                                     sort=("created", "desc"))
        return [MobileServiceRequest(**{k: v for k, v in r.items() if k != "tenant_key"})
               for r in rows]

    # ── the shop's own review ──────────────────────────────────────────────────────────────────
    async def accept(self, tenant: str, request_id: str, *, actor: str) -> MobileServiceRequest:
        row = await self._require_pending(tenant, request_id)
        row.status = ACCEPTED
        row.decided_at = _now()
        row.decided_by = actor
        await self._save(tenant, row)
        return row

    async def reject(self, tenant: str, request_id: str, *, actor: str,
                     reason: str = "") -> MobileServiceRequest:
        row = await self._require_pending(tenant, request_id)
        row.status = REJECTED
        row.decided_at = _now()
        row.decided_by = actor
        row.reject_reason = reason[:300]
        await self._save(tenant, row)
        return row

    async def _require_pending(self, tenant: str, request_id: str) -> MobileServiceRequest:
        row = await self.get(tenant, request_id)
        if row is None:
            raise MobileRequestError("الطلب غير موجود.")
        if row.status != PENDING:
            raise MobileRequestError("هذا الطلب سبق أن رُوجع.")
        return row

    # ── after the appointment — the only two ways this ends ───────────────────────────────────
    async def complete(self, tenant: str, request_id: str, *, occurred_at: int = 0
                       ) -> MobileServiceRequest:
        """The visit actually happened — record it exactly like any other visit, so loyalty
        points, insights and reminders all pick it up automatically. `record_visit()` is called
        DIRECTLY (same service, no network hop), the same core function every other visit-
        creation path in this file already shares — never a second definition of what a visit
        is."""
        row = await self._require_accepted(tenant, request_id)
        recorded = await self._ops.record_visit(
            tenant=tenant, phone=row.phone, service_ids=row.service_ids,
            name=row.customer_name, occurred_at=occurred_at or _now(),
            idempotency_key=f"mreq:{row.id}", note=row.note)
        row.status = COMPLETED
        row.visit_id = recorded.visit.id
        await self._save(tenant, row)
        return row

    async def no_show(self, tenant: str, request_id: str) -> MobileServiceRequest:
        row = await self._require_accepted(tenant, request_id)
        row.status = NO_SHOW
        await self._save(tenant, row)
        return row

    async def _require_accepted(self, tenant: str, request_id: str) -> MobileServiceRequest:
        row = await self.get(tenant, request_id)
        if row is None:
            raise MobileRequestError("الطلب غير موجود.")
        if row.status != ACCEPTED:
            raise MobileRequestError("هذا الطلب لم يُقبل بعد، أو أُغلق مسبقاً.")
        return row

    async def _save(self, tenant: str, row: MobileServiceRequest) -> None:
        await self._s.put(MOBILE_REQUESTS, f"{tenant}|{row.id}",
                          {"tenant_key": tenant, **asdict(row)})

    # ── the heads-up at accept time — a note, never an enforced deposit ───────────────────────
    async def no_show_risk(self, tenant: str, phone: str) -> NoShowRisk:
        """A number beside the request at the moment the shop is about to accept it — same
        posture bookings' own `no_show_risk()` documents (§2.6): a number, not a verdict. This
        product has no deposit/payment concept at all (owner's own words, 2026-09-15: "ننبهه
        فقط") — the caller (the console's own accept button) shows this as a plain warning
        sentence, nothing is withheld or charged."""
        phone = canonical_phone(phone, default_cc=self._cc)
        rows, _ = await self._s.find(
            MOBILE_REQUESTS, {"tenant": tenant, "phone": phone}, limit=200,
            sort=("created", "desc"))
        closed = [r for r in rows if r.get("status") in (COMPLETED, NO_SHOW)][:self._risk_window]
        no_shows = sum(1 for r in closed if r.get("status") == NO_SHOW)
        considered = len(closed)
        min_sample = -(-(self._risk_threshold_percent * self._risk_window) // 100)
        risky = (considered >= min_sample
                and (no_shows * 100) >= self._risk_threshold_percent * considered)
        return NoShowRisk(considered=considered, no_shows=no_shows, risky=risky,
                          threshold_percent=self._risk_threshold_percent)
