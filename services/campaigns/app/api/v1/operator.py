"""The operator surface — policy, changeable after launch.

EVERY MUTATION IS AUDITED WRITE-AHEAD. A change that cannot be recorded must not happen: an
unprovable one is indistinguishable from an attacker's, and the previous value is already gone by
the time anybody looks.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.auth import Principal, require_user
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.config import get_settings
from app.core.pii import subject_ref
from app.core.runtime_config import RuntimeConfig, RuntimeConfigError

router = APIRouter(prefix="/api/v1/campaigns/operator", tags=["operator"])

_CONFIG = require_capability("platform.config")


def _actor(principal: Principal) -> str:
    """A pseudonym. An audit row naming the operator is still personal data, and this one lands in
    an append-only chain."""
    s = get_settings()
    if not s.PII_SALT:
        return ""
    return subject_ref(s.PII_SALT, principal.tenant or "", principal.subject)


async def _audit_refused(request: Request, action: str, *, resource: str, tenant: str,
                        actor: str, reason: str) -> None:
    """A second, corrective entry for the SAME action/resource — fixed 2026-09-12, a real gap a
    QA audit found. The write-ahead record above exists so a config change that cannot be
    witnessed must not happen at all — it was never meant to claim SUCCESS for a refusal that is
    refused for an ordinary, expected reason (bad value, unknown/undeclared key) and never
    touched anything. Append-only, so this is a correction an investigator reads alongside the
    attempt, never an edit to it."""
    await request.app.state.auditor.record(
        action, actor=actor, tenant=tenant, resource=resource,
        ip=request.client.host if request.client else "",
        metadata={"outcome": "refused", "reason": reason})


def _runtime_config(request: Request) -> RuntimeConfig:
    """The instance wired at boot, so the service's RUNTIME_POLICY applies.

    Building a fresh one here would silently carry no policy, and a RuntimeConfig with no policy
    refuses everything — the panel would report every knob as unsettable while the service believed
    it had wired them.
    """
    rc = getattr(request.app.state, "runtime_config", None)
    if rc is not None:
        return rc
    from app.config import Settings
    from app.runtime_policy import RUNTIME_POLICY

    return RuntimeConfig(request.app.state.container.datastore, Settings, policy=RUNTIME_POLICY)



def _refuse(reason: str, status_code: int = 400) -> JSONResponse:
    """A refusal the OPERATOR can read — returned, not raised.

    The platform's error handler strips `detail` from every HTTPException on purpose (CWE-209),
    which is right for a stack trace and wrong for this: these are sentences WE wrote, naming a
    rule the operator broke. Raised, they arrive as `{"error": "BAD_REQUEST"}` and the operator on
    our own panel is told only that something is invalid — so he tries the same thing again.

    THE STATUS IS KEPT. A caller checking `response.ok` behaves exactly as before; only the body
    gains the sentence. Changing the status to 200 would have made the refusal look like a success
    to every existing reader, which is a worse defect than the one being fixed.
    """
    return JSONResponse({"error": "BAD_REQUEST", "reason": reason}, status_code=status_code)


class ConfigIn(BaseModel):
    key: str = Field(..., min_length=1, max_length=128)
    value: str | int | float | bool
    tenant: str = Field(default="", max_length=128)


# The operator surface: policy an operator changes after launch. The credential-management routes
# that used to sit here (a dead SecretStore nothing ever consumed) were removed — see git history.
# ── policy ────────────────────────────────────────────────────────────────────
@router.get("/config", dependencies=[Depends(_CONFIG), Depends(rate_limit)])
async def effective_config(request: Request, tenant: str = "",
                           principal: Principal = Depends(require_user)) -> dict:
    """Every knob an operator may change, with its current effective value.

    Built from the settable set, so a credential, a DSN or a frozen identifier cannot appear here
    even by accident — the filter is in one place rather than repeated per field.
    """
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
        await _audit_refused(request, "operator.config_changed", resource=f"config:{body.key}",
                             tenant=body.tenant or "", actor=_actor(principal), reason=str(exc))
        return _refuse(str(exc))
    # The tenant is NOT echoed. The caller supplied it, so returning it adds nothing, and a
    # response field named "tenant" is indistinguishable — to a reader and to the tenancy gate —
    # from a verified claim. The one wall between every company on this platform is that the
    # tenant is believed everywhere and checked in exactly one place; nothing here should look
    # like that check.
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
