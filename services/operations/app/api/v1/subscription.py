"""The owner's subscribe path — ours, so a product rule has somewhere to live.

    POST /api/v1/subscription     subscribe this establishment to a plan

WHY NOT CALL BILLING DIRECTLY, which is what happened before this file: because there was then no
moment that belonged to us. billing-service is the platform's, shared by every product built on
it, and it must never learn that ours requires WhatsApp before it will take money.

So this is thin on purpose — one question, then their route, then their answer. It holds no plan,
prices nothing, and stores no subscription. Everything about money stays where it already works.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.auth import require_user
from app.api.authz import require_capability
from app.config import get_settings
from app.core import apps as app_catalogue
from app.core.subscribe import held_keys, is_base, may_add, may_subscribe

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


def _tenant(p) -> str:
    return getattr(p, "tenant", "") or ""


@router.get("/payment", dependencies=[Depends(rate_limit)])
async def payment_state(principal=Depends(_OWNER)) -> dict:
    """Is there a live way to pay — and what does the screen need in order to offer it?

    THE SCREEN MUST NOT GUESS. Until this existed the plans page assumed payment worked, so with no
    gateway configured every press wrote «باقتك» over the last one and no riyal moved. A product
    that hands out its paid tiers to whoever presses hardest is not generous; it is broken, and the
    first shop to notice tells the second.

    AND IT FLIPS BY ITSELF. One key decides: absent, the screen apologises and sells nothing;
    present, the card form appears and a subscription waits for a real charge. Nobody edits code
    on the day we sign with a provider — the key goes in the secret and the product starts selling.

    THE PUBLISHABLE KEY IS MEANT TO BE READ BY A BROWSER — it can mint a single-use token and do
    nothing else. The secret key lives in billing-service and appears in no response, ever.
    """
    cfg = get_settings()
    key = (cfg.PAYMENT_PUBLISHABLE_KEY or "").strip()
    return {"enabled": bool(key), "provider": cfg.PAYMENT_PROVIDER if key else "",
            "publishable_key": key,
            "message": "" if key else
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
    """«ايش فيه» — تسجيل زيارة/جهات الاتصال/التقييم's own catalog, the ONE gap the other five
    services' `.../features` routes never had: `/apps` just above answers a TENANT's own held
    apps, and there was no standalone, tenant-free read of these three apps' feature lists at
    all — bookings/loyalty/campaigns/insights/whatsapp-assistant each got a real `.../features`
    route, but operations only ever spread `VISIT_FEATURES`/`CONTACTS_FEATURES`/`RATING_FEATURES`
    inline into `public()`'s per-shop answer, which needs `held`/`checked` neither of which the
    admin panel — no shop, no tenant — can ever supply. Found live: PlanCards.tsx fell back to
    the raw boolean-limit list for these three specifically, one lone card among a shelf of rich
    ones (owner's own screenshot). Same posture as every sibling route: `require_user` only, no
    capability, no subscription check — the content is identical for every caller regardless of
    tenant, same as the constants it reads.
    """
    return {
        "visit": list(app_catalogue.VISIT_FEATURES),
        "contacts": list(app_catalogue.CONTACTS_FEATURES),
        "rating": list(app_catalogue.RATING_FEATURES),
    }


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
    decision = may_subscribe(connected=connected, trial_days=trial_days,
                             paid=bool(body.payment_token) or free)
    if not decision.allowed:
        # RETURNED, NEVER RAISED. The platform's error handler strips an HTTPException's detail,
        # so a raised refusal arrives as a bare 402 and the sentence telling him what to do — the
        # only useful part — is thrown away.
        await request.app.state.auditor.record(
            "subscription.refused", actor=principal.subject, tenant=tenant,
            resource=f"plan:{body.plan_id}",
            ip=request.client.host if request.client else "")
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
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={"error": "BAD_INTERVAL",
                                     "message": "مدة الاشتراك غير صحيحة."})
    if body.interval == "once" and is_base(plan_limits):
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={"error": "BAD_INTERVAL",
                                     "message": "هذه الباقة تُجدَّد شهرياً ولا تُشترى مرة واحدة."})

    # A FREE APP IS SUBSCRIBED ONCE, NOT MONTHLY, REGARDLESS OF WHAT THE CALLER SENT. `once`
    # gives `period_end = 0`, which the resolver reads as "never lapses" and the renewal sweep
    # skips outright — so a free-forever standalone app never re-cycles through a pointless
    # SAR 0 invoice every month. Never for a base row (refused just above, and a base is never
    # free): this only ever touches an app, and only a free one.
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
    return JSONResponse(status_code=status.HTTP_201_CREATED, content=out)
