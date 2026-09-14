"""Salla — infrastructure only. See `core/marketplaces/salla.py`'s own module docstring for the
full reasoning and the exact Salla docs each piece was read from; this file is the HTTP door.

TWO ROUTES NEED A TOKEN (`/staff/salla/install`, `/staff/salla/status`) AND TWO CANNOT
(`/salla/callback`, `/salla/webhook`) — same split `signup.py`'s own module docstring documents
for its two unauthenticated routes: Salla's own redirect and Salla's own server call arrive with
no Bearer token to check, so these two are rate-limited and self-contained instead, exactly like
signup's pair. NOT IN THE ACTION CATALOGUE either, for the identical reason signup's aren't.
"""
from __future__ import annotations

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
from app.core.marketplaces.salla import verify_signature

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


_CALLBACK_PAGE = """<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<title>ربط سلة</title></head><body style="font-family:system-ui;text-align:center;padding:48px">
<h1>{title}</h1><p>{message}</p></body></html>"""


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
        return HTMLResponse(_CALLBACK_PAGE.format(
            title="تعذّر الربط", message="تم إلغاء الربط أو رفضه من سلة. أغلق هذه الصفحة وحاول مرة أخرى."))
    tenant = oauth_state.tenant_for(s.PII_SALT, _STATE_PURPOSE, state)
    if not tenant:
        return HTMLResponse(_CALLBACK_PAGE.format(
            title="انتهت صلاحية الرابط",
            message="ابدأ الربط من جديد من لوحة تحكمك — هذا الرابط لم يعد صالحاً."), status_code=400)
    client = request.app.state.container.salla.client
    if not client.configured or not code:
        return HTMLResponse(_CALLBACK_PAGE.format(
            title="تعذّر الربط", message="لم يصل رمز صحيح من سلة."), status_code=400)

    tokens = await run_in_threadpool(client.exchange_code, code)
    if not tokens or not tokens.get("access_token"):
        return HTMLResponse(_CALLBACK_PAGE.format(
            title="تعذّر الربط", message="تعذّر إتمام الربط مع سلة. حاول مرة أخرى بعد قليل."),
            status_code=502)

    access_token = str(tokens.get("access_token") or "")
    info = await run_in_threadpool(client.user_info, access_token) or {}
    # Salla's own docs (docs.salla.dev/421118m0) do not put a merchant id on the TOKEN response —
    # it is read separately from /oauth2/user/info. `merchant`/`id` are read defensively (`or {}`
    # chains) since a real vendor response shape is trusted no further than what it actually sent.
    merchant = info.get("merchant") if isinstance(info.get("merchant"), dict) else info
    merchant_id = str((merchant or {}).get("id") or "")
    store_name = str((merchant or {}).get("name") or "")
    if not merchant_id:
        return HTMLResponse(_CALLBACK_PAGE.format(
            title="تعذّر الربط", message="لم نستطع التعرف على متجرك من سلة."), status_code=502)

    expires_at = int(time.time()) + int(tokens.get("expires") or 0)
    svc = request.app.state.container.salla
    await svc.save_connection(
        tenant=tenant, merchant_id=merchant_id, store_name=store_name,
        access_token=access_token, refresh_token=str(tokens.get("refresh_token") or ""),
        expires_at=expires_at, scope=str(tokens.get("scope") or ""))

    await request.app.state.auditor.record(
        "salla.connected", actor=tenant, tenant=tenant, resource=f"salla_merchant:{merchant_id}",
        ip=request.client.host if request.client else "")

    return HTMLResponse(_CALLBACK_PAGE.format(
        title="تم الربط بنجاح",
        message=f"متجرك «{store_name or merchant_id}» أصبح مرتبطاً بحسابك عندنا. أغلق هذه الصفحة وارجع للوحة تحكمك."))


@router.post("/salla/webhook", dependencies=[Depends(rate_limit)])
async def salla_webhook(request: Request) -> Any:
    """Salla's own server call, on every subscribed event this app's Partners Portal settings
    declare. VERIFIED, NEVER TRUSTED BY ORIGIN — signature checked against the RAW body (see
    `verify_signature`'s own note on why re-parsed JSON cannot be used here), under the app-wide
    Webhook Secret from the Partners Portal (secrets-admin, not per merchant).

    ACKS FAST. Salla retries a slow or non-2xx response; the actual business action a real order
    triggers is a deliberately separate, later decision (module docstring) — for now this only
    verifies and durably logs the event, which is itself the whole point of standing this up before
    that decision is made: the connection and the intake are both real and tested today.
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
    return {"received": True}
