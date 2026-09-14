"""Salla — infrastructure only. See `core/marketplaces/salla.py`'s own module docstring for the
full reasoning and the exact Salla docs each piece was read from; this file is the HTTP door.

TWO ROUTES NEED A TOKEN (`/staff/salla/install`, `/staff/salla/status`) AND TWO CANNOT
(`/salla/callback`, `/salla/webhook`) — same split `signup.py`'s own module docstring documents
for its two unauthenticated routes: Salla's own redirect and Salla's own server call arrive with
no Bearer token to check, so these two are rate-limited and self-contained instead, exactly like
signup's pair. NOT IN THE ACTION CATALOGUE either, for the identical reason signup's aren't.
"""
from __future__ import annotations

import html
import json
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.concurrency import run_in_threadpool

from app.api.auth import Principal
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.core import oauth_state
from app.core.marketplaces.salla import APP_UNINSTALLED_EVENT, WEBHOOK_EVENT, verify_signature

router = APIRouter(tags=["salla"])


def _tenant(p: Principal) -> str:
    """Same one-line rule as every other staff door in this service (staff.py's own copy) — kept
    local rather than imported so this file has no dependency on staff.py's internals."""
    if not p.tenant:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "NO_TENANT")
    return p.tenant

_STATE_PURPOSE = "salla"

# SAME CAPABILITY `connect.py` GATES META EMBEDDED SIGNUP WITH — connecting an external account
# to this shop is a self-service OWNER action in both cases, never a plain operator's.
_OWNER = require_capability("billing.self")


@router.get("/staff/salla/install", dependencies=[Depends(rate_limit)])
async def salla_install(request: Request, principal: Principal = Depends(_OWNER)) -> Any:
    """The URL the console sends the owner's browser to — a full-page redirect to Salla's own
    consent screen, not a popup (unlike WhatsApp's Embedded Signup): Salla's OAuth is a plain
    server-redirect flow, read live from docs.salla.dev/421118m0.

    THE WIRED `container.salla.client`, NEVER A FRESH INSTANCE — one client, built once from
    settings at container-build time (see `container.py`), is what `/callback` below also reads;
    two independently-constructed clients would be two places a monkeypatched test (or a future
    runtime credential swap) could silently diverge from what actually runs."""
    tenant = _tenant(principal)
    client = request.app.state.container.salla.client
    if not client.configured:
        return JSONResponse(
            {"error": "NOT_CONFIGURED",
             "message": "تكامل سلة لم يُفعَّل بعد على هذا الخادم."}, status_code=400)
    s = request.app.state.container_settings
    state = oauth_state.issue(s.PII_SALT, _STATE_PURPOSE, tenant)
    return {"url": client.authorize_url(state)}


@router.get("/staff/salla/status", dependencies=[Depends(rate_limit)])
async def salla_status(request: Request, principal: Principal = Depends(_OWNER)) -> Any:
    tenant = _tenant(principal)
    svc = request.app.state.container.salla
    conn = await svc.connection_for(tenant)
    if conn is None:
        return {"connected": False}
    return {"connected": True, **conn.public()}


@router.post("/staff/salla/disconnect", dependencies=[Depends(rate_limit)])
async def salla_disconnect(request: Request, principal: Principal = Depends(_OWNER)) -> Any:
    """The owner's own undo — see `SallaService.disconnect`'s own docstring: removes the
    connection only, never touches an alliance already granted through it. Answers `{"connected":
    false}` either way (something really was removed, or there was nothing to remove), the exact
    same shape `/status` above answers when nothing is connected — a second click, or a stale
    page's retry, reads as success rather than a confusing 404."""
    tenant = _tenant(principal)
    svc = request.app.state.container.salla
    removed = await svc.disconnect(tenant)
    if removed:
        await request.app.state.auditor.record(
            "salla.disconnected", actor=tenant, tenant=tenant, resource="salla_connection",
            ip=request.client.host if request.client else "")
    return {"connected": False}


