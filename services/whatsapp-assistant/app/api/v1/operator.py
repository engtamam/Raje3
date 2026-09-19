"""The operator surface — credentials AND policy, changeable after launch.

WRITE-ONLY IS ENFORCED HERE, and this file is where the guarantee lives, for the secrets half.
`SecretStore.get()` returns plaintext because an adapter cannot authenticate with a masked string;
no route in this module returns it, and `safety:no-secret-reads` fails the build if one ever does.
That split is deliberate: the store is a mechanism, the API boundary is the control.

/operator/config JOINED THE SECRETS ROUTES HERE 2026-09-07 — this file's own note used to say this
service had no `app/runtime_policy.py` and no reason for one; the console's provider-management
screen (المزوّدين الخارجيين ← الذكاء الاصطناعي ← الإدارة) needed live control over the model and a
couple of behavioural knobs, which is exactly what reminders'/operations' identical machinery
exists for. Mirrors reminders' own /operator/config three routes exactly — see
app/core/runtime_config.py's own docstring for the whole doctrine (a key is advertised only if
something reads it; wiring and secrets stay off this surface entirely).

WHY THE SECRETS ROUTES EXIST: an LLM backend credential is the one thing this service actually
needed changeable at runtime before today — every wipe+reinstall regenerates the platform's shared
secrets but has nothing that mints a third-party credential (ASSISTANT_MODEL_PROJECT/
ASSISTANT_MODEL_CREDENTIAL), so it silently reverted to empty and the assistant CrashLoopBackOff'd
until someone found the gap and repatched it by hand, off any audited path.
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.auth import Principal, require_user
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.config import Settings, get_settings
from app.core.conversation import build_system_prompt
from app.core.pii import subject_ref
from app.core.booking_assignment import ACTOR as ACTOR_CREATED_BY
from app.core.pricing_report import report as pricing_report
from app.core.invoice_report import report as invoice_report
from app.core.upsell_report import report as upsell_report
from app.core.pricing_schedule import cancel as cancel_pricing_change
from app.core.pricing_schedule import is_a_pricing_key
from app.core.pricing_schedule import pending as pending_pricing_changes
from app.core.pricing_schedule import schedule as schedule_pricing_change
from app.core.ai_unit_pricing import parse_model_costs
from app.core.runtime_config import RuntimeConfig, RuntimeConfigError
from app.core.secret_store import SecretError, SecretStore
from app.runtime_policy import RUNTIME_POLICY, validate_runtime_override

router = APIRouter(prefix="/api/v1/assistant/operator", tags=["operator"])

_SECRETS = require_capability("platform.secrets")
_CONFIG = require_capability("platform.config")


def _actor(principal: Principal) -> str:
    """A pseudonym. An audit row naming the operator is still personal data, and this one lands in
    an append-only chain."""
    s = get_settings()
    if not s.PII_SALT:
        return ""
    return subject_ref(s.PII_SALT, principal.tenant or "", principal.subject)


def _secret_store(request: Request) -> SecretStore:
    s = get_settings()
    if not s.SECRETS_KEK:
        # A clear refusal rather than a 500. Without a KEK there is nothing to seal with, and
        # storing the credential anyway is the one outcome that must never happen.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "SECRETS_UNAVAILABLE")
    return SecretStore(request.app.state.container.datastore, s.SECRETS_KEK)


def _refuse(reason: str, status_code: int = 400) -> JSONResponse:
    """A refusal the OPERATOR can read — returned, not raised (see reminders/app/api/v1/assistant/operator.py
    for the full rationale: the global handler strips HTTPException.detail on purpose, which is
    wrong for a sentence WE wrote naming a rule the operator broke)."""
    return JSONResponse({"error": "BAD_REQUEST", "reason": reason}, status_code=status_code)


class SecretIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    value: str = Field(..., min_length=1, max_length=8192)
    tenant: str = Field(default="", max_length=128)   # empty = platform-wide (every LLM credential is)


def _invalidate_llm(request: Request) -> None:
    """Drop the container's cached LLM client's resolved credential so a rotated one takes effect
    on the next conversation turn rather than waiting for a pod restart — see
    app/adapters/llm/assistant_service.py's own note on why the client resolves its credential
    fresh per call instead of caching it at construction."""
    container = getattr(request.app.state, "container", None)
    llm = getattr(container, "llm", None) if container is not None else None
    invalidate = getattr(llm, "invalidate_key_cache", None)
    if callable(invalidate):
        invalidate()


def _runtime_config(request: Request) -> RuntimeConfig:
    """The instance wired at boot (app/container.py), so the service's RUNTIME_POLICY applies.
    Falls back to building a fresh one only if the container somehow has none yet — same shape as
    reminders'/operations' own copy of this helper."""
    container = getattr(request.app.state, "container", None)
    rc = getattr(container, "runtime_config", None) if container is not None else None
    if rc is not None:
        return rc
    return RuntimeConfig(request.app.state.container.datastore, Settings, policy=RUNTIME_POLICY,
                         validate=validate_runtime_override)


class ConfigIn(BaseModel):
    key: str = Field(..., min_length=1, max_length=128)
    value: str | int | float | bool
    tenant: str = Field(default="", max_length=128)


# ── policy (app/runtime_policy.py) ───────────────────────────────────────────────────────────────
@router.get("/config", dependencies=[Depends(_CONFIG), Depends(rate_limit)])
async def effective_config(request: Request, tenant: str = "",
                           principal: Principal = Depends(require_user)) -> dict:
    """Every knob an operator may change, with its current effective value — built from the
    settable set, so a credential or a frozen identifier cannot appear here even by accident."""
    rc = _runtime_config(request)
    # READ-ONLY, NOT A SETTABLE KNOB — `AI_ASSISTANT_ENABLED` (config.py, 2026-09-19) is a
    # deploy-time, platform-wide switch on purpose, not a per-tenant runtime override; it never
    # goes through `rc.effective()`'s settable set. Included here only so the admin pricing panel
    # (AdminProviderSecrets.tsx's own `AIConfigCard`) can hide its now-pointless "المحاسبة"
    # section when the switch is off, without a second round trip — the same JSON this card
    # already fetches.
    return {"config": await rc.effective(tenant=tenant, settings=get_settings()),
            "ai_assistant_enabled": get_settings().AI_ASSISTANT_ENABLED}


@router.put("/config", dependencies=[Depends(_CONFIG), Depends(rate_limit)])
async def set_config(request: Request, body: ConfigIn,
                     principal: Principal = Depends(require_user)) -> dict:
    """Override one policy value. Refused if the boot guard would refuse it."""
    # A PRICING KEY NEVER TAKES THIS PATH — see core/pricing_schedule.py's own docstring for why
    # a pricing change is scheduled with a mandatory delay, never instant. Refusing it here rather
    # than only failing to offer it in the console means a raw API call cannot bypass the delay
    # either; POST /pricing/schedule below is the ONLY door a pricing key can change through.
    if is_a_pricing_key(body.key):
        return _refuse(
            f"{body.key} is a pricing key — it can only be changed via POST /pricing/schedule, "
            f"which applies after a delay so shops are never billed a new rate with no notice.")
    # AUDITED AFTER THE WRITE SUCCEEDS, NOT BEFORE — fixed 2026-09-07. This used to record BEFORE
    # calling `.set()`, so a value `RuntimeConfigError` refused (a bad key/value — the ordinary
    # case, not a crash) was still permanently logged as "operator.config_changed", a change that
    # never actually happened. A refusal gets its own distinctly-named event instead, so the audit
    # trail stays a true account of what happened rather than what was attempted.
    try:
        o = await _runtime_config(request).set(
            tenant=body.tenant, key=body.key, value=body.value, actor_ref=_actor(principal))
    except RuntimeConfigError as exc:
        await request.app.state.auditor.record(
            "operator.config_change_refused", actor=_actor(principal), tenant=body.tenant or "",
            resource=f"config:{body.key}", ip=request.client.host if request.client else "",
            metadata={"key": body.key, "reason": str(exc)[:200]})
        return _refuse(str(exc))
    await request.app.state.auditor.record(
        "operator.config_changed", actor=_actor(principal), tenant=body.tenant or "",
        resource=f"config:{body.key}", ip=request.client.host if request.client else "",
        metadata={"key": body.key})     # the KEY is not a secret; settable knobs never are
    # ASSISTANT_MODEL_NAME is read fresh every LLM call already (see assistant_service.py's own
    # `_resolve_model_name`) — no cache to invalidate here the way the secrets routes need to.
    return {"key": o.key, "value": o.value}


@router.delete("/config/{key}", dependencies=[Depends(_CONFIG), Depends(rate_limit)])
async def clear_config(request: Request, key: str, tenant: str = "",
                       principal: Principal = Depends(require_user)) -> dict:
    """Drop an override so the configured default applies again."""
    # SAME GUARD AS set_config ABOVE — reverting to the configured default is itself an instant
    # pricing change (whatever that default is may differ from the current effective rate), so it
    # is refused here too. DELETE /pricing/pending/{key} is how a SCHEDULED-BUT-NOT-YET-APPLIED
    # change is cancelled instead.
    if is_a_pricing_key(key):
        return _refuse(
            f"{key} is a pricing key — it cannot be cleared instantly. Schedule a change back to "
            f"the desired value via POST /pricing/schedule instead.")
    await request.app.state.auditor.record(
        "operator.config_changed", actor=_actor(principal), tenant=tenant,
        resource=f"config:{key}", ip=request.client.host if request.client else "",
        metadata={"key": key, "cleared": True})
    return {"cleared": await _runtime_config(request).clear(tenant=tenant, key=key)}


# ── pricing (المحاسبة) — real usage, and changes that always wait before landing ─────────────────
_MIN_SCHEDULE_DELAY_DAYS = 1   # STRUCTURAL, NOT A SUGGESTION — see PricingScheduleIn's own note.


class PricingScheduleIn(BaseModel):
    key: str = Field(..., min_length=1, max_length=128)
    value: str | int | float | bool
    # DAYS, NOT AN EPOCH — the console's own calculator screen is the only caller, and it never
    # has a reason to compute a timestamp itself when "15 يوم من الآن" is both what the operator
    # typed and what this body should say. `effective_in_days` must be >= _MIN_SCHEDULE_DELAY_DAYS
    # (1) — a pricing change scheduled for "today" would be indistinguishable from the instant
    # apply this whole module exists to prevent; the console may default its own input to 15, but
    # the floor here is what actually stops a 0-day request from landing immediately.
    effective_in_days: int = Field(..., ge=_MIN_SCHEDULE_DELAY_DAYS, le=365)


# SANITY BOUNDS FOR THE FIVE AI-UNIT KEYS — mirrors the type bounds their own Settings field_
# validators enforce at boot (app/config.py), applied here too because a runtime schedule never
# goes through pydantic's own validators (RuntimeConfig._coerce only casts type, it does not
# re-run Settings' field_validator chain — see core/runtime_config.py's own `_coerce`). Without
# this, a typo like "500" instead of "5" for a margin multiplier would schedule cleanly and only
# fail (or worse, silently overcharge every shop) the moment the tick applies it.
def _ai_unit_bounds_violation(key: str, value: Any) -> str | None:
    if key == "PRICING_AI_UNIT_UNITS_PER_HALALA":
        try:
            n = int(value)
        except (TypeError, ValueError):
            return "must be a whole number"
        if not (0 < n <= 1_000_000):
            return "must be a positive integer up to 1,000,000"
        return None
    if key in ("PRICING_AI_UNIT_INPUT_MARGIN_MULTIPLIER", "PRICING_AI_UNIT_OUTPUT_MARGIN_MULTIPLIER"):
        try:
            f = float(value)
        except (TypeError, ValueError):
            return "must be a number"
        if not (1.0 < f <= 50.0):
            return "must be greater than 1 and at most 50"
        return None
    if key == "PRICING_AI_UNIT_USD_TO_SAR":
        try:
            f = float(value)
        except (TypeError, ValueError):
            return "must be a number"
        if not (0.0 < f <= 50.0):
            return "must be a positive, plausible exchange rate (<= 50) — the SAR peg is 3.75"
        return None
    if key == "PRICING_AI_UNIT_MODEL_COSTS_JSON":
        raw = str(value)
        parsed = parse_model_costs(raw)
        if raw.strip() and raw.strip() != "{}" and not parsed:
            return ('did not parse into any usable model — expected '
                   '{"model_name": {"input_usd_per_million": x, "output_usd_per_million": y}}')
        for name, cost in parsed.items():
            if cost.input_usd_per_million < 0 or cost.output_usd_per_million < 0:
                return f"{name!r} has a negative price"
            if cost.input_usd_per_million > 1000 or cost.output_usd_per_million > 1000:
                return (f"{name!r} exceeds $1000/million tokens — almost certainly a typo (a "
                        f"per-1k price entered where per-million is expected)")
        return None
    return None


@router.get("/pricing/report", dependencies=[Depends(_CONFIG), Depends(rate_limit)])
async def get_pricing_report(request: Request, days: int = 30, tenant: str = "",
                             principal: Principal = Depends(require_user)) -> dict:
    """Real usage over the trailing `days` — calls, distinct conversations, and token totals,
    straight off COST_LEDGER (core/pricing_report.py). What the calculator screen shows instead of
    a guessed average when the operator picks "من قيمة النظام" for the assumption.

    `tenant` is a platform-admin OPTION to inspect one shop, never a requirement — the console's
    own calculator never sends it and gets the platform-wide number this route has always returned.
    Deliberately an explicit query param, not read off `principal.tenant`: a platform-operator
    token has no real tenant claim (see get_invoice_report's own note below on the bug this exact
    mistake caused there), so the ONLY correct source for "which shop" on an operator-gated route
    is the operator's own explicit choice, never their own identity."""
    days = max(1, min(days, 365))
    container = request.app.state.container
    rep = await pricing_report(container.datastore, days=days, now=int(time.time()),
                               tenant=(tenant or None))
    return rep.as_dict()


