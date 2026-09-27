"""Mobile/on-the-go service requests — a shop whose SERVICE travels to the customer (a mobile car
wash, a home visit, a mobile detailer) rather than the customer coming in, reviewed by the shop
itself before anything is promised. SOLD STANDALONE (owner's own decision, 2026-09-15) — a request
can arrive over the WhatsApp bot's own door OR be typed in by the shop's own staff by hand
(api/v1/mobile_requests.py's own `POST` route), and neither is ever a prerequisite for the other.

`MOBILE_REQUESTS_KEY`/`is_subscribed()` below are this app's own entitlement check — asked ONLY at
the ONE non-human door (the WhatsApp bot's `/internal/operations/mobile-requests`, api/internal.py),
the same "a credential proves only that a caller IS the bot, never which apps the shop it claims to
speak for actually bought" reasoning `core/coupons.py::granter_is_subscribed`'s own docstring gives
for the till's door — never at the staff console routes below, whose capability IS the entitlement
check there (same posture every other bundled app's console screen already takes).

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
  * the shop's own weekly working hours — read live via `BookingsDesk.working_hours()` (the same
    peer `staff.py`'s own staff-hours edit already calls), injected here as `working_hours`, so a
    requested visit is validated against the shop's REAL open days/hours instead of a guess.

OWNER'S OWN WORDS (2026-09-15) ON WHY REVIEW IS A REAL GATE, NOT AUTO-ACCEPT: "الحجز يتسجل
ولكن ما يكون مقبول او مرفوض يتم مراجعته واعتماده من المحل نفسه" — and once accepted, "بعد القبول
او الرفض احنا مالنا دخل اللي يسير تواصل بينهم خارج المنصة": coordinating the actual visit is
entirely the shop's and the customer's own business from that point on. Our own involvement
resumes only once — completed or not.

`requested_time` IS A REAL, VALIDATED INSTANT, NOT FREE TEXT (revised 2026-09-15 — the owner's own
correction: "الوقت ماهو نص حر الوقت من اوقات عمل المنشاه"). There is still no slot-booking/
concurrency engine behind this (module docstring above) — no capacity concept, "طلبات تترص
وانتهينا" — but the customer must choose a real moment inside the shop's own real working hours,
never an unverifiable sentence like the free-text guess this field used to accept.
`validate_requested_time()` below is that check: the same day/hour shape `bookings` itself already
exposes, re-used rather than re-invented.
"""
from __future__ import annotations

import datetime as dt
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from app.core.riyadh import RIYADH
from app.core.signup import canonical_phone

MOBILE_REQUESTS = "mobile_service_requests"
MOBILE_REQUESTS_KEY = "feature.mobile_requests"

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


