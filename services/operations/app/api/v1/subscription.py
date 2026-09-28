"""The owner's subscribe path — ours, so a product rule has somewhere to live.

    POST /api/v1/subscription     subscribe this establishment to a plan

WHY NOT CALL BILLING DIRECTLY, which is what happened before this file: because there was then no
moment that belonged to us. billing-service is the platform's, shared by every product built on
it, and it must never learn that ours requires WhatsApp before it will take money.

So this is thin on purpose — one question, then their route, then their answer. It holds no plan,
prices nothing, and stores no subscription. Everything about money stays where it already works.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.auth import require_user
from app.api.authz import require_capability
from app.config import get_settings
from app.core import apps as app_catalogue
from app.core.apps import requires_whatsapp_connection
from app.core.subscribe import (
    BundleItem, granted_keys, held_keys, is_base, may_add, may_add_bundle, may_subscribe,
)

from app.api.ratelimit import rate_limit
from app.api.subscribed import no_subscription_needed, subscribed_write

#: EXACTLY WHAT billing KNOWS (platform/.../billing_service.py `_INTERVAL`). It reads an unknown
#: word as a month rather than refusing it, so the refusal has to happen on this side.
BILLING_INTERVALS = ("month", "year", "once")

# The parent router in __init__ already carries /api/v1.
router = APIRouter(prefix="/subscription", tags=["subscription"])

# THE OWNER'S OWN CAPABILITY, not an operator's. He is buying his own subscription, and requiring
# a platform capability here would mean nobody could subscribe without us.
_OWNER = require_capability("billing.self")


class SubscribeIn(BaseModel):
    plan_id: str = Field(min_length=1, max_length=64)
    # `once` for a one-time purchase, `month` otherwise. Passed through rather than inferred: the
    # plan's PRICE carries an interval but the SUBSCRIPTION takes its own, and defaulting it here
    # would repeat the bug that made a pack renew monthly.
    interval: str = Field(default="month", max_length=16)
    # WHAT THE GATEWAY'S FORM HANDED THE BROWSER — a single-use reference to a card we never see.
    # Absent on a trial, required on anything paid: see may_subscribe.
    payment_token: str = Field(default="", max_length=256)


class CheckoutLinkIn(BaseModel):
    plan_id: str = Field(min_length=1, max_length=64)
    interval: str = Field(default="month", max_length=16)
    idempotency_key: str = Field(default="", max_length=128)


class CheckoutItemIn(BaseModel):
    plan_id: str = Field(min_length=1, max_length=64)
    interval: str = Field(default="month", max_length=16)


class CheckoutIn(BaseModel):
    # 20 IS A SANITY CAP, NOT A PRODUCT LIMIT — no real cart approaches this; it exists so a
    # malformed or abusive request cannot make this route fan out into dozens of billing-service
    # calls in one request.
    items: list[CheckoutItemIn] = Field(min_length=1, max_length=20)
    payment_token: str = Field(default="", max_length=256)
    # THE CONSOLE'S OWN RETRY GUARD — a double-tap or a resent network request replays the SAME
    # invoice instead of charging twice, exactly like `/api/v1/field/visits`'s own key. Optional:
    # an empty key still checks out fine, it simply cannot be safely retried.
    idempotency_key: str = Field(default="", max_length=128)


def _tenant(p) -> str:
    return getattr(p, "tenant", "") or ""


@router.get("/payment", dependencies=[Depends(rate_limit)])
async def payment_state(request: Request, principal=Depends(_OWNER)) -> dict:
    """Is there a live way to pay — checked at the one place that actually knows, never guessed.

    NO PUBLISHABLE KEY ANY MORE (2026-09-24) — that concept was Moyasar-specific (a token the
    BROWSER mints directly against the gateway) and never matched TuwaiqPay, the gateway actually
    live here (hosted-checkout-link only, no browser-side tokenisation at all — see
    `subscribeFlow.ts`'s own header note on why the card-form path was retired). The real question
    a screen needs answered is simpler and gateway-agnostic: "is billing configured to sell at
    all" — `billing_plans.driver` is exactly that ("null" only when BILLING_PLANS_DRIVER itself is
    unset, the same posture `checkout`/`subscribe` already refuse on with BILLING_NOT_CONFIGURED).
    Which specific gateway is active, and whether IT is configured, is billing-service's own
    business — a checkout-link attempt against an unconfigured gateway still answers 503 honestly.
    """
    c = request.app.state.container
    enabled = getattr(c.billing_plans, "driver", "null") != "null"
    return {"enabled": enabled,
            "message": "" if enabled else
                       "الدفع الإلكتروني غير متاح مؤقتاً. نعتذر — نعمل على تفعيله، "
                       "وحتى ذلك الحين تواصل معنا لتفعيل باقتك."}


@router.get("/apps", dependencies=[Depends(rate_limit)])
async def apps(request: Request, principal=Depends(_OWNER)) -> dict:
    """What has this shop bought — one call, for every lock in the console.

    UNTIL THIS EXISTED, no screen could answer it. The console draws a lock from a CAPABILITY, and
    an owner holds every capability on every plan — so the lock never appeared for the one person
    who would have paid to remove it. The only screen that knew better was «محلّي», by reading a
    key that the insights dashboard happened to return with its numbers.

    IT DECIDES NOTHING. The gates live in the services that own the acts and fail closed there; a
    tampered answer here draws a button that the service behind it still refuses. Which is exactly
    why it does NOT fail closed itself: a billing outage must not tell every paying shop at once
    that it has not paid. `checked: false` says what happened, and the screen offers to retry.
    """
    c = request.app.state.container
    tenant = _tenant(principal)
    held, checked = await c.apps.held(tenant)
    # THE BASE ITSELF, not a flag saying one exists. `subscriptions` carries the plan and the
    # renewal date, so the screen can say «يتجدّد في …» — the first thing an owner opening this
    # page wants, and something an entitlement check could never answer.
    rows = await c.billing_plans.subscriptions(tenant)
    # SELF-HEALING, NOT A SWEEP (owner's own instruction, 2026-09-11) — a dependent app
    # (برنامج النقاط/التقييم/فرصي/الحملات) left orphaned by its prerequisite (تسجيل زيارة/
    # الحجوزات) being cancelled through ANY path is caught right here, on the read every screen
    # already makes, rather than by a new recurring job scanning every tenant. Failures are
    # swallowed by `cancel()` itself (returns `False`, never raises) — an unreachable billing-
    # service must not break the ordinary read this rides along on; the orphan is caught again
    # the next time this tenant's own apps are read.
    if rows and checked:
        for sub_id in app_catalogue.orphaned_dependents(rows, held):
            await c.billing_plans.cancel(tenant=tenant, sub_id=sub_id)
    # EVERY ROW, NOT THE BASE'S ALONE. This list arrived whole and left with one date in it: the
    # apps a shop pays for renew on their own days — the day each was bought — and no screen said
    # so, so the second and third charges of the month arrived unannounced.
    renewals = app_catalogue.renewals_by_key(rows)
    base = None
    if rows:
        for row in rows:
            if is_base(row.get("limits_snapshot")):
                base = {"plan_id": row.get("plan_id", ""), "status": row.get("status", ""),
                        "renews_at": row.get("current_period_end", 0)}
                break
    return app_catalogue.public(held, checked, base, renewals)


@router.get("/apps/static-features", dependencies=[Depends(rate_limit)])
async def apps_static_features(principal=Depends(require_user)) -> dict:
    """«ايش فيه» — every operations-owned app's own catalog, the ONE gap the other five services'
    `.../features` routes never had: `/apps` just above answers a TENANT's own held apps, and
    there was no standalone, tenant-free read of these apps' feature lists at all —
    bookings/loyalty/campaigns/insights/whatsapp-assistant each got a real `.../features` route,
    but operations only ever spread these constants inline into `public()`'s per-shop answer,
    which needs `held`/`checked` neither of which a caller BROWSING an app they do not yet own
    can ever supply (the same read a store card's own "التفاصيل" makes, before any purchase).

    ORIGINALLY THREE (تسجيل زيارة/جهات الاتصال/التقييم), added for the admin panel alone (no
    shop, no tenant, could ever ask `/apps`) — found live, a SECOND, wider gap: the shop-owner-
    facing store shelf itself (console `AppTile`/mobile `apps_store_screen.dart`) had the exact
    same problem for every OTHER operations-owned app with no `featuresAction` of its own
    (المساعد الذكي عبر واتساب's siblings تبادل منافع/الاستضافة المهنية/خدمات متنقلة/ولاء
    الشركاء): `Owned.apps[].features` only ever answers for an app already bought, so a shop
    deciding WHETHER to buy one saw an empty features section — the one moment a real feature
    list matters most. All seven now ride the same tenant-free read.

    Same posture as every sibling route: `require_user` only, no capability, no subscription
    check — the content is identical for every caller regardless of tenant, same as the constants
    it reads.
    """
    return {
        "visit": list(app_catalogue.VISIT_FEATURES),
        "contacts": list(app_catalogue.CONTACTS_FEATURES),
        "rating": list(app_catalogue.RATING_FEATURES),
        "mobile_requests": list(app_catalogue.MOBILE_REQUESTS_FEATURES),
        "coworking": list(app_catalogue.COWORKING_FEATURES),
        "coupons": list(app_catalogue.COUPONS_FEATURES),
        "mutual_benefit": list(app_catalogue.MUTUAL_BENEFIT_FEATURES),
        "referrals": list(app_catalogue.REFERRALS_FEATURES),
    }


@router.get("/apps/visibility-overrides", dependencies=[Depends(rate_limit)])
async def apps_visibility_overrides(request: Request, principal=Depends(require_user)) -> dict:
    """Which otherwise-hidden (`listed: false`) apps THIS shop specifically has been shown — see
    `core/app_visibility.py`'s own module docstring for the full design. `require_user` only, same
    posture as `apps_static_features` above — any staff role browsing the store may ask this, not
    only the owner. Tenant comes ONLY from `_tenant(principal)`, never a query param — the read
    side of this mechanism can never be asked about a tenant other than the caller's own."""
    c = request.app.state.container
    keys = await c.app_visibility.visible_keys_for_tenant(_tenant(principal))
    return {"visible_keys": keys}


@router.post("/renew-now", dependencies=[Depends(rate_limit)])
async def renew_now(request: Request, principal=Depends(_OWNER)) -> JSONResponse:
    """Force EARLY renewal for this shop's WHOLE group of together-billed subscriptions, ahead of
    the automatic date, and hand back real pay-links for the invoices it just created.

    NEVER ONE APP ALONE (the owner's own call, 2026-09-22): as long as an app is not cancelled it
    stays in the shop's one shared monthly cycle, so "renew early" means the whole group, exactly
    like the real sweep would bill it on the actual date — never a single subscription pulled out
    of sync with the rest. See `adapters/renewal_provider.py::RenewalProvider.renew_now`'s own
    docstring for the group-selection rule and why this still cannot mint ONE combined invoice.

    THE SAME REAL MECHANISM THE WHATSAPP RENEWAL FLOW ALREADY USES (`services/whatsapp-assistant`'s
    `upcoming_renewal_trigger.py`), reused unchanged here rather than a second copy.

    OWNERSHIP IS THE PROVIDER'S OWN JOB (see its own docstring) — this route adds nothing on top.
    """
    c = request.app.state.container
    tenant = _tenant(principal)
    if not tenant:
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"error": "NO_TENANT"})
    out = await c.renewal_provider.renew_now(tenant=tenant)
    await request.app.state.auditor.record(
        "subscription.renewed_early" if out.get("ok") else "subscription.renew_now_refused",
        actor=principal.subject, tenant=tenant, resource=f"tenant:{tenant}",
        ip=request.client.host if request.client else "",
        metadata={} if out.get("ok") else {"reason": str(out.get("reason", ""))})
    if not out.get("ok"):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"error": "RENEW_FAILED",
                            "message": out.get("reason", "تعذّر تجديد الاشتراكات الآن.")})
    return JSONResponse(status_code=status.HTTP_200_OK,
                        content={"ok": True, "pay_urls": out.get("refs", [])})


