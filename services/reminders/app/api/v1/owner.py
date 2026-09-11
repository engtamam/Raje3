"""The owner's surface: what is coming, what happened, and why something did not.

FOUR ROUTES, AND THE MOST IMPORTANT ONE IS THE LOG. Every other screen on this product shows what
happened; this one has to show what DIDN'T, with the reason. "Why didn't my customer get the
message?" is the only support question this service generates, and a screen that cannot answer it
turns every rule we wrote into a suspected bug.
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from app.api.auth import Principal
from app.api.authz import require_capability
from app.adapters.branch_scope import DENIED
from app.api.ratelimit import rate_limit
from app.core.reach import Reach
from app.core.spent import SpentUnknown, spent_refs
from app.core import rendering as R
from app.core.stores import RuleStore, ScheduleStore, SendLogStore, _sched_key
from app.api.subscribed import no_subscription_needed, subscribed_write


def _ops_url(request: Request) -> str:
    """Where operations lives. Read off settings at call time, never captured at import — the
    container is what a test replaces, and a module-level copy would ignore it."""
    from app.config import get_settings
    return get_settings().OPERATIONS_SERVICE_URL


def _ops_token(request: Request) -> str:
    from app.config import get_settings
    return get_settings().INTERNAL_SERVICE_TOKEN

router = APIRouter(prefix="/reminders", tags=["reminders"])

_READ = require_capability("reminders.read")
_MANAGE = require_capability("reminders.manage")

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



@router.get("/schedule", dependencies=[Depends(rate_limit)])
async def list_schedule(request: Request, state: str = Query(default="pending"),
                        limit: int = Query(default=50, ge=1, le=200),
                        principal: Principal = Depends(_READ)) -> dict:
    """What is coming, soonest first.

    Returns the pseudonym, not a customer name — this service has no names. The console joins
    against operations for display, which keeps the identifier in one place instead of two.
    """
    store = ScheduleStore(request.app.state.container.datastore)
    rows, _ = await store._find(_tenant(principal), {"state": state} if state else None,
                                limit=limit, sort=("due_at", "asc"))
    return {"schedule": rows, "count": len(rows)}


@router.delete("/schedule/{schedule_key:path}", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def cancel(request: Request, schedule_key: str,
                 principal: Principal = Depends(_MANAGE)) -> dict:
    """Cancel one pending reminder.

    Cancels the message, NOT the rule. The next visit schedules a new one — which is what an owner
    almost always means, and the thing they would be surprised by if we did the other.
    """
    store = ScheduleStore(request.app.state.container.datastore)
    row = await store.get(schedule_key)
    key = schedule_key

    # ── AN ID IS ALSO A HANDLE ────────────────────────────────────────────────────────────────
    # THE BUTTON NEVER WORKED, FROM THE DAY IT WAS BUILT. This route takes the NATURAL key —
    # «tenant|subject|service|kind» — while every list this service answers with carries `id`
    # («sch_66eba7…»), which is what a screen has to send. Every «أوقفها» press was a 404, and the
    # row stayed pending: an owner stopping a message he did not want watched it go out anyway.
    #
    # THE ID IS RESOLVED, NOT ACCEPTED BLINDLY. It is looked up inside the caller's own tenant, so
    # an id belonging to another establishment finds nothing here rather than being cancelled.
    if row is None:
        found, _ = await store._find(_tenant(principal), {"id": schedule_key}, limit=1)
        if found:
            row = found[0]
            key = _sched_key(row)

    # THE TENANT CHECK IS EXPLICIT, because this key comes off the request. The store prefixes keys
    # by tenant, so a forged key from another establishment cannot be read — but relying on a key
    # format for authorisation is relying on a convention, and this makes it a check.
    if row is None or row.get("tenant") != _tenant(principal):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    await request.app.state.auditor.record(
        "reminders.schedule_cancelled", actor=principal.subject, tenant=_tenant(principal),
        resource=f"schedule:{row.get('id','')}",
        ip=request.client.host if request.client else "")
    row["state"] = "cancelled"
    row["reason"] = "ألغاه المالك"
    await store.upsert(_tenant(principal), key, row)
    return {"cancelled": True, "id": row.get("id", "")}


@router.get("/rules", dependencies=[Depends(rate_limit)])
async def list_rules(request: Request, service_id: str = Query(default=""),
                     subject_ref: str = Query(default=""),
                     principal: Principal = Depends(_READ)) -> dict:
    """The learned interval per customer and service.

    `learned` is reported separately from the number itself. An owner told "learned: 90 days" from
    zero observations stops trusting every number on the screen — so an estimate that is still the
    service's default says so.
    """
    from app.config import get_settings
    from app.core.adaptive import AdaptiveConfig, is_learned
    cfg = AdaptiveConfig(warmup=get_settings().ADAPTIVE_WARMUP_OBSERVATIONS)
    store = RuleStore(request.app.state.container.datastore)
    # BY CUSTOMER AS WELL AS BY SERVICE — which is what his own page needed. A rule is learned per
    # (customer, service), and «هذا العميل يعود كل 47 يوماً» is the sentence §5.2 promises and no
    # screen could ask for, because the only filter here was the service.
    if subject_ref:
        rows, _ = await store._find(_tenant(principal), {"subject_ref": subject_ref},
                                    limit=100, sort=("updated", "desc"))
    elif service_id:
        rows = await store.for_service(_tenant(principal), service_id)
    else:
        rows = (await store._find(_tenant(principal), limit=200, sort=("updated", "desc")))[0]
    for r in rows:
        r["learned"] = is_learned(int(r.get("observations") or 0), cfg)
    return {"rules": rows, "count": len(rows)}


class RuleIn(BaseModel):
    # Bounded at the model, not only in the engine. A rule set to 4000 days is not a slow reminder,
    # it is a reminder that never arrives — and the owner would never know which.
    interval_days: float = Field(ge=1, le=1095)
    lead_days: float = Field(default=7, ge=0, le=60)


@router.put("/rules/{rule_key:path}", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def set_rule(request: Request, rule_key: str, body: RuleIn,
                   principal: Principal = Depends(_MANAGE)) -> dict:
    """Override a learned interval.

    THE OVERRIDE STOPS THE LEARNING for that customer and service, and says so in the response.
    Silently resuming adaptation would walk the owner's number back toward the observed rhythm over
    the next few visits, and they would conclude the setting does not work.
    """
    store = RuleStore(request.app.state.container.datastore)
    row = await store.get(rule_key)
    if row is None or row.get("tenant") != _tenant(principal):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    await request.app.state.auditor.record(
        "reminders.rule_changed", actor=principal.subject, tenant=_tenant(principal),
        resource=f"rule:{row.get('id','')}", ip=request.client.host if request.client else "")
    row["interval_days"] = body.interval_days
    row["lead_days"] = body.lead_days
    row["pinned"] = True
    await store.upsert(_tenant(principal), rule_key, row)
    return {"rule": row, "adaptation": "paused",
            "note": "الفترة مثبّتة الآن ولن يعدّلها النظام تلقائياً."}


class OutsideHisBranch(Exception):
    """The caller may not read this customer's messages. Carries the sentence the screen shows."""

    def __init__(self, unavailable: str = "") -> None:
        self.unavailable = unavailable


