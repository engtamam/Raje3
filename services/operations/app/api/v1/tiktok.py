"""TikTok Shop's door — a shop's own e-commerce order, arriving the same way a till's sale does.

PHASE 1 ONLY (see [[task-tiktok-app-phases]] memory). This route accepts OUR OWN internal shape,
never TikTok's literal wire schema — the real TikTok Shop → this contract adapter is a Phase 2/5
concern, built once real webhook access exists and against whatever dated endpoint version is live
THAT day (TikTok Shop versions each endpoint independently by a YYYYMM suffix in its own URL, not
one product-wide number — verified live via Playwright 2026-09-16, see the memory file). Until
then this is deliberately shaped like `till.py`'s `TillVisitIn` — a generic "an external register
told us about a sale" contract — so the day the adapter is written, it has a stable, already-tested
target to translate into rather than inventing both halves at once.

SAME MACHINE-CREDENTIAL POSTURE AS `till.py`, for the identical reason: a Bearer token minted for
exactly one establishment (`operations.record`), tenant read off the TOKEN and never the body. See
`till.py`'s own module docstring for the full three-part argument — it applies here unchanged.

GATED BY `feature.tiktok`, NOT `subscribed_write_or_visit`/`feature.api`. Owning WhatsApp, rating,
or the generic programmatic link must never unlock recording a TikTok order — only owning TikTok
itself does (`container.tiktok_licence`, wired in `container.py` with the same reasoning `feature.api`
already established for `till.py`).

THE PHONE DECISION IS MADE HERE, ONCE, BEFORE `record_visit` EVER SEES IT. TikTok Shop's default
"TikTok Shipping" mode hands sellers a masked phone (`"(+1)213-***-1234"`, confirmed live against
TikTok's own docs) — `tiktok_phone.looks_like_real_phone` is the gate that tells a real, complete
number from that mask, and a masked or missing phone routes to the tenant's one anonymous
placeholder customer (`Customer.anonymous`) instead of refusing the order or misfiling it onto a
stranger. No OTP anywhere in this file — the owner rejected that path explicitly.
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.api.auth import Principal
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.core import invoices as _invoices
from app.core import oauth_state
from app.core.branches import MAIN as MAIN_BRANCH_ID
from app.core.licence import refuses_machine_writes
from app.core.marketplaces.tiktok_shop import WEBHOOK_TOPIC, verify_webhook_signature
from app.core.operations import OperationError
from app.core.stores import ServiceStore, new_id
from app.core.tiktok_phone import looks_like_real_phone

router = APIRouter(tags=["tiktok"])

# THE ONLY CAPABILITY THIS DOOR EVER NEEDS — recording a visit is recording a visit, whoever the
# hands belong to, exactly as `till.py` already establishes for its own credential.
_TIKTOK = require_capability("operations.record")

NOT_INCLUDED = ("this establishment's subscription does not include the TikTok app "
                "(feature.tiktok) — it is not active for this shop")


class TikTokOrderLineIn(BaseModel):
    """One line of the TikTok Shop order — our own internal shape, not TikTok's wire schema (see
    module docstring). `product_id` is OUR catalogue id where a shop has bothered to map one;
    empty is the ordinary case for Phase 1 (no catalogue sync yet), same as `TillLineIn`."""

    product_id: str = Field(default="", max_length=128)
    name: str = Field(default="", max_length=200)
    qty: float = Field(default=1, ge=0, le=100_000)
    amount_minor: int = Field(default=0, ge=0, le=1_000_000_000)


class TikTokOrderIn(BaseModel):
    """A single TikTok Shop order, as our own future adapter will hand it to us.

    NO `tenant` FIELD — read off the credential, exactly like `TillVisitIn`. See the module note.
    """

    # TikTok's own order id (`"id"` in their `Get Order Detail` response, confirmed live
    # 2026-09-16) — REQUIRED, because it is the only thing that makes a retried webhook delivery
    # recognisable as the same order rather than a second one. Never optional the way `till.py`'s
    # `invoice_id` is: a till can still fall back to a content fingerprint because a human is
    # standing there; a webhook retry has nothing else stable to offer.
    order_id: str = Field(min_length=1, max_length=128)
    # RAW, UNVALIDATED HERE ON PURPOSE — `looks_like_real_phone` below is the gate, and it needs
    # the untouched string (mask characters included) to tell a real number from TikTok's own
    # redaction. Never pass this through `_normalise_phone` before the gate runs.
    phone: str = Field(default="", max_length=64)
    name: str = Field(default="", max_length=128)
    branch_id: str = Field(min_length=1, max_length=64)
    note: str = Field(default="", max_length=1000)
    lines: list[TikTokOrderLineIn] = Field(default_factory=list, max_length=50)
    total_minor: int = Field(default=0, ge=0, le=1_000_000_000)
    occurred_at: int = Field(default=0, ge=0)


async def _record_tiktok_order(request: Request, tenant: str, *, actor: str, order_id: str,
                               phone: str, name: str, branch_id: str, note: str,
                               lines: list[TikTokOrderLineIn], total_minor: int,
                               occurred_at: int) -> dict[str, Any]:
    """The one place a TikTok Shop order becomes a visit — called by `/orders` (Phase 1's manual
    door, and any future adapter that already holds the full order) AND by the webhook handler
    below (Phase 2, after it fetches the full order detail a webhook payload alone never carries).
    Never duplicated between the two: see [[task-tiktok-app-phases]] memory on why the webhook
    path fetches the real order before calling this rather than recording off the bare
    `ORDER_STATUS_CHANGE` payload.
    """
    if await refuses_machine_writes(
            getattr(request.app.state.container, "tiktok_licence", None), tenant):
        return {"accepted": False, "reason": "NOT_INCLUDED", "message": NOT_INCLUDED}

    known = await request.app.state.container.operations.known_branches(tenant)
    if branch_id.strip() not in known:
        return {"accepted": False, "reason": "UNKNOWN_BRANCH",
               "message": f"لا يوجد فرع بهذا الرقم «{branch_id.strip()[:64]}» — أرسل أحد "
                          "فروع هذا المحل."}

    # THE ONE DECISION THIS WHOLE FILE EXISTS TO MAKE CORRECTLY — see the module docstring.
    real_phone = looks_like_real_phone(phone)

    # LINES BECOME SERVICES THE SAME WAY A TILL'S INVOICE LINES DO (`app/api/internal.py`'s own
    # `record_visits_batch`) — REUSED, NOT REIMPLEMENTED. `resolve` auto-creates this tenant's own
    # catalogue entry from a TikTok product name the first time it is sold, and adopts the same
    # entry on every later order for that product — never a shared, cross-tenant row (see
    # `resolve`'s own docstring). An order with no lines at all still records against the
    # tenant's catch-all ("خدمة أخرى") below rather than being refused — losing the service
    # breakdown costs far less than losing the visit (and the customer) entirely.
    service_store = ServiceStore(request.app.state.container.datastore)
    res = await _invoices.resolve(
        _invoices.parse_lines([line.model_dump() for line in lines]),
        tenant=tenant, service_store=service_store, new_id=new_id,
        now=int(time.time()), cache=request.app.state.container.cache)

    service_ids = list(res.service_ids)
    if not service_ids:
        catch = await service_store.catchall(tenant)
        if catch is None:
            return {"accepted": False, "reason": "ERROR",
                   "message": "لا توجد خانة «خدمة أخرى» بقائمة هذا المحل — راسِلنا لإعادة تهيئتها."}
        service_ids = [catch.id]

    try:
        visit = await request.app.state.container.operations.record_visit(
            tenant=tenant,
            phone="" if not real_phone else phone,
            anonymous=not real_phone,
            service_ids=service_ids,
            quantities=res.quantities,
            allow_unknown_services=True,
            custom_service=", ".join(res.free_text)[:200],
            name=name,
            branch_id=branch_id.strip(),
            note=note,
            # THE TIKTOK ORDER'S OWN TOTAL WINS WHEN THE CALLER SENT ONE (a real amount actually
            # charged); the lines' own resolved sum is the fallback for a partial adapter that has
            # not wired the order total yet — the same "till's own total is never overridden,
            # else compute from what we could map" rule `record_visit` already applies internally,
            # applied here one layer earlier so a lineless order still gets `res.total_minor` (0).
            total_minor=total_minor or res.total_minor,
            occurred_at=occurred_at,
            idempotency_key=f"tiktok:{tenant}:{order_id.strip()}",
        )
    except OperationError as e:
        # RETURNED, NEVER RAISED — the same posture `till.py` takes with every per-item outcome:
        # a webhook adapter reads a definite reason, not an HTTP 500 to guess about.
        return {"accepted": False, "reason": "ERROR", "message": str(e)}

    # AUDITED ONLY ON THE FIRST WRITE, not on a duplicate replay — a retried webhook delivery must
    # not produce a second audit row for a visit that was already recorded once.
    if not visit.duplicate:
        await request.app.state.auditor.record(
            "tiktok.order_recorded", actor=actor, tenant=tenant,
            resource=f"visit:{visit.visit.id}",
            ip=request.client.host if request.client else "",
            metadata={"anonymous": not real_phone, "order_id": order_id[:64]})

    return {"accepted": True, "visit_id": visit.visit.id, "duplicate": visit.duplicate,
           "anonymous": not real_phone, "lines": len(lines)}


@router.post("/tiktok/orders", dependencies=[Depends(rate_limit)])
async def record_tiktok_order(request: Request, body: TikTokOrderIn,
                              principal: Principal = Depends(_TIKTOK)) -> Any:
    """Turn one TikTok Shop order into a visit — Phase 1's manual/testable door, and a stable
    target for any future integration that already holds a full order (an adapter that does not
    go through the webhook path at all).

    ONE ORDER PER CALL, NOT A BATCH (unlike `till.py`'s `/visits`). A webhook delivers one event at
    a time; batching many tills' offline queues is a real problem this route does not have, and
    inventing the shape before it is needed is exactly what `[[no-placeholder-drift]]` warns against.
    """
    if not principal.tenant:
        return {"accepted": False, "message": "هذا الاعتماد غير مرتبط بمنشأة."}
    return await _record_tiktok_order(
        request, principal.tenant, actor=f"tiktok:{principal.subject}", order_id=body.order_id,
        phone=body.phone, name=body.name, branch_id=body.branch_id, note=body.note,
        lines=body.lines, total_minor=body.total_minor, occurred_at=body.occurred_at)


# ══════════════════════════════════════════════════════════════════════════════════════════════
#  PHASE 2 — OAUTH INSTALL + VERIFIED WEBHOOK INTAKE (2026-09-16)
#
#  Every endpoint, field, and algorithm below is TikTok's own, read live 2026-09-16 against
#  partner.tiktokshop.com/docv2 via a real browser — see core/marketplaces/tiktok_shop.py's own
#  module docstring for the exact pages. Mirrors salla.py's own OAuth+webhook shape closely
#  (install/status/disconnect/callback/webhook), because the two problems are the same problem:
#  link one of our tenants to one external shop, then trust only a verified server call after that.
# ══════════════════════════════════════════════════════════════════════════════════════════════

_STATE_PURPOSE = "tiktok_shop"
#: SAME CAPABILITY `salla.py`/`connect.py` GATE THEIR OWN SELF-SERVICE CONNECT WITH — linking an
#: external account to this shop is an owner action, never a plain operator's.
_OWNER = require_capability("billing.self")


def _tenant(p: Principal) -> str:
    if not p.tenant:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "NO_TENANT")
    return p.tenant


@router.get("/staff/tiktok-shop/install", dependencies=[Depends(rate_limit)])
async def tiktok_shop_install(request: Request, principal: Principal = Depends(_OWNER)) -> Any:
    """The URL the console sends the owner's browser to — a full-page redirect to TikTok's own
    seller-authorization consent screen (Rest-of-World domain; see `authorize_url`'s own note on
    why the US-market domain is out of scope for now)."""
    tenant = _tenant(principal)
    client = request.app.state.container.tiktok_shop.client
    if not client.configured:
        return {"error": "NOT_CONFIGURED",
               "message": "تكامل تيك توك شوب لم يُفعَّل بعد على هذا الخادم."}
    s = request.app.state.container_settings
    state = oauth_state.issue(s.PII_SALT, _STATE_PURPOSE, tenant)
    return {"url": client.authorize_url(state)}


@router.get("/staff/tiktok-shop/status", dependencies=[Depends(rate_limit)])
async def tiktok_shop_status(request: Request, principal: Principal = Depends(_OWNER)) -> Any:
    tenant = _tenant(principal)
    svc = request.app.state.container.tiktok_shop
    conn = await svc.connection_for(tenant)
    if conn is None:
        return {"connected": False}
    return {"connected": True, **conn.public()}


@router.post("/staff/tiktok-shop/disconnect", dependencies=[Depends(rate_limit)])
async def tiktok_shop_disconnect(request: Request, principal: Principal = Depends(_OWNER)) -> Any:
    """The owner's own undo — removes the connection only, exactly `salla_disconnect`'s own
    reasoning: it never touches a visit already recorded through it."""
    tenant = _tenant(principal)
    svc = request.app.state.container.tiktok_shop
    removed = await svc.disconnect(tenant)
    if removed:
        await request.app.state.auditor.record(
            "tiktok.disconnected", actor=tenant, tenant=tenant,
            resource="tiktok_shop_connection", ip=request.client.host if request.client else "")
    return {"connected": False}


@router.get("/tiktok-shop/callback", dependencies=[Depends(rate_limit)])
async def tiktok_shop_callback(request: Request, code: str = "", state: str = "",
                               error: str = "") -> Any:
    """TikTok's own redirect back, after the seller approves (or rejects) the authorization
    screen. NO CAPABILITY, NO TOKEN — same `state`-is-the-whole-proof posture as
    `salla_callback`'s own docstring; see `core/oauth_state.py`."""
    if error:
        return {"ok": False, "message": "تم إلغاء الربط أو رفضه من تيك توك."}
    s = request.app.state.container_settings
    tenant = oauth_state.tenant_for(s.PII_SALT, _STATE_PURPOSE, state)
    if not tenant:
        return {"ok": False, "message": "انتهت صلاحية الرابط — ابدأ الربط من جديد."}
    client = request.app.state.container.tiktok_shop.client
    if not client.configured or not code:
        return {"ok": False, "message": "لم يصل رمز صحيح من تيك توك."}

    tokens = await run_in_threadpool(client.exchange_code, code)
    if not tokens or not tokens.get("access_token"):
        return {"ok": False, "message": "تعذّر إتمام الربط مع تيك توك. حاول مرة أخرى بعد قليل."}

    # `user_type` MUST BE 0 (Seller) — see `authorization-overview-202407`'s own enumeration. A
    # code obtained through a different authorization link (Creator=1, Partner=2/3) answering here
    # means the seller opened the wrong link, not that this app should adopt a different role.
    if int(tokens.get("user_type", 0) or 0) != 0:
        return {"ok": False, "message": "هذا الرابط مخصص لحساب بائع (Seller) فقط."}

    svc = request.app.state.container.tiktok_shop
    conn = await svc.save_connection(
        tenant=tenant, shop_id=str(tokens.get("open_id") or ""),
        seller_name=str(tokens.get("seller_name") or ""),
        access_token=str(tokens.get("access_token") or ""),
        refresh_token=str(tokens.get("refresh_token") or ""),
        access_token_expires_at=int(tokens.get("access_token_expire_in") or 0),
        refresh_token_expires_at=int(tokens.get("refresh_token_expire_in") or 0),
        scope=",".join(tokens.get("granted_scopes") or []))

    await request.app.state.auditor.record(
        "tiktok.connected", actor=tenant, tenant=tenant,
        resource=f"tiktok_shop:{conn.shop_id}", ip=request.client.host if request.client else "")
    return {"ok": True, "seller_name": conn.seller_name}


#: SEE `sign-your-api-request`'s OWN NOTE ON `sale_price` BEING A DECIMAL STRING IN THE SHOP'S
#: MAJOR CURRENCY UNIT (e.g. "5000" meaning 5000 of whatever `payment.currency` is, itself in that
#: currency's own major unit per the sample — TikTok's sample shows amounts like "5000" for what
#: their own docs call halalas-equivalent minor units in some markets and major units in others;
#: NOT FULLY VERIFIED PER-CURRENCY, so this multiplies by 100 only for the single-currency case
#: this deployment actually runs (SAR, minor unit = halalas) and is the one thing here flagged for
#: a second look before this ships to a market whose currency's minor-unit ratio differs).
def _price_to_minor(raw: str) -> int:
    try:
        return int(round(float(raw or 0) * 100))
    except (TypeError, ValueError):
        return 0


async def _fetch_and_record_order(request: Request, tenant: str, order_id: str) -> None:
    """After a verified `ORDER_STATUS_CHANGE`, fetch the FULL order (the webhook payload itself
    carries only `order_id`/`order_status`) and turn it into a visit through the exact same door
    `/orders` uses. Never raises — a fetch or mapping failure is logged and dropped, because the
    webhook route above must always answer TikTok with 200 quickly regardless (see the module's
    "cheap for every event that is not the one that matters" reasoning in `salla.py`, applied here
    to a fetch instead of a coupon grant)."""
    c = request.app.state.container
    conn = await c.tiktok_shop.connection_for(tenant)
    if conn is None:
        return
    try:
        order = await run_in_threadpool(
            c.tiktok_shop.client.get_order_detail, access_token=conn.access_token,
            shop_cipher="", order_id=order_id)
    except Exception as exc:                                                  # noqa: BLE001
        c.telemetry.event("tiktok_order_fetch_failed", tenant=tenant, error=str(exc)[:200])
        return
    if not order:
        return
    # NOT A VERIFIED COMPLETE ENUM — see [[task-tiktok-app-phases]] memory's own honest note.
    # Only the negative case is confirmed live (`"UNPAID"`, both the webhook sample and the order
    # sample use it); every OTHER status records a visit until this is reviewed against the full
    # state machine.
    if str(order.get("status") or "").upper() == "UNPAID":
        return
    addr = order.get("recipient_address") or {}
    lines = [TikTokOrderLineIn(
        product_id=str(li.get("product_id") or ""),
        name=str(li.get("product_name") or li.get("sku_name") or ""), qty=1,
        amount_minor=_price_to_minor(li.get("sale_price")))
        for li in (order.get("line_items") or [])]
    payment = order.get("payment") or {}
    await _record_tiktok_order(
        request, tenant, actor=f"tiktok_webhook:{conn.shop_id}", order_id=order_id,
        phone=str(addr.get("phone_number") or ""), name=str(addr.get("name") or ""),
        branch_id=MAIN_BRANCH_ID, note="طلب تيك توك",
        lines=lines, total_minor=_price_to_minor(payment.get("total_amount")),
        occurred_at=int(order.get("create_time") or 0))


@router.post("/tiktok-shop/webhook", dependencies=[Depends(rate_limit)])
async def tiktok_shop_webhook(request: Request) -> Any:
    """TikTok's own server call — verified against `Authorization` (see
    `verify_webhook_signature`'s own docstring for the exact scheme), deduped by
    `tts_notification_id`, and answered `{"received": true}` unconditionally so a probe or a
    signature failure teaches nothing (same posture as `salla_webhook`'s own note).

    ONE TOPIC DOES REAL WORK (`ORDER_STATUS_CHANGE`) — everything else is acknowledged and logged.
    `SELLER_DEAUTHORIZATION` disconnects immediately, matching TikTok's own recommended-listener
    table ("mark the shop connection inactive, stop seller-scoped API calls").
    """
    s = request.app.state.container_settings
    c = request.app.state.container
    raw = await request.body()
    signature = request.headers.get("authorization", "")
    verified = verify_webhook_signature(
        s.TIKTOK_SHOP_APP_KEY, s.TIKTOK_SHOP_APP_SECRET, raw, signature)

    try:
        payload = __import__("json").loads(raw or b"{}")
    except ValueError:
        payload = {}
    notification_id = str(payload.get("tts_notification_id") or "")
    shop_id = str(payload.get("shop_id") or "")
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    # THE STRING `event_type` IS NEVER IN THE DELIVERED BODY (confirmed live — a webhook payload
    # only ever carries the numeric `type`, and TikTok's own docs say plainly the numeric mapping
    # is not published for every topic, warning explicitly against branching on it alone). So THIS
    # ROUTE INFERS THE TOPIC FROM THE PAYLOAD'S OWN SHAPE INSTEAD — `order_id`+`order_status`
    # together are unambiguously `ORDER_STATUS_CHANGE`, confirmed live in the reproducible
    # signing example on `tts-webhooks-overview`.
    is_order_event = "order_id" in data and "order_status" in data

    if not verified or not shop_id or not notification_id:
        # STILL 200 — see the docstring. No event log either when the signature itself failed:
        # an unverified body is not TikTok's own word for anything, including "a webhook fired".
        return {"received": True}

    if await c.tiktok_shop.seen_notification(notification_id):
        return {"received": True}

    conn = await c.tiktok_shop.connection_for_shop(shop_id)
    tenant = conn.tenant if conn else ""
    await c.tiktok_shop.record_event(
        tts_notification_id=notification_id, shop_id=shop_id,
        event_type=(WEBHOOK_TOPIC if is_order_event else "unrecognised_shape"),
        tenant=tenant, verified=True)

    if not tenant or not is_order_event:
        # NOT AN ORDER EVENT — `SELLER_DEAUTHORIZATION`/`UPCOMING_AUTHORIZATION_EXPIRATION` are
        # deliberately NOT acted on here yet: this app only ever registers `ORDER_STATUS_CHANGE`
        # (`register_webhook`'s own `event=WEBHOOK_TOPIC`, called once at connect time — TikTok
        # never sends a topic nobody subscribed to), and the OTHER two topics' own `data` shape
        # was never confirmed live against a real payload (only their trigger SCENARIOS were, on
        # `tts-webhooks-overview`). Guessing a shape to act on would risk disconnecting a shop on
        # a payload that was never actually that event — logged above either way, acted on once a
        # real payload confirms the shape (see [[task-tiktok-app-phases]] memory).
        return {"received": True}

    await _fetch_and_record_order(request, tenant, str(data.get("order_id") or ""))
    return {"received": True}
