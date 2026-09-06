"""The operator surface — credentials, changeable after launch.

WRITE-ONLY IS ENFORCED HERE, and this file is where the guarantee lives. `SecretStore.get()`
returns plaintext because an adapter cannot authenticate with a masked string; no route in this
module returns it, and `safety:no-secret-reads` fails the build if one ever does. That split is
deliberate: the store is a mechanism, the API boundary is the control.

SECRETS ONLY, NO /operator/config — unlike reminders/loyalty, this service has no
`app/runtime_policy.py`: every knob it has today is deploy-time env, not a per-tenant/runtime
override (see app/api/v1/__init__.py's own note, now half out of date — mirror this file's own
note there the day a real tunable setting shows up and /operator/config is worth adding).

WHY THIS EXISTS NOW: an LLM backend credential is the one thing this service actually needs
changeable at runtime — every wipe+reinstall regenerates the platform's shared secrets but has
nothing that mints a third-party credential (ASSISTANT_MODEL_PROJECT/
ASSISTANT_MODEL_CREDENTIAL), so it silently reverted to empty and the assistant CrashLoopBackOff'd
until someone found the gap and repatched it by hand, off any audited path. This route is that
path, mirroring services/reminders' operator.py exactly for the parts this service actually needs.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.auth import Principal, require_user
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.config import get_settings
from app.core.pii import subject_ref
from app.core.secret_store import SecretError, SecretStore

router = APIRouter(prefix="/api/v1/assistant/operator", tags=["operator"])

_SECRETS = require_capability("platform.secrets")


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