def _callback_page(*, title: str, message: str, ok: bool, store_name: str = "",
                   status_code: int = 200) -> HTMLResponse:
    """The one page every branch below renders — HTML-escaped for what a human reads, AND wired
    to close itself and hand the result back to the console when it was opened as a POPUP
    (`window.open`, the console's own connect button — see Coupons.tsx). Falls back to a plain
    readable page with nothing to click when there is no `window.opener` (the owner opened the
    link directly, or a browser blocked the popup) — the same content either way, just an extra
    silent step when a popup opener IS there.

    `store_name` IS FROM SALLA, NOT OURS — a merchant name is free text on their side, so it goes
    through `html.escape` for the visible page exactly like `title`/`message`, and the payload
    handed to `postMessage` is defanged against a literal `</script>` breaking out of its own tag
    (`json.dumps` makes a JS-string-safe value, not an HTML/script-tag-safe one — those are two
    different escaping problems, and only the second needs the extra replace below).
    """
    safe_title = html.escape(title)
    safe_message = html.escape(message)
    payload = json.dumps({"source": "raje3:salla-connect", "ok": ok, "message": message,
                          "store_name": store_name}).replace("</", "<\\/")
    body = (
        f'<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">'
        f'<title>ربط سلة</title></head>'
        f'<body style="font-family:system-ui;text-align:center;padding:48px">'
        f'<h1>{safe_title}</h1><p>{safe_message}</p>'
        f'<script>(function(){{var p={payload};'
        f'if(window.opener){{try{{window.opener.postMessage(p,"*");}}catch(e){{}}window.close();}}'
        f'}})();</script>'
        f'</body></html>'
    )
    return HTMLResponse(body, status_code=status_code)


@router.get("/salla/callback", dependencies=[Depends(rate_limit)])
async def salla_callback(request: Request, code: str = "", state: str = "",
                         error: str = "") -> HTMLResponse:
    """Salla's own redirect back, after the owner approves (or refuses) the consent screen.

    NO CAPABILITY, NO TOKEN — this arrives as a fresh browser navigation FROM salla.sa, carrying
    none of ours. `state` is the entire proof of which tenant asked (see `core/oauth_state.py`'s
    own module docstring); a `state` that does not verify is answered exactly like an expired one
    — there is nothing more specific to tell an unauthenticated caller that would not also help
    someone probing this URL blind.
    """
    s = request.app.state.container_settings
    if error:
        return _callback_page(
            ok=False, title="تعذّر الربط",
            message="تم إلغاء الربط أو رفضه من سلة. أغلق هذه الصفحة وحاول مرة أخرى.")
    tenant = oauth_state.tenant_for(s.PII_SALT, _STATE_PURPOSE, state)
    if not tenant:
        return _callback_page(
            ok=False, title="انتهت صلاحية الرابط",
            message="ابدأ الربط من جديد من لوحة تحكمك — هذا الرابط لم يعد صالحاً.",
            status_code=400)
    client = request.app.state.container.salla.client
    if not client.configured or not code:
        return _callback_page(ok=False, title="تعذّر الربط",
                              message="لم يصل رمز صحيح من سلة.", status_code=400)

    tokens = await run_in_threadpool(client.exchange_code, code)
    if not tokens or not tokens.get("access_token"):
        return _callback_page(
            ok=False, title="تعذّر الربط",
            message="تعذّر إتمام الربط مع سلة. حاول مرة أخرى بعد قليل.", status_code=502)

    access_token = str(tokens.get("access_token") or "")
    info = await run_in_threadpool(client.user_info, access_token) or {}
    # Salla's own docs (docs.salla.dev/421118m0) do not put a merchant id on the TOKEN response —
    # it is read separately from /oauth2/user/info. `merchant`/`id` are read defensively (`or {}`
    # chains) since a real vendor response shape is trusted no further than what it actually sent.
    merchant = info.get("merchant") if isinstance(info.get("merchant"), dict) else info
    merchant_id = str((merchant or {}).get("id") or "")
    store_name = str((merchant or {}).get("name") or "")
    if not merchant_id:
        return _callback_page(ok=False, title="تعذّر الربط",
                              message="لم نستطع التعرف على متجرك من سلة.", status_code=502)

    expires_at = int(time.time()) + int(tokens.get("expires") or 0)
    svc = request.app.state.container.salla

    # REGISTER OUR WEBHOOK, AUTOMATICALLY — the whole point of `webhooks.read_write` in
    # DEFAULT_SCOPE. Best-effort: a failure here does not fail the connect (the OAuth link is
    # real either way) — it just means this connection's own `webhook_id` stays "" and this
    # merchant's real orders never reach `/salla/webhook`, exactly the same silent-until-a-refresh
    # -fails shape a missing manual Partners Portal subscription used to have, minus the manual
    # step. See SallaClient.register_webhook's own docstring.
    webhook_url = f"{s.PUBLIC_BASE_URL.rstrip('/')}/api/v1/salla/webhook"
    registration = await run_in_threadpool(
        client.register_webhook, access_token, event=WEBHOOK_EVENT, url=webhook_url,
        name="Raje3 — تحالف استراتيجي")
    webhook_id = str(((registration or {}).get("data") or {}).get("id") or "")

    await svc.save_connection(
        tenant=tenant, merchant_id=merchant_id, store_name=store_name,
        access_token=access_token, refresh_token=str(tokens.get("refresh_token") or ""),
        expires_at=expires_at, scope=str(tokens.get("scope") or ""), webhook_id=webhook_id)

    await request.app.state.auditor.record(
        "salla.connected", actor=tenant, tenant=tenant, resource=f"salla_merchant:{merchant_id}",
        ip=request.client.host if request.client else "",
        metadata={"webhook_registered": bool(webhook_id)})

    return _callback_page(
        ok=True, store_name=store_name, title="تم الربط بنجاح",
        message=f"متجرك «{store_name or merchant_id}» أصبح مرتبطاً بحسابك عندنا. "
                "أغلق هذه الصفحة وارجع للوحة تحكمك.")


