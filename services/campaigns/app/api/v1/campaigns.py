"""The owner's three screens, as three routes (spec §10.9).

  GET  /campaigns/goals        the cards, with their reasons
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

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.adapters.datastore.drain import drain
from app.api.auth import Principal
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.core.goals import GOAL_CATEGORIES, cards, resolve_goal
from app.core.models import (GOAL_TEMPLATE, REWARD_ENABLED_GOALS, Campaign, as_row,
                             offers_something, validate_loyalty_window, validate_reward,
                             validate_window)
from app.core.licence import NOT_INCLUDED as LICENCE_NOT_INCLUDED
from app.core.goal_stats import read_goal_stats, record_use
from app.core import press
from app.core.preview import PreviewError, build as build_preview, describe_when, window_sentence
from app.core.share import compute as compute_share
from app.core.spread import plan as plan_spread
from app.core.spread import sentence as spread_sentence
from app.core.report import build as build_report, history, totals
from app.core.riyadh import local

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
    #
    # SUPERSEDED BY `service_ids`/`package_ids` BELOW as the console's own multi-select input
    # (2026-09-13) — kept, and still folded in (never dropped), for any older/other caller that
    # only ever knew this field.
    scope_service_ids: list[str] = Field(default_factory=list, max_length=100)
    # WHICH SERVICE THE `service_offer` GOAL IS ABOUT — and it had no way in.
    #
    # The field existed on the campaign, the audience engine read it, and the 70% cycle lock was
    # written and tested against it (§10.9.1). But no request model carried it, so nothing could
    # ever set it: every "offer on a service" went out as an untargeted announcement, the lock
    # never engaged once, and the reach number read as proof that it had. A feature complete in
    # the depth and severed at the door.
    #
    # KEPT for a console that still sends only one — `service_ids` below is folded in on top of
    # it, never instead of it.
    service_id: str = Field(default="", max_length=64)
    # SEVERAL SERVICES, ONE CAMPAIGN (2026-09-13) — the owner picks more than one on the create
    # screen and every one is named in the same merged message (rendering.merged_service_text).
    # Reached if ready for even one (`audience.resolve`'s own note on why): a shop selling three
    # services under one offer should not hold a customer back because he took ONE of them
    # yesterday.
    service_ids: list[str] = Field(default_factory=list, max_length=20)
    # THE CHOSEN SERVICES' NAMES, in the SAME order as `service_ids` — the screen has the
    # catalogue, this service does not. Each is sanitised the same way `owner_text` is.
    service_names: list[str] = Field(default_factory=list, max_length=20)
    # WHICH PACKAGE THE `package_offer` GOAL IS ABOUT — mutually exclusive with `service_id`, same
    # "one or the other, never both" rule the packages feature already applies at every other
    # layer (operations' own Package/Booking). The console fetches its own package list directly
    # from operations (this service holds no catalogue of its own — see peers/__init__.py's
    # module docstring), so it already has this id before the owner ever presses launch.
    package_id: str = Field(default="", max_length=64)
    # THE CHOSEN PACKAGE'S NAME (and, since it is worth stating, its own price) — same reasoning
    # as `service_name` just above: the screen has it, this service does not.
    package_name: str = Field(default="", max_length=120)
    # SEVERAL PACKAGES, ONE CAMPAIGN — same reasoning as `service_ids`. A package has no cycle
    # lock of its own (no single rhythm to hold anyone back on — `_MATCHERS["package_offer"]`'s
    # own note), so this only ever widens the merged message, never the audience rule.
    package_ids: list[str] = Field(default_factory=list, max_length=20)
    package_names: list[str] = Field(default_factory=list, max_length=20)
    # WHICH BRANCH THIS CAMPAIGN IS FOR — empty is the whole establishment, and is the default for
    # every shop that never opened a second one.
    branch_id: str = Field(default="", max_length=64)
    # THE OWNER'S OWN WINDOW — offer goals only (`OFFER_GOALS`; see `Campaign.window_*`'s own
    # note). Defaults are "no window at all", so a console that never sends these three fields
    # gets exactly today's behaviour, unchanged.
    window_start_hour: int = Field(default=0, ge=0, le=24)
    window_end_hour: int = Field(default=24, ge=0, le=24)
    window_weekdays: list[int] = Field(default_factory=list, max_length=7)
    # «كافئ المخلصين»'s OWN AUDIENCE THRESHOLDS (2026-09-13) — an interactive live control on the
    # create screen, never a fixed rule baked into the code. Meaningless for every other goal;
    # bounds match `models.py::LOYALTY_WINDOW_DAYS_RANGE`/`LOYALTY_MIN_VISITS_RANGE`.
    loyalty_window_days: int = Field(default=90, ge=7, le=365)
    loyalty_min_visits: int = Field(default=3, ge=1, le=50)
    # WHICH OF THREE REWARDS THIS CAMPAIGN GIVES (`occasion`/`win_back`, 2026-09-13 — extended
    # from the `occasion`-only pilot to `win_back` once that pilot proved out) — "discount" is
    # every OTHER goal's whole reality today, so this is a no-op for them; see `validate_reward`
    # and `REWARD_ENABLED_GOALS` below.
    reward_type: str = Field(default="discount", max_length=16)
    reward_points: int = Field(default=0, ge=0, le=100000)


def _combine_ids_and_names(single_id: str, ids: list[str], single_name: str,
                           names: list[str]) -> tuple[list[str], list[str]]:
    """The full multi-select list (2026-09-13), backward-compatible with a console that still
    sends only the singular field. `ids`/`names` (the plural, authoritative fields) come first so
    their own order is what the merged message names first; the singular is appended only if it
    is not already there, never duplicated.
    """
    all_ids = list(dict.fromkeys(ids + ([single_id] if single_id else [])))
    all_names = list(dict.fromkeys(names + ([single_name] if single_name else [])))
    return all_ids, all_names


@router.get("/goals", dependencies=[Depends(rate_limit)])
async def list_goals(request: Request, principal: Principal = Depends(_READ)) -> dict:
    """The five cards.

    Carries each card's LOCK and its reason, because the screen renders exactly what this returns —
    a console that computed its own availability would disagree with the server the first time
    either changed.

    A CARD MUST NEVER BE SHOWN AVAILABLE AND THEN REFUSED — a shop owner opened «رجّع اللي غابوا»,
    it looked pressable, and `/preview` answered "لا يوجد قالب مفعّل لهذا الهدف" the moment he
    asked for a number. `enabled_types()` and `pick()` used to be two SEPARATE peer calls, each
    capable of its own cache/timing, answering the same underlying question ("does a template
    exist for this type") through two different paths that could disagree for a moment neither
    call could see. `enabled` is now derived from the EXACT SAME `pick()` reads `fills` already
    needs below — one read per template type, one truth, so a card cannot be unlocked here by a
    fact `preview` itself would refuse a breath later.
    """
    c = request.app.state.container
    # reminders' OWN reason a type is not sendable — «قيد مراجعة واتساب» is patience, «لا يوجد
    # قالب فعّال» is ours to fix — never guessed here, and never the one hardcoded sentence that
    # used to stand in for both.
    blocked = await c.templates.blocked_reasons(_tenant(principal))
    # THE BADGE — one status word per type, shown on every card whether it is locked or not
    # (see Card.template_status's own docstring).
    statuses = await c.templates.statuses(_tenant(principal))
    # AND WHAT EACH GOAL WILL ASK HIM TO FILL (ط-4), read from the template this shop would
    # actually send — including one he rewrote himself — so the screen draws the blanks that
    # exist rather than one free box for every goal, four of which had nowhere to put it. THE
    # SAME READS now also decide `enabled` — see the docstring above for why that used to be a
    # second, independently-timed call. DEDUPED FIRST: several goals share one template type
    # (e.g. `service_offer` and `package_offer` both render `mkt_offer`), so looking it up
    # per-goal asked the store the same question twice for no different answer — a `set`
    # collapses that before any lookup happens. THEN FETCHED CONCURRENTLY: the lookups are
    # independent reads, so there is no reason to wait on one before starting the next.
    tenant = _tenant(principal)
    types = {template_type for template_type, _cls in GOAL_TEMPLATE.values()}
    # THE RAIL'S OWN "استُخدمت N مرة" / "N وصلهم" — a single-key side read (app.core.goal_stats),
    # never a scan of this tenant's whole campaign/run history. Read alongside the template
    # lookups above, not after them: an independent fact, no reason to wait on the other first.
    # `pick_for_preview`, NOT THE STRICT `pick` (2026-09-13) — the fields this card asks him to
    # fill (`fills`) must describe the SAME template `/preview` will actually render, which since
    # the preview-only fallback (services/reminders' own `preview_only`) can now be one Meta has
    # not approved yet. Using the strict, approval-only `pick` here left a goal whose template was
    # still under review with an empty middle of the screen — no service picker, no discount, no
    # end date — with nothing telling the owner why, even though `/preview` would happily show him
    # the words. `enabled` stays tied to `meta_approved` rather than "a row exists at all", so the
    # card still locks/unlocks exactly as before and the "never show available then refuse"
    # invariant (`test_goals_route_never_disagrees_with_preview.py`) holds — now against the exact
    # same read `/preview` performs, which is a STRONGER guarantee than two independently-timed
    # calls ever were.
    stats_row, rows = await asyncio.gather(
        read_goal_stats(c.datastore, tenant),
        asyncio.gather(*(c.templates.pick_for_preview(tenant, t) for t in types)))
    enabled: set[str] = set()
    fills: dict[str, list[str]] = {}
    for template_type, row in zip(types, rows):
        if row:
            if row.get("meta_approved", True):
                enabled.add(template_type)
            fills[template_type] = list(row.get("fills") or [])
    return {"goals": [vars(card) for card in
                      cards(fills_by_type=fills, enabled_types=enabled,
                            blocked_reasons=blocked, statuses=statuses, stats=stats_row)],
            # THE FILTER CHIPS' OWN ORDER — a rail/filter reads this rather than collecting each
            # card's own `category` and sorting them itself, which would reorder the moment a
            # category's first card changed or a goal moved buckets.
            "categories": GOAL_CATEGORIES}


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

    # `pick_for_preview` — NOT `pick` — because this screen is allowed to show the words even
    # before Meta has approved them (2026-09-13); `template.get("meta_approved")` says which.
    # `create()` below still calls the strict `pick`.
    template = await c.templates.pick_for_preview(_tenant(principal), spec["template_type"])
    if template is None:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={"error": "BAD_REQUEST",
                                     "reason": "لا يوجد قالب مفعّل لهذا الهدف — فعّله أولاً."})

    # SAME WINDOW RULE `/campaigns` (create) ENFORCES — checked here too, so a malformed window is
    # refused on the SCREEN HE IS LOOKING AT rather than only at the moment he presses launch.
    # EVERY GOAL MAY SET ONE (2026-09-12) — no goal-based restriction here any more.
    window_error = validate_window(start_hour=body.window_start_hour, end_hour=body.window_end_hour,
                                   weekdays=body.window_weekdays)
    if window_error:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={"error": "BAD_REQUEST", "reason": window_error})

    # «كافئ المخلصين»'s OWN THRESHOLDS — same "refused on the screen he is looking at" reasoning
    # as the window check above. Pydantic's own `ge`/`le` on the field already reject anything
    # wildly out of range; this is the coherence check same shape as `validate_window`'s own.
    loyalty_error = validate_loyalty_window(window_days=body.loyalty_window_days,
                                            min_visits=body.loyalty_min_visits)
    if loyalty_error:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={"error": "BAD_REQUEST", "reason": loyalty_error})

    # THE FULL MULTI-SELECT LIST (2026-09-13) — the owner may now name several services (or
    # several packages) under one offer; every one is joined into the same merged message at send
    # time (rendering.merged_service_text). `scope_service_ids` (the older, more general field) is
    # folded into whichever list applies.
    service_ids_all, service_names_all = _combine_ids_and_names(
        body.service_id, list(dict.fromkeys(body.service_ids + (
            body.scope_service_ids if body.goal != "package_offer" else []))),
        body.service_name, body.service_names)
    package_ids_all, package_names_all = _combine_ids_and_names(
        body.package_id, list(dict.fromkeys(body.package_ids + (
            body.scope_service_ids if body.goal == "package_offer" else []))),
        body.package_name, body.package_names)

    # THE CLASS THE CAMPAIGN WILL ACTUALLY BE SENT UNDER (ج-1). Not the resolver's default: the
    # preview exists to tell the owner what will happen, and a preview run under different rules
    # than the send is a number that is worse than no number.
    audience = await c.audience.resolve_for(
        _tenant(principal), goal=body.goal, now=_now(), cls=spec["cls"],
        already_reached=set(), service_id=body.service_id, service_ids=service_ids_all,
        branch_id=body.branch_id,
        window_days=body.loyalty_window_days, min_visits=body.loyalty_min_visits)

    try:
        p = build_preview(
            goal=body.goal, template=template,
            establishment=await c.identity.name(_tenant(principal)),
            owner_text=body.owner_text, audience=audience,
            offer_value=body.offer_value,
            ends_at=arabic_date(body.expires_at or 0),
            # NAMED BY THE CALLER, and it has to be: this service holds service/package IDS and
            # the catalogue belongs to operations. «خصم على svc_9f2» is not a message, and an empty
            # name makes the renderer refuse rather than send a hole in a sentence. `package_name`
            # takes over the SAME "catalogue" fill for `package_offer` — one blank kind, two doors.
            # SEVERAL NAMES JOIN WITH «، » — the preview's own merged sentence, the same shape
            # `rendering.merged_service_text` produces for the real send.
            service_text="، ".join(package_names_all or service_names_all),
            reward_type=body.reward_type if body.goal in REWARD_ENABLED_GOALS else "discount",
            reward_points=body.reward_points if body.goal in REWARD_ENABLED_GOALS else 0,
            when=describe_when(trigger=spec["trigger"],
                               inside_window=c.gate.inside_window(_now()),
                               own_window=window_sentence(
                                   start_hour=body.window_start_hour,
                                   end_hour=body.window_end_hour,
                                   weekdays=body.window_weekdays)))
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

    # THE MESSAGE MAY BE SHOWN EVEN WHILE IT CANNOT BE SENT — the owner's own instruction
    # (2026-09-13): a template still under Meta's review (or never submitted) is not yet a
    # sendable message, but its exact wording, its blanks, and the audience it would reach are
    # all real facts he can see and act on right now. Only the one thing this status actually
    # forbids — pressing launch — stays refused, by `create()`'s own guard below and by the
    # console reading this flag to grey the button out.
    out["template_active"] = bool(template.get("meta_approved", True))
    if not out["template_active"]:
        out["template_inactive_reason"] = "لا يوجد قالب مفعّل لهذا الهدف بعد — فعّله لتقدر تُطلق."

    # WHAT THE NUMBER DOES NOT INCLUDE, IN HIS WORDS. Two different truncations reach this screen
    # and until now neither was ever spoken: `truncated` means our own audience cap stopped the
    # count, `source_truncated` means operations could not hand over the whole customer book, so
    # the rule never saw the rest of his shop. Both were computed and both were dropped on the
    # floor here — `grep truncated` across every screen in the product returned nothing.
    #
    # An owner reading «تصل 4,300 عميلاً» has no way to know it might have been «5,000 من أصل
    # 9,000». Saying so costs one sentence and is the whole difference between a count and a
    # guess wearing a count's clothes.
    if getattr(audience, "source_truncated", False):
        out["audience_note"] = ("هذا العدد محسوبٌ من جزءٍ من عملائك — قاعدتك أكبر مما استطعنا "
                                "قراءته دفعةً واحدة. راجعنا قبل الإطلاق.")
    elif audience.truncated:
        out["audience_note"] = ("بلغت الحملة سقف الجمهور، فتوقّف العدّ عنده — هناك من ينطبق "
                                "عليه الشرط ولم يدخل هذه الحملة.")
    else:
        out["audience_note"] = ""

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

    # Validated BEFORE the campaign exists. Creating it and then refusing the text would leave a
    # draft the owner did not ask for, in a list they now have to clean.
    # THE STRICT `pick` — NEVER `pick_for_preview` — because a not-yet-approved row that only
    # `/preview` is allowed to show as a courtesy (2026-09-13) must stay None here regardless of
    # what the console sent: this is the one place that actually decides whether anything goes out.
    template = await c.templates.pick(_tenant(principal), spec["template_type"])
    if template is None:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={"error": "BAD_REQUEST",
                                     "reason": "لا يوجد قالب مفعّل لهذا الهدف — فعّله أولاً."})
    # THE FULL MULTI-SELECT LIST, SAME AS `/preview` (2026-09-13) — computed before sanitising so
    # every name in it (not only the singular ones) passes through the same filter below.
    service_ids_all, service_names_raw = _combine_ids_and_names(
        body.service_id, list(dict.fromkeys(body.service_ids + (
            body.scope_service_ids if body.goal != "package_offer" else []))),
        body.service_name, body.service_names)
    package_ids_all, package_names_raw = _combine_ids_and_names(
        body.package_id, list(dict.fromkeys(body.package_ids + (
            body.scope_service_ids if body.goal == "package_offer" else []))),
        body.package_name, body.package_names)

    try:
        from app.core.preview import sanitise_owner_text
        needs = any(f == "owner" for f in (template.get("fills") or []))
        clean = sanitise_owner_text(body.owner_text, required=needs)
        # SAME FILTER AS `owner_text` — fixed 2026-09-12, a real gap a QA audit found: this fills
        # the identical "catalogue" template variable and is stored verbatim into
        # `scope_service_names`, forwarded to reminders as `service_names` and rendered straight
        # into the customer-facing message at send time. A link or phone number here reached the
        # customer under the establishment's own approved template, the exact channel this
        # sanitiser exists to close. APPLIED TO EVERY NAME NOW, not only a single one — a
        # multi-select offer (2026-09-13) carries several, each named in the merged message.
        clean_service_names = [sanitise_owner_text(n, required=False) for n in service_names_raw]
        clean_package_names = [sanitise_owner_text(n, required=False) for n in package_names_raw]
    except PreviewError as exc:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={"error": "BAD_REQUEST",
                                     "reason": str(exc)})

    # ── package_offer needs EVERY chosen package to be a real, CURRENTLY OFFERABLE one ───────
    # CHECKED HERE, WHILE HE IS LOOKING AT THE SCREEN — the same "ask fresh, never assume" rule
    # HttpAudience.allows() already applies to the audience gate, and the same reason dispatch.fire()
    # asks again at every pass rather than trusting this answer forever: a package can be turned
    # off or fall outside its own schedule at any moment after this campaign is created. Checked
    # for EACH selected package (2026-09-13's own multi-select) — one unofferable package among
    # several is still a campaign that cannot honestly launch as configured.
    if body.goal == "package_offer":
        if not package_ids_all:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                                content={"error": "BAD_REQUEST",
                                         "reason": "اختر الباقة التي يخصّها هذا العرض."})
        offerable = getattr(c, "package_offerable", None)
        for pid in package_ids_all:
            if offerable is None or not await offerable.offerable(_tenant(principal), pid, now):
                return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                                    content={"error": "BAD_REQUEST",
                                             "reason": "إحدى الباقات المختارة غير متاحة الآن — "
                                                       "تحقّق من حالتها وجدولتها من «خدماتي "
                                                       "ومنتجاتي»."})

    # AN OFFER WITHOUT AN END IS A PRICE CHANGE NOBODY DECIDED ON — refused here, before anything
    # exists, and with the reason named. It is also what makes "this offer is yours" enforceable:
    # the send log says who received it, and this says until when. Without a date the operator at
    # the counter has nothing to check and the customer's own page has nothing to count down.
    #
    # REFUSED, NOT DEFAULTED. A silent "thirty days" would be a discount the shop never chose,
    # discovered a month later in the margin.
    # THE SANITISER'S ANSWER IS WHAT GETS STORED, not the raw field re-stripped at the call site.
    # It was validated here and then discarded, and three consumers each stripped `body.offer_value`
    # again — so the authority on this field had no say in what was written. Equal today, because
    # stripping is all it does beyond refusing; unequal the day it normalises anything else.
    #
    # AND IT STARTS EMPTY, WHICH IS THE PART THAT WAS A HOLE. A goal that offers nothing never
    # reaches the sanitiser, yet an `offer_value` sent with it was stored unvalidated — invisible
    # only because no such template has an `amount` slot to render it into.
    offer_value = ""
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

    # WHICH OF THREE REWARDS THIS CAMPAIGN GIVES — `REWARD_ENABLED_GOALS` only, for now; every
    # other goal still gives exactly the discount it always has, so this is skipped for them
    # rather than re-checking `offer_value` a second way.
    if body.goal in REWARD_ENABLED_GOALS:
        reward_error = validate_reward(
            reward_type=body.reward_type, reward_points=body.reward_points,
            # `package_offer` NAMES PACKAGES, NOT SERVICES — `service_ids_all` is empty for it, so
            # a "gift" reward would refuse even a properly-chosen package without this. Same split
            # the send itself already makes a few hundred lines down.
            scope_service_ids=(service_ids_all if body.goal != "package_offer"
                              else package_ids_all),
            offer_value=offer_value)
        if reward_error:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                                content={"error": "BAD_REQUEST", "reason": reward_error})

    # THE OWNER'S OWN WINDOW — EVERY GOAL MAY SET ONE (2026-09-12 correction; see
    # `Campaign.window_*`'s own note). Always optional, always coherence-checked regardless of
    # goal.
    window_error = validate_window(start_hour=body.window_start_hour, end_hour=body.window_end_hour,
                                   weekdays=body.window_weekdays)
    if window_error:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={"error": "BAD_REQUEST", "reason": window_error})

    loyalty_error = validate_loyalty_window(window_days=body.loyalty_window_days,
                                            min_visits=body.loyalty_min_visits)
    if loyalty_error:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={"error": "BAD_REQUEST", "reason": loyalty_error})

    # ── one press, one campaign ──────────────────────────────────────────────────────────────
    # See core/press.py for why. In short: everything that stops a customer receiving the same
    # thing twice is keyed on `campaign_id`, and this route minted a new one on every request —
    # so two presses of a button that gives no feedback for several seconds were two campaigns
    # that could not see each other, and the shop paid for both.
    press_key = press.key_for(
        _tenant(principal), goal=body.goal, owner_text=clean, service_id=body.service_id or "",
        branch_id=body.branch_id or "", offer_value=body.offer_value or "",
        expires_at=body.expires_at or 0, fire_at=body.fire_at or 0,
        package_id=body.package_id or "", window_start_hour=body.window_start_hour,
        window_end_hour=body.window_end_hour, window_weekdays=body.window_weekdays)
    taken = await press.claim(c.datastore, _tenant(principal), press_key, now=now)
    if not taken.first:
        if taken.in_flight:
            # THE FIRST PRESS IS STILL SENDING. Refused rather than duplicated, and refused in his
            # words: 409 is «this is already happening», not «you did something wrong».
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={"error": "IN_PROGRESS",
                         "reason": "حملتك قيد الإطلاق الآن — انتظر قليلاً ثم حدّث الصفحة."})
        existing = await c.datastore.get("campaigns", f"{_tenant(principal)}|{taken.campaign_id}")
        if existing:
            # THE SAME CAMPAIGN, NOT A SECOND ONE, and no send. He gets the answer he would have
            # got the first time, which is what he was pressing for.
            return {"campaign": existing, "run": None, "behaviour": spec["behaviour"],
                    "duplicate": True}

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
                        # STORED THE SAME WAY, for the SAME reason — dispatch.fire() re-asks
                        # whether this exact package is still offerable on every pass, reading it
                        # off the row (container.py `_resolver`'s sibling check), never off
                        # whatever was true the moment this campaign was created.
                        package_id=(body.package_id or "").strip(),
                        branch_id=(body.branch_id or "").strip(),
                        offer_value=offer_value,
                        # `REWARD_ENABLED_GOALS` only, for now — every other goal's default
                        # ("discount", 0) simply reproduces today's behaviour, unchanged.
                        reward_type=body.reward_type if body.goal in REWARD_ENABLED_GOALS
                        else "discount",
                        reward_points=body.reward_points if body.goal in REWARD_ENABLED_GOALS
                        else 0,
                        window_start_hour=body.window_start_hour,
                        window_end_hour=body.window_end_hour,
                        window_weekdays=list(body.window_weekdays or []),
                        # STORED THE SAME WAY, for the SAME reason — dispatch.fire() re-resolves
                        # the audience on every pass from the STORED thresholds (container.py
                        # `_resolver`), never from whatever was true the moment the owner pressed
                        # preview. Meaningless for every goal but `reward_loyal`.
                        loyalty_window_days=body.loyalty_window_days,
                        loyalty_min_visits=body.loyalty_min_visits,
                        # EVERY CHOSEN NAME, empties dropped (a name that sanitised to "" — never
                        # sent in the first place — is not named). SEVERAL, since 2026-09-13: one
                        # per selected service or package, in the order chosen — the same order
                        # the merged message names them in.
                        scope_service_names=([n for n in clean_service_names if n] or
                                             [n for n in clean_package_names if n]),
                        # THE TARGETED SERVICES/PACKAGES ARE ALWAYS IN THEIR OWN SCOPE (2026-09-13:
                        # now the full multi-select list, not only one forced in). `service_offer`
                        # reaches people who are 70% through their cycle for at least one of them;
                        # an offer that arrived because of a service and then did not cover it
                        # would be the cruellest version of this feature. `package_offer` has no
                        # cycle lock of its own, so its own chosen ids simply ARE the scope.
                        scope_service_ids=(service_ids_all if body.goal != "package_offer"
                                          else package_ids_all))

    await request.app.state.auditor.record(
        "campaign.created", actor=principal.subject, tenant=_tenant(principal),
        resource=f"campaign:{campaign.id}", ip=request.client.host if request.client else "")
    await c.datastore.put("campaigns", campaign.key, as_row(campaign))
    # THE CLAIM NOW NAMES A CAMPAIGN THAT EXISTS. Settled here rather than at the end, because
    # what a second press must be given back is the CAMPAIGN — a crash during the send must not
    # leave the claim pointing at nothing while the row is on disk.
    await press.settle(c.datastore, _tenant(principal), press_key, campaign.id, now=now)
    # THE RAIL'S OWN "استُخدمت N مرة" — a side counter, never a scan of this tenant's whole
    # campaign history (see app.core.goal_stats's own docstring, same move `record_lock` already
    # made). Counted here, once, on an actual creation — never on a re-press the idempotency claim
    # above already resolved to the SAME campaign.
    await record_use(c.datastore, campaign.tenant, campaign.goal)

    # A FUTURE `fire_at` — ANY GOAL NOW, not only «مناسبة عميلك» (2026-09-12). Best-effort handed
    # to job-service (platform/services/job-service) so it fires close to the exact moment
    # instead of waiting on this service's own 15-minute scan to notice the day arrived. Never
    # BLOCKS creation: `NullJobService`/any transport failure here is swallowed, because
    # `tick.py`'s own scan (`_one`'s manual-rescue branch, which now itself refuses to touch a
    # campaign while `fire_at > now`) remains the correct fallback the moment the scheduled time
    # actually passes — the same safety net this feature relied on before job-service existed,
    # unchanged, just less prompt without it.
    if campaign.fire_at and campaign.fire_at > now:
        try:
            await c.jobs.enqueue(queue="campaigns", tenant=campaign.tenant, type="campaigns.fire",
                                 payload={"campaign_id": campaign.id},
                                 delay_seconds=campaign.fire_at - now,
                                 unique_key=f"cmp-fire:{campaign.id}")
        except Exception:      # noqa: BLE001 — best-effort; the tick-scan fallback still applies
            pass
        return {"campaign": as_row(campaign), "run": None, "behaviour": spec["behaviour"]}

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
        # STAMPED ONLY WHEN THE PASS ACTUALLY FINISHED (2026-09-12 correction — see
        # `DispatchResult.finished`'s own note in dispatch.py). `tick._one` rescues a manual
        # campaign that was written and never fired — a pod evicted between the `put` above and
        # this send used to strand it at `active` for ever. That rescue is keyed on
        # `last_evaluated == 0`, so a campaign that DID finish has to say so here, or the next
        # tick would send it all over again.
        #
        # BUT A CAMPAIGN CREATED OUTSIDE ITS OWN WINDOW (`Campaign.window_*`) ALSO COMES BACK
        # `finished=False` from this very first inline call — and stamping `last_evaluated` here
        # regardless, as this route used to, silenced the rescue for exactly the campaigns that
        # most need it: it would never fire again, not at the next tick and not ever, since
        # nothing else re-opens `last_evaluated` back to 0. Leaving it untouched instead means
        # the ordinary 15-minute tick keeps retrying — through `_one`'s own manual-rescue branch —
        # until the window opens (or, for the pre-existing large-audience case, until this same
        # first pass eventually completes).
        if out.finished:
            row = as_row(campaign)
            row["last_evaluated"] = now
            await c.datastore.put("campaigns", campaign.key, row)

    return {"campaign": as_row(campaign), "run": fired,
            "behaviour": spec["behaviour"]}


@router.get("", dependencies=[Depends(rate_limit)])
async def list_campaigns(request: Request, state: str = "",
                         principal: Principal = Depends(_READ)) -> dict:
    where = {"tenant": principal.tenant}
    if state:
        where["state"] = state
    # DRAINED, NOT PAGE-ONE-AND-COUNT — fixed 2026-09-12, a real gap
    # ci/check_a_discarded_cursors_page_is_not_counted.py found: the old `limit=200` read discarded
    # its cursor and reported `len(rows)` as `count` anyway, so a shop past 200 campaigns (own
    # standing rules plus every scheduled/paused one, which never move to state=done) saw a count
    # that quietly stopped moving.
    rows = await drain(request.app.state.container.datastore, "campaigns", where,
                       sort=("created", "desc"))
    return {"campaigns": rows, "count": len(rows)}


@router.get("/{campaign_id}/runs", dependencies=[Depends(rate_limit)])
async def runs(request: Request, campaign_id: str,
               principal: Principal = Depends(_READ)) -> dict:
    """Every firing, newest first, each with its own reasons.

    NOT AGGREGATED. Forty runs are forty questions, and an owner asking why it reached nobody last
    Tuesday needs Tuesday — the totals are a separate field for the one place a total belongs.
    """
    # DRAINED, NOT PAGE-ONE-AND-STOP — a manually-confirmed companion to the `list_campaigns` fix
    # just above: a standing campaign past 200 firings used to have every run before its most
    # recent 200 permanently unreachable through this route, with no cursor exposed to page
    # further and no signal that anything was missing.
    rows = await drain(request.app.state.container.datastore, "campaign_runs",
                       {"tenant": principal.tenant, "campaign_id": campaign_id}, sort=("at", "desc"))

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


_AR_MONTHS = ("يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
              "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر")


def arabic_date(epoch: int) -> str:
    """The last day, as a person reads it — in Riyadh, because an offer ending at 01:00 UTC ends
    the previous evening for whoever is reading the message."""
    if not epoch:
        return ""
    from datetime import datetime, timedelta, timezone
    d = local(epoch)
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