@router.post("", dependencies=[Depends(no_subscription_needed), Depends(rate_limit)])
async def subscribe(request: Request, body: SubscribeIn,
                    principal=Depends(_OWNER)) -> JSONResponse:
    """Subscribe, once the one rule that is ours has been satisfied."""
    c = request.app.state.container
    tenant = _tenant(principal)
    if not tenant:
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN,
                            content={"error": "NO_TENANT"})

    # ── WHAT HE ALREADY HAS, BEFORE ANYTHING IS BOUGHT ───────────────────────────────────────
    # Two rules that billing cannot hold, because neither is true of every product built on the
    # platform: one base per establishment, and an app bought once (core/subscribe.py says what
    # each defect costs — a second base makes `messages.monthly` -1 + -1 = -2).
    #
    # SKIPPED, NOT GUESSED, WHEN EITHER READ FAILS. Both are None when they could not be read;
    # refusing then would block a legitimate purchase during an outage the shop did not cause, and
    # inventing a `False` would let the impossible pair through. The rules are advisory on a bad
    # day and exact on every other — and the entitlement gates in the services still hold either
    # way, because they ask billing at the act.
    #
    # ONE READ, TWO ANSWERS. `subscriptions` carries each row's own `limits_snapshot`, so «has a
    # base» and «already owns this app» both come out of it — where they used to be a `feature.base`
    # flag plus a five-key entitlement sweep, which was two reads that could disagree.
    plan_limits = await c.billing_plans.limits(body.plan_id)
    rows = await c.billing_plans.subscriptions(tenant)
    if plan_limits is None or rows is None:
        # ── IT USED TO FAIL OPEN, AND ON THIS PATH THAT MEANS TAKING MONEY (ز-2) ──────────────
        #
        # The reasoning was «refusing during an outage would block a purchase the shop did not
        # break», and the audit row below was the whole of the mitigation: the sale went through
        # and somebody would find the duplicate later. But the two errors are not comparable.
        #
        # Failing OPEN charges a card for a second base — a real riyal amount, taken from a real
        # shop, recoverable only by noticing it, explaining it and refunding it. Failing CLOSED
        # costs him one press, on a screen that tells him to try again in a moment. The reversible
        # one is the one to choose, and it is not close.
        #
        # STILL RECORDED, because «we could not check» is a fact about OUR availability, and a
        # cluster of these rows is how a billing outage is seen from the product side.
        await request.app.state.auditor.record(
            "subscription.gate_unreadable", actor=getattr(principal, "subject", ""), tenant=tenant,
            resource=f"plan:{body.plan_id}",
            ip=request.client.host if request.client else "")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "SUBSCRIPTION_UNAVAILABLE",
                     "message": "تعذّر التحقق من اشتراكك الحالي. أعد المحاولة بعد قليل — "
                                "لم يُخصم شيء."})
    if plan_limits is not None and rows is not None:
        # الأساس RETIRED (2026-09-10) — `may_add` no longer takes `has_base`/
        # `standalone_plans_enabled`; every app stands on its own, gated only by
        # `plan.requires_any` (checked inside `may_add` itself) and duplicate-purchase.
        addition = may_add(plan_limits=plan_limits, held=held_keys(rows))
        if not addition.allowed:
            # AUDITED LIKE EVERY OTHER REFUSAL BELOW IT IN THIS ROUTE (fixed 2026-09-12, a real
            # gap a QA audit found) — `gate_unreadable`, `refused` (payment) and `created` all
            # already record; a duplicate-purchase attempt is the same kind of fact and was the
            # one refusal in this file support could not see.
            await request.app.state.auditor.record(
                "subscription.already_subscribed", actor=getattr(principal, "subject", ""),
                tenant=tenant, resource=f"plan:{body.plan_id}",
                ip=request.client.host if request.client else "")
            return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                                content={"error": "ALREADY_SUBSCRIBED",
                                         "message": addition.reason})

    # THE PLAN'S TRIAL DECIDES WHETHER THE RULE APPLIES, so it is read before the check rather
    # than assumed. A plan with a trial is an evaluation and needs no connection.
    trial_days = await c.billing_plans.trial_days(body.plan_id)
    connected = await c.connections.connected(tenant)

    # A FREE PLAN NEEDS NO TOKEN EITHER — "جهات الاتصال" (plans.json) is the first of these,
    # amount 0, and `may_subscribe`'s own "no token, no plan" rule used to refuse it unconditionally,
    # exactly as it should refuse a paid plan with no way to charge it. `amount_minor` asks the
    # SAME live price billing would actually charge; `None` means "could not read" and must NOT be
    # read as free — an outage must never let a paid plan through with no payment token.
    price_minor = await c.billing_plans.amount_minor(body.plan_id)
    free = price_minor == 0

    # PAID MEANS A TOKEN WE CAN ACTUALLY CHARGE, OR A PLAN THAT CHARGES NOTHING AT ALL. An empty
    # token on a PAID plan is not "pay later"; it is the press of a button with no money behind
    # it, and the plan must not start on it — `free` is the one exception, decided by price, not
    # by the caller's own claim.
    decision = may_subscribe(
        connected=connected, trial_days=trial_days, paid=bool(body.payment_token) or free,
        requires_connection=requires_whatsapp_connection(granted_keys(plan_limits)))
    if not decision.allowed:
        # RETURNED, NEVER RAISED. The platform's error handler strips an HTTPException's detail,
        # so a raised refusal arrives as a bare status code and the sentence telling him what to
        # do — the only useful part — is thrown away.
        await request.app.state.auditor.record(
            "subscription.whatsapp_connection_required" if decision.redirect_screen
            else "subscription.refused",
            actor=principal.subject, tenant=tenant, resource=f"plan:{body.plan_id}",
            ip=request.client.host if request.client else "")
        if decision.redirect_screen:
            # A DIFFERENT REFUSAL THAN "NOT PAID" — 409, not 402: nothing is wrong with his
            # payment, the plan itself cannot be delivered yet. `redirect_screen` lets the
            # console jump straight to the connect screen instead of a dead-end error toast.
            return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                                content={"error": "WHATSAPP_CONNECTION_REQUIRED",
                                         "message": decision.reason,
                                         "redirect_screen": decision.redirect_screen})
        return JSONResponse(status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            content={"error": "PAYMENT_REQUIRED",
                                     "message": decision.reason})

    # ── THE INTERVAL IS CHECKED HERE, BECAUSE NOTHING DOWNSTREAM CHECKS IT (ز-1) ──────────────
    #
    # billing keeps `{"month": 30d, "year": 365d, "once": 0}` and reads it as
    # `_INTERVAL.get(interval, _INTERVAL["month"])` — so a word it does not know is not refused,
    # it becomes a MONTH. The field arrives from the request with nothing but a length limit, so
    # «forever», «day» and a typo all buy a monthly subscription nobody asked for.
    #
    # AND `once` ON A RECURRING PLAN IS THE EXPENSIVE ONE. It sets the period end to the moment of
    # purchase, so the plan never comes round to be charged again — one payment, and the shop keeps
    # what it is holding. A one-time interval belongs to the rows that are sold once: a pack, never
    # a base. The base is recognised the same way the price list recognises it, by carrying the
    # message meter (ci/check_plans_shape.py) — read off the plan, never guessed from its name.
    if body.interval not in BILLING_INTERVALS:
        # AUDITED, SAME AS EVERY OTHER REFUSAL IN THIS ROUTE (fixed 2026-09-12, a real gap a QA
        # audit found) — a request sending an interval billing does not know is exactly the
        # integration fault support needs to see, and it went unrecorded while every neighbouring
        # refusal already was.
        await request.app.state.auditor.record(
            "subscription.bad_interval", actor=getattr(principal, "subject", ""), tenant=tenant,
            resource=f"plan:{body.plan_id}", ip=request.client.host if request.client else "")
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={"error": "BAD_INTERVAL",
                                     "message": "مدة الاشتراك غير صحيحة."})
    if body.interval == "once" and is_base(plan_limits):
        await request.app.state.auditor.record(
            "subscription.bad_interval", actor=getattr(principal, "subject", ""), tenant=tenant,
            resource=f"plan:{body.plan_id}", ip=request.client.host if request.client else "")
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={"error": "BAD_INTERVAL",
                                     "message": "هذه الباقة تُجدَّد شهرياً ولا تُشترى مرة واحدة."})

    # A FREE APP IS SUBSCRIBED ONCE, NOT MONTHLY, REGARDLESS OF WHAT THE CALLER SENT. `once`
    # gives `period_end = 0`, which the resolver reads as "never lapses" and the renewal sweep
    # skips outright — so a free-forever standalone app never re-cycles through a pointless
    # SAR 0 invoice every month. Never for a base row (refused just above, and a base is never
    # free): this only ever touches an app, and only a free one.
    interval_overridden = free and not is_base(plan_limits) and body.interval != "once"
    interval = "once" if free and not is_base(plan_limits) else body.interval

    status_code, out = await c.billing_plans.subscribe(
        tenant=tenant, plan_id=body.plan_id, interval=interval,
        payment_token=body.payment_token)
    if status_code >= 400:
        # BILLING'S REFUSAL IS BILLING'S. We do not translate it into a sentence of our own — an
        # invented explanation for somebody else's decision is how support ends up answering for a
        # rule that does not exist.
        return JSONResponse(status_code=status_code,
                            content={"error": "BILLING_REFUSED", "detail": out})

    await request.app.state.auditor.record(
        "subscription.created", actor=principal.subject, tenant=tenant,
        resource=f"plan:{body.plan_id}", ip=request.client.host if request.client else "")
    # WHAT IS STILL OWED, ALONGSIDE THE RECEIPT. He may subscribe unconnected — see
    # core/subscribe.py for why that gate was removed — but he must never learn it from the
    # absence of messages a week later. The notice travels with the success, not instead of it.
    if decision.notice:
        out = {**out, "notice": decision.notice}
    if interval_overridden:
        out = {**out, "interval": interval}
    return JSONResponse(status_code=status.HTTP_201_CREATED, content=out)


