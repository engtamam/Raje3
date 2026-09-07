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

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.auth import Principal, require_user
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.config import Settings, get_settings
from app.core.pii import subject_ref
from app.core.runtime_config import RuntimeConfig, RuntimeConfigError
from app.core.secret_store import SecretError, SecretStore
from app.runtime_policy import RUNTIME_POLICY

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
    return RuntimeConfig(request.app.state.container.datastore, Settings, policy=RUNTIME_POLICY)


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
    return {"config": await rc.effective(tenant=tenant, settings=get_settings())}


@router.put("/config", dependencies=[Depends(_CONFIG), Depends(rate_limit)])
async def set_config(request: Request, body: ConfigIn,
                     principal: Principal = Depends(require_user)) -> dict:
    """Override one policy value. Refused if the boot guard would refuse it."""
    await request.app.state.auditor.record(
        "operator.config_changed", actor=_actor(principal), tenant=body.tenant or "",
        resource=f"config:{body.key}", ip=request.client.host if request.client else "",
        metadata={"key": body.key})     # the KEY is not a secret; settable knobs never are
    try:
        o = await _runtime_config(request).set(
            tenant=body.tenant, key=body.key, value=body.value, actor_ref=_actor(principal))
    except RuntimeConfigError as exc:
        return _refuse(str(exc))
    # ASSISTANT_MODEL_NAME is read fresh every LLM call already (see assistant_service.py's own
    # `_resolve_model_name`) — no cache to invalidate here the way the secrets routes need to.
    return {"key": o.key, "value": o.value}


@router.delete("/config/{key}", dependencies=[Depends(_CONFIG), Depends(rate_limit)])
async def clear_config(request: Request, key: str, tenant: str = "",
                       principal: Principal = Depends(require_user)) -> dict:
    """Drop an override so the configured default applies again."""
    await request.app.state.auditor.record(
        "operator.config_changed", actor=_actor(principal), tenant=tenant,
        resource=f"config:{key}", ip=request.client.host if request.client else "",
        metadata={"key": key, "cleared": True})
    return {"cleared": await _runtime_config(request).clear(tenant=tenant, key=key)}


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
    """Set or rotate a credential. Audited BEFORE the write: a change the log cannot take must not
    happen, and here the old value is overwritten by the action itself, so an unrecorded rotation
    is unreconstructable."""
    await request.app.state.auditor.record(
        "operator.secret_set", actor=_actor(principal), tenant=body.tenant or "",
        resource=f"secret:{body.name}",          # the NAME, never the value or the hint
        ip=request.client.host if request.client else "")
    try:
        info = await _secret_store(request).set(
            tenant=body.tenant, name=body.name, value=body.value, actor_ref=_actor(principal))
    except SecretError as exc:
        return _refuse(str(exc))
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