# THE SAME 7-DAY SHAPE `bookings/app/core/operations.py::working_hours()` ALREADY RETURNS —
# {"0".."6" (Monday..Sunday, date.weekday()'s own numbering): {closed, start_minute, end_minute}}
# — consumed here as-is, never re-encoded.
def validate_requested_time(requested_time: int, weekly: dict[str, Any] | None) -> None:
    """Raises MobileRequestError with a real, sayable reason if `requested_time` falls outside the
    shop's own real working hours. `weekly is None` (the peer could not be reached, or none is
    wired — see MobileRequestService's own `working_hours` note) SKIPS the check entirely, same
    fail-open posture `BookingsDesk`'s own docstring already documents for a read this uncertain —
    refusing every request because a peer hiccuped would be a worse failure than occasionally
    letting one through unchecked."""
    if weekly is None:
        return
    when = dt.datetime.fromtimestamp(requested_time, RIYADH)
    entry = weekly.get(str(when.weekday())) or {}
    if entry.get("closed"):
        raise MobileRequestError("المحل مغلق في هذا اليوم — اختر وقتاً آخر ضمن أيام الدوام.")
    minute_of_day = when.hour * 60 + when.minute
    start = int(entry.get("start_minute", 0))
    end = int(entry.get("end_minute", 0))
    if not (start <= minute_of_day < end):
        start_txt = f"{start // 60:02d}:{start % 60:02d}"
        end_txt = f"{end // 60:02d}:{end % 60:02d}"
        raise MobileRequestError(f"هذا الوقت خارج أوقات دوام المحل ({start_txt}–{end_txt}).")


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
    # A REAL, VALIDATED INSTANT — see this module's own docstring and `validate_requested_time()`.
    # Epoch seconds, always inside the shop's own working hours on the day `create()` accepted it
    # (a later working-hours EDIT is never retroactively enforced on an already-created request —
    # the shop reviewing it sees the time it was asked for either way).
    requested_time: int
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
    # OPTIONAL, MANUAL, NEVER AUTO-ROUTED (owner's own words, 2026-09-15: still "لا لا خلاص
    # طلبات تترص وانتهينا" for the queue itself — this only lets a manager NAME who is going,
    # never an engine deciding for them). The operator id `assign()` set it to, or "" (unassigned
    # — visible to every manager, to no plain operator). See `assign()`'s own docstring.
    assigned_to: str = ""
    # A NEW CUSTOMER'S REFERRAL CODE, offered when the request was submitted — the only moment a
    # customer booking a mobile-service request ever types one in. Carried on the ROW (not just
    # passed straight through) so it survives until `complete()` actually turns this into a real
    # visit, which may be days after the code was offered.
    referral_code: str = ""

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
    path already shares) and `seams` (injected as `container.seams`, the same instance every other
    visit-creation ROUTE already shares — see this module's own `complete()`)."""

    def __init__(self, *, store: Any, operations: Any, default_cc: str, seams: Any = None,
                working_hours: Any = None, plans: Any = None,
                risk_window: int = 20, risk_threshold_percent: int = 40) -> None:
        self._s = store
        self._ops = operations
        self._cc = default_cc
        # `container.billing_plans` — see `is_subscribed()`'s own docstring for what this is asked
        # for and why only there. None-safe like every other optional peer here.
        self._plans = plans
        # `BookingsDesk` (or any peer with the same `async working_hours(tenant) -> dict | None`
        # shape) — see `validate_requested_time()`'s own fail-open note. None-safe: a service
        # built without one (every pre-existing test constructor) simply never checks the working-
        # hours boundary, same "optional peer, safe default" shape as every other one here.
        self._working_hours = working_hours
        # THE RIGHT WAY TO WIRE INTO "loyalty points, insights and reminders all pick it up
        # automatically" — NOT an immediate send. `seams.after_visit()` only publishes the
        # `visit.recorded` FACT (core/seams.py::_emit_visit) — reminders-service is what actually
        # schedules the rating-request/visit-confirmation message, at whatever delay the shop
        # owner configured for it (an hour, a day, whatever — that knob lives entirely in
        # reminders, not here). Calling this promptly, same as api/v1/field.py's own
        # `record_visit` route does, is what makes that owner-configured delay start counting from
        # the real completion moment instead of from whenever the 5-minute reseam sweep
        # (api/internal.py::_RESEAM_AFTER) next happens to run — a fully correct fallback, just a
        # slower one, so `seams` stays optional here rather than required.
        self._seams = seams
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
                     service_ids: list[str], requested_time: int,
                     lat: float, lng: float, referral_code: str = "") -> MobileServiceRequest:
        phone = canonical_phone(phone, default_cc=self._cc)
        if not phone:
            raise MobileRequestError("رقم الجوال غير صحيح.")
        if not service_ids:
            raise MobileRequestError("اختر خدمة واحدة على الأقل.")
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise MobileRequestError("الموقع المُرسَل غير صالح.")
        if requested_time <= 0:
            raise MobileRequestError("اختر وقتاً حقيقياً ضمن أوقات دوام المحل.")
        weekly = await self._working_hours.working_hours(tenant) if self._working_hours else None
        validate_requested_time(requested_time, weekly)
        now = _now()
        row = MobileServiceRequest(
            id=f"mreq_{uuid.uuid4().hex}", tenant=tenant, phone=phone,
            customer_name=customer_name[:128], service_ids=list(service_ids),
            requested_time=int(requested_time), lat=float(lat), lng=float(lng),
            status=PENDING, created=now, referral_code=(referral_code or "").strip()[:16])
        await self._s.put(MOBILE_REQUESTS, f"{tenant}|{row.id}",
                          {"tenant_key": tenant, **asdict(row)})
        return row

    async def get(self, tenant: str, request_id: str) -> MobileServiceRequest | None:
        raw = await self._s.get(MOBILE_REQUESTS, f"{tenant}|{request_id}")
        if not raw:
            return None
        return MobileServiceRequest(**{k: v for k, v in raw.items() if k != "tenant_key"})

    async def list(self, tenant: str, *, status: str = "", assigned_to: str = "",
                  limit: int = 200) -> list[MobileServiceRequest]:
        """`assigned_to`, WHEN GIVEN, IS THE SCOPING BOUNDARY a plain operator's own queue is
        built from — see api/v1/mobile_requests.py's own dual-capability route: a manager calls
        this with it empty (sees everything), an operator-tier caller always has it forced to
        their own id, server-side, never trusted from a query param a client could omit."""
        where: dict[str, Any] = {"tenant": tenant}
        if status:
            where["status"] = status
        if assigned_to:
            where["assigned_to"] = assigned_to
        rows, _ = await self._s.find(MOBILE_REQUESTS, where, limit=limit,
                                     sort=("created", "desc"))
        return [MobileServiceRequest(**{k: v for k, v in r.items() if k != "tenant_key"})
               for r in rows]

    # ── the shop's own review ──────────────────────────────────────────────────────────────────
    async def assign(self, tenant: str, request_id: str, *, operator_id: str) -> MobileServiceRequest:
        """Names who is actually going — purely informational for the requests engine itself
        (there is no capacity/scheduling concept here, module docstring), but it is what lets a
        manager's own console show each operator's current load and split the day's requests by
        hand, and what scopes a plain operator's OWN queue (`list(assigned_to=...)` above) and
        their own «تم»/«لم يتم» (`complete()`/`no_show()`'s own `expected_assignee`).

        Never gated on status — a manager may assign before OR after accepting, and may
        reassign/clear (`operator_id=""`) right up to the terminal states, same "still open, still
        editable" posture as `note`."""
        row = await self.get(tenant, request_id)
        if row is None:
            raise MobileRequestError("الطلب غير موجود.")
        if row.status in TERMINAL:
            raise MobileRequestError("هذا الطلب مغلق، لا يمكن تعديل إسناده.")
        row.assigned_to = operator_id
        await self._save(tenant, row)
        return row

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
    async def complete(self, tenant: str, request_id: str, *, occurred_at: int = 0,
                       expected_assignee: str = "") -> MobileServiceRequest:
        """The visit actually happened — record it exactly like any other visit, so loyalty
        points, insights and reminders all pick it up automatically. `record_visit()` is called
        DIRECTLY (same service, no network hop), the same core function every other visit-
        creation path in this file already shares — never a second definition of what a visit
        is.

        `expected_assignee`, WHEN GIVEN, IS THE OWNERSHIP CHECK a plain operator's own «تم» is
        held to — set by the route ONLY for an execute-tier caller (never a manager, who may
        always act regardless of who a request is assigned to); refused, never silently
        no-op'd, if this request belongs to someone else or nobody yet."""
        row = await self._require_accepted(tenant, request_id)
        if expected_assignee and row.assigned_to != expected_assignee:
            raise MobileRequestError("هذا الطلب مسنَد لموظف آخر.")
        recorded = await self._ops.record_visit(
            tenant=tenant, phone=row.phone, service_ids=row.service_ids,
            name=row.customer_name, occurred_at=occurred_at or _now(),
            idempotency_key=f"mreq:{row.id}", note=row.note,
            referral_code=row.referral_code)
        # SAME "not already seamed" GUARD api/v1/field.py's OWN route uses — a duplicate-key retry
        # (idempotency_key above) returns the SAME already-recorded visit, and re-running its seams
        # a second time would re-publish `visit.recorded` and re-schedule its own rating request.
        if not recorded.visit.seamed_at and self._seams is not None:
            await self._seams.after_visit(recorded)
        row.status = COMPLETED
        row.visit_id = recorded.visit.id
        await self._save(tenant, row)
        return row

    async def no_show(self, tenant: str, request_id: str, *,
                      expected_assignee: str = "") -> MobileServiceRequest:
        """Same ownership check as `complete()` above, for the same reason."""
        row = await self._require_accepted(tenant, request_id)
        if expected_assignee and row.assigned_to != expected_assignee:
            raise MobileRequestError("هذا الطلب مسنَد لموظف آخر.")
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

    # ── entitlement — asked ONLY at the WhatsApp bot's own door, see module docstring ──────────
    async def is_subscribed(self, tenant: str) -> bool | None:
        """Does THIS tenant hold `feature.mobile_requests` — asked by the bot's own creation door
        only (api/internal.py), same reasoning `core/coupons.py::granter_is_subscribed` documents
        at length: a shared internal-service credential proves only "this really is the bot",
        never which apps the tenant it names actually bought — so a request arriving over
        WhatsApp for a shop that let this app lapse must be refused there, not silently accepted.

        THREE ANSWERS, same as `granter_is_subscribed`: `True`/`False` on a real read, `None` when
        billing could not be asked at all — the caller's own job to treat those differently (a
        definite `False` refuses; `None` falls through, same `core/licence.py` doctrine every
        other billing read in this service already follows)."""
        if self._plans is None:
            return None
        plan_id = await self._plans.plan_id_for_key(MOBILE_REQUESTS_KEY)
        if not plan_id:
            return False
        subs = await self._plans.subscriptions(tenant)
        if subs is None:
            return None
        return any(str(s.get("plan") or "") == plan_id
                  and str(s.get("status") or "") in ("active", "trialing") for s in subs)