@router.post("/checkout-link", dependencies=[Depends(no_subscription_needed), Depends(rate_limit)])
async def checkout_link(request: Request, body: CheckoutLinkIn,
                        principal=Depends(_OWNER)) -> JSONResponse:
    """Start a NEW paid subscription with a real, hosted pay-link — the gateway-agnostic
    replacement for the old browser-tokenised card form (`payment.ts`/`CardForm.tsx`, retired
    2026-09-24, the same day billing-service's own `subscribe()` was fixed for a real hole: it
    used to activate a subscription the instant ANY token arrived, never checking whether a charge
    actually succeeded — base-services v0.25.29).

    SAME PRODUCT RULES AS `subscribe()` ABOVE, MINUS THE MONEY QUESTION — duplicate-purchase
    (`may_add`) and the WhatsApp-before-paid ordering (`may_subscribe`'s `requires_connection`
    branch) are both still ours to enforce; billing must never learn either. `paid=True` is passed
    UNCONDITIONALLY here, not from a client-claimed token: `may_subscribe`'s "no plan without a
    payment" refusal existed to stop an UNVERIFIED claim from activating a subscription outright,
    and this path makes no such claim at all — it hands back a link and billing itself refuses to
    activate anything until the SAME payment settles through the real webhook/reconcile seam every
    invoice already goes through (see `checkout_link`'s own docstring on `HttpPlans`).
    """
    c = request.app.state.container
    tenant = _tenant(principal)
    if not tenant:
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"error": "NO_TENANT"})

    plan_limits = await c.billing_plans.limits(body.plan_id)
    rows = await c.billing_plans.subscriptions(tenant)
    if plan_limits is None or rows is None:
        await request.app.state.auditor.record(
            "subscription.gate_unreadable", actor=getattr(principal, "subject", ""), tenant=tenant,
            resource=f"plan:{body.plan_id}", ip=request.client.host if request.client else "")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "SUBSCRIPTION_UNAVAILABLE",
                     "message": "تعذّر التحقق من اشتراكك الحالي. أعد المحاولة بعد قليل — "
                                "لم يُخصم شيء."})
    addition = may_add(plan_limits=plan_limits, held=held_keys(rows))
    if not addition.allowed:
        await request.app.state.auditor.record(
            "subscription.already_subscribed", actor=getattr(principal, "subject", ""),
            tenant=tenant, resource=f"plan:{body.plan_id}",
            ip=request.client.host if request.client else "")
        return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                            content={"error": "ALREADY_SUBSCRIBED", "message": addition.reason})

    trial_days = await c.billing_plans.trial_days(body.plan_id)
    connected = await c.connections.connected(tenant)
    decision = may_subscribe(
        connected=connected, trial_days=trial_days, paid=True,
        requires_connection=requires_whatsapp_connection(granted_keys(plan_limits)))
    if not decision.allowed:
        # ONLY THE `requires_connection` BRANCH CAN EVER REFUSE HERE — `paid=True` short-circuits
        # every other one (see this route's own docstring). Kept as the real `Decision`, never
        # special-cased, so a change to `may_subscribe` cannot silently stop applying here too.
        await request.app.state.auditor.record(
            "subscription.whatsapp_connection_required", actor=principal.subject, tenant=tenant,
            resource=f"plan:{body.plan_id}", ip=request.client.host if request.client else "")
        return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                            content={"error": "WHATSAPP_CONNECTION_REQUIRED",
                                     "message": decision.reason,
                                     "redirect_screen": decision.redirect_screen})

    if body.interval not in BILLING_INTERVALS:
        await request.app.state.auditor.record(
            "subscription.bad_interval", actor=getattr(principal, "subject", ""), tenant=tenant,
            resource=f"plan:{body.plan_id}", ip=request.client.host if request.client else "")
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={"error": "BAD_INTERVAL", "message": "مدة الاشتراك غير صحيحة."})
    if body.interval == "once" and is_base(plan_limits):
        await request.app.state.auditor.record(
            "subscription.bad_interval", actor=getattr(principal, "subject", ""), tenant=tenant,
            resource=f"plan:{body.plan_id}", ip=request.client.host if request.client else "")
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={"error": "BAD_INTERVAL",
                                     "message": "هذه الباقة تُجدَّد شهرياً ولا تُشترى مرة واحدة."})

    status_code, out = await c.billing_plans.checkout_link(
        tenant=tenant, plan_id=body.plan_id, interval=body.interval,
        idempotency_key=body.idempotency_key)
    if status_code >= 400:
        return JSONResponse(status_code=status_code,
                            content={"error": "BILLING_REFUSED", "detail": out})
    await request.app.state.auditor.record(
        "subscription.checkout_link_created", actor=principal.subject, tenant=tenant,
        resource=f"plan:{body.plan_id}", ip=request.client.host if request.client else "")
    return JSONResponse(status_code=status.HTTP_201_CREATED, content=out)