async def _branch_scope(container, principal) -> frozenset[str]:
    """The branches this caller may read — EMPTY MEANS ALL OF THEM, never «none».

    THREE ROUTES READ THE SEND LOG AND ONE OF THEM CHECKED (ط-4). `/log` resolved the scope; the
    two routes that answer «what has this customer been sent» — `/offer` and `/offers` — took a
    `subject_ref` and nothing else. A marketing supervisor scoped to Jeddah needed one pseudonym to
    read the text of every message Riyadh sent that customer, its offer code and its value: the
    same data the guarded route refuses him, through a door beside it.

    A guard that protects the route somebody remembered is not a guard on the data. So the
    resolution lives here, once, and each reader calls it — the next route that reads this
    collection finds the check already written and named.
    """
    resolver = getattr(container, "branch_scope", None)
    if resolver is None:
        return frozenset()
    scope = await resolver.scope(_tenant(principal), getattr(principal, "subject", "") or "")
    if scope in DENIED:
        # «WE COULD NOT CHECK» IS NOT «NO LIMIT», and a stopped employee refuses here too.
        raise OutsideHisBranch("تعذّر التحقق من صلاحيتك على الفروع الآن. أعد المحاولة بعد قليل.")
    # A SET, EVEN WHEN THE ANSWER IS ONE BRANCH. Where a man WORKS is one place; what he may SEE is
    # a list, and the two were the same field for as long as an owner had no way to say otherwise —
    # so «مشرف يعمل في الملز ويتابع أربعة» could not be expressed at all. Normalising here means the
    # readers below ask MEMBERSHIP, and the day the wire carries four branches not one of them
    # changes: an equality test would have kept working, silently showing him one.
    return frozenset({scope}) if scope else frozenset()


def _in_scope(row: dict, scope: frozenset[str]) -> bool:
    """Whether one send-log row belongs to a branch this caller may read."""
    return not scope or str(row.get("branch_id") or "") in scope


@router.get("/log", dependencies=[Depends(rate_limit)])
async def send_log(request: Request, outcome: str = Query(default=""),
                   branch_id: str = Query(default="", max_length=64),
                   subject_ref: str = Query(default="", max_length=128),
                   limit: int = Query(default=100, ge=1, le=500),
                   principal: Principal = Depends(_READ)) -> dict:
    """What was sent, and what was not, with the reason.

    THE SUPPRESSIONS ARE THE POINT. This is the screen that answers the only question this service
    generates, and it is why every refusal in the gate returns a sentence rather than a code.

    AND IT NARROWS BY BRANCH, which is the whole reason the rows carry one. An owner with three
    branches reading one list of everything cannot answer «ما الذي خرج باسم فرع جدة؟» — the
    question he actually has. `_none` selects the rows with no branch at all: they are a real
    group (campaigns, and shops that label nothing), and folding them into "everything" is how
    they stop being visible as a gap worth closing.
    """
    c = request.app.state.container

    # WHOSE MESSAGES MAY HE READ — asked before the query is built, not after.
    #
    # THE HOLE THIS CLOSES: the filter took whatever branch the CALLER typed, so a manager assigned
    # to Jeddah read every message that went out in Riyadh's name by changing one query parameter.
    # On the one screen this service exists to provide, about the one thing a shop is most
    # sensitive about — what was said to its customers, in its name.
    try:
        scope = await _branch_scope(c, principal)
    except OutsideHisBranch as refused:
        # «WE COULD NOT CHECK» IS NOT «NO LIMIT». Refusing costs him the log for a minute;
        # guessing shows him somebody else's.
        #
        # AND A STOPPED EMPLOYEE REFUSES HERE TOO. His membership is revoked the moment the owner
        # stops him, so no token of his should reach this line at all — but if one is still in
        # flight, an inactive row used to answer «no branch», which read as «every branch». The
        # sentence is deliberately the same: neither state entitles him to somebody's messages.
        return {"log": [], "count": 0, "unavailable": refused.unavailable}

    store = SendLogStore(c.datastore)
    where: dict[str, str] | None = {"outcome": outcome} if outcome else None

    # ── ONE CUSTOMER'S MESSAGES, WHEN ONE CUSTOMER IS ASKED ABOUT ────────────────────────────
    #
    # THE CUSTOMER PAGE HAS ALWAYS SENT THIS, and this route never declared it — so FastAPI
    # dropped it in silence and answered with the WHOLE SHOP'S log, which the screen then printed
    # under one man's name, headed «رسائله». The owner read other customers' messages believing
    # they were his, and answered «لماذا لم تصلني رسالة؟» from a history that was not the asker's.
    #
    # Nothing failed anywhere: 200, a full list, a fast screen. The only way to see it was to know
    # both sides at once.
    if subject_ref:
        where = {**(where or {}), "subject_ref": subject_ref}
    if len(scope) == 1:
        # HIS OWN BRANCH, AND THE PARAMETER IS IGNORED. Not refused — a bookmark carrying another
        # branch is a stale link, not an attack, and answering it with his own rows is both the
        # safe reading and the useful one.
        #
        # PUSHED INTO THE QUERY ONLY WHEN IT IS ONE. A `where` clause is an equality and cannot say
        # «any of these four», so a man who watches several is filtered below instead — the same
        # answer, read at the cost of a wider page.
        where = {**(where or {}), "branch_id": next(iter(scope))}
    elif not scope and branch_id:
        where = {**(where or {}), "branch_id": "" if branch_id == "_none" else branch_id}
    rows, _ = await store._find(_tenant(principal), where, limit=limit, sort=("at", "desc"))
    # THE SECOND HALF OF THE SAME GUARD, for the caller who may see more than one branch. It is a
    # no-op for everybody else, and it is what stops the widened scope from becoming an unfiltered
    # one the day a supervisor is given his second branch.
    rows = [r for r in rows if _in_scope(r, scope)]
    # The visit-idempotency markers live in this collection (see core/scheduling.py) and are not
    # messages. Showing them would put rows in an owner's log that mean nothing to them.
    rows = [r for r in rows if r.get("subject_ref") != "_visit_marker"]
    return {"log": rows, "count": len(rows)}


# ── the reasons: what goes out in his name, and whether it goes at all ───────────────────────
class ReasonIn(BaseModel):
    """Two decisions, both optional — an owner switching one off has not asked to change its text.

    `None` MEANS "LEAVE IT". A model that required both would make every switch a two-field
    decision, and a screen sending the current value back would race with a change made on his
    phone a second earlier.
    """

    on: bool | None = None
    # His own approved template for this reason. Empty string means "back to ours", which is a
    # deletion rather than a stored blank — see ChoiceStore.set.
    template: str | None = Field(default=None, max_length=512)


@router.get("/reasons", dependencies=[Depends(rate_limit)])
async def list_reasons(request: Request, principal: Principal = Depends(_READ)) -> dict:
    """Everything that sends in this shop's name, with his answers folded in.

    THE SCREEN HAD NOTHING TO SHOW BEFORE THIS. «رسائلي» listed the send log and the campaigns —
    so the one question an owner actually has, «ما الذي يخرج باسمي، ومتى؟», had no answer anywhere
    in the product, and the only way to stop a message was to cancel it one row at a time.

    EACH ROW NOW CARRIES ITS OWN APPROVAL STATUS (`template_status`) — the same picture the
    admin panel's own template screen shows, surfaced here instead of hidden behind a modal a
    person has to open one row at a time to learn a fact that decides whether it sends at all.
    """
    from app.core.reason_choices import ChoiceStore
    from app.core import reasons as TR
    c = request.app.state.container
    choices = await ChoiceStore(c.datastore).load(_tenant(principal))
    rows = choices.public()
    library = await c.library.all()
    statuses = await c.approved_templates.statuses(_tenant(principal))
    for row in rows:
        reason = TR.get(str(row.get("id") or ""))
        row["template_status"] = (
            R.type_status(reason.template_type, library=library, statuses=statuses)
            if reason else "unknown")
    return {"reasons": rows}