@router.get("/growth/upsell-report", dependencies=[Depends(_CONFIG), Depends(rate_limit)])
async def get_upsell_report(request: Request, days: int = 30, tenant: str = "",
                            principal: Principal = Depends(require_user)) -> dict:
    """Real package-upsell offer/accept/decline counts and rate, per branch, current-window vs the
    equal window before it — straight off `wa_upsell_ledger` (core/upsell_report.py). SCOPE NOTE,
    stated in the response itself so a shop owner is never told less than the whole truth by
    omission: this covers only offer/accept/decline + rate — average invoice value now lives at
    GET .../growth/invoice-report instead (a real bookings-service query, not this local ledger);
    session/conversion counts and which services got booked are still not answered here.

    `tenant` — same platform-admin-only option as get_pricing_report's own, same reasoning: never
    sourced from the caller's own identity, only an explicit ask; empty means every shop combined,
    exactly as before this param existed."""
    days = max(1, min(days, 365))
    container = request.app.state.container
    rep = await upsell_report(container.datastore, days=days, now=int(time.time()),
                              tenant=(tenant or None))
    body = rep.as_dict()
    body["scope_note"] = ("upsell offer/accept/decline + rate only — average invoice value moved "
                          "to GET .../growth/invoice-report; session/conversion and "
                          "services-booked are not yet computed anywhere")
    return body


