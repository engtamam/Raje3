"""The owner's own surface for the five external credentials — WRITE-ONLY, on purpose.

A VALUE CAN BE SET AND NEVER READ BACK. That is the single rule this file is built around, and it
is enforced structurally rather than by discipline:

  * the list route calls `read_secret_annotations`, which is the only read method the k8s adapter
    has, and it discards `data` one layer below every caller here;
  * the write route returns the key, the last four characters and the timestamp — the value it was
    just handed never appears in a response model;
  * there is no third route. "Reveal", even behind a second capability, is not implemented, because
    a credential a console can display is a credential in every screenshot, every screen-share and
    every browser history of everyone who ever held that capability.

WHY THIS IS A SERVICE AND NOT A RUNBOOK. Rotating a leaked provider key used to mean a developer
with a kubeconfig, by hand, at speed, under pressure — the exact conditions under which somebody
patches the right secret in the wrong namespace. Now it is a form the owner fills in, gated by one
capability nobody else on the platform holds, and every write is witnessed.

EVERY WRITE RESTARTS SOMETHING, and the screen says so before the button is pressed. A secret is
read into a container's environment at start, so a write with no rollout is a write that appears to
work and changes nothing until the next unrelated deploy.
"""
from __future__ import annotations

import datetime as _dt

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.auth import Principal
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.adapters.k8s_client import K8sError
from app.core.secret_registry import (
    BY_KEY,
    SECRETS,
    last4_annotation,
    last4_of,
    updated_at_annotation,
    updated_by_annotation,
)

# The parent router in __init__ already carries /api/v1 — this prefix is appended to it.
router = APIRouter(prefix="/secrets", tags=["secrets"])

# NARROWER THAN `platform.operations`, DELIBERATELY. Editing a message template and replacing the
# credential that every WhatsApp message in the product is sent with are not the same privilege,
# and an operator who curates content should not hold the second because he needed the first.
_OWNER = require_capability("platform.secrets_manage")


def _refuse(reason: str) -> JSONResponse:
    """A refusal OUR OWN OPERATOR can read — returned, not raised.

    The platform's handler strips `detail` from every HTTPException (CWE-209 by design), which is
    right for a stack trace and wrong for these: each one names a rule the form broke, and raised
    it would arrive as `{"error": "BAD_REQUEST"}` in front of somebody holding a key they cannot
    save. THE STATUS IS KEPT, so every caller that checks `response.ok` behaves exactly as before.
    """
    return JSONResponse({"error": "BAD_REQUEST", "reason": reason}, status_code=400)


def _now_iso() -> str:
    """UTC, to the second, with a `Z`. Written into an annotation a person reads in kubectl."""
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class SecretIn(BaseModel):
    """The one field on the form.

    NO `key` IN THE BODY — it is in the path, checked against the registry, and a body that could
    also name a key would be two sources for one fact with no rule about which wins.

    NOT BOUNDED ABOVE BY A GUESS. 4096 is well past any provider token in the registry and well
    short of a body that could be used to push something large through an audited path.
    """

    value: str = Field(max_length=4096)


@router.get("", dependencies=[Depends(rate_limit)])
async def list_secrets(request: Request, principal: Principal = Depends(_OWNER)) -> dict:
    """What is configured, and what is not — read from ANNOTATIONS, never from `data`.

    THIS HANDLER CANNOT RETURN A SECRET VALUE, and that is a property of its shape rather than a
    promise about its behaviour. It never fetches `data`: the adapter method it calls returns a
    dict of annotations and nothing else, so there is no variable in this scope that has ever held
    a credential. A future edit that wanted to leak one would have to add a method to the adapter
    first, which is a diff somebody reads.

    NOT AUDITED. This is a read of metadata an operator is entitled to see, performed on every page
    load; recording it would bury the writes — the events an investigation is actually looking for
    — under a stream of routine list calls. The WRITES are what this service exists to prove.

    A CLUSTER THAT WILL NOT ANSWER IS SAID OUT LOUD, per row. Reporting «غير مُعدّ» for a secret we
    simply could not read would tell the owner to set a key that is already set — and that
    instruction ends in a working credential being overwritten during an incident.
    """
    k8s = request.app.state.container.k8s
    # ONE READ PER SECRET OBJECT, NOT PER KEY. Four of the five live in the same Secret, so keying
    # the cache on (namespace, name) turns five API calls into two.
    seen: dict[tuple[str, str], dict[str, str] | None] = {}
    rows = []
    for entry in SECRETS:
        addr = (entry.namespace, entry.secret)
        if addr not in seen:
            try:
                seen[addr] = k8s.read_secret_annotations(entry.namespace, entry.secret)
            except K8sError:
                seen[addr] = None
        anns = seen[addr]
        if anns is None:
            rows.append({"key": entry.key, "label": entry.label, "configured": None,
                         "last4": None, "updated_at": None, "updated_by": None,
                         "unreadable": True})
            continue
        last4 = anns.get(last4_annotation(entry), "")
        rows.append({
            "key": entry.key,
            "label": entry.label,
            # THE ANNOTATION IS THE EVIDENCE, and it is written by this service alone. A secret set
            # by a developer with kubectl carries no annotation, so it reads as «غير مُعدّ» while
            # being perfectly live — the honest answer, since we genuinely do not know its last
            # four characters and inventing them would be worse than admitting the gap.
            "configured": bool(last4),
            "last4": last4 or None,
            "updated_at": anns.get(updated_at_annotation(entry)) or None,
            "updated_by": anns.get(updated_by_annotation(entry)) or None,
            "unreadable": False,
        })
    return {"secrets": rows}