@router.put("/reasons/{reason_id}", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def set_reason(request: Request, reason_id: str, body: ReasonIn,
                      principal: Principal = Depends(_MANAGE)) -> dict:
    """Switch one on or off, or point it at his own text.

    REFUSES RATHER THAN STORING WHAT IT WILL IGNORE. A privacy code is not his to silence, and a
    stored setting that does nothing is the shape of every "I turned it off and it kept sending"
    call this product will ever get.
    """
    from app.core.reason_choices import ChoiceStore
    await request.app.state.auditor.record(
        "reminders.rule_changed", actor=principal.subject, tenant=_tenant(principal),
        resource=f"reason:{reason_id}", ip=request.client.host if request.client else "")
    store = ChoiceStore(request.app.state.container.datastore)
    try:
        choices = await store.set(_tenant(principal), reason_id,
                                  on=body.on, template=body.template)
    except ValueError as exc:
        # RETURNED, NOT RAISED. The platform's handler strips an HTTPException's detail, and the
        # sentence is the whole answer here.
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "reasons": choices.public()}


# ── the rating app's own settings — read on every visit's send decision ───────────────────────
# `enabled` and `delay_minutes` feed `_rating_eligible`/`_message_delay_seconds` (api/internal.py);
# `points` feeds tick.py's `rating_points` (the participation line rendered into the message
# itself). All three are live, not placeholders — a shop that owns the app and toggles this off
# gets the plain confirmation on its very next visit, not "eventually".
class RatingSettingsIn(BaseModel):
    """Three knobs, all optional — `None` means "leave it", same rule `ReasonIn` uses above."""

    enabled: bool | None = None
    delay_minutes: int | None = Field(default=None, ge=1, le=7 * 24 * 60)
    points: int | None = Field(default=None, ge=0, le=10_000)


@router.get("/rating_settings", dependencies=[Depends(rate_limit)])
async def get_rating_settings(request: Request, principal: Principal = Depends(_READ)) -> dict:
    from app.core.rating_settings import RatingSettingsStore
    settings = await RatingSettingsStore(request.app.state.container.datastore).load(_tenant(principal))
    return settings.public()


@router.put("/rating_settings", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def set_rating_settings(request: Request, body: RatingSettingsIn,
                              principal: Principal = Depends(_MANAGE)) -> dict:
    from app.core.rating_settings import RatingSettingsStore
    await request.app.state.auditor.record(
        "reminders.rating_settings_changed", actor=principal.subject, tenant=_tenant(principal),
        resource="rating_settings", ip=request.client.host if request.client else "")
    store = RatingSettingsStore(request.app.state.container.datastore)
    try:
        settings = await store.set(_tenant(principal), enabled=body.enabled,
                                   delay_minutes=body.delay_minutes, points=body.points)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, **settings.public()}


async def _template_options(c, template_type: str, establishment: str, *, tenant: str) -> tuple[list[dict], dict]:
    """Every wording OUR library holds for one template type, rendered with example values.

    THE SHARED HALF OF THE PREVIEW — pulled out of `preview_reason` so a goal with no reason (see
    `preview_by_type` below) reads the exact same library, the exact same renderer, and the exact
    same «approved on his number» check, rather than a second, drifting copy of all three.
    """
    from app.core import reasons as TR

    # READ, NOT JUST FETCHED. `all()` answers `[]` for a library it could not reach exactly as it
    # does for one with nothing in it, and the screen turned that single emptiness into «القوالب
    # تُراجَع لدى واتساب» — a cause it had no evidence for, and reassurance in the two cases that
    # needed a report instead.
    shelf = await c.library.read()
    library = shelf.get("templates") or []

    options: list[dict] = []
    for row in library:
        if row.get("type") != template_type or not row.get("active", True):
            continue
        try:
            # ONE DICT, PASSED AS ALL THREE — the same shape `tick.py`'s real send already uses
            # (see its own comment). This used to pass `catalogue={}, owner={}` and no link at
            # all: `sample_slots()` computes a plausible sample for EVERY source kind (catalogue,
            # owner, stop_link, ...), but `render()` reads catalogue/owner/link fills from their
            # OWN separate arguments, never from `system` — so every one of those slots raised and
            # the whole option silently vanished. Found live: every marketing template (mandatory
            # `stop_link` tail) and both awareness/warning templates (`owner`/`catalogue` fills)
            # disappeared from every reason's preview, for a mismatch that had nothing to do with
            # Meta review or the template's own text.
            system = TR.sample_slots(row, establishment=establishment)
            rendered = R.render(template=row, system=system, catalogue=system, owner=system,
                                public_base_url=TR._SAMPLE_BASE, reference=TR._SAMPLE_REF)
        except R.RenderError:
            # A TEXT WE CANNOT RENDER IS NOT OFFERED. Listing it would let him choose a wording
            # that silently never sends — the failure this whole preview exists to make visible.
            continue
        body = row.get("body", "")
        for i, value in enumerate(rendered.variables, start=1):
            body = body.replace("{{" + str(i) + "}}", value)
        option = {"name": row.get("name", ""), "tone": row.get("tone", ""),
                 "text": body, "mine": False,
                 # AND THE SHAPE THE EXAMPLE CAME FROM. Reading the sheet: «العميل
                 # يقرأ الرسالة ما يعرف وين الفراغات». A filled example is what his
                 # customer receives; it is not what the message IS. Without the blanks he
                 # cannot tell which words are his shop's forever and which change per
                 # person — and if he wants to write his own he has no idea where the
                 # blanks go.
                 "template": _with_named_blanks(row),
                 # CAN THIS ONE ACTUALLY GO OUT TODAY — asked of the account, not assumed.
                 # `approved` is filled below in one read rather than one per row.
                 "approved": None, "status": "", "reason": ""}
        # THE BUTTON META ACTUALLY SENDS, SURFACED — not just read. `row["button"]` (the visible
        # label) and `row["flow_button"]` (which Flow it opens, by stable flow_name — see the
        # rating template's own seed comment) have always been on this row; nothing before this
        # ever put them where an owner deciding on a wording could see them. Only a genuine
        # Flow-carrying row gets one — `button` sits blank on every ordinary template, and a
        # blank label is not a button.
        if row.get("flow_button") and row.get("button"):
            # `flow_name` RIDES ALONG NOW, not just the label — «رسائلي»'s own interactive
            # preview (WhatsAppTemplatePreview, rj-ui) needs the Flow's registered name to fetch
            # its real generated screens; the label alone was enough to show a button existed,
            # never enough to open it.
            option["buttons"] = [{"label": row["button"], "kind": "flow",
                                  "flow_name": (row["flow_button"] or {}).get("flow_name", "")}]
        options.append(option)

    # WHAT META HAS ACTUALLY APPROVED ON HIS NUMBER. `None` from this reader means NOT KNOWN —
    # notification-service unreachable or not configured — and not-known must never be rendered as
    # a verdict. The screen shows no badge at all in that case, because «not ready» and «we could
    # not ask» are different sentences and only one of them is about him.
    approved_names = await c.approved_templates.names(tenant)
    if approved_names is not None:
        for option in options:
            option["approved"] = option["name"] in approved_names

    return options, shelf


