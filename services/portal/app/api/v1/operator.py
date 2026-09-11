"""The operator surface — credentials and policy, changeable after launch.

WRITE-ONLY IS ENFORCED HERE, and this file is where the guarantee lives. `SecretStore.get()`
returns plaintext because an adapter cannot authenticate with a masked string; no route in this
module returns it, and `safety:no-secret-reads` fails the build if one ever does. That split is
deliberate: the store is a mechanism, the API boundary is the control.

`platform.secrets` IS ITS OWN CAPABILITY. Setting a payment key and reading a report are not the
same privilege, and a panel that conflates them hands every report-reader the ability to redirect
money.

EVERY MUTATION IS AUDITED WRITE-AHEAD AND CRITICAL. A credential change that cannot be recorded
must not happen: an unprovable one is indistinguishable from an attacker's, and the previous value
is already gone by the time anybody looks.
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

router = APIRouter(prefix="/api/v1/portal/operator", tags=["operator"])

_CONFIG = require_capability("platform.config")


def _actor(principal: Principal) -> str:
    """A pseudonym. An audit row naming the operator is still personal data, and this one lands in
    an append-only chain.

    REFUSES ON AN EMPTY SALT, NOW — fixed 2026-09-12, a real gap a QA audit found. Production
    already refuses to boot with no PII_SALT (config.py's own guard), so this is reachable only in
    a misconfigured dev/local run — but silently returning "" there meant every privileged config
    change in that state got audited with NO actor at all, destroying forensic traceability for
    exactly the mutations this file's own module docstring calls "write-ahead AND critical". Same
    "refuse rather than silently degrade" posture core.pii.subject_ref itself already takes on an
    empty salt.
    """
    s = get_settings()
    if not s.PII_SALT:
        raise RuntimeConfigError("PII_SALT غير مُهيَّأ — تعذّر تسجيل من قام بهذا التغيير")
    return subject_ref(s.PII_SALT, principal.tenant or "", principal.subject)


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


# ── policy ────────────────────────────────────────────────────────────────────
# RATE_LIMIT BEFORE THE CAPABILITY CHECK, ON ALL THREE ROUTES BELOW — fixed 2026-09-12, a real
# gap a QA audit found. FastAPI resolves top-level `dependencies=[...]` in the order listed; with
# `_CONFIG` (require_capability -> require_user -> full JWT verification) listed first, every
# request — no token, a garbage token, an insufficiently-privileged one — paid for a complete
# token verification and raised its own 401/403 before `rate_limit` ever ran, on the highest-
# privilege runtime-config surface this service exposes. Listing the limiter first means an
# unthrottled flood of invalid-auth requests is throttled before the token verifier ever sees it.
@router.get("/config", dependencies=[Depends(rate_limit), Depends(_CONFIG)])
async def effective_config(request: Request, tenant: str = "",
                           principal: Principal = Depends(require_user)) -> dict:
    """Every knob an operator may change, with its current effective value.

    Built from the settable set, so a credential, a DSN or a frozen identifier cannot appear here
    even by accident — the filter is in one place rather than repeated per field.
    """
    rc = _runtime_config(request)
    return {"config": await rc.effective(tenant=tenant, settings=get_settings())}


@router.put("/config", dependencies=[Depends(rate_limit), Depends(_CONFIG)])
async def set_config(request: Request, body: ConfigIn,
                     principal: Principal = Depends(require_user)) -> dict:
    """Override one policy value. Refused if the boot guard would refuse it."""
    try:
        actor = _actor(principal)
    except RuntimeConfigError as exc:
        return _refuse(str(exc))
    await request.app.state.auditor.record(
        "operator.config_changed", actor=actor, tenant=body.tenant or "",
        resource=f"config:{body.key}", ip=request.client.host if request.client else "",
        metadata={"key": body.key})     # the KEY is not a secret; settable knobs never are
    try:
        o = await _runtime_config(request).set(
            tenant=body.tenant, key=body.key, value=body.value, actor_ref=actor)
    except RuntimeConfigError as exc:
        return _refuse(str(exc))
    # The tenant is NOT echoed. The caller supplied it, so returning it adds nothing, and a
    # response field named "tenant" is indistinguishable — to a reader and to the tenancy gate —
    # from a verified claim. The one wall between every company on this platform is that the
    # tenant is believed everywhere and checked in exactly one place; nothing here should look
    # like that check.
    return {"key": o.key, "value": o.value}


@router.delete("/config/{key}", dependencies=[Depends(rate_limit), Depends(_CONFIG)])
async def clear_config(request: Request, key: str, tenant: str = "",
                       principal: Principal = Depends(require_user)) -> dict:
    """Drop an override so the configured default applies again."""
    try:
        actor = _actor(principal)
    except RuntimeConfigError as exc:
        return _refuse(str(exc))
    await request.app.state.auditor.record(
        "operator.config_changed", actor=actor, tenant=tenant,
        resource=f"config:{key}", ip=request.client.host if request.client else "",
        metadata={"key": key, "cleared": True})
    return {"cleared": await _runtime_config(request).clear(tenant=tenant, key=key)}