@router.post("/{key}", dependencies=[Depends(rate_limit)])
async def set_secret(request: Request, key: str, body: SecretIn,
                     principal: Principal = Depends(_OWNER)) -> dict:
    """Replace one credential and roll the service that reads it.

    THE ORDER IS WRITE THEN RESTART, AND A FAILED RESTART IS REPORTED RATHER THAN SWALLOWED. If the
    rollout patch fails, the new value IS stored and the running pods are still on the old one —
    which is a real, recoverable state, and the one sentence the owner needs is that the value
    saved but the service did not restart. Reporting success there would leave him watching a
    correct key fail to send.

    THE ACTOR IS THE TOKEN'S SUBJECT, never a field in the body. «Who replaced this key, and when»
    is the entire reason the record exists, and a self-declared name is not an answer.

    AUDITED BEFORE THE WRITE, AND CRITICAL. `AuditUnavailable` propagates to a 503 and nothing is
    patched: a credential change nobody can attribute is indistinguishable from an attacker's, and
    an unwitnessed one is exactly the event an investigation turns on.
    """
    entry = BY_KEY.get(key)
    if entry is None:
        # THE REGISTRY IS THE ALLOW-LIST, and the 404 is the first of two refusals — the cluster
        # Role refuses the same thing again with `resourceNames`. Two enforcements of one rule,
        # in the two places that can enforce it.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    value = body.value.strip()
    if not value:
        return _refuse("أدخل القيمة — لا يمكن حفظ مفتاح فارغ.")

    at = _now_iso()
    actor = getattr(principal, "subject", "") or ""
    # NO VALUE AND NO FRAGMENT OF ONE IN THIS RECORD — not the last four either. The audit log is
    # a hash chain nobody can edit and everybody with the audit capability can read; four
    # characters of a live credential written into it permanently is a disclosure to a wider
    # audience than the one person who typed them.
    await request.app.state.auditor.record(
        "platform.secret_changed", actor=actor, tenant="",
        resource=f"secret:{entry.secret}:{entry.key}",
        ip=request.client.host if request.client else "",
        metadata={"namespace": entry.namespace, "deployment": entry.deployment})

    last4 = last4_of(value)
    k8s = request.app.state.container.k8s
    try:
        k8s.patch_secret(entry.namespace, entry.secret,
                         data={entry.key: value},
                         annotations={last4_annotation(entry): last4,
                                      updated_at_annotation(entry): at,
                                      updated_by_annotation(entry): actor})
    except K8sError as exc:
        return _refuse(f"تعذّر حفظ المفتاح في العنقود: {exc}")

    try:
        k8s.restart_deployment(entry.namespace, entry.deployment, at=at)
    except K8sError as exc:
        # SAVED, NOT APPLIED — and the difference is the whole message. Retrying the save would
        # rewrite a value that is already correct; what is needed is a restart.
        return JSONResponse(
            {"error": "BAD_REQUEST",
             "reason": f"حُفظ المفتاح، ولم تُعد تشغيل الخدمة ({entry.deployment}): {exc}. "
                       f"القيمة الجديدة لن تُقرأ حتى إعادة التشغيل.",
             "key": entry.key, "last4": last4, "updated_at": at, "restarted": False},
            status_code=400)

    return {"key": entry.key, "last4": last4, "updated_at": at, "restarted": True}
