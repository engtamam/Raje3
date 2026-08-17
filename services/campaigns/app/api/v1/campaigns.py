"""The owner's three screens, as three routes (spec §10.9).

  GET  /campaigns/goals        the five cards, with their locks and their reasons
  POST /campaigns/preview      the message and the count, computed but not saved
  POST /campaigns              create and fire, or create and schedule

PREVIEW IS A POST THAT WRITES NOTHING, and that is deliberate rather than sloppy. It carries the
owner's text in a body — a GET would put an offer in a URL, which lands in an access log, a proxy
cache and a browser history. And it must be recomputed on every keystroke-ish change, so it cannot
be a resource with an id.

THE CREATE ROUTE FIRES INSIDE THE REQUEST for a manual campaign, and that is a choice worth
defending. The alternative — create, then let the tick pick it up — means the owner presses "send"
and nothing visibly happens for up to five minutes. They press it again. Firing inline is bounded
(the dispatcher caps a pass), and anything left over is finished by the tick.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.adapters.datastore.drain import drain
from app.api.auth import Principal
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.core.goals import CARDS, cards, lock_after_send, resolve_goal
from app.core.models import GOAL_TEMPLATE, Campaign, as_row, offers_something
from app.core.licence import NOT_INCLUDED as LICENCE_NOT_INCLUDED
from app.core.preview import PreviewError, build as build_preview, describe_when
from app.core.share import compute as compute_share
from app.core.spread import plan as plan_spread
from app.core.spread import sentence as spread_sentence
from app.core.report import build as build_report, history, totals

router = APIRouter(prefix="/campaigns", tags=["campaigns"])

_READ = require_capability("campaigns.read")
_MANAGE = require_capability("campaigns.manage")

def _tenant(p: Principal) -> str:
    """The establishment this request belongs to, or no request at all.

    `Principal.tenant` is None whenever the token carries no tenant claim — a platform token, an
    operator's, a machine key minted for the fleet — and `require_capability` has never looked at
    it. Left raw, that None reaches the write side: a key becomes the literal string «None|...»,
    a stored row's `tenant` becomes null, and the row belongs to nobody. No owner ever sees it, no
    export carries it, and no erasure reaches it, because an erasure fans out per tenant.

    Refused rather than defaulted, and the same four lines the other route modules already carry.
    """
    if not p.tenant:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "NO_TENANT")
    return p.tenant



class CampaignIn(BaseModel):
    goal: str = Field(min_length=2, max_length=32)
    # The owner's ONE free-text field. Bounded here as well as sanitised in core — the model is
    # the door, and a rule enforced only in the core is a rule pydantic can drop on the way in.
    owner_text: str = Field(default="", max_length=200)
    # «20%» or «50 ريال» — typed, and validated against the same shape the send validates. It
    # travelled inside `owner_text` before this, which is why a shop could promise «خصم كبير».
    offer_value: str = Field(default="", max_length=32)
    # The chosen service's NAME. The screen has it (it lists the catalogue) and we do not.
    service_name: str = Field(default="", max_length=120)
    # For `occasion` only. Ignored for every other goal rather than rejected: a console that sends
    # a spare field must not fail a campaign over it.
    fire_at: int = Field(default=0, ge=0)
    # When the offer stops being true. Optional, and it CHANGES THE ANSWER rather than decorating
    # it: a campaign that cannot reach everyone before this date refuses at launch instead of
    # spilling past it, because a customer receiving an offer that expired yesterday sees a shop
    # that looks careless (§8.4.3).
    expires_at: int = Field(default=0, ge=0)
    # WHICH SERVICES THE OFFER COVERS. Empty is not "unset" — it is "the whole shop", which is a
    # real and common answer ("20% on everything this week"). Bounded because a scope longer than
    # a shop's catalogue is not a scope.
    scope_service_ids: list[str] = Field(default_factory=list, max_length=100)
    # WHICH SERVICE THE `service_offer` GOAL IS ABOUT — and it had no way in.
    #
    # The field existed on the campaign, the audience engine read it, and the 70% cycle lock was
    # written and tested against it (§10.9.1). But no request model carried it, so nothing could
    # ever set it: every "offer on a service" went out as an untargeted announcement, the lock
    # never engaged once, and the reach number read as proof that it had. A feature complete in
    # the depth and severed at the door.
    service_id: str = Field(default="", max_length=64)
    # WHICH BRANCH THIS CAMPAIGN IS FOR — empty is the whole establishment, and is the default for
    # every shop that never opened a second one.
    branch_id: str = Field(default="", max_length=64)


@router.get("/goals", dependencies=[Depends(rate_limit)])
async def list_goals(request: Request, principal: Principal = Depends(_READ)) -> dict:
    """The five cards.

    Carries each card's LOCK and its reason, because the screen renders exactly what this returns —
    a console that computed its own availability would disagree with the server the first time
    either changed.
    """
    c = request.app.state.container
    locks = await _locks(c, _tenant(principal))
    enabled = await c.templates.enabled_types(_tenant(principal))
    # AND WHAT EACH GOAL WILL ASK HIM TO FILL (ط-4). Read from the template this shop would
    # actually send — including one he rewrote himself — so the screen draws the blanks that
    # exist rather than one free box for every goal, four of which had nowhere to put it.
    fills: dict[str, list[str]] = {}
    for template_type, _cls in GOAL_TEMPLATE.values():
        row = await c.templates.pick(_tenant(principal), template_type)
        if row:
            fills[template_type] = list(row.get("fills") or [])
    return {"goals": [vars(card) for card in
                      cards(now=_now(), fills_by_type=fills, locks=locks,
                            enabled_types=enabled)]}


@router.post("/preview", dependencies=[Depends(rate_limit)])
async def preview(request: Request, body: CampaignIn,
                  principal: Principal = Depends(_READ)) -> dict:
    """The message and the count. Writes nothing."""
    c = request.app.state.container
    try:
        spec = resolve_goal(body.goal)
    except ValueError as exc:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={"error": "BAD_REQUEST",
                                     "reason": str(exc)})

    template = await c.templates.pick(_tenant(principal), spec["template_type"])
    if template is None:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={"error": "BAD_REQUEST",
                                     "reason": "لا يوجد قالب مفعّل لهذا الهدف — فعّله أولاً."})

    # THE CLASS THE CAMPAIGN WILL ACTUALLY BE SENT UNDER (ج-1). Not the resolver's default: the
    # preview exists to tell the owner what will happen, and a preview run under different rules
    # than the send is a number that is worse than no number.
    audience = await c.audience.resolve_for(
        _tenant(principal), goal=body.goal, now=_now(), cls=spec["cls"],
        already_reached=set(), service_id=body.service_id, branch_id=body.branch_id)

    try:
        p = build_preview(
            goal=body.goal, template=template,
            establishment=await c.identity.name(_tenant(principal)),
            owner_text=body.owner_text, audience=audience,
            offer_value=body.offer_value,
            ends_at=arabic_date(body.expires_at or 0),
            # NAMED BY THE CALLER, and it has to be: this service holds service IDs and the
            # catalogue belongs to operations. «خصم على svc_9f2» is not a message, and an empty
            # name makes the renderer refuse rather than send a hole in a sentence.
            service_text=body.service_name,
            when=describe_when(trigger=spec["trigger"],
                               inside_window=c.gate.inside_window(_now())))
    except PreviewError as exc:
        # 400 WITH THE OWNER'S SENTENCE. Not a code and not a field name: this message is rendered
        # straight onto the screen they are looking at, and it has to be actionable in their words.
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={"error": "BAD_REQUEST",
                                     "reason": str(exc)})

    # HOW LONG IT WILL TAKE, ON THE SCREEN WHERE HE DECIDES — not reconstructed afterwards from a
    # progress bar. Ten thousand recipients against a share of two thousand is five days whether
    # we plan it or not, and an owner who expected an afternoon and got a week will say the
    # product is broken. He will be right to: nothing told him.
    out = vars(p)
    share = await _todays_share(c, _tenant(principal))
    if share.known:
        # FOUR ARGUMENTS, WHICH IS ALL `plan` TAKES. It was being called with `offer_value=` and
        # `scope_service_names=` as well — a TypeError on every preview where the ceiling was
        # known. It never fired because the ceiling was NEVER known (the peer was missing), so one
        # dead wire hid the other: repairing the ceiling alone would have replaced a silent
        # omission with a 500 on the owner's screen. The spread sentence takes the plan and says
        # only what the plan knows; the offer's own words belong to the campaign, not to it.
        sp = plan_spread(audience=audience.count, available_per_day=share.per_day,
                         expires_at=body.expires_at or 0, now=_now())
        out["spread"] = sp.to_dict()
        out["spread_says"] = spread_sentence(sp)
    else:
        # NO ESTIMATE RATHER THAN A WRONG ONE. The ceiling is unknown — a shop that connected this
        # morning, or a peer that did not answer — and a promise made on a guess is worse than no
        # promise: he plans around it, and we are the reason he was wrong.
        out["spread"] = None
        out["spread_says"] = ""
    return out


async def _todays_share(c, tenant: str):
    """The campaign's slice of today: the ceiling, minus the engine's reserve, minus what has
    already gone. Three numbers from three services, none of which this one could compute."""
    ceiling = await c.ceiling.read(tenant)
    reserved, used = await c.engine_load(tenant)
    return compute_share(ceiling=ceiling.limit, reserved=reserved, used=used,
                         fallback=c.settings.CAMPAIGN_MAX_AUDIENCE)


@router.post("", dependencies=[Depends(rate_limit)])
async def create(request: Request, body: CampaignIn,
                 principal: Principal = Depends(_MANAGE)) -> dict:
    """Create the campaign, and fire it if it is a manual one."""
    c = request.app.state.container
    now = _now()

    # ── has this shop bought campaigns at all? ───────────────────────────────────────────────
    # FIRST, BEFORE ANYTHING IS VALIDATED OR WRITTEN. `feature.campaigns` is the line between
    # الأساسية and الذكية and nothing in the fleet has ever checked it: an owner on the cheapest
    # plan pressed «أطلق الحملة» and it went out. The lock the console draws is a CAPABILITY lock
    # — about his role, not about what the shop bought — so the one person who would have paid to
    # remove it never saw it.
    #
    # 402, NOT 403. He is not forbidden; he has not bought it, and the difference is what the
    # screen offers him next (`insights` answers the same way for its own key).
    # RETURNED, NEVER RAISED. The platform's handler strips `detail` off every HTTPException
    # (CWE-209) — right for a stack trace, and fatal for a sentence we wrote for an owner to read.
    # A raised refusal here would reach him as an empty 402.
    licence = getattr(c, "licence", None)
    if licence is not None and not await licence.allowed(_tenant(principal)):
        return JSONResponse({"error": "PAYMENT_REQUIRED", "reason": LICENCE_NOT_INCLUDED},
                            status_code=status.HTTP_402_PAYMENT_REQUIRED)
    try:
        spec = resolve_goal(body.goal)
    except ValueError as exc:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={"error": "BAD_REQUEST",
                                     "reason": str(exc)})

    locks = await _locks(c, _tenant(principal))
    if int(locks.get(body.goal) or 0) > now:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                            content={"error": "CONFLICT",
                                     "reason": "هذا الهدف مقفل مؤقتاً — انظر البطاقة."})

    # Validated BEFORE the campaign exists. Creating it and then refusing the text would leave a
    # draft the owner did not ask for, in a list they now have to clean.
    template = await c.templates.pick(_tenant(principal), spec["template_type"])
    if template is None:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={"error": "BAD_REQUEST",
                                     "reason": "لا يوجد قالب مفعّل لهذا الهدف — فعّله أولاً."})
    try:
        from app.core.preview import sanitise_owner_text
        needs = any(f == "owner" for f in (template.get("fills") or []))
        clean = sanitise_owner_text(body.owner_text, required=needs)
    except PreviewError as exc:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={"error": "BAD_REQUEST",
                                     "reason": str(exc)})

    # AN OFFER WITHOUT AN END IS A PRICE CHANGE NOBODY DECIDED ON — refused here, before anything
    # exists, and with the reason named. It is also what makes "this offer is yours" enforceable:
    # the send log says who received it, and this says until when. Without a date the operator at
    # the counter has nothing to check and the customer's own page has nothing to count down.
    #
    # REFUSED, NOT DEFAULTED. A silent "thirty days" would be a discount the shop never chose,
    # discovered a month later in the margin.
    if offers_something(body.goal):
        try:
            from app.core.preview import sanitise_offer_value
            # REQUIRED ONLY WHEN THE TEMPLATE HAS A SLOT FOR IT. «أعلن جديدك» promises nothing and
            # would refuse for a field it has nowhere to put.
            offer_value = sanitise_offer_value(
                body.offer_value,
                required=any(f == "amount" for f in (template.get("fills") or [])))
        except PreviewError as exc:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                                content={"error": "BAD_REQUEST",
                                         "reason": str(exc)})
        if not body.expires_at:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                                content={"error": "BAD_REQUEST",
                                         "reason": "حدّد تاريخ انتهاء العرض — عرض بلا نهاية خصمٌ دائم."})
        if body.expires_at <= now:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                                content={"error": "BAD_REQUEST",
                                         "reason": "تاريخ الانتهاء مضى — اختر وقتاً قادماً."})

    campaign = Campaign(tenant=_tenant(principal), goal=body.goal, owner_text=clean,
                        template_type=spec["template_type"], cls=spec["cls"],
                        trigger=spec["trigger"], state="active", fire_at=body.fire_at,
                        expires_at=body.expires_at or 0,
                        # STORED, BOTH OF THEM, and `service_id` was not.
                        #
                        # The dispatcher resolves the audience again at fire time from the STORED
                        # campaign (container.py `_resolver`), reading `service_id` and now
                        # `branch_id` off the row. Only `scope_service_ids` was being written, so
                        # the preview applied the 70% cycle lock and the send that followed it did
                        # not: the owner was shown a targeted count and the campaign went to the
                        # whole shop. One field, and it made the feature a demo.
                        service_id=(body.service_id or "").strip(),
                        branch_id=(body.branch_id or "").strip(),
                        offer_value=(body.offer_value or "").strip(),
                        scope_service_names=([body.service_name] if body.service_name else []),
                        # THE TARGETED SERVICE IS ALWAYS IN ITS OWN SCOPE. `service_offer` reaches
                        # people who are 70% through their cycle for one service; an offer that
                        # arrived because of a service and then did not cover it would be the
                        # cruellest version of this feature.
                        scope_service_ids=list(dict.fromkeys(
                            ([body.service_id] if getattr(body, "service_id", "") else [])
                            + list(body.scope_service_ids))))

    await request.app.state.auditor.record(
        "campaign.created", actor=principal.subject, tenant=_tenant(principal),
        resource=f"campaign:{campaign.id}", ip=request.client.host if request.client else "")
    await c.datastore.put("campaigns", campaign.key, as_row(campaign))

    fired = None
    if campaign.trigger == "manual":
        # INLINE, and bounded by the dispatcher. Letting the tick pick it up means the owner
        # presses send and nothing visibly happens for five minutes — so they press it again.
        # THE SAME NUMBER THE PREVIEW SHOWED HIM. The screen says «سنوزّعها على N أيام» from
        # `_todays_share`; the send used to ignore it entirely and spend the whole pass batch, so
        # the sentence was a promise nothing kept — and the engine's reserve went with it.
        share = await _todays_share(c, _tenant(principal))
        out = await c.dispatcher.fire(as_row(campaign), now=now, fired_by=principal.subject,
                                      # `None` WHEN WE COULD NOT READ THE CEILING, never 0: an
                                      # unknown share must not silence a shop, and a known zero
                                      # must not be overridden. Two facts, two values (ج-3).
                                      daily_share=share.per_day if share.known else None)
        fired = vars(build_report(as_row(out.run)))
        until = lock_after_send(body.goal, now=now, sent=out.run.sent)
        if until:
            row = as_row(campaign)
            row["locked_until"] = until
            row["state"] = "done"
            await c.datastore.put("campaigns", campaign.key, row)

    return {"campaign": as_row(campaign), "run": fired,
            "behaviour": spec["behaviour"]}


@router.get("", dependencies=[Depends(rate_limit)])
async def list_campaigns(request: Request, state: str = "",
                         principal: Principal = Depends(_READ)) -> dict:
    where = {"tenant": principal.tenant}
    if state:
        where["state"] = state
    rows, _ = await request.app.state.container.datastore.find(
        "campaigns", where, limit=200, sort=("created", "desc"))
    return {"campaigns": rows, "count": len(rows)}


@router.get("/{campaign_id}/runs", dependencies=[Depends(rate_limit)])
async def runs(request: Request, campaign_id: str,
               principal: Principal = Depends(_READ)) -> dict:
    """Every firing, newest first, each with its own reasons.

    NOT AGGREGATED. Forty runs are forty questions, and an owner asking why it reached nobody last
    Tuesday needs Tuesday — the totals are a separate field for the one place a total belongs.
    """
    rows, _ = await request.app.state.container.datastore.find(
        "campaign_runs", {"tenant": principal.tenant, "campaign_id": campaign_id},
        limit=200, sort=("at", "desc"))

    # WHO THIS CAMPAIGN REACHED, so `redeemed` can ask operations who among them came back and
    # spent an offer (ط-3). `campaign_reached` already names every recipient and when — the piece
    # that was always missing was asking the other half of the question, not recording the first.
    #
    # DRAINED. Two thousand oldest, cursor discarded — so for any campaign larger than that, the
    # `redeemed` figure was computed against part of its own recipients. The number shown to the
    # owner as «this campaign brought back N people» was not wrong by a little; it was the answer
    # to a smaller question, and it looked identical to the right one.
    reached_rows = await drain(
        request.app.state.container.datastore, "campaign_reached",
        {"tenant": principal.tenant, "campaign_id": campaign_id}, sort=("at", "asc"))
    reached = [{"subject_ref": r.get("subject_ref", ""), "since": int(r.get("at") or 0)}
              for r in reached_rows if r.get("subject_ref")]
    redeemed = (await request.app.state.container.audience.redeemed(_tenant(principal), reached)
               if reached else 0)

    return {"runs": [vars(r) for r in history(rows)],
            "totals": {**totals(rows), "redeemed": redeemed}}


@router.post("/{campaign_id}/pause", dependencies=[Depends(rate_limit)])
async def pause(request: Request, campaign_id: str,
                principal: Principal = Depends(_MANAGE)) -> dict:
    """Stop a standing campaign. PAUSED, never deleted — its runs are referenced by the send log,
    and an owner reading their history six months later must not find rows pointing at nothing."""
    c = request.app.state.container
    row = await c.datastore.get("campaigns", f"{_tenant(principal)}|{campaign_id}")
    if row is None or row.get("tenant") != _tenant(principal):
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND,
                            content={"error": "NOT_FOUND",
                                     "reason": "لم نجد هذه الحملة."})
    await request.app.state.auditor.record(
        "campaign.paused", actor=principal.subject, tenant=_tenant(principal),
        resource=f"campaign:{campaign_id}", ip=request.client.host if request.client else "")
    row["state"] = "paused"
    await c.datastore.put("campaigns", f"{_tenant(principal)}|{campaign_id}", row)
    return {"campaign_id": campaign_id, "state": "paused"}


async def _locks(c, tenant: str) -> dict[str, int]:
    """goal -> locked_until, from the campaigns that carry one."""
    rows, _ = await c.datastore.find("campaigns", {"tenant": tenant}, limit=200,
                                     sort=("created", "desc"))
    out: dict[str, int] = {}
    for r in rows:
        until = int(r.get("locked_until") or 0)
        goal = r.get("goal", "")
        if until and goal in CARDS:
            out[goal] = max(out.get(goal, 0), until)
    return out


_AR_MONTHS = ("يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
              "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر")


def arabic_date(epoch: int) -> str:
    """The last day, as a person reads it — in Riyadh, because an offer ending at 01:00 UTC ends
    the previous evening for whoever is reading the message."""
    if not epoch:
        return ""
    from datetime import datetime, timedelta, timezone
    d = datetime.fromtimestamp(int(epoch), timezone(timedelta(hours=3)))
    return f"{d.day} {_AR_MONTHS[d.month - 1]}"


def _now() -> int:
    import time
    return int(time.time())


# ── ours, not an establishment's ───────────────────────────────────────────────────────────────
_PLATFORM = require_capability("platform.campaigns")


class AudienceCapIn(BaseModel):
    # The ceiling on one campaign's audience. A product limit, not a technical one: an
    # establishment sending to more than this in one go is a case we want to see before it goes
    # out, and a silent truncation would be worse than a refusal.
    max_audience: int = Field(ge=100, le=20000)
    reason: str = Field(min_length=10, max_length=500)


@router.put("/platform/audience-cap", dependencies=[Depends(rate_limit)])
async def set_audience_cap(request: Request, body: AudienceCapIn, tenant: str = "",
                           principal: Principal = Depends(_PLATFORM)) -> dict:
    """Raise or lower the audience ceiling, globally or for one establishment.

    OURS BECAUSE THE COST IS NOT THEIRS ALONE. A campaign to twenty thousand people at once is a
    volume spike Meta reads as a quality signal against every number we hold — so a shop cannot
    lift its own ceiling any more than it can lift its own sending caps (spec §8.4.2).

    The reason is required and is not decoration: six months from now somebody finds a tenant with
    four times the ceiling and no way to tell whether it was a considered exception or a mistake,
    and the safe response to an unexplained permission is always to remove it — which breaks the
    shop that legitimately needed it.
    """
    scope = tenant or "_global"
    await request.app.state.auditor.record(
        "campaign.audience_cap_changed", actor=principal.subject, tenant=tenant,
        resource=f"audience_cap:{scope}", ip=request.client.host if request.client else "")
    row = body.model_dump()
    row["id"] = scope
    row["tenant"] = "_platform"
    row["scope"] = scope
    row["actor"] = principal.subject
    await request.app.state.container.datastore.put(
        "audience_caps", f"_platform|{scope}", row)
    return {"scope": scope, "max_audience": body.max_audience}


@router.get("/platform/audience-cap", dependencies=[Depends(rate_limit)])
async def get_audience_cap(request: Request, tenant: str = "",
                           principal: Principal = Depends(_PLATFORM)) -> dict:
    from app.core.audience import DEFAULT_MAX_AUDIENCE
    row = await request.app.state.container.datastore.get(
        "audience_caps", f"_platform|{tenant or '_global'}")
    return {"scope": tenant or "_global", "default": DEFAULT_MAX_AUDIENCE, "override": row}
