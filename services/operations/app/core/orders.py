"""WhatsApp Direct Ordering — the order itself. A customer messages the shop's own WhatsApp
number, orders off its catalogue, and pays into the SHOP'S OWN payment gateway account — we never
hold the money and never touch a refund (see `no-payment-refunds` — unaffected, since the funds
never reach us at all). This module only has to get the ORDER right: what was bought, at what
price, whether it was actually paid for, and where it goes.

DELIBERATELY NOT `Visit`'S OWN SHAPE, for the same reason `mobile_requests.py` is not `bookings`'s:
a `Visit` is a thing that ALREADY HAPPENED, recorded after the fact, with money as an optional
afterthought (`total_minor` only "from an integrated till"). An order is the opposite — money is
the first fact, arriving before the work does, and a wrong number here is a shop charged (or
charging a customer) for the wrong thing. So this is its own small state machine, and `complete()`
hands off to `record_visit()` only once the order is actually delivered, the same "reuse the one
piece that is genuinely shared" discipline `mobile_requests.py`'s own docstring documents.

THE PRICE IS NEVER TRUSTED FROM THE CALLER. `create()` takes service ids and quantities ONLY —
never a price — and looks up every line's real, current `Service.price_minor` itself. A WhatsApp
conversation layer (or a compromised one) that could set its own price would let a customer pay
1 halala for anything; the catalogue is the one source of truth for what something costs, the same
posture every priced read in this service already takes.

IDEMPOTENCY IS A REAL CLAIM, NOT A CHEAP READ-THEN-WRITE. `Visit.by_idempotency_key` (operations.py)
accepts a TOCTOU window because its only realistic racer is one human's own double tap. An inbound
WhatsApp order is created from a WEBHOOK, and webhooks are retried CONCURRENTLY by design (Meta's
own delivery guarantee is at-least-once, not at-most-once) — two deliveries of the same event
landing within the same millisecond is the ordinary case this module must survive, not a rare one.
So order creation claims its idempotency key the same way `signup.py::hire()` claims a phone number
(`ORDER_CLAIMS`, see `create()`) — one caller wins the lane, the other is told to retry rather than
being allowed to read "not yet created" and create a second order for the same event.

PAYMENT CONFIRMATION IS AMOUNT-CHECKED, NEVER TRUST-THE-WEBHOOK. `confirm_payment()` refuses to
mark an order paid unless the gateway's own reported amount matches the order's computed total
EXACTLY. A mismatch does not raise and does not silently accept — it parks the order in
`PAYMENT_MISMATCH`, a real status a human must resolve, because "close enough" on money is never a
rule this codebase gets to invent on an order's behalf. And a second, DIFFERENT payment reference
arriving for an already-confirmed order raises (`OrderError`) rather than being accepted or
ignored — a shop must not be shown one order while two payments against it are DOUBLE-CHARGING a
customer and keep this silently. The same reference is also refused outright on a SECOND, different
order — a reused or leaked `payment_ref` confirming two separate charges for the price of one is
the mirror-image fraud this module closes just as hard.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from app.core.mobile_requests import MobileRequestError, maps_link, validate_requested_time
from app.core.signup import canonical_phone

ORDERS = "whatsapp_orders"
ORDER_CLAIMS = "whatsapp_order_idempotency_claims"
ORDER_CLAIM_TTL_SECONDS = 20.0
# A SECOND CLAIM, KEYED ON THE DISCOUNT'S OWN REFERENCE rather than on this customer's event —
# so two unpaid orders racing to use the SAME single-use discount cannot both believe they will
# get it (see `create()`'s own note on why this is a separate lane from `ORDER_CLAIMS` above).
# Held for the SAME lifetime an unpaid order is realistically given to be paid or abandoned —
# long enough to cover a slow WhatsApp conversation, short enough that a customer who never pays
# is not locked out of their own discount for days.
DISCOUNT_CLAIMS = "whatsapp_order_discount_claims"
DISCOUNT_CLAIM_TTL_SECONDS = 1800.0

MAX_LINE_QUANTITY = 50
MAX_DISTINCT_LINES = 40
MAX_IDEMPOTENCY_KEY_LEN = 300  # a webhook event id, never a blob — an unbounded key is a storage-
                               # abuse vector, the same reasoning every other free-text field in
                               # this service is capped at the door rather than left open.

# ── the order's own lifecycle — forward only, same discipline mobile_requests' STATUS set uses ──
RECEIVED = "received"                 # created, awaiting payment confirmation
PAYMENT_MISMATCH = "payment_mismatch"  # gateway reported an amount that does not match the total
CONFIRMED = "confirmed"               # payment verified, exact amount
PREPARING = "preparing"
READY = "ready"
OUT_FOR_DELIVERY = "out_for_delivery"
DELIVERED = "delivered"
CANCELLED = "cancelled"

TERMINAL = frozenset({DELIVERED, CANCELLED})
# States a cancellation may still happen from — once the shop has started actually making it,
# cancelling is no longer this module's call to make (same "once accepted, coordinating what
# happens next is the shop's own business" posture `mobile_requests.py`'s module docstring states).
CANCELLABLE_FROM = frozenset({RECEIVED, PAYMENT_MISMATCH, CONFIRMED})
# States `confirm_payment` may still act on. Once preparation has started the order's money side
# is settled history, not something a retried webhook gets to re-evaluate.
PAYABLE_FROM = frozenset({RECEIVED, PAYMENT_MISMATCH})


class OrderError(Exception):
    """A refusal the caller (an API route or webhook handler) can show or log verbatim."""


def _now() -> int:
    return int(time.time())


def _discount_minor_for(discount: dict[str, Any], lines: list["OrderLine"],
                        total_minor: int) -> int:
    """How much `discount` (reminders' `{ref, reward_kind, reward_amount, scope_service_ids,
    expires_at}` shape) is actually worth on THIS order.

    SCOPED, THE SAME WAY A CAMPAIGN'S OWN SCOPE ALREADY WORKS EVERYWHERE ELSE (see
    `services/campaigns/app/core/models.py::Campaign.scope_service_ids`'s own docstring): empty
    scope is the whole order, a non-empty one is only the matching lines' own subtotal.

    CAPPED AT `total_minor`, NEVER BELOW ZERO — a discount can make an order free, never negative;
    a percent on a narrow scope or a fixed amount larger than the order itself must never produce
    a number the gateway would be asked to charge a customer NEGATIVE money for.
    """
    scope = set(discount.get("scope_service_ids") or [])
    base = (sum(line.line_total_minor for line in lines if line.service_id in scope)
           if scope else total_minor)
    kind = str(discount.get("reward_kind") or "")
    amount = int(discount.get("reward_amount") or 0)
    if kind == "percent":
        off = base * amount // 100
    elif kind == "fixed_halalas":
        off = amount
    else:
        off = 0
    return max(0, min(off, total_minor))


@dataclass
class OrderLine:
    service_id: str
    name: str                 # copied at order time — a later catalogue rename must not reword
                              # an old order's own receipt
    quantity: int
    unit_price_minor: int     # copied at order time, for the same reason as `name`

    @property
    def line_total_minor(self) -> int:
        return self.quantity * self.unit_price_minor

    def public(self) -> dict[str, Any]:
        row = asdict(self)
        row["line_total_minor"] = self.line_total_minor
        return row


@dataclass
class Order:
    id: str
    tenant: str
    branch_id: str
    # THE PHONE IN THE CLEAR — same posture `MobileServiceRequest.phone` already documents: this
    # is one of the few rows in the platform that holds it, deliberately, because a shop fulfilling
    # (or disputing) an order needs to be able to call the customer back.
    phone: str
    customer_name: str
    # RESOLVED AT CREATION, NEVER CARRIED AS A BARE PHONE TO ANOTHER SERVICE — same "a peer that
    # never receives the raw number cannot leak it" posture `seams.py::_emit_visit` documents for
    # visits. `subject_ref` is what `reminders` actually schedules against (see
    # `OrderService._emit`); `customer_id` is ours to look the row back up by.
    customer_id: str
    subject_ref: str
    lines: list[OrderLine]
    total_minor: int
    lat: float
    lng: float
    # THE EXACT TEXT MATCHING WEBHOOK (OR STAFF-TYPED) EVENT THIS ORDER CAME FROM — never reused
    # across orders. See module docstring on why this is claimed atomically rather than merely
    # checked.
    idempotency_key: str
    status: str
    created: int
    # PAYMENT FACTS, SEPARATE FROM STATUS — a payment can be confirmed, mismatched or absent while
    # the order itself sits in exactly one of the lifecycle states above; keeping both lets a
    # reader ask "was this ever paid" without inferring it from which status the order happens to
    # be in today.
    paid_amount_minor: int = 0
    payment_ref: str = ""
    confirmed_at: int = 0
    # SET THE MOMENT A PAY-LINK IS MINTED — `payments-service`'s own id for this request, needed to
    # ask it later "is this paid yet" (see `OrderService.sync_payment`). `pay_url` is what the
    # WhatsApp message actually sends the customer; both stay on the order even after payment
    # completes, so a receipt can always show where the money went.
    payment_request_id: str = ""
    pay_url: str = ""
    # THE DISCOUNT, KEPT SEPARATE FROM `total_minor` — same discipline this dataclass already
    # applies to `pay_url`/`payment_request_id` being their own fields rather than folded into one
    # number: `total_minor` stays the pure catalogue-priced sum (the receipt's own "before
    # discount" figure), and the discount is a separate fact layered on top, never blended in — a
    # receipt that only ever showed one number could never answer "what was this actually off of".
    # The amount actually QUOTED to the gateway and CHECKED on payment is `amount_due_minor`
    # (`total_minor - discount_minor`, see that property below) — never `total_minor` directly.
    #
    # ZERO/EMPTY IS THE OVERWHELMING MAJORITY OF ORDERS — most customers order with no live
    # campaign discount at all, and that is not a gap to explain, it is the normal case.
    discount_minor: int = 0
    # "campaign:{sendlog_id}" — the reminders send-log row this discount came from, carried so a
    # receipt (or a dispute) can trace the number back to an actual campaign send rather than a
    # bare amount nobody can explain six months later.
    discount_source: str = ""
    preparing_at: int = 0
    ready_at: int = 0
    out_for_delivery_at: int = 0
    delivered_at: int = 0
    cancelled_at: int = 0
    cancel_reason: str = ""
    note: str = ""
    # SET ONLY ON DELIVERY — the real Visit this order turned into, same "never a dead end" shape
    # `MobileServiceRequest.visit_id` already uses, so loyalty/insights/reminders pick it up.
    visit_id: str = ""

    @property
    def maps_url(self) -> str:
        return maps_link(self.lat, self.lng)

    @property
    def amount_due_minor(self) -> int:
        """What the customer is ACTUALLY asked to pay — `total_minor` stays the pure catalogue
        sum on purpose (it is the receipt's own "before discount" figure), but the gateway must
        never be quoted that number once a discount is sitting on the order: `request_payment()`
        mints the link for THIS amount, and `confirm_payment()` checks the gateway's reported
        amount against THIS amount, never `total_minor` directly."""
        return max(0, self.total_minor - self.discount_minor)

    def public(self) -> dict[str, Any]:
        row = asdict(self)
        row["lines"] = [line.public() if isinstance(line, OrderLine) else line
                        for line in self.lines]
        row["maps_url"] = self.maps_url
        row["amount_due_minor"] = self.amount_due_minor
        return row


def _row_from(raw: dict[str, Any]) -> Order:
    raw = {k: v for k, v in raw.items() if k != "tenant_key"}
    raw = dict(raw)
    raw["lines"] = [OrderLine(**line) for line in raw.get("lines") or []]
    return Order(**raw)


class OrderService:
    """Everything an order needs other than `record_visit()` itself (injected the same way
    `MobileRequestService` already takes it) and the catalogue/branch reads needed to PRICE and
    PLACE an order rather than trust either off the wire."""

    def __init__(self, *, store: Any, services: Any, branches: Any, operations: Any = None,
                seams: Any = None, payments: Any = None, events: Any = None,
                working_hours: Any = None, pauses: Any = None, discounts: Any = None,
                default_cc: str = "966") -> None:
        self._s = store
        self._services = services      # ServiceStore — the one source of truth for price/active
        self._branches = branches      # BranchStore — confirms the branch is real and this tenant's
        self._ops = operations         # Operations — record_visit() on delivery, same as mobile_requests
        self._seams = seams
        self._payments = payments      # PaymentsDesk — mints/reconciles the merchant's own pay-link
        self._events = events          # EventBus — publishes "operations.order.changed", see _emit
        # `BookingsDesk` (or any peer with the same `async working_hours(tenant) -> dict | None`
        # shape) — same fail-open posture `mobile_requests.py`'s own docstring documents: an
        # unreachable peer SKIPS the check rather than refusing every order no one can verify.
        self._working_hours = working_hours
        self._pauses = pauses          # OrderPauseStore — the cashier's own manual stop button
        # `{find, redeem}` — adapters/discount_desk.py's own `http_discount_desk`. `None` is the
        # real, supported "no campaign discount feature reaches orders at all" state, the same
        # posture every other optional peer on this class already takes: `create()` simply never
        # looks one up and every order prices from the catalogue alone, exactly as before this
        # existed.
        self._discounts = discounts
        self._cc = default_cc

    async def _emit(self, row: "Order") -> None:
        """Publish the fact, for `reminders` to turn into a WhatsApp message — same "publish
        rather than call" discipline `seams.py::_emit_visit` documents: this service stays
        ignorant of who consumes an order status change. The payload carries `subject_ref`, NEVER
        the phone — see `Order.subject_ref`'s own docstring.

        BEST-EFFORT, NEVER RAISES AND NEVER BLOCKS THE STATUS CHANGE ITSELF — an event-bus outage
        must not stop a shop from marking an order ready; `reminders`' own doc on this exact port
        is explicit that an event is a hint, never the only way a fact may be learned, so losing
        one here is not data loss, only a slower notification than usual."""
        if self._events is None or not row.subject_ref:
            return
        try:
            from app.ports.event_bus import Event
            await self._events.publish("operations.order.changed", Event(
                type="operations.order.changed",
                payload={"tenant": row.tenant, "order_id": row.id, "subject_ref": row.subject_ref,
                        "status": row.status, "branch_id": row.branch_id}))
        except Exception:                                                   # noqa: BLE001
            pass

    # ── creation — the WhatsApp catalogue door ─────────────────────────────────────────────────
    async def create(self, *, tenant: str, branch_id: str, phone: str, customer_name: str,
                     items: list[tuple[str, int]], lat: float, lng: float,
                     idempotency_key: str, note: str = "") -> Order:
        """`items` is `[(service_id, quantity), ...]` — NEVER a price. Raises `OrderError` with a
        sayable reason for every bad input; raises it for a key already claimed by another
        in-flight request too, so a webhook handler's retry logic has exactly one exception type
        to catch for "try again shortly"."""
        if not idempotency_key:
            raise OrderError("لا يوجد معرّف لمنع تكرار الطلب — لن يُسجَّل الطلب.")
        if len(idempotency_key) > MAX_IDEMPOTENCY_KEY_LEN:
            raise OrderError("معرّف منع التكرار طويل بشكل غير معتاد.")
        if not branch_id:
            raise OrderError("لم يُحدَّد الفرع المسؤول عن هذا الطلب.")
        phone = canonical_phone(phone, default_cc=self._cc)
        if not phone:
            raise OrderError("رقم جوال العميل غير صحيح.")
        if not items:
            raise OrderError("لا يوجد أي صنف في الطلب.")
        if len(items) > MAX_DISTINCT_LINES:
            raise OrderError("عدد أصناف الطلب كبير بشكل غير معتاد — تواصل مع الدعم.")
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise OrderError("الموقع المُرسَل غير صالح.")

        branch = await self._branches.get(tenant, branch_id)
        if branch is None or not branch.active:
            raise OrderError("الفرع المحدَّد غير موجود أو غير نشِط.")

        # CLOSED FOR THE DAY — same real, validated instant check `mobile_requests.py`'s own
        # `validate_requested_time` already enforces for a REQUESTED time; here it is asked about
        # RIGHT NOW. Fail-open on an unreachable peer, same reasoning that module's docstring gives.
        if self._working_hours is not None:
            weekly = await self._working_hours.working_hours(tenant)
            try:
                validate_requested_time(int(time.time()), weekly)
            except MobileRequestError as exc:
                raise OrderError(str(exc)) from exc

        # THE CASHIER'S OWN MANUAL STOP, SEPARATE FROM WORKING HOURS — a branch well within its
        # posted hours can still need to pause (core/order_pause.py's own module docstring).
        if self._pauses is not None:
            paused, reason = await self._pauses.get(tenant, branch_id)
            if paused:
                raise OrderError(f"هذا الفرع متوقف عن استقبال الطلبات مؤقتاً"
                                 f"{f' — {reason}' if reason else ''}.")

        # MERGE DUPLICATE LINES BEFORE PRICING, NEVER AFTER — a customer (or a buggy conversation
        # flow) sending the same service twice must total the same as sending it once with double
        # the quantity; pricing each raw line separately and summing would be correct arithmetic
        # that still double-counts nothing, but merging first is what makes the RECEIPT read right
        # too (one line, not two, same as `Visit.quantities`'s own reasoning).
        merged: dict[str, int] = {}
        for service_id, quantity in items:
            service_id = str(service_id).strip()
            if not service_id:
                raise OrderError("أحد الأصناف بلا معرّف خدمة.")
            quantity = int(quantity)
            if quantity <= 0:
                raise OrderError("كمية أحد الأصناف غير صحيحة.")
            if quantity > MAX_LINE_QUANTITY:
                raise OrderError("كمية أحد الأصناف كبيرة بشكل غير معتاد — تواصل مع الدعم.")
            merged[service_id] = merged.get(service_id, 0) + quantity

        lines: list[OrderLine] = []
        total_minor = 0
        for service_id, quantity in merged.items():
            svc = await self._services.get(tenant, service_id)
            if svc is None or not svc.active:
                raise OrderError(f"أحد الأصناف المطلوبة لم يعد متاحاً ({service_id}).")
            if svc.price_minor <= 0:
                # A catalogue entry with no real price (e.g. a catch-all, or one the owner never
                # priced) cannot become a charged line — the whole point of pricing server-side.
                raise OrderError(f"الصنف «{svc.name}» ليس له سعر محدَّد، لا يمكن طلبه عبر واتساب.")
            if quantity * svc.price_minor > total_minor + 10_000_000_00:
                # A sanity ceiling, not a real limit — catches a quantity/price combination that
                # overflows into nonsense (a corrupt catalogue row, a unit mismatch) before it
                # becomes an order nobody can actually be charged.
                raise OrderError("إجمالي الطلب كبير بشكل غير منطقي — تحقّق من الكميات.")
            lines.append(OrderLine(service_id=service_id, name=svc.name, quantity=quantity,
                                   unit_price_minor=svc.price_minor))
            total_minor += quantity * svc.price_minor

        now = time.time()
        if not await self._s.claim(ORDER_CLAIMS, f"{tenant}|{idempotency_key}", {"tenant": tenant},
                                   ttl_seconds=ORDER_CLAIM_TTL_SECONDS, now=now):
            # SOMEBODY ELSE HOLDS THIS EXACT EVENT RIGHT NOW. It may already be done — check before
            # refusing, so a webhook retry that lands just after the winner finished gets the real
            # order back instead of a confusing "try again" for a request that already succeeded.
            existing = await self.by_idempotency_key(tenant, idempotency_key)
            if existing is not None:
                return existing
            raise OrderError("هذا الطلب قيد المعالجة الآن — أعد المحاولة خلال لحظات.")
        try:
            # THE CLAIM COULD HAVE BEEN WON AFTER A PRIOR ATTEMPT ALREADY FINISHED AND RELEASED IT
            # (the TTL lane is for the in-flight window, not a permanent ledger) — so the real,
            # permanent check is this read, made again now that the lane is ours alone.
            existing = await self.by_idempotency_key(tenant, idempotency_key)
            if existing is not None:
                return existing
            customer_id, subject_ref = "", ""
            if self._ops is not None:
                # RESOLVED, NEVER A VISIT — `ensure_customer` is the same "find or create by
                # phone, no visit attached" call `bookings`' own console dialog already uses
                # (operations.py::ensure_customer's own docstring). This is NOT a visit: the order
                # has not been fulfilled yet, and `complete()` below records the real one later.
                customer, _created = await self._ops.ensure_customer(
                    tenant=tenant, phone=phone, name=(customer_name or "").strip(),
                    source="whatsapp")
                customer_id, subject_ref = customer.id, customer.subject_ref

            # ── a live campaign discount, IF one is held AND not already promised elsewhere ────
            #
            # NOT CONSUMED HERE. The discount is only RESERVED at creation — `confirm_payment()`
            # below is the one place that ever tells reminders it was actually spent. An order
            # that is cancelled or simply never paid must leave the discount exactly as available
            # as it was before this order existed; spending it here would charge the customer's
            # one-time offer against an order that never became real money.
            #
            # A FAILURE HERE MEANS "NO DISCOUNT THIS ATTEMPT", NEVER A REFUSED ORDER — same
            # posture `offer_choice.py`'s own docstring takes for visits: an unreachable reminders
            # must not stop a customer from ordering, it must simply not promise them a discount
            # peer we could not verify.
            discount_minor, discount_source = 0, ""
            if self._discounts is not None and subject_ref:
                try:
                    discount = await self._discounts["find"](tenant=tenant,
                                                              subject_ref=subject_ref)
                except Exception:                                          # noqa: BLE001
                    discount = None
                ref = str((discount or {}).get("ref") or "")
                if ref:
                    # THE SECOND CLAIM — keyed on the discount, not the webhook event, so two
                    # unpaid orders racing for the SAME single-use discount cannot both believe
                    # they will get it (module-level `DISCOUNT_CLAIMS`'s own note). Released on
                    # `cancel()` and on a successful `confirm_payment()`; otherwise it simply
                    # expires, freeing the discount back up for a customer who never paid.
                    reserved = await self._s.claim(
                        DISCOUNT_CLAIMS, f"{tenant}|{ref}", {"tenant": tenant, "order_id": ""},
                        ttl_seconds=DISCOUNT_CLAIM_TTL_SECONDS, now=now)
                    if reserved:
                        discount_minor = _discount_minor_for(discount, lines, total_minor)
                        discount_source = f"campaign:{ref}"

            row = Order(id=f"ord_{uuid.uuid4().hex}", tenant=tenant, branch_id=branch_id,
                       phone=phone, customer_name=(customer_name or "")[:128],
                       customer_id=customer_id, subject_ref=subject_ref, lines=lines,
                       total_minor=total_minor, lat=float(lat), lng=float(lng),
                       idempotency_key=idempotency_key, status=RECEIVED, created=int(now),
                       note=(note or "")[:1000], discount_minor=discount_minor,
                       discount_source=discount_source)
            await self._save(row)
            return row
        finally:
            await self._s.delete(ORDER_CLAIMS, f"{tenant}|{idempotency_key}")

    async def by_idempotency_key(self, tenant: str, key: str) -> Order | None:
        if not key:
            return None
        rows, _ = await self._s.find(ORDERS, {"tenant": tenant, "idempotency_key": key}, limit=1)
        return _row_from(rows[0]) if rows else None

    async def get(self, tenant: str, order_id: str) -> Order | None:
        raw = await self._s.get(ORDERS, f"{tenant}|{order_id}")
        return _row_from(raw) if raw else None

    async def list(self, tenant: str, *, status: str = "", branch_id: str = "",
                  limit: int = 200) -> list[Order]:
        where: dict[str, Any] = {"tenant": tenant}
        if status:
            where["status"] = status
        if branch_id:
            where["branch_id"] = branch_id
        rows, _ = await self._s.find(ORDERS, where, limit=limit, sort=("created", "desc"))
        return [_row_from(r) for r in rows]

    async def _save(self, row: Order) -> None:
        await self._s.put(ORDERS, f"{row.tenant}|{row.id}",
                          {"tenant_key": row.tenant, **{**asdict(row)}})

    # ── payment — minting the link, then the real source of truth, never an event alone ────────
    async def request_payment(self, tenant: str, order_id: str) -> Order:
        """Mint (or re-use — payments-service's own `reference` idempotency is `Order.id`) the
        hosted pay-link the WhatsApp message actually sends the customer. Safe to call again on
        the SAME order (e.g. the conversation retries after a timeout): payments-service returns
        the same link for the same reference rather than minting a second one."""
        row = await self.get(tenant, order_id)
        if row is None:
            raise OrderError("الطلب غير موجود.")
        if row.status not in PAYABLE_FROM:
            raise OrderError("هذا الطلب لم يعد بانتظار الدفع.")
        if self._payments is None:
            raise OrderError("تعذّر إنشاء رابط الدفع الآن — حاول بعد لحظات.")
        out = await self._payments.create_request(
            tenant=tenant, reference=row.id, amount_minor=row.amount_due_minor,
            metadata={"branch_id": row.branch_id})
        if out is None or not out.get("ok"):
            raise OrderError("تعذّر إنشاء رابط الدفع الآن — حاول بعد لحظات.")
        row.payment_request_id = str(out.get("request_id") or "")
        row.pay_url = str(out.get("pay_url") or "")
        await self._save(row)
        return row

    async def sync_payment(self, tenant: str, order_id: str) -> Order:
        """Ask `payments-service` for this order's CURRENT status and apply it — the pollable
        fallback every consumer of its event bus must have (see `adapters/payments_desk.py`'s own
        module docstring): called by a periodic sweep, or on demand right after a customer tells
        the WhatsApp conversation "I paid". A no-op, safely re-callable, if there is nothing new."""
        row = await self.get(tenant, order_id)
        if row is None:
            raise OrderError("الطلب غير موجود.")
        if not row.payment_request_id or self._payments is None:
            return row
        out = await self._payments.reconcile(tenant=tenant, request_id=row.payment_request_id)
        if out is None or not out.get("ok"):
            return row  # peer unreachable, or nothing resolvable yet — try again later
        if out.get("status") != "completed":
            return row
        return await self.confirm_payment(
            tenant, order_id, paid_amount_minor=int(out.get("amount_minor") or 0),
            payment_ref=str(out.get("provider_ref") or out.get("request_id") or ""))

    async def confirm_payment(self, tenant: str, order_id: str, *, paid_amount_minor: int,
                              payment_ref: str) -> Order:
        if not payment_ref:
            raise OrderError("لا يوجد مرجع للدفعة.")
        row = await self.get(tenant, order_id)
        if row is None:
            raise OrderError("الطلب غير موجود.")
        # A PAYMENT REFERENCE IS ONE ORDER'S, NEVER TWO'S. Without this check, a leaked, replayed,
        # or simply reused `payment_ref` (a bug upstream, or a malicious caller who learned a real
        # one) could confirm a SECOND, unrelated order as paid for free — the exact same money
        # marked as covering two different charges. Checked BEFORE this order's own `payment_ref`
        # state, since a collision with a DIFFERENT order is a worse, more suspicious case than
        # this order's own retry and must never be shadowed by it.
        clash, _ = await self._s.find(ORDERS, {"tenant": tenant, "payment_ref": payment_ref},
                                      limit=2)
        if any(r.get("id") != order_id for r in clash):
            raise OrderError("مرجع هذه الدفعة مستخدَم بالفعل لطلب آخر — لن يُعتمَد هنا.")
        if row.payment_ref:
            # ALREADY HAS A PAYMENT ON FILE. The SAME reference arriving again is the gateway's own
            # at-least-once retry — a no-op, return as-is. A DIFFERENT reference is a second,
            # distinct payment attempt reaching an order that already has one: never silently
            # accepted or silently dropped, because either outcome can hide a customer being
            # charged twice.
            if row.payment_ref == payment_ref:
                return row
            raise OrderError("هذا الطلب له دفعة مسجَّلة بالفعل بمرجع مختلف — راجع الأمر يدوياً.")
        if row.status not in PAYABLE_FROM:
            raise OrderError("هذا الطلب لم يعد بانتظار تأكيد الدفع.")
        row.paid_amount_minor = int(paid_amount_minor)
        row.payment_ref = payment_ref
        if row.paid_amount_minor == row.amount_due_minor:
            row.status = CONFIRMED
            row.confirmed_at = _now()
        else:
            # PARKED, NOT GUESSED. A human resolves whether this was a partial payment, a currency
            # mixup upstream, or a gateway reporting error — this module never decides that a
            # "close enough" amount means the order is paid.
            row.status = PAYMENT_MISMATCH
        await self._save(row)
        if row.status == CONFIRMED:
            await self._redeem_discount(tenant, row)
            await self._emit(row)
        return row

    async def _redeem_discount(self, tenant: str, row: "Order") -> None:
        """THE ONLY MOMENT A DISCOUNT IS EVER ACTUALLY SPENT — never at `create()`. The amount was
        already locked in at `discount_minor` and must not change here; this only tells reminders
        the single-use send-log row is now consumed, so it can never be promised to a second
        order. Called from every path that lands an order on CONFIRMED — `confirm_payment()`'s own
        exact-match case AND `resolve_mismatch()`'s human override both spend the SAME discount the
        SAME way; neither is a special case of the other.

        BEST-EFFORT, NEVER RAISES: the payment is already confirmed/approved by this point —
        refusing to confirm it because reminders happens to be unreachable right now would be a
        second, worse failure layered on top of a real payment we already verified. The cost of a
        redeem call that never lands is a discount that could in principle be spent twice by an
        unlucky customer; the cost of refusing a verified payment is a shop that charged a customer
        and then told them their order failed."""
        if not row.discount_source.startswith("campaign:") or self._discounts is None:
            return
        ref = row.discount_source.split(":", 1)[1]
        try:
            await self._discounts["redeem"](tenant=tenant, ref=ref,
                                            redeemed_by=f"order:{row.id}")
        except Exception:                                                  # noqa: BLE001
            pass
        await self._s.delete(DISCOUNT_CLAIMS, f"{tenant}|{ref}")

    async def resolve_mismatch(self, tenant: str, order_id: str, *, actor: str) -> Order:
        """A human looked at the mismatch and is satisfied the order should proceed as paid —
        moves it to CONFIRMED without touching `paid_amount_minor`/`total_minor` (the discrepancy
        stays on the record; only the STATUS moves on), so the mismatch is never silently erased
        from an order's own history."""
        row = await self.get(tenant, order_id)
        if row is None:
            raise OrderError("الطلب غير موجود.")
        if row.status != PAYMENT_MISMATCH:
            raise OrderError("هذا الطلب ليس به تعارض بالمبلغ.")
        row.status = CONFIRMED
        row.confirmed_at = _now()
        row.note = (row.note + f"\n[{actor}] تم اعتماد الطلب رغم فرق المبلغ.").strip()[:1000]
        await self._save(row)
        await self._redeem_discount(tenant, row)
        await self._emit(row)
        return row

    # ── the shop's own fulfilment — forward only ───────────────────────────────────────────────
    async def start_preparing(self, tenant: str, order_id: str) -> Order:
        row = await self._require_status(tenant, order_id, CONFIRMED)
        row.status = PREPARING
        row.preparing_at = _now()
        await self._save(row)
        await self._emit(row)
        return row

    async def mark_ready(self, tenant: str, order_id: str) -> Order:
        row = await self._require_status(tenant, order_id, PREPARING)
        row.status = READY
        row.ready_at = _now()
        await self._save(row)
        await self._emit(row)
        return row

    async def start_delivery(self, tenant: str, order_id: str) -> Order:
        row = await self._require_status(tenant, order_id, READY)
        row.status = OUT_FOR_DELIVERY
        row.out_for_delivery_at = _now()
        await self._save(row)
        await self._emit(row)
        return row

    async def complete(self, tenant: str, order_id: str) -> Order:
        """Delivered — record it as a real visit so loyalty points, insights and reminders all
        pick it up, same hand-off `MobileRequestService.complete()` already does."""
        row = await self._require_status(tenant, order_id, OUT_FOR_DELIVERY)
        if self._ops is not None and not row.visit_id:
            service_ids = [line.service_id for line in row.lines for _ in range(line.quantity)]
            quantities = {line.service_id: line.quantity for line in row.lines}
            recorded = await self._ops.record_visit(
                tenant=tenant, phone=row.phone, service_ids=service_ids,
                name=row.customer_name, branch_id=row.branch_id,
                occurred_at=_now(), idempotency_key=f"order:{row.id}",
                note=row.note, quantities=quantities, total_minor=row.amount_due_minor)
            if not recorded.visit.seamed_at and self._seams is not None:
                await self._seams.after_visit(recorded)
            row.visit_id = recorded.visit.id
        row.status = DELIVERED
        row.delivered_at = _now()
        await self._save(row)
        await self._emit(row)
        return row

    async def cancel(self, tenant: str, order_id: str, *, reason: str, actor: str = "") -> Order:
        row = await self.get(tenant, order_id)
        if row is None:
            raise OrderError("الطلب غير موجود.")
        if row.status not in CANCELLABLE_FROM:
            raise OrderError("لم يعد ممكناً إلغاء هذا الطلب — بدأ تجهيزه بالفعل.")
        row.status = CANCELLED
        row.cancelled_at = _now()
        row.cancel_reason = (reason or "")[:300]
        # FREE THE DISCOUNT BACK UP IMMEDIATELY — a cancelled order never spent it (only
        # `confirm_payment` ever does), so there is no reason to make the customer wait out
        # `DISCOUNT_CLAIM_TTL_SECONDS` before it is available to a next attempt.
        if row.discount_source.startswith("campaign:"):
            ref = row.discount_source.split(":", 1)[1]
            await self._s.delete(DISCOUNT_CLAIMS, f"{tenant}|{ref}")
        await self._save(row)
        await self._emit(row)
        return row

    async def _require_status(self, tenant: str, order_id: str, expected: str) -> Order:
        row = await self.get(tenant, order_id)
        if row is None:
            raise OrderError("الطلب غير موجود.")
        if row.status != expected:
            raise OrderError("حالة الطلب الحالية لا تسمح بهذا الإجراء.")
        return row