@router.get("/growth/invoice-report", dependencies=[Depends(_CONFIG), Depends(rate_limit)])
async def get_invoice_report(request: Request, days: int = 30, tenant: str = "",
                             principal: Principal = Depends(require_user)) -> dict:
    """Average invoice value across every AI-made booking (package OR plain service), per branch,
    current-window vs the equal window before it — the replacement for the old
    `avg_ticket_increase_minor` (core/invoice_report.py's own module docstring has the full
    reasoning: that old stat only ever priced an accepted PACKAGE upsell, never a plain booking, and
    was never actually an "increase"). Fed by bookings-service's own `/internal/bookings/by-actor`
    (booking_actor_report.py) plus live catalogue price resolution — real peer calls, not a local
    ledger, so this route can legitimately be slower than the others on this file.

    ONLY `status == "attended"` BOOKINGS FEED THE AVERAGE (real, realized revenue) — see
    invoice_report.py's own note on why, and `status_breakdown` for the full non-cancelled picture
    alongside it.

    `tenant` USED TO BE READ FROM `principal.tenant or ""` — a real bug, fixed 2026-09-07:
    `Principal.tenant` is `None` for every genuine platform-operator token (they aren't scoped to
    one shop), so this route silently asked bookings-service's `/internal/bookings/by-actor` for
    tenant `""`, which that route's own `min_length=1` validation rejects outright — the console's
    own invoice-report card would have 422'd the moment a real operator opened it. Now an explicit
    query param the console can genuinely leave empty ONLY once this route itself supports a real
    "every shop combined" mode (core/invoice_report.py's own `report()` still requires a real
    `tenant`, unlike its two siblings above — a shop-scoped stat this pass didn't extend that far;
    for now this route requires the caller to actually name a shop)."""
    days = max(1, min(days, 365))
    if not tenant:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            detail="tenant is required — this report has no platform-wide mode yet")
    days = max(1, min(days, 365))
    container = request.app.state.container
    rep = await invoice_report(
        container.booking_actor_report, container.service_catalog, container.package_catalog,
        tenant=tenant, created_by=ACTOR_CREATED_BY, days=days,
        now=int(time.time()))
    return rep.as_dict()