@router.get("/templates/by-type/{template_type}/preview", dependencies=[Depends(rate_limit)])
async def preview_by_type(request: Request, template_type: str,
                          principal: Principal = Depends(_READ)) -> dict:
    """The same preview as `preview_reason`, for a campaign GOAL with no reasons-registry
    counterpart at all.

    THE ASYMMETRY THIS FIXES. Only three of «حملاتي»'s eight goals share a reason id
    (`win_back`/`occasion`/`reward_loyal`, via Launch.tsx's own `GOAL_REASON_ID`), and only those
    three ever got «اعرض نص هذه الرسالة، أو عدّله». The other five — announce, awareness,
    seasonal_care, service_offer, package_offer — have no reason to preview by, so they never got
    the modal at all. This route asks by template TYPE instead, which every goal already carries
    (campaigns/app/core/models.py's own `GOAL_TEMPLATE`).

    NO `reason`, NO `mine`, NO `chosen` — there is no reason row to attach his own texts or his
    switch to; those stay reachable through «متى نرسل» for the three that DO have one. A goal whose
    type has no active template at all (`awr_seasonal_care` — none seeded yet) answers with an
    empty `options` list and `empty_because`, exactly like an unwritten reason would.
    """
    c = request.app.state.container
    shop = await c.identity.get(_tenant(principal))
    establishment = getattr(shop, "name", "") or "محلّك"
    options, shelf = await _template_options(c, template_type, establishment,
                                             tenant=_tenant(principal))
    empty_because = ""
    if not options:
        read_ok = bool(shelf.get("ok"))
        empty_because = "unread" if not read_ok else "none"
    return {"options": options, "chosen": "", "empty_because": empty_because,
            "tone": getattr(shop, "tone", "") or "warm"}


@router.get("/reasons/{reason_id}/preview", dependencies=[Depends(rate_limit)])
async def preview_reason(request: Request, reason_id: str,
                          principal: Principal = Depends(_READ)) -> dict:
    """The three wordings of this message, as the customer will read them.

    RENDERED BY THE ENGINE, NOT BY THE SCREEN. It goes through the same `render()` a send goes
    through, with example values — so a wording that cannot render is one he cannot choose, and
    what he reads here is what leaves the building. A screen that assembled the text itself would
    show a message that works on his phone and fails on the customer's.

    HIS OWN APPROVED TEXTS COME BACK BESIDE OURS, in the same shape and marked as his. This is the
    list «رسائلي» offers him: three of ours, and whatever he has written and Meta approved.
    """
    from app.core import reasons as TR
    from app.core.custom_templates import APPROVED, CustomTemplateStore
    from app.core.reason_choices import ChoiceStore

    reason = TR.get(reason_id)
    if reason is None:
        return {"ok": False, "error": "لا يوجد داعٍ للإرسال بهذا الاسم."}

    c = request.app.state.container
    shop = await c.identity.get(_tenant(principal))
    establishment = getattr(shop, "name", "") or "محلّك"
    options, shelf = await _template_options(c, reason.template_type, establishment,
                                             tenant=_tenant(principal))

    mine = await CustomTemplateStore(c.datastore).list(_tenant(principal), reason_id=reason_id)
    for row in mine:
        # EVERY TEXT HE WROTE, WHATEVER ITS STATE — reading the screen as the owner would:
        # «مو المفروض الصيغ والرسائل تكون ظاهرة له؟». They were filtered to APPROVED only, so a
        # text he wrote and Meta REFUSED simply vanished: no wording, no reason, nothing to fix. He
        # writes it again, it is refused again, and the product never says why.
        #
        # His own row carries Meta's verdict verbatim in `reason` — never re-worded, because a
        # refusal he cannot read is a refusal he cannot answer.
        options.append({"name": row.get("name", ""), "tone": "", "mine": True,
                        "status": row.get("status", ""), "reason": row.get("reason", ""),
                        "approved": row.get("status") == APPROVED,
                        # HIS OWN WORDS WITH THE BLANKS SHOWN FILLED, by what each blank MEANS —
                        # his numbering is his, not the library's.
                        "text": _fill_custom(row, establishment=establishment),
                        "template": _with_named_blanks(row)})

    chosen = (await ChoiceStore(c.datastore).load(_tenant(principal))).template_name(reason_id)
    # WHY THE LIST IS EMPTY, WHEN IT IS — because there are three reasons and they belong to three
    # different people.
    #
    #   unread   we could not read our own library. His to be told about, ours to fix, and Meta
    #            has nothing to do with it.
    #   none     read, and we ship no active wording for this reason. Our gap, not a wait.
    #   pending  he wrote his own and it is genuinely at Meta — the ONLY case the old sentence
    #            described, and it was shown for all three.
    #
    # THE SCREEN IS TOLD THE STATE, NOT THE SENTENCE. Wording belongs where the reader is, and a
    # state travels safely through a version skew that a translated sentence does not.
    waiting = any(row.get("status") != APPROVED for row in mine)
    empty_because = ""
    if not options:
        # NO DEFAULT ON `ok`. `.get("ok", True)` would read an answer that never carried the field
        # — an adapter changed under us, a driver that predates `read()` — as a successful read,
        # and the empty list would then be reported to the owner as our gap rather than as an
        # unread. Absent is treated as unread, which costs a truthful «حاول بعد قليل» and never a
        # sentence about a shelf nobody looked at.
        read_ok = bool(shelf.get("ok"))
        empty_because = "unread" if not read_ok else ("pending" if waiting else "none")
    return {"reason": TR.public(reason), "options": options, "chosen": chosen,
            "empty_because": empty_because,
            "tone": getattr(shop, "tone", "") or "warm"}


def _with_named_blanks(row: dict) -> str:
    """The wording as it is WRITTEN — every blank replaced by what fills it, in his words.

    NOT `{{1}}`, WHICH IS META'S NUMBERING AND MEANS NOTHING TO A SHOP OWNER. `{{2}}` is a
    customer's name in one template and a service in the next; the numbers are positions, and the
    only thing that carries meaning is the `fills` list beside them. So the blank is shown as
    «[اسم العميل]» — the same word the editor puts on its chips, from `reasons.SLOT_LABEL`, so one
    vocabulary describes a blank everywhere it appears.

    A BLANK WITH NO DECLARED MEANING STAYS A NUMBER rather than being guessed at. A wrong name
    over a blank is worse than a bare one: he would write his own text around a promise the
    template does not keep.
    """
    from app.core import reasons as TR
    body = str(row.get("body") or "")
    for i, kind in enumerate(list(row.get("fills") or []), start=1):
        label = TR.SLOT_LABEL.get(kind, "")
        if label:
            body = body.replace("{{" + str(i) + "}}", f"[{label}]")
    return body


def _fill_custom(row: dict, *, establishment: str) -> str:
    """Show one of HIS texts filled in. Blank meanings, not blank numbers — see custom_templates."""
    from app.core import reasons as TR
    body = row.get("body", "")
    for i, kind in enumerate(list(row.get("fills") or []), start=1):
        value = establishment if kind == TR.SHOP else TR.SAMPLE.get(kind, "")
        body = body.replace("{{" + str(i) + "}}", value)
    return body