@router.post("/checkout", dependencies=[Depends(no_subscription_needed), Depends(rate_limit)])
async def checkout(request: Request, body: CheckoutIn, principal=Depends(_OWNER)) -> JSONResponse:
    """Buy several apps together, one cart, ONE INVOICE, one charge — the answer to a dependency
    that `may_add`'s single-purchase rule could never satisfy on its own: نقاط الولاء needs تسجيل زيارة/
    الحجوزات first, and until this route existed a shop holding neither had to complete a whole
    separate purchase for one of them before it could even attempt نقاط الولاء.

    A REAL ATOMIC CHECKOUT, NOT A LOOP OF SINGLE PURCHASES — billing-service shipped
    `POST /internal/billing/subscriptions/checkout` (base-services v0.25.25, at our own
    escalation) for exactly this: validate-all-first, then ONE invoice and ONE charge for the
    whole cart, N subscription rows. This route's own job stays the same as ever — the product
    rule billing must never learn (`may_add_bundle`, WhatsApp-connection gating) — but the
    EXECUTION is now billing's own atomic primitive instead of a per-item loop we had to guard by
    refusing more than one paid item at a time. That restriction is gone: a cart may hold as many
    genuinely-paid apps as it likes, because there is only ever one charge attempt against the
    token either way.

    ALL VALIDATION STILL HAPPENS BEFORE ANY CHARGE — the bundle rule, then every item's own
    `may_subscribe` gate (connection/trial/interval) — for the exact same reason as before: a cart
    that will fail its third item must never even reach billing for its first two. What changed is
    what happens after: one call, one result, no partial state to report.
    """
    c = request.app.state.container
    tenant = _tenant(principal)
    if not tenant:
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"error": "NO_TENANT"})

    plan_ids = [i.plan_id for i in body.items]

    rows = await c.billing_plans.subscriptions(tenant)
    if rows is None:
        # SAME POSTURE AS THE SINGLE-PURCHASE ROUTE ABOVE (ز-2): failing OPEN here would mean
        # validating a cart against an unknown `held` set and possibly charging for a duplicate —
        # a real riyal amount, recoverable only by noticing it. Failing closed costs one retry.
        await request.app.state.auditor.record(
            "subscription.gate_unreadable", actor=getattr(principal, "subject", ""), tenant=tenant,
            resource="checkout", ip=request.client.host if request.client else "")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "SUBSCRIPTION_UNAVAILABLE",
                     "message": "تعذّر التحقق من اشتراكك الحالي. أعد المحاولة بعد قليل — "
                                "لم يُخصم شيء."})
    held = held_keys(rows)

    # EVERY PLAN READ CONCURRENTLY — the same single `/plans` read each individual `limits()` call
    # already makes under the hood; fetching them one at a time here would just serialise N
    # network round trips this route does not need to serialise.
    limits_list = await asyncio.gather(*(c.billing_plans.limits(pid) for pid in plan_ids))

    if any(lim is None for lim in limits_list):
        # SAME POSTURE AS THE SINGLE-PURCHASE ROUTE ABOVE — an unreadable PLAN (not just an
        # unreadable subscriptions list) is an outage there (503), never a validation refusal
        # (409). `may_add_bundle`'s own None-guard exists for its unit tests and stays as a
        # defensive second layer; the route itself must not let a checkout reach it this way.
        await request.app.state.auditor.record(
            "subscription.gate_unreadable", actor=getattr(principal, "subject", ""), tenant=tenant,
            resource="checkout", ip=request.client.host if request.client else "")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "SUBSCRIPTION_UNAVAILABLE",
                     "message": "تعذّر قراءة أحد التطبيقات بالسلة. أعد المحاولة بعد قليل — "
                                "لم يُخصم شيء."})

    bundle_decision = may_add_bundle(
        items=[BundleItem(plan_id=pid, plan_limits=lim) for pid, lim in zip(plan_ids, limits_list)],
        held=held)
    if not bundle_decision.allowed:
        await request.app.state.auditor.record(
            "subscription.checkout_refused", actor=getattr(principal, "subject", ""), tenant=tenant,
            resource=f"plan:{bundle_decision.failed_plan_id}" if bundle_decision.failed_plan_id
                     else "checkout",
            ip=request.client.host if request.client else "")
        return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                            content={"error": "CHECKOUT_REFUSED",
                                     "message": bundle_decision.reason,
                                     "plan_id": bundle_decision.failed_plan_id})

    # ── PER-ITEM may_subscribe — connection/trial/interval, same rule as a single purchase ──────
    connected = await c.connections.connected(tenant)
    checks: list[tuple[CheckoutItemIn, dict, bool, str]] = []  # (item, limits, free, notice)
    for checkout_item, limits in zip(body.items, limits_list):
        if checkout_item.interval not in BILLING_INTERVALS:
            await request.app.state.auditor.record(
                "subscription.bad_interval", actor=getattr(principal, "subject", ""), tenant=tenant,
                resource=f"plan:{checkout_item.plan_id}",
                ip=request.client.host if request.client else "")
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                                content={"error": "BAD_INTERVAL",
                                         "message": "مدة الاشتراك غير صحيحة.",
                                         "plan_id": checkout_item.plan_id})
        if checkout_item.interval == "once" and is_base(limits):
            await request.app.state.auditor.record(
                "subscription.bad_interval", actor=getattr(principal, "subject", ""), tenant=tenant,
                resource=f"plan:{checkout_item.plan_id}",
                ip=request.client.host if request.client else "")
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                                content={"error": "BAD_INTERVAL",
                                         "message": "هذه الباقة تُجدَّد شهرياً ولا تُشترى مرة واحدة.",
                                         "plan_id": checkout_item.plan_id})

        trial_days = await c.billing_plans.trial_days(checkout_item.plan_id)
        price_minor = await c.billing_plans.amount_minor(checkout_item.plan_id)
        free = price_minor == 0

        item_decision = may_subscribe(
            connected=connected, trial_days=trial_days,
            paid=bool(body.payment_token) or free,
            requires_connection=requires_whatsapp_connection(granted_keys(limits)))
        if not item_decision.allowed:
            await request.app.state.auditor.record(
                "subscription.whatsapp_connection_required" if item_decision.redirect_screen
                else "subscription.refused",
                actor=principal.subject, tenant=tenant, resource=f"plan:{checkout_item.plan_id}",
                ip=request.client.host if request.client else "")
            if item_decision.redirect_screen:
                return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                                    content={"error": "WHATSAPP_CONNECTION_REQUIRED",
                                             "message": item_decision.reason,
                                             "redirect_screen": item_decision.redirect_screen,
                                             "plan_id": checkout_item.plan_id})
            return JSONResponse(status_code=status.HTTP_402_PAYMENT_REQUIRED,
                                content={"error": "PAYMENT_REQUIRED",
                                         "message": item_decision.reason,
                                         "plan_id": checkout_item.plan_id})

        checks.append((checkout_item, limits, free, item_decision.notice))

    # ── EXECUTE — ONE atomic call: one invoice, one charge, for the whole cart ──────────────────
    checkout_items = [
        {"plan_id": checkout_item.plan_id,
         "interval": "once" if free and not is_base(limits) else checkout_item.interval}
        for checkout_item, limits, free, _notice in checks
    ]
    status_code, out = await c.billing_plans.checkout(
        tenant=tenant, items=checkout_items, payment_token=body.payment_token,
        idempotency_key=body.idempotency_key)
    ok = status_code < 400 and isinstance(out, dict)
    await request.app.state.auditor.record(
        "subscription.checkout_completed" if ok else "subscription.checkout_refused",
        actor=principal.subject, tenant=tenant,
        resource=f"invoice:{out.get('invoice_id') or '-'}" if ok else "checkout",
        ip=request.client.host if request.client else "",
        metadata={} if ok else {"detail": out})

    if not ok:
        message = (out.get("message") or out.get("detail")) if isinstance(out, dict) else None
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY if status_code >= 500
            else status.HTTP_409_CONFLICT,
            content={"error": "CHECKOUT_FAILED",
                     "message": message or "تعذّر إتمام الشراء. لم يُخصم شيء.",
                     "detail": out})

    content: dict = dict(out)
    # ONE NOTICE, NOT N — every item's own `may_subscribe` decision was checked against the SAME
    # `connected` answer, so at most one distinct notice can ever appear across the whole cart;
    # the first non-empty one (if any) is the one sentence the shop reads.
    notice = next((n for _i, _l, _f, n in checks if n), "")
    if notice:
        content["notice"] = notice
    return JSONResponse(status_code=status.HTTP_200_OK, content=content)