#: THE ONLY EVENT/STATUS PAIR THAT DOES ANY REAL WORK (owner's own decision, 2026-09-15: "ما
#: نسمح إلا على order.status.updated وتكون completed عشان نخفف ضغط على السيرفر"). Salla's own
#: docs (docs.salla.dev/421119m0) list nine order events — created, updated, cancelled, refunded,
#: deleted, payment.updated, coupon.updated, total.price.updated, status.updated — an order
#: genuinely fires several of these across its life, and `order.created` in particular can (and
#: often does) mean "under review", not "money changed hands". Granting on that would spend the
#: platform's own subscription discount on a sale that has not actually happened yet, and might
#: never. `status.updated` + `completed` is the one combination that means the deal is done.
_TARGET_STATUS_SLUG = "completed"


@router.post("/salla/webhook", dependencies=[Depends(rate_limit)])
async def salla_webhook(request: Request) -> Any:
    """Salla's own server call, on `WEBHOOK_EVENT` — registered PROGRAMMATICALLY at connect time
    (`salla_callback`'s own call to `client.register_webhook`, `webhooks.read_write` scope), not
    configured by hand in the Partners Portal any more. VERIFIED, NEVER TRUSTED BY ORIGIN —
    signature checked against the RAW body (see `verify_signature`'s own note on why re-parsed
    JSON cannot be used here), under the app-wide Webhook Secret from the Partners Portal
    (secrets-admin, not per merchant — that part IS still a one-time portal setting, since the
    secret itself has nowhere else to come from).

    CHEAP FOR EVERY EVENT THAT IS NOT THE ONE THAT MATTERS. Verifying a signature and parsing a
    small JSON body cost nothing; a coupon grant costs a phone lookup AND a round trip to
    billing-service. So every event still gets a durable, minimal log line (`record_event`, one
    store write — the receipt that we heard from this merchant at all, useful on its own for
    "my webhook stopped firing" support questions), but the EXPENSIVE path below only ever runs
    for `order.status.updated` at `completed` — every other event is acknowledged and dropped
    right there. The subscription we register is already scoped to just this one event, but the
    check here stays anyway as the real guarantee: a subscription record on Salla's own side is
    not something this route can verify at request time, so it never trusts the registration
    alone to be the only thing standing between a webhook call and a grant.
    """
    s = request.app.state.container_settings
    raw = await request.body()
    signature = request.headers.get("x-salla-signature", "")
    verified = verify_signature(s.SALLA_WEBHOOK_SECRET, raw, signature)

    try:
        payload = json.loads(raw or b"{}")
    except ValueError:
        payload = {}
    event = str(payload.get("event") or "")
    merchant_id = str(payload.get("merchant") or "")

    svc = request.app.state.container.salla
    tenant = ""
    if verified and merchant_id:
        conn = await svc.connection_for_merchant(merchant_id)
        tenant = conn.tenant if conn else ""
    await svc.record_event(merchant_id=merchant_id, event=event, tenant=tenant, verified=verified)

    if not verified:
        # STILL 200. Answering 4xx to an unverified call teaches an attacker probing this URL
        # which shape of forged signature gets further — the safe, uninformative answer is the
        # same "received" every genuine call gets, with nothing acted on behind it.
        return {"received": True}

    if event == APP_UNINSTALLED_EVENT:
        # A MERCHANT REMOVED THE APP FROM SALLA'S OWN SIDE — the connection is dead the moment
        # this arrives, not merely stale; waiting for the daily refresh scan to eventually
        # discover a dead refresh token (core/marketplaces/salla.py's own module note on why THAT
        # sweep exists) would leave a lifeless "مرتبط" badge showing for days. `tenant` empty here
        # means we never had a connection for this merchant in the first place (nothing to do).
        if tenant:
            await svc.disconnect(tenant)
            await request.app.state.auditor.record(
                "salla.disconnected", actor=f"salla:{merchant_id}", tenant=tenant,
                resource="salla_connection", ip=request.client.host if request.client else "")
        return {"received": True}

    if event != WEBHOOK_EVENT or not tenant:
        # NOT THE TARGET EVENT, OR A MERCHANT WE HAVE NO LINK FOR — either way, nothing more to
        # do. `tenant` is empty both for "this merchant never connected" and "signature verified
        # but merchant id missing from the payload"; both are answered identically.
        return {"received": True}

    order = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    status = order.get("status") if isinstance(order.get("status"), dict) else {}
    if str(status.get("slug") or "") != _TARGET_STATUS_SLUG:
        return {"received": True}

    order_id = str(order.get("id") or "")
    customer = order.get("customer") if isinstance(order.get("customer"), dict) else {}
    mobile = str(customer.get("mobile") or "").strip()
    if not order_id or not mobile:
        return {"received": True}

    # THE GRANT ITSELF — reuses core/coupons.py's engine exactly as the console's own form and
    # the till's external door do: same tier cap, same duplicate-order protection (`order_id`),
    # same per-app "already has a better coupon" guard. `general=True` because a real Salla order
    # names no specific app to discount — the whole point is "my supplier succeeded, give them
    # whatever they are eligible for right now, automatically, no configuration needed".
    coupons = request.app.state.container.coupons
    percent = await coupons.effective_cap(tenant)
    if percent > 0:
        att = await coupons.grant(
            granter_tenant=tenant, granter_operator_id=f"salla:{merchant_id}",
            phone=mobile, percent=percent, general=True,
            order_id=f"salla:{merchant_id}:{order_id}")
        await request.app.state.auditor.record(
            "coupon.grant_attempt", actor=f"salla:{merchant_id}", tenant=tenant,
            resource=f"coupon_attempt:{att.id}",
            ip=request.client.host if request.client else "")
    return {"received": True}