# ── his own texts (§6.7, and the owner's decision that there is no review of ours) ────────────
class CustomTemplateIn(BaseModel):
    reason_id: str = Field(min_length=2, max_length=64)
    body: str = Field(min_length=1, max_length=1024)
    # WHAT EACH BLANK MEANS, in position order. Not derived from the text and not derivable: Meta
    # numbers blanks and names nothing, so `{{2}}` is a customer's name in one template and a
    # service in another. The editor knows, because he inserted the chip.
    fills: list[str] = Field(default_factory=list, max_length=10)
    # NOT HIS ANSWER, AND NOT A DEFAULT — the class comes from the reason he is rewriting, and
    # `CustomTemplateStore.draft` reads it there. It decides the mandatory «أوقفها» tail, the
    # consent required, the quiet window and the monthly cap; a reason is precisely «متى تُرسَل
    # ولماذا», so it already holds the answer. Empty here, and a value that disagrees with the
    # reason is refused rather than corrected — see the note at the derivation.
    cls: str = Field(default="", max_length=32)
    # The approved text this one replaces. A new NAME every time: Meta freezes a name at approval,
    # so reusing it would take his messages off the air for a day over one word.
    replaces: str = Field(default="", max_length=512)


@router.get("/templates", dependencies=[Depends(rate_limit)])
async def list_custom_templates(request: Request, reason_id: str = "",
                                principal: Principal = Depends(_READ)) -> dict:
    """His own texts and where each one stands."""
    from app.core.custom_templates import CustomTemplateStore
    store = CustomTemplateStore(request.app.state.container.datastore)
    rows = await store.list(_tenant(principal), reason_id=reason_id)
    return {"templates": [{k: r.get(k) for k in
                           ("name", "reason_id", "body", "fills", "status", "reason",
                            "version", "updated")} for r in rows]}


