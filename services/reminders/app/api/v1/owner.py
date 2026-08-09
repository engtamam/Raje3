"""The owner's surface: what is coming, what happened, and why something did not.

FOUR ROUTES, AND THE MOST IMPORTANT ONE IS THE LOG. Every other screen on this product shows what
happened; this one has to show what DIDN'T, with the reason. "Why didn't my customer get the
message?" is the only support question this service generates, and a screen that cannot answer it
turns every rule we wrote into a suspected bug.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from app.api.auth import Principal
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.core.stores import RuleStore, ScheduleStore, SendLogStore

router = APIRouter(prefix="/reminders", tags=["reminders"])

_READ = require_capability("reminders.read")
_MANAGE = require_capability("reminders.manage")


@router.get("/schedule", dependencies=[Depends(rate_limit)])
async def list_schedule(request: Request, state: str = Query(default="pending"),
                        limit: int = Query(default=50, ge=1, le=200),
                        principal: Principal = Depends(_READ)) -> dict:
    """What is coming, soonest first.

    Returns the pseudonym, not a customer name — this service has no names. The console joins
    against operations for display, which keeps the identifier in one place instead of two.
    """
    store = ScheduleStore(request.app.state.container.datastore)
    rows, _ = await store._find(principal.tenant, {"state": state} if state else None,
                                limit=limit, sort=("due_at", "asc"))
    return {"schedule": rows, "count": len(rows)}


@router.delete("/schedule/{schedule_key:path}", dependencies=[Depends(rate_limit)])
async def cancel(request: Request, schedule_key: str,
                 principal: Principal = Depends(_MANAGE)) -> dict:
    """Cancel one pending reminder.

    Cancels the message, NOT the rule. The next visit schedules a new one — which is what an owner
    almost always means, and the thing they would be surprised by if we did the other.
    """
    store = ScheduleStore(request.app.state.container.datastore)
    row = await store.get(schedule_key)
    # THE TENANT CHECK IS EXPLICIT, because this key comes off the request. The store prefixes keys
    # by tenant, so a forged key from another establishment cannot be read — but relying on a key
    # format for authorisation is relying on a convention, and this makes it a check.
    if row is None or row.get("tenant") != principal.tenant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    await request.app.state.auditor.record(
        "reminders.schedule_cancelled", actor=principal.subject, tenant=principal.tenant,
        resource=f"schedule:{row.get('id','')}",
        ip=request.client.host if request.client else "")
    row["state"] = "cancelled"
    row["reason"] = "ألغاه المالك"
    await store.upsert(principal.tenant, schedule_key, row)
    return {"cancelled": True, "id": row.get("id", "")}


@router.get("/rules", dependencies=[Depends(rate_limit)])
async def list_rules(request: Request, service_id: str = Query(default=""),
                     principal: Principal = Depends(_READ)) -> dict:
    """The learned interval per customer and service.

    `learned` is reported separately from the number itself. An owner told "learned: 90 days" from
    zero observations stops trusting every number on the screen — so an estimate that is still the
    sector default says so.
    """
    from app.config import get_settings
    from app.core.adaptive import AdaptiveConfig, is_learned
    cfg = AdaptiveConfig(warmup=get_settings().ADAPTIVE_WARMUP_OBSERVATIONS)
    store = RuleStore(request.app.state.container.datastore)
    rows = (await store.for_service(principal.tenant, service_id)) if service_id else \
        (await store._find(principal.tenant, limit=200, sort=("updated", "desc")))[0]
    for r in rows:
        r["learned"] = is_learned(int(r.get("observations") or 0), cfg)
    return {"rules": rows, "count": len(rows)}


class RuleIn(BaseModel):
    # Bounded at the model, not only in the engine. A rule set to 4000 days is not a slow reminder,
    # it is a reminder that never arrives — and the owner would never know which.
    interval_days: float = Field(ge=1, le=1095)
    lead_days: float = Field(default=7, ge=0, le=60)


@router.put("/rules/{rule_key:path}", dependencies=[Depends(rate_limit)])
async def set_rule(request: Request, rule_key: str, body: RuleIn,
                   principal: Principal = Depends(_MANAGE)) -> dict:
    """Override a learned interval.

    THE OVERRIDE STOPS THE LEARNING for that customer and service, and says so in the response.
    Silently resuming adaptation would walk the owner's number back toward the observed rhythm over
    the next few visits, and they would conclude the setting does not work.
    """
    store = RuleStore(request.app.state.container.datastore)
    row = await store.get(rule_key)
    if row is None or row.get("tenant") != principal.tenant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    await request.app.state.auditor.record(
        "reminders.rule_changed", actor=principal.subject, tenant=principal.tenant,
        resource=f"rule:{row.get('id','')}", ip=request.client.host if request.client else "")
    row["interval_days"] = body.interval_days
    row["lead_days"] = body.lead_days
    row["pinned"] = True
    await store.upsert(principal.tenant, rule_key, row)
    return {"rule": row, "adaptation": "paused",
            "note": "الفترة مثبّتة الآن ولن يعدّلها النظام تلقائياً."}


@router.get("/log", dependencies=[Depends(rate_limit)])
async def send_log(request: Request, outcome: str = Query(default=""),
                   limit: int = Query(default=100, ge=1, le=500),
                   principal: Principal = Depends(_READ)) -> dict:
    """What was sent, and what was not, with the reason.

    THE SUPPRESSIONS ARE THE POINT. This is the screen that answers the only question this service
    generates, and it is why every refusal in the gate returns a sentence rather than a code.
    """
    store = SendLogStore(request.app.state.container.datastore)
    where = {"outcome": outcome} if outcome else None
    rows, _ = await store._find(principal.tenant, where, limit=limit, sort=("at", "desc"))
    # The visit-idempotency markers live in this collection (see core/scheduling.py) and are not
    # messages. Showing them would put rows in an owner's log that mean nothing to them.
    rows = [r for r in rows if r.get("subject_ref") != "_visit_marker"]
    return {"log": rows, "count": len(rows)}


# ── settings: general, group, and one service's own (spec §10.8.1) ────────────────────────────
class SettingsIn(BaseModel):
    # Every field optional: an owner changing the lead time must not be forced to restate the
    # interval, and a model requiring both would make a one-field edit a two-field decision.
    interval_days: float | None = Field(default=None, ge=1, le=1095)
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


@router.get("/settings", dependencies=[Depends(rate_limit)])
async def read_settings(request: Request, service_id: str = Query(default=""),
                        principal: Principal = Depends(_READ)) -> dict:
    """The effective settings, and WHERE each value came from.

    The source is not decoration: the screen cannot say "this one is customised — tap to go back"
    unless the API says which level answered. A response carrying only the numbers would force the
    console to re-derive it, and the two would disagree the first time the resolver changed.
    """
    tree = await _settings(request).load(principal.tenant)
    if service_id:
        return {"service_id": service_id,
                "customised": tree.is_customised(service_id),
                "settings": {k: {"value": r.value, "source": r.source}
                             for k, r in tree.resolve_all(service_id).items()}}
    return {"general": tree.general, "groups": tree.groups,
            "customised_services": sorted(tree.services)}


@router.put("/settings", dependencies=[Depends(rate_limit)])
async def set_general_settings(request: Request, body: SettingsIn,
                               principal: Principal = Depends(_MANAGE)) -> dict:
    """Change the tenant-wide setting.

    Reaches every service that follows and leaves every customised one alone. An owner who spent a
    minute setting the oil change to 60 days has not asked us to undo that minute.
    """
    await request.app.state.auditor.record(
        "reminders.rule_changed", actor=principal.subject, tenant=principal.tenant,
        resource="settings:general", ip=request.client.host if request.client else "")
    tree = await _settings(request).set_general(principal.tenant, body.values())
    return {"general": tree.general,
            "note": "يسري على كل خدمة تتبع الإعداد العام. الخدمات المخصّصة تبقى كما هي."}


@router.put("/settings/service/{service_id}", dependencies=[Depends(rate_limit)])
async def set_service_settings(request: Request, service_id: str, body: SettingsIn,
                               principal: Principal = Depends(_MANAGE)) -> dict:
    """Give one service its own values — which is what "customising" means here."""
    await request.app.state.auditor.record(
        "reminders.rule_changed", actor=principal.subject, tenant=principal.tenant,
        resource=f"settings:service:{service_id}",
        ip=request.client.host if request.client else "")
    tree = await _settings(request).set_service(principal.tenant, service_id, body.values())
    return {"service_id": service_id, "own": tree.services.get(service_id, {}),
            "note": "هذه الخدمة لها إعدادها الخاص الآن. للعودة إلى العام احذف تخصيصها."}


@router.delete("/settings/service/{service_id}", dependencies=[Depends(rate_limit)])
async def follow_general_again(request: Request, service_id: str,
                               principal: Principal = Depends(_MANAGE)) -> dict:
    """The "tap to go back" the note offers.

    DELETES the service's own values rather than writing the current general ones into it. Writing
    them would look identical today and diverge tomorrow — the service would stop following, and
    the next general edit would skip it.
    """
    await request.app.state.auditor.record(
        "reminders.rule_changed", actor=principal.subject, tenant=principal.tenant,
        resource=f"settings:service:{service_id}",
        ip=request.client.host if request.client else "")
    await _settings(request).follow_again(principal.tenant, service_id)
    return {"service_id": service_id, "follows": "general"}


class GroupIn(SettingsIn):
    service_ids: list[str] = Field(default_factory=list, max_length=200)


@router.put("/settings/group/{name}", dependencies=[Depends(rate_limit)])
async def set_group_settings(request: Request, name: str, body: GroupIn,
                             principal: Principal = Depends(_MANAGE)) -> dict:
    """Create or update a group. Arrives late and by suggestion — never as a step somebody must
    complete before sending their first message."""
    await request.app.state.auditor.record(
        "reminders.rule_changed", actor=principal.subject, tenant=principal.tenant,
        resource=f"settings:group:{name}", ip=request.client.host if request.client else "")
    values = {k: v for k, v in body.values().items() if k != "service_ids"}
    tree = await _settings(request).set_group(principal.tenant, name, values,
                                              service_ids=body.service_ids)
    return {"group": name, "settings": tree.groups.get(name, {}),
            "services": [s for s, g in tree.service_group.items() if g == name]}


@router.get("/settings/suggest-group", dependencies=[Depends(rate_limit)])
async def suggest_group(request: Request, principal: Principal = Depends(_READ)) -> dict:
    """Is the owner repeating themselves?

    Proposes only. Acting on it would be a system rearranging their settings without being asked,
    which is the fastest way to lose their trust in a screen.
    """
    return {"suggestion": await _settings(request).suggest_group(principal.tenant)}