@router.get("/pricing/pending", dependencies=[Depends(_CONFIG), Depends(rate_limit)])
async def list_pending_pricing(request: Request,
                               principal: Principal = Depends(require_user)) -> dict:
    """Every scheduled-but-not-yet-applied pricing change — what "قادم" shows on the calculator."""
    container = request.app.state.container
    changes = await pending_pricing_changes(container.datastore)
    return {"pending": [
        {"key": c.key, "value": c.value, "effective_at": c.effective_at,
         "scheduled_by": c.scheduled_by, "scheduled_at": c.scheduled_at} for c in changes]}


@router.post("/pricing/schedule", dependencies=[Depends(_CONFIG), Depends(rate_limit)])
async def schedule_pricing(request: Request, body: PricingScheduleIn,
                           principal: Principal = Depends(require_user)) -> dict:
    """Schedule a pricing key to change after a mandatory delay — never instant. See
    core/pricing_schedule.py's own docstring for why, and PricingScheduleIn's own note for why the
    delay is enforced here (>= 1 day) rather than trusted from the caller."""
    if not is_a_pricing_key(body.key):
        return _refuse(f"{body.key} is not a pricing key — see app/runtime_policy.py for the "
                       f"five that are.")
    if body.key not in RUNTIME_POLICY:
        # DEFENSE IN DEPTH, NOT REDUNDANT — is_a_pricing_key's own list is hand-kept in sync with
        # RUNTIME_POLICY's pricing subset; this catches the day they drift instead of scheduling
        # a change for a key RuntimeConfig.set() would refuse anyway once the tick tries to apply it.
        return _refuse(f"{body.key} is not declared settable.")
    violation = _ai_unit_bounds_violation(body.key, body.value)
    if violation is not None:
        return _refuse(f"{body.key}: {violation}")
    now = int(time.time())
    effective_at = now + body.effective_in_days * 86_400
    container = request.app.state.container
    await request.app.state.auditor.record(
        "operator.pricing_scheduled", actor=_actor(principal), tenant="",
        resource=f"config:{body.key}", ip=request.client.host if request.client else "",
        metadata={"key": body.key, "effective_in_days": body.effective_in_days})
    change = await schedule_pricing_change(
        container.datastore, key=body.key, value=body.value, effective_at=effective_at,
        actor=_actor(principal), now=now)
    return {"key": change.key, "value": change.value, "effective_at": change.effective_at}