@router.post("/templates", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def write_custom_template(request: Request, body: CustomTemplateIn,
                                principal: Principal = Depends(_MANAGE)) -> dict:
    """Write one. It is a DRAFT — nothing reaches Meta until he says so.

    REFUSES WHAT META WOULD REFUSE, and what our own renderer would: a link, a numbering gap, or a
    blank this reason cannot fill. The last is the one that matters — it would pass Meta's review
    and then fail at send, once, for one shop, with nothing to read.
    """
    from app.core.custom_templates import CustomTemplateError, CustomTemplateStore
    store = CustomTemplateStore(request.app.state.container.datastore)
    try:
        row = await store.draft(_tenant(principal), reason_id=body.reason_id, body=body.body,
                                fills=list(body.fills), cls=body.cls, replaces=body.replaces)
    except CustomTemplateError as exc:
        # RETURNED, NOT RAISED — the platform's handler strips an HTTPException's detail, and the
        # sentence is the whole answer.
        return {"ok": False, "error": str(exc)}
    await request.app.state.auditor.record(
        "reminders.rule_changed", actor=principal.subject, tenant=_tenant(principal),
        resource=f"template:{row.name}", ip=request.client.host if request.client else "")
    return {"ok": True, "template": row.public()}


@router.post("/templates/{name}/submit", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def submit_custom_template(request: Request, name: str,
                                 principal: Principal = Depends(_MANAGE)) -> dict:
    """Hand HIS text to Meta, on his own number, with no review of ours in between.

    THE DRAFT USED TO HAVE NOWHERE TO GO. He could write a text, read it back on a phone-shaped
    preview, and that was the end of it: registering and submitting were user-tier routes needing a
    JWT this service cannot mint. So «قوالبي» was a notepad — every text he wrote sat as a draft,
    for ever, and nothing said why.

    THE VERDICT IS META'S AND SO ARE THE WORDS. A refusal comes back as Meta wrote it, because
    «ساعدوني» turns that exact sentence into a request a human answers — and a re-worded rejection
    sends him looking for a problem we invented.

    NOTHING BREAKS WHILE HE WAITS. His messages keep going out in OUR words until Meta approves
    this one; that is the fallback in `rendering.choose`, and it is what makes submitting safe.
    """
    from app.core.custom_templates import (CustomTemplateError, CustomTemplateStore, DRAFT,
                                           PENDING, REJECTED)
    c = request.app.state.container
    store = CustomTemplateStore(c.datastore)
    row = await store.get(_tenant(principal), name)
    if row is None:
        return {"ok": False, "error": "لا يوجد نصّ بهذا الاسم."}
    if row.get("status") not in (DRAFT, REJECTED):
        # ALREADY WITH META, OR ALREADY LIVE. Submitting again would spend one of his hundred
        # hourly slots to ask about a template Meta has not finished reading.
        return {"ok": False, "error": "هذا النص مرفوع بالفعل."}

    # ── THE SYSTEM CEILING, SPENT BEFORE THE SUBMISSION AND NOT AFTER ────────────────────────
    #
    # `templates.custom` USED TO BE SOLD PER APP through billing-service (الحملات: 1/month,
    # صفقات: 9/month) — the owner's own call (2026-09-11) retired that entirely: every shop gets
    # the SAME flat allowance now, regardless of which apps it owns, enforced locally rather than
    # billed (core/template_quota.py's own header explains the whole shape).
    #
    # AND THE COST IS NOT OURS ALONE. Every submission goes to Meta under the establishment's own
    # WhatsApp account and counts against OUR quality standing as its Tech Provider; a rejected
    # name cannot be reused. So an unenforced limit is not lost revenue, it is a reputation we
    # cannot buy back.
    #
    # BEFORE, because after is a limit that has already been exceeded. The unit is released below
    # if Meta refuses, so a rejection does not cost him a slot he never got the use of.
    from app.core.template_quota import QuotaError, TemplateQuota

    template_quota = TemplateQuota(c.datastore)
    try:
        await template_quota.take(_tenant(principal))
    except QuotaError as exc:
        # RETURNED, NEVER RAISED — the platform strips a raised detail, and «بلغت الحدّ الأقصى من
        # القوالب الخاصة» is the whole answer.
        return {"ok": False, "error": str(exc)}

    # HIS SHOP'S OWN NAME, NOT META'S PLACEHOLDER (ح-8). `submission._examples` fills the
    # "establishment" slot in its sample text and falls back to «محلّك» — the generic form our
    # own comments say a review rejects — whenever the row it is handed carries none. `row` here
    # is `custom_templates.CustomTemplate.to_dict()`, which has no such key, so every submission
    # was reviewed against an example carrying the placeholder rather than the shop's real name.
    shop = await c.identity.get(_tenant(principal))
    out = await c.submitter.submit(_tenant(principal), {**row, "establishment": shop.name})
    if not out.get("ok"):
        # HIS SLOT BACK. Meta refused the wording, and charging him a lifetime slot for a text
        # that never reached anybody would make the limit punish the attempt rather than the use.
        await template_quota.release(_tenant(principal))
    status = PENDING if out.get("ok") else REJECTED
    try:
        row = await store.mark(_tenant(principal), name, status=status,
                               reason=str(out.get("reason", "")))
    except CustomTemplateError as exc:
        return {"ok": False, "error": str(exc)}
    await request.app.state.auditor.record(
        "reminders.rule_changed", actor=principal.subject, tenant=_tenant(principal),
        resource=f"template:{name}", ip=request.client.host if request.client else "")
    return {"ok": bool(out.get("ok")), "template": {k: row.get(k) for k in
                                                    ("name", "reason_id", "status", "reason",
                                                     "version", "updated")}}


class HelpIn(BaseModel):
    """His own sentence, and nothing else asked of him.

    OPTIONAL, DELIBERATELY. The whole value of this button is that it needs no explanation from a
    man in the middle of a working day — Meta's refusal and his text are attached without him
    typing anything. A required field would turn one press into a form, and a form is what he
    abandons.
    """

    note: str = Field(default="", max_length=600)


@router.post("/templates/{name}/help", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def ask_for_help(request: Request, name: str, body: HelpIn | None = None,
                       principal: Principal = Depends(_MANAGE)) -> dict:
    """«ساعدوني» — Meta refused his text, and this turns the refusal into a request we answer.

    WHY THIS BUTTON EXISTS AT ALL. We took ourselves out from between him and Meta on purpose
    («هو يقرر ونحط ميزة ساعدوني»). The cost is that a rejection arrives in English, from a reviewer
    he cannot reach, about a policy he has never read — and what follows is always the same: he
    edits a word, resubmits, is refused again, and after the third time he stops using the feature
    and tells us the product does not work.

    NOTHING IS ASKED OF HIM. The refusal, the text as he wrote it, and the reason it was for are
    attached from what we already hold. He may add a sentence; he does not have to.
    """
    from app.core.custom_templates import CustomTemplateStore, REJECTED
    from app.core.help_requests import HelpRequestStore

    c = request.app.state.container
    row = await CustomTemplateStore(c.datastore).get(_tenant(principal), name)
    if row is None:
        return {"ok": False, "error": "لا يوجد نصّ بهذا الاسم."}
    if row.get("status") != REJECTED:
        # ONLY A REFUSAL OPENS A TICKET. A draft he has not submitted has no problem to solve yet,
        # and an approved text has none at all — answering either would spend a human on a
        # question nobody asked.
        return {"ok": False, "error": "لا يُطلب المساعدة إلا بعد رفض واتساب للنص."}

    saved = await HelpRequestStore(c.datastore).ask(
        _tenant(principal), name=name, reason_id=str(row.get("reason_id", "")),
        body=str(row.get("body", "")), refusal=str(row.get("reason", "")),
        note=(body.note if body else ""))
    await request.app.state.auditor.record(
        "reminders.rule_changed", actor=principal.subject, tenant=_tenant(principal),
        resource=f"template_help:{name}", ip=request.client.host if request.client else "")
    return {"ok": True, "request": {k: saved.get(k) for k in
                                    ("name", "reason_id", "status", "note", "asked", "answer")}}


@router.get("/templates/help", dependencies=[Depends(rate_limit)])
async def my_help_requests(request: Request, principal: Principal = Depends(_READ)) -> dict:
    """Where each of his requests stands, and what we answered.

    THE ANSWER GOES BACK TO THE SCREEN HE ASKED FROM. A reply that arrives only in a support
    channel is one he reads once and cannot find again the day he sits down to fix the text.
    """
    from app.core.help_requests import HelpRequestStore
    rows = await HelpRequestStore(request.app.state.container.datastore).list(_tenant(principal))
    return {"requests": [{k: r.get(k) for k in
                          ("name", "reason_id", "status", "refusal", "note", "answer",
                           "asked", "updated")} for r in rows]}


# ── settings: general, group, and one service's own (spec §10.8.1) ────────────────────────────
class SettingsIn(BaseModel):
    # Every field optional: an owner changing the lead time must not be forced to restate the
    # interval, and a model requiring both would make a one-field edit a two-field decision.
    # ZERO IS A VALUE, NOT AN ABSENCE. It means "this service has no natural cycle" — a one-off
    # repair, a diagnostic — and `operations` has always allowed it on the catalogue row. The tree
    # refused it (ge=1), so an owner clearing the cycle on «خدماتي» got a 422 and a screen that
    # simply did not save, with no sentence to read. The two stores now agree on what 0 means.
    interval_days: float | None = Field(default=None, ge=0, le=1095)
    lead_days: float | None = Field(default=None, ge=0, le=60)
    follow_up_days: int | None = Field(default=None, ge=0, le=180)
    enabled: bool | None = None

    def values(self) -> dict:
        # `exclude_none` is the whole contract: an omitted field means "leave it", NOT "clear it".
        # Sending nulls for what the owner did not touch would erase settings on every save.
        return self.model_dump(exclude_none=True)


def _settings(request: Request):
    from app.config import get_settings
    from app.core.settings_tree import SettingsStore
    s = get_settings()
    return SettingsStore(request.app.state.container.datastore, defaults={
        "interval_days": s.DEFAULT_INTERVAL_DAYS,
        "lead_days": s.DEFAULT_LEAD_DAYS,
        "follow_up_days": 0,
        "enabled": True})


@router.get("/offer", dependencies=[Depends(rate_limit)])
async def active_offer(request: Request, subject_ref: str = Query(min_length=8, max_length=128),
                       principal: Principal = Depends(_READ)) -> dict:
    """The offer this customer is holding, for the line above the service grid (§5.6.2).

    AN OFFER THE OPERATOR CANNOT SEE BECOMES AN ARGUMENT AT THE COUNTER. The customer is holding a
    message from this shop; the man in front of him knows nothing about it; both are embarrassed,
    and the shop either honours something it did not plan or refuses something it did send.

    THE PSEUDONYM IS THE KEY, because this service has no names and wants none. The console gets it
    from the customer record operations already serves it — the same identifier every peer uses.

    EXPIRED ANSWERS `null`, not an expired offer with a flag. A screen that renders one that has
    run out contradicts the operator out loud, which is worse than showing nothing at all.
    """
    # WHAT HE HAS ALREADY SPENT COMES FROM operations (§5.6.2), because the visit is where the
    # spending is recorded. Unknown is NOT treated as "nothing spent": showing an offer that was
    # already honoured puts the operator in an argument with a customer holding a phone, so an
    # unreachable peer shows nothing rather than something possibly wrong.
    try:
        used = spent_refs(operations_url=_ops_url(request), token=_ops_token(request),
                          tenant=_tenant(principal), subject_ref=subject_ref)
    except SpentUnknown:
        return {"offer": None}

    # HIS BRANCH, HERE TOO (ط-4). This route answers «what is this customer holding» from the same
    # collection `/log` guards, and took only a pseudonym.
    try:
        scope = await _branch_scope(request.app.state.container, principal)
    except OutsideHisBranch:
        return {"offer": None}

    row = await SendLogStore(request.app.state.container.datastore).active_offer(
        _tenant(principal), subject_ref, used_refs=used, now=int(time.time()))
    if not row or not _in_scope(row, scope):
        return {"offer": None}
    return {"offer": {"text": row.get("offer_text", ""),
                      "expires_at": int(row.get("offer_expires_at") or 0),
                      "sent_at": int(row.get("at") or 0),
                      # AND THE AMOUNT ITSELF (أ-7). It was typed at creation — «20%», «50 ريال» —
                      # rendered into the message, and then existed nowhere a person could read it
                      # again. When the owner wrote his own line the sentence may not restate it at
                      # all, so the operator's only source was the customer's word for it.
                      "value": row.get("offer_value", ""),
                      # WHICH SERVICES IT COVERS (ب-4). The field screen reads `offer.service_ids`
                      # to decide whether the visit in front of the operator is one the offer
                      # applies to — and to badge those services in the grid. The route never sent
                      # the key, so the set was empty on every visit: the «طبّق العرض» control was
                      # never rendered once, and no service ever carried its badge.
                      "service_ids": list(row.get("offer_services") or [])}}


class DsarCodeOut(BaseModel):
    dsar_id: str = Field(min_length=1, max_length=128)


@router.post("/dsar-code", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def send_my_dsar_code(request: Request, body: DsarCodeOut,
                            principal: Principal = Depends(_READ)) -> dict:
    """Send ME the code that proves this request is mine (PDPL Article 4).

    THE SUBJECT ASKS FOR HIS OWN. `_READ` and not `manage`: the person pressing this is the person
    whose data it is, and the code goes to the number on his own session — never to one supplied
    in the request, which would turn a verification into a way to send codes to strangers.

    THE DELIVERY ITSELF IS THE INTERNAL ROUTE, unchanged: it fetches the code from compliance, and
    a spent code sends nothing. This is only the door a screen may knock on.
    """
    from app.api.internal import DsarCodeIn, send_dsar_code

    return await send_dsar_code(request, DsarCodeIn(
        tenant=_tenant(principal),
        dsar_id=body.dsar_id,
        # HIS OWN PSEUDONYM, off the token. The one identifier a caller cannot choose.
        subject_ref=getattr(principal, "subject", "") or "",
        shop_name=""))


@router.get("/offers", dependencies=[Depends(rate_limit)])
async def customer_offers(request: Request, subject_ref: str = Query(min_length=8, max_length=128),
                          include_expired: bool = Query(default=True),
                          principal: Principal = Depends(_READ)) -> dict:
    """Every offer this customer has been sent, for the owner looking at his record.

    THE EXPIRED ONES ARE INCLUDED HERE AND NOWHERE ELSE, and the difference is who is asking. The
    customer's page and the field screen must never show a dead offer — it contradicts the shop out
    loud. The owner asks a different question: "did he get last month's offer?" as often as "what
    is he holding now", and hiding it would make his own history unreadable.

    THE SEND LOG IS THE ANSWER, not a second table. Whoever received the message holds the offer;
    whoever did not, never did.
    """
    now = int(time.time())
    # AND HIS BRANCH HERE (ط-4). This is the widest of the three — every offer ever sent to one
    # customer, with its code and its value — and it was the one with no check at all.
    try:
        scope = await _branch_scope(request.app.state.container, principal)
    except OutsideHisBranch as refused:
        return {"offers": [], "unavailable": refused.unavailable}

    store = SendLogStore(request.app.state.container.datastore)
    rows = await store.since(_tenant(principal), subject_ref, since=0)
    out = []
    for r in rows:
        if not r.get("offer_text") or r.get("outcome") != "sent":
            continue
        if not _in_scope(r, scope):
            continue
        expires = int(r.get("offer_expires_at") or 0)
        if not include_expired and expires <= now:
            continue
        out.append({"text": r.get("offer_text", ""), "expires_at": expires,
                    "sent_at": int(r.get("at") or 0),
                    "services": list(r.get("offer_services") or []),
                    # Said by the server rather than derived by the screen: two clocks disagreeing
                    # about whether an offer is live is a support call nobody can settle.
                    "live": expires > now})
    return {"offers": sorted(out, key=lambda o: -o["sent_at"])}


@router.get("/settings", dependencies=[Depends(rate_limit)])
async def read_settings(request: Request, service_id: str = Query(default=""),
                        principal: Principal = Depends(_READ)) -> dict:
    """The effective settings, and WHERE each value came from.

    The source is not decoration: the screen cannot say "this one is customised — tap to go back"
    unless the API says which level answered. A response carrying only the numbers would force the
    console to re-derive it, and the two would disagree the first time the resolver changed.
    """
    tree = await _settings(request).load(_tenant(principal))
    if service_id:
        return {"service_id": service_id,
                "customised": tree.is_customised(service_id),
                "settings": {k: {"value": r.value, "source": r.source}
                             for k, r in tree.resolve_all(service_id).items()}}
    # `service_group` TRAVELS WITH THE GROUPS, and it has to. A group's settings without its
    # membership is a name and a number the screen cannot attach to anything — «خدماتي» rendered a
    # flat list of twenty services while the system already knew four of them were one group,
    # because the only place membership was ever reported was the answer to the write that created
    # it. A screen that must remember a POST to know the world is a screen that is wrong after a
    # reload.
    # AND THE OVERRIDES THEMSELVES, NOT A LIST OF NAMES. This answered `customised_services` — the
    # ids and nothing else — so a screen listing twenty services could say WHICH were customised
    # but not to what, and its only way to find out was one request per service. Twenty round
    # trips for values that are already in the row this handler just read.
    return {"general": tree.general, "groups": tree.groups,
            "service_group": tree.service_group,
            "services": tree.services}


@router.put("/settings", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def set_general_settings(request: Request, body: SettingsIn,
                               principal: Principal = Depends(_MANAGE)) -> dict:
    """Change the tenant-wide setting.

    Reaches every service that follows and leaves every customised one alone. An owner who spent a
    minute setting the oil change to 60 days has not asked us to undo that minute.
    """
    await request.app.state.auditor.record(
        "reminders.rule_changed", actor=principal.subject, tenant=_tenant(principal),
        resource="settings:general", ip=request.client.host if request.client else "")
    tree = await _settings(request).set_general(_tenant(principal), body.values())
    return {"general": tree.general,
            "note": "يسري على كل خدمة تتبع الإعداد العام. الخدمات المخصّصة تبقى كما هي."}


@router.put("/settings/service/{service_id}", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def set_service_settings(request: Request, service_id: str, body: SettingsIn,
                               principal: Principal = Depends(_MANAGE)) -> dict:
    """Give one service its own values — which is what "customising" means here."""
    await request.app.state.auditor.record(
        "reminders.rule_changed", actor=principal.subject, tenant=_tenant(principal),
        resource=f"settings:service:{service_id}",
        ip=request.client.host if request.client else "")
    tree = await _settings(request).set_service(_tenant(principal), service_id, body.values())
    return {"service_id": service_id, "own": tree.services.get(service_id, {}),
            "note": "هذه الخدمة لها إعدادها الخاص الآن. للعودة إلى العام احذف تخصيصها."}


@router.delete("/settings/service/{service_id}", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def follow_general_again(request: Request, service_id: str,
                               principal: Principal = Depends(_MANAGE)) -> dict:
    """The "tap to go back" the note offers.

    DELETES the service's own values rather than writing the current general ones into it. Writing
    them would look identical today and diverge tomorrow — the service would stop following, and
    the next general edit would skip it.
    """
    await request.app.state.auditor.record(
        "reminders.rule_changed", actor=principal.subject, tenant=_tenant(principal),
        resource=f"settings:service:{service_id}",
        ip=request.client.host if request.client else "")
    await _settings(request).follow_again(_tenant(principal), service_id)
    return {"service_id": service_id, "follows": "general"}


class GroupIn(SettingsIn):
    service_ids: list[str] = Field(default_factory=list, max_length=200)


@router.put("/settings/group/{name}", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def set_group_settings(request: Request, name: str, body: GroupIn,
                             principal: Principal = Depends(_MANAGE)) -> dict:
    """Create or update a group. Arrives late and by suggestion — never as a step somebody must
    complete before sending their first message."""
    await request.app.state.auditor.record(
        "reminders.rule_changed", actor=principal.subject, tenant=_tenant(principal),
        resource=f"settings:group:{name}", ip=request.client.host if request.client else "")
    values = {k: v for k, v in body.values().items() if k != "service_ids"}
    tree = await _settings(request).set_group(_tenant(principal), name, values,
                                              service_ids=body.service_ids)
    return {"group": name, "settings": tree.groups.get(name, {}),
            "services": [s for s, g in tree.service_group.items() if g == name]}


@router.delete("/settings/group/{name}/service/{service_id}", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def leave_group(request: Request, name: str, service_id: str,
                      principal: Principal = Depends(_MANAGE)) -> dict:
    """Take one service out of its group.

    `name` is in the path for the audit record and for a URL that reads as what it does; the write
    itself is keyed by service, because a service is in at most one group. It returns to following
    general, which is where it was before anyone grouped it.
    """
    await request.app.state.auditor.record(
        "reminders.rule_changed", actor=principal.subject, tenant=_tenant(principal),
        resource=f"settings:group:{name}:service:{service_id}",
        ip=request.client.host if request.client else "")
    await _settings(request).leave_group(_tenant(principal), service_id)
    return {"service_id": service_id, "group": "", "follows": "general"}


@router.delete("/settings/group/{name}", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def delete_group(request: Request, name: str,
                       principal: Principal = Depends(_MANAGE)) -> dict:
    """Delete a group. Its members become ungrouped and keep whatever they hold of their own."""
    await request.app.state.auditor.record(
        "reminders.rule_changed", actor=principal.subject, tenant=_tenant(principal),
        resource=f"settings:group:{name}", ip=request.client.host if request.client else "")
    tree = await _settings(request).delete_group(_tenant(principal), name)
    return {"group": name, "deleted": True, "groups": sorted(tree.groups)}


@router.get("/settings/suggest-group", dependencies=[Depends(rate_limit)])
async def suggest_group(request: Request, principal: Principal = Depends(_READ)) -> dict:
    """Is the owner repeating themselves?

    Proposes only. Acting on it would be a system rearranging their settings without being asked,
    which is the fastest way to lose their trust in a screen.
    """
    return {"suggestion": await _settings(request).suggest_group(_tenant(principal))}


@router.get("/today", dependencies=[Depends(rate_limit)])
async def today(request: Request, principal: Principal = Depends(_READ)) -> dict:
    """Everything «اليوم» needs, in one call.

    ONE CALL RATHER THAN FOUR, and the reason is the screen's own promise. It opens on the question
    "is everything running", which is answered by the WHOLE picture or not at all: a ceiling that
    arrives after the send count renders a screen that says "23 sent" and then, a beat later,
    "you have 4 left" — and the owner has already formed an impression from the first number. Four
    requests also means four ways to be half-loaded, and a status screen that is sometimes partly
    wrong is worse than one that is briefly blank.

    AND WHAT IT DOES NOT INCLUDE IS THE POINT OF THE SCREEN. No indicator, no trend, no comparison
    beyond yesterday. Those live in «محلّي» and are read once a week; this is read every day and
    must stay answerable at a glance.
    """
    c = request.app.state.container
    tenant = principal.tenant or ""
    store = ScheduleStore(c.datastore)

    # THE CEILING IS READ FROM META, NOT FROM A COPY. A second copy of a number we do not own
    # eventually disagrees with the source, and the owner sees two figures with no way to tell
    # which is true — the shape of a support call nobody can close.
    ceiling = await c.ceiling.read(tenant)
    # BUILT HERE RATHER THAN READ OFF THE CONTAINER, because the container has no `reach`: the
    # window belongs to the tick, which constructs its own. `c.reach` was written from memory,
    # never called, and answered every request with a 500 — and the screen it feeds sat on a
    # loading skeleton for ever rather than saying so. Found by opening the page in a browser.
    #
    # AND WITH THE CONFIGURED WINDOW, which is the second half of that bug. Built bare, `Reach`
    # takes its own default — so a deployment that tunes REACH_WINDOW_SECONDS showed the owner one
    # number and gated his sends on another, and the two disagreed by exactly the amount nobody
    # could account for.
    from app.config import get_settings as _settings
    reached = await Reach(c.datastore, window=_settings().REACH_WINDOW_SECONDS).count(
        tenant, now=int(time.time()))

    pending, _ = await store._find(tenant, {"state": "pending"}, limit=200,
                                   sort=("due_at", "asc"))
    # ── WAITING IS NOT THE SAME AS STUCK, AND `pending` HOLDS BOTH ────────────────────────────
    #
    # A row whose pass throws goes back to `pending` an hour out with its `attempts` raised — a
    # number Meta refuses, a template rejected for this shop alone, a peer that is down. So the
    # single word covered two states: a reminder calmly booked for next Tuesday, and a message
    # that has failed eleven times and will be tried a few more before it is given up on.
    #
    # COUNTED TOGETHER, THE SCREEN LIED IN THE ONLY DIRECTION THAT MATTERS. It is named «هل كل
    # شيء يعمل؟», and a shop whose every message was failing read «12 في الانتظار» and concluded
    # it was working. This screen already refuses to render an unknown ceiling as a zero and an
    # unreadable name as calm; this is the same rule, one field further along.
    stuck = [r for r in pending if int(r.get("attempts") or 0) > 0]
    sent, _ = await store._find(tenant, {"state": "sent"}, limit=200, sort=("due_at", "desc"))

    now = int(time.time())
    day = now - 86_400
    sent_today = [r for r in sent if int(r.get("sent_at") or r.get("due_at") or 0) >= day]

    # ── CAN THIS SHOP SEND AT ALL? ────────────────────────────────────────────────────────────
    # THE OUTAGE THAT LOOKED LIKE CALM. The tick skips an establishment whose name it cannot read —
    # correctly, because a message signed by nobody is worse than a late one — and it skips it
    # BEFORE the send log exists, so every screen the owner has said the same thing as a shop with
    # nothing due: zero sent, N waiting, no refusals. He recorded real visits for a day and
    # concluded the product was working.
    #
    # A SCREEN NAMED «هل كل شيء يعمل؟» MUST ANSWER THE ONE CASE WHERE NOTHING DOES. This reads the
    # same adapter the tick reads, so the two cannot disagree, and it names the repair rather than
    # the fault: he does not care that a peer omits a field, he cares that his name is missing and
    # that one screen fixes it.
    shop = await c.identity.get(tenant)
    blocked_reason = "" if shop.usable else (
        "اسم محلّك غير مضبوط، ولا تخرج أي رسالة باسم فارغ — اكتبه في «حسابي» وتُستأنف رسائلك تلقائياً."
    )

    return {
        "can_send": bool(shop.usable),
        # EMPTY WHEN ALL IS WELL. A field that always carries a sentence is a field the screen
        # learns to render unconditionally, and then a real warning looks like furniture.
        "blocked": blocked_reason,
        "messages": {
            "sent_today": len(sent_today),
            # WAITING IS THE CALM ONES ONLY. Subtracting rather than counting a second query: one
            # read, and the two numbers cannot disagree about the same rows.
            "waiting": len(pending) - len(stuck),
            # AND THE STUCK ONES CARRY THEIR OWN NUMBER AND THEIR OWN SENTENCE. Zero is a real
            # answer here and the screen shows nothing for it — a warning that is always present
            # is furniture, exactly as the `blocked` field above says.
            "retrying": len(stuck),
            "retrying_reason": (
                "رسائل تحاول الخروج ولا تنجح — سنعيد المحاولة، وإن لم تنجح ستجدها في سجلّ "
                "الرسائل بسببها." if stuck else ""),
        },
        "ceiling": {
            # `known` distinguishes "we asked and Meta said unlimited" from "we could not ask".
            # The screen must never render an unknown ceiling as a zero — a zero reads as "you may
            # send to nobody", which is the opposite of what an unreadable answer means.
            "known": ceiling.known(),
            "unlimited": ceiling.unlimited(),
            "limit": ceiling.limit,
            "reached_today": reached,
            "remaining": ceiling.remaining(reached),
            "quality": ceiling.quality,
        },
    }