@router.post("/checkout/link", dependencies=[Depends(no_subscription_needed), Depends(rate_limit)])
async def checkout_cart_link(request: Request, body: CheckoutIn,
                             principal=Depends(_OWNER)) -> JSONResponse:
    """`checkout()`'s own sibling for a cart that pays by hosted link rather than a client-claimed
    token (2026-09-24, replacing the browser-tokenised cart checkout the launcher's own
    `useAppBilling.ts` used to run) — ONE real pay-link for the whole cart; every subscription is
    created `incomplete` and they all activate together once that ONE invoice settles, same
    webhook/reconcile seam as every other payment on this platform.

    SAME VALIDATION AS `checkout()`, MINUS THE MONEY QUESTION — `may_add_bundle` and every item's
    own `may_subscribe` (connection/trial/interval) still run BEFORE anything reaches billing; only
    what happens after differs. `paid=True` unconditionally, same reasoning as `checkout_link`'s
    own docstring above: this call makes no claim about a completed charge, it hands back a link
    and billing itself gates activation on the SAME payment actually settling.
    """
    c = request.app.state.container
    tenant = _tenant(principal)
    if not tenant:
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"error": "NO_TENANT"})

    plan_ids = [i.plan_id for i in body.items]

    rows = await c.billing_plans.subscriptions(tenant)
    if rows is None:
        await request.app.state.auditor.record(
            "subscription.gate_unreadable", actor=getattr(principal, "subject", ""), tenant=tenant,
            resource="checkout_link", ip=request.client.host if request.client else "")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "SUBSCRIPTION_UNAVAILABLE",
                     "message": "تعذّر التحقق من اشتراكك الحالي. أعد المحاولة بعد قليل — "
                                "لم يُخصم شيء."})
    held = held_keys(rows)

    limits_list = await asyncio.gather(*(c.billing_plans.limits(pid) for pid in plan_ids))
    if any(lim is None for lim in limits_list):
        await request.app.state.auditor.record(
            "subscription.gate_unreadable", actor=getattr(principal, "subject", ""), tenant=tenant,
            resource="checkout_link", ip=request.client.host if request.client else "")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "SUBSCRIPTION_UNAVAILABLE",
                     "message": "تعذّر قراءة أحد التطبيقات بالسلة. أعد المحاولة بعد قليل — "
                                "لم يُخصم شيء."})

    bundle_decision = may_add_bundle(
        items=[BundleItem(plan_id=pid, plan_limits=lim) for pid, lim in zip(plan_ids, limits_list)],
        held=held)
    if not bundle_decision.allowed:
        await request.app.state.auditor.record(
            "subscription.checkout_refused", actor=getattr(principal, "subject", ""), tenant=tenant,
            resource=f"plan:{bundle_decision.failed_plan_id}" if bundle_decision.failed_plan_id
                     else "checkout_link",
            ip=request.client.host if request.client else "")
        return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                            content={"error": "CHECKOUT_REFUSED",
                                     "message": bundle_decision.reason,
                                     "plan_id": bundle_decision.failed_plan_id})

    connected = await c.connections.connected(tenant)
    checkout_items: list[dict] = []
    for checkout_item, limits in zip(body.items, limits_list):
        if checkout_item.interval not in BILLING_INTERVALS:
            await request.app.state.auditor.record(
                "subscription.bad_interval", actor=getattr(principal, "subject", ""), tenant=tenant,
                resource=f"plan:{checkout_item.plan_id}",
                ip=request.client.host if request.client else "")
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                                content={"error": "BAD_INTERVAL",
                                         "message": "مدة الاشتراك غير صحيحة.",
                                         "plan_id": checkout_item.plan_id})
        if checkout_item.interval == "once" and is_base(limits):
            await request.app.state.auditor.record(
                "subscription.bad_interval", actor=getattr(principal, "subject", ""), tenant=tenant,
                resource=f"plan:{checkout_item.plan_id}",
                ip=request.client.host if request.client else "")
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                                content={"error": "BAD_INTERVAL",
                                         "message": "هذه الباقة تُجدَّد شهرياً ولا تُشترى مرة واحدة.",
                                         "plan_id": checkout_item.plan_id})

        item_decision = may_subscribe(
            connected=connected, trial_days=await c.billing_plans.trial_days(checkout_item.plan_id),
            paid=True, requires_connection=requires_whatsapp_connection(granted_keys(limits)))
        if not item_decision.allowed:
            # ONLY THE `requires_connection` BRANCH CAN EVER REFUSE HERE — same reasoning as
            # `checkout_link`'s own docstring, `paid=True` short-circuits every other one.
            await request.app.state.auditor.record(
                "subscription.whatsapp_connection_required", actor=principal.subject, tenant=tenant,
                resource=f"plan:{checkout_item.plan_id}",
                ip=request.client.host if request.client else "")
            return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                                content={"error": "WHATSAPP_CONNECTION_REQUIRED",
                                         "message": item_decision.reason,
                                         "redirect_screen": item_decision.redirect_screen,
                                         "plan_id": checkout_item.plan_id})
        checkout_items.append({"plan_id": checkout_item.plan_id, "interval": checkout_item.interval})

    status_code, out = await c.billing_plans.checkout_cart_link(
        tenant=tenant, items=checkout_items, idempotency_key=body.idempotency_key)
    if status_code >= 400:
        return JSONResponse(status_code=status_code,
                            content={"error": "BILLING_REFUSED", "detail": out})
    await request.app.state.auditor.record(
        "subscription.checkout_link_created", actor=principal.subject, tenant=tenant,
        resource=f"invoice:{out.get('invoice_id') or '-'}",
        ip=request.client.host if request.client else "")
    return JSONResponse(status_code=status.HTTP_201_CREATED, content=out)