@router.delete("/pricing/pending/{key}", dependencies=[Depends(_CONFIG), Depends(rate_limit)])
async def cancel_pending_pricing(request: Request, key: str,
                                 principal: Principal = Depends(require_user)) -> dict:
    """Cancel a scheduled change before it lands — the operator changed their mind."""
    container = request.app.state.container
    await request.app.state.auditor.record(
        "operator.pricing_schedule_cancelled", actor=_actor(principal), tenant="",
        resource=f"config:{key}", ip=request.client.host if request.client else "")
    return {"cancelled": await cancel_pricing_change(container.datastore, key=key)}


@router.get("/persona-preview", dependencies=[Depends(_CONFIG), Depends(rate_limit)])
async def persona_preview(shop_name: str = "", owner_notes: str = "",
                          principal: Principal = Depends(require_user)) -> dict:
    """The exact text sent as the system prompt — READ-ONLY. build_system_prompt (core/conversation.py)
    is fixed house prose today, not a stored template; there is nothing here yet for an operator to
    save. This exists so "الشخصية والسلوك" can show what actually ships rather than making someone
    read Python to find out — shop_name/owner_notes are optional so a specific shop's real owner_notes
    can be previewed exactly as the model would see them, same rules-first ordering and redaction
    included (see build_system_prompt's own docstring on why owner_notes is treated as data, not
    instructions)."""
    return {"prompt": build_system_prompt(shop_name, owner_notes)}


