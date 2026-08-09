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
from pydantic import BaseModel, Field

from app.api.auth import Principal
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.core.goals import CARDS, cards, lock_after_send, resolve_goal
from app.core.models import Campaign, as_row
from app.core.preview import PreviewError, build as build_preview, describe_when
from app.core.report import build as build_report, history, totals

router = APIRouter(prefix="/campaigns", tags=["campaigns"])

_READ = require_capability("campaigns.read")
_MANAGE = require_capability("campaigns.manage")


class CampaignIn(BaseModel):
    goal: str = Field(min_length=2, max_length=32)
    # The owner's ONE free-text field. Bounded here as well as sanitised in core — the model is
    # the door, and a rule enforced only in the core is a rule pydantic can drop on the way in.
    owner_text: str = Field(default="", max_length=200)
    # For `occasion` only. Ignored for every other goal rather than rejected: a console that sends
    # a spare field must not fail a campaign over it.
    fire_at: int = Field(default=0, ge=0)


@router.get("/goals", dependencies=[Depends(rate_limit)])
async def list_goals(request: Request, principal: Principal = Depends(_READ)) -> dict:
    """The five cards.

    Carries each card's LOCK and its reason, because the screen renders exactly what this returns —
    a console that computed its own availability would disagree with the server the first time
    either changed.
    """
    c = request.app.state.container
    locks = await _locks(c, principal.tenant)
    enabled = await c.templates.enabled_types(principal.tenant)
    return {"goals": [vars(card) for card in
                      cards(now=_now(), locks=locks, enabled_types=enabled)]}


@router.post("/preview", dependencies=[Depends(rate_limit)])
async def preview(request: Request, body: CampaignIn,
                  principal: Principal = Depends(_READ)) -> dict:
    """The message and the count. Writes nothing."""
    c = request.app.state.container
    try:
        spec = resolve_goal(body.goal)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    template = await c.templates.pick(principal.tenant, spec["template_type"])
    if template is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "لا يوجد قالب مفعّل لهذا الهدف — فعّله أولاً.")

    audience = await c.audience.resolve_for(
        principal.tenant, goal=body.goal, now=_now(),
        already_reached=set())

    try:
        p = build_preview(
            goal=body.goal, template=template,
            establishment=await c.identity.name(principal.tenant),
            owner_text=body.owner_text, audience=audience,
            when=describe_when(trigger=spec["trigger"],
                               inside_window=c.gate.inside_window(_now())))
    except PreviewError as exc:
        # 400 WITH THE OWNER'S SENTENCE. Not a code and not a field name: this message is rendered
        # straight onto the screen they are looking at, and it has to be actionable in their words.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return vars(p)


@router.post("", dependencies=[Depends(rate_limit)])
async def create(request: Request, body: CampaignIn,
                 principal: Principal = Depends(_MANAGE)) -> dict:
    """Create the campaign, and fire it if it is a manual one."""
    c = request.app.state.container
    now = _now()
    try:
        spec = resolve_goal(body.goal)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    locks = await _locks(c, principal.tenant)
    if int(locks.get(body.goal) or 0) > now:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "هذا الهدف مقفل مؤقتاً — انظر البطاقة.")

    # Validated BEFORE the campaign exists. Creating it and then refusing the text would leave a
    # draft the owner did not ask for, in a list they now have to clean.
    template = await c.templates.pick(principal.tenant, spec["template_type"])
    if template is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "لا يوجد قالب مفعّل لهذا الهدف — فعّله أولاً.")
    try:
        from app.core.preview import sanitise_owner_text
        needs = any(f == "owner" for f in (template.get("fills") or []))
        clean = sanitise_owner_text(body.owner_text, required=needs)
    except PreviewError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    campaign = Campaign(tenant=principal.tenant, goal=body.goal, owner_text=clean,
                        template_type=spec["template_type"], cls=spec["cls"],
                        trigger=spec["trigger"], state="active", fire_at=body.fire_at)

    await request.app.state.auditor.record(
        "campaign.created", actor=principal.subject, tenant=principal.tenant,
        resource=f"campaign:{campaign.id}", ip=request.client.host if request.client else "")
    await c.datastore.put("campaigns", campaign.key, as_row(campaign))

    fired = None
    if campaign.trigger == "manual":
        # INLINE, and bounded by the dispatcher. Letting the tick pick it up means the owner
        # presses send and nothing visibly happens for five minutes — so they press it again.
        out = await c.dispatcher.fire(as_row(campaign), now=now, fired_by=principal.subject)
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
    return {"runs": [vars(r) for r in history(rows)], "totals": totals(rows)}


@router.post("/{campaign_id}/pause", dependencies=[Depends(rate_limit)])
async def pause(request: Request, campaign_id: str,
                principal: Principal = Depends(_MANAGE)) -> dict:
    """Stop a standing campaign. PAUSED, never deleted — its runs are referenced by the send log,
    and an owner reading their history six months later must not find rows pointing at nothing."""
    c = request.app.state.container
    row = await c.datastore.get("campaigns", f"{principal.tenant}|{campaign_id}")
    if row is None or row.get("tenant") != principal.tenant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    await request.app.state.auditor.record(
        "campaign.paused", actor=principal.subject, tenant=principal.tenant,
        resource=f"campaign:{campaign_id}", ip=request.client.host if request.client else "")
    row["state"] = "paused"
    await c.datastore.put("campaigns", f"{principal.tenant}|{campaign_id}", row)
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
    from app.core.audience import MAX_AUDIENCE
    row = await request.app.state.container.datastore.get(
        "audience_caps", f"_platform|{tenant or '_global'}")
    return {"scope": tenant or "_global", "default": MAX_AUDIENCE, "override": row}