class CheckoutPreviewIn(BaseModel):
    items: list[CheckoutItemIn] = Field(min_length=1, max_length=20)


@router.post("/checkout/preview", dependencies=[Depends(rate_limit)])
async def checkout_preview(request: Request, body: CheckoutPreviewIn,
                           principal=Depends(_OWNER)) -> JSONResponse:
    """THE REAL PRICE OF THE CART, before he pays — read-only, creates and charges nothing.

    THIS IS WHY THE CART CAN SHOW A NUMBER AT ALL. A shop's own discounts can come from a coupon,
    a cross-app relationship rule, a trial, or proration into an existing period — and the total
    also carries VAT where this establishment's own tax configuration applies one. No client-side
    arithmetic can reproduce that (see console's own `useAppBilling.ts` — an earlier pass tried a
    plain "price × (1 − percent)" estimate and it was flatly wrong the moment tax entered). This
    route asks billing-service's own `_compute_renewal` to run the SAME pricing the real checkout
    will charge, over a cart that has not been bought yet, so what the shop sees before paying is
    the exact figure the invoice will show after — never an estimate, never rounded differently.

    NO BUNDLE VALIDATION HERE, DELIBERATELY. A live total must keep updating as items are added or
    removed even before the cart is a legally purchasable set — refusing to price an incomplete
    cart would blank the total at the exact moment a shop is deciding what to add next. The bundle
    rule (`may_add_bundle`) and the WhatsApp-connection gate stay exactly where they are, on
    `POST /checkout` itself: nothing here can ever be charged without passing both.
    """
    tenant = _tenant(principal)
    if not tenant:
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"error": "NO_TENANT"})
    c = request.app.state.container
    items = [{"plan_id": i.plan_id, "interval": i.interval} for i in body.items]
    status_code, out = await c.billing_plans.checkout_preview(tenant=tenant, items=items)
    if status_code >= 400:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY if status_code >= 500
            else status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "PREVIEW_UNAVAILABLE",
                     "message": "تعذّر حساب السعر النهائي حالياً.",
                     "detail": out})
    return JSONResponse(status_code=status.HTTP_200_OK, content=out)