@router.post("/knowledge/sync-business-info", dependencies=[Depends(_CONFIG), Depends(rate_limit)])
async def sync_business_info(request: Request, tenant: str = "",
                             principal: Principal = Depends(require_user)) -> dict:
    """Push this tenant's owner_notes to Meta Business Agent's real Knowledge API, right now.

    EXPLICIT, OPERATOR-TRIGGERED — NOT ON EVERY owner_notes SAVE. The write path for owner_notes
    lives on operations' AiNotesStore (services/operations/app/core/ai_notes.py), a different
    service with no Graph credential of its own and no reason to gain a hard dependency on Meta's
    API being reachable just to save a text field; that route's own doctrine is "unreadable/unset
    fails open to nothing", which is right for an LLM-prompt field and wrong for a call that
    actually informs Meta's own agent — a failed sync must be something an operator SEES and can
    retry, not something silently swallowed on a save that otherwise succeeded. A real-time hook
    would also fire on every keystroke-debounced autosave the console may add later, hammering a
    third-party API for a field an owner is still drafting. This route is the deliberate seam: the
    owner writes his notes normally (unaffected either way), and an operator pushes them to Meta
    when the shop is ready — same shape as /operator/secrets' own "changed here, take effect when
    asked" surface, not a hidden side effect of a different write.
    """
    if not tenant:
        return _refuse("tenant is required")
    container = request.app.state.container
    ctx = await container.shop_identity.resolve(tenant)
    sent = await container.knowledge_export.export(tenant=tenant, owner_notes=ctx.ai_notes)
    await request.app.state.auditor.record(
        "operator.knowledge_sync", actor=_actor(principal), tenant=tenant,
        resource="knowledge:business_info", ip=request.client.host if request.client else "",
        metadata={"sent": sent})
    return {"sent": sent}


@router.get("/secrets", dependencies=[Depends(_SECRETS), Depends(rate_limit)])
async def list_secrets(request: Request, tenant: str = "",
                       principal: Principal = Depends(require_user)) -> dict:
    """Which credentials are set, and a four-character hint for each — never the value."""
    store = _secret_store(request)
    infos = await store.list_info(tenant=tenant)
    return {"secrets": [{"name": i.name, "hint": i.hint, "set_at": i.set_at,
                         "rotating": i.rotating} for i in infos]}


@router.put("/secrets", dependencies=[Depends(_SECRETS), Depends(rate_limit)])
async def set_secret(request: Request, body: SecretIn,
                     principal: Principal = Depends(require_user)) -> dict:
    """Set or rotate a credential.

    AUDITED AFTER THE WRITE SUCCEEDS, NOT BEFORE — fixed 2026-09-07. The original reasoning here
    ("audited before: the old value is overwritten by the action itself, so an unrecorded rotation
    is unreconstructable") does not survive contact with `SecretError`: a bad value refused by
    `.set()` never touches the old value at all, yet used to be logged as "operator.secret_set"
    regardless — a QA audit found the audit trail could record a rotation that never happened. A
    refusal now gets its own distinctly-named event; a genuine crash between the write and this
    line (the one narrow case the old ordering guarded against) is a real but much rarer risk than
    mislabeling every ordinary validation failure as a completed change."""
    try:
        info = await _secret_store(request).set(
            tenant=body.tenant, name=body.name, value=body.value, actor_ref=_actor(principal))
    except SecretError as exc:
        await request.app.state.auditor.record(
            "operator.secret_set_refused", actor=_actor(principal), tenant=body.tenant or "",
            resource=f"secret:{body.name}", ip=request.client.host if request.client else "",
            metadata={"reason": str(exc)[:200]})
        return _refuse(str(exc))
    await request.app.state.auditor.record(
        "operator.secret_set", actor=_actor(principal), tenant=body.tenant or "",
        resource=f"secret:{body.name}",          # the NAME, never the value or the hint
        ip=request.client.host if request.client else "")
    _invalidate_llm(request)
    return {"name": info.name, "hint": info.hint, "rotating": info.rotating}


@router.delete("/secrets/{name}", dependencies=[Depends(_SECRETS), Depends(rate_limit)])
async def clear_secret(request: Request, name: str, tenant: str = "",
                       principal: Principal = Depends(require_user)) -> dict:
    """Remove a credential so the configured environment value applies again."""
    await request.app.state.auditor.record(
        "operator.secret_cleared", actor=_actor(principal), tenant=tenant,
        resource=f"secret:{name}", ip=request.client.host if request.client else "")
    cleared = await _secret_store(request).clear(tenant=tenant, name=name)
    _invalidate_llm(request)
    return {"cleared": cleared}
