"""The till's door — a shop's own point-of-sale, sending the visits it already captured.

THIS EXISTS TO CLOSE A HOLE, and the hole is worth stating plainly because it is the kind that
looks like nothing on a diagram.

The only route that accepted invoice lines was `/internal/operations/visits/batch`, guarded by
`X-Internal-Token` — ONE secret, shared by every service in the fleet. Handing it to a POS company
would not have given them the invoice door; it would have given them every internal door in the
product: backup export, the erasure fan-out, seeding any tenant's catalogue. One key, everything.

And a second hole behind it: that route reads `tenant` OFF THE REQUEST BODY. Even with a narrower
credential, a till could write visits into somebody else's shop by changing one line — which is
not a bug you find by testing your own integration, because your own integration never tries.

────────────────────────────────────────────────────────────────────────────────────────────────
SO THIS ROUTE IS DIFFERENT IN THREE WAYS, AND ALL THREE MATTER

  1. A MACHINE'S OWN CREDENTIAL. It takes an ordinary Bearer token — the one identity mints for a
     service account (OAuth2 client-credentials). Signed by the same issuer as a human's, so it
     verifies on the path this service already has, and its subject reads `svc_…` in the audit
     trail: the log distinguishes "the till" from "Ahmed in accounting".

  2. ONE CAPABILITY. `operations.record`, and a service account can never hold more than the human
     who issued it. So a till may record a visit and can do nothing else — not because we trust it
     not to, but because the token does not carry the power.

  3. THE TENANT COMES FROM THE TOKEN, NEVER FROM THE BODY. This is the whole security property.
     A machine credential is minted for exactly one establishment, so a till physically cannot
     name another one: there is no field for it to set. Any `tenant` a caller sends is IGNORED
     rather than validated — a validated field is a field somebody later "fixes" to accept a
     legitimate-looking override.

────────────────────────────────────────────────────────────────────────────────────────────────
THE INTERNAL ROUTE STAYS, and it is not a duplicate. It serves OUR services — the ones that
legitimately act across tenants and legitimately hold the shared token. What changed is that it is
no longer the door an outside party would have to be let through.
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.auth import Principal
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit

router = APIRouter(prefix="/till", tags=["till"])

# THE ONLY CAPABILITY A TILL EVER NEEDS. It is deliberately the same one the operator at the
# counter holds: recording a visit is recording a visit, whoever the hands belong to.
_TILL = require_capability("operations.record")


class TillLineIn(BaseModel):
    """One line of the shop's invoice TO ITS CUSTOMER — not our invoice to the shop."""

    product_id: str = Field(default="", max_length=128)
    name: str = Field(default="", max_length=200)
    qty: float = Field(default=1, ge=0, le=100_000)
    amount_minor: int = Field(default=0, ge=0, le=1_000_000_000)


class TillVisitIn(BaseModel):
    """A completed sale, as the till holds it.

    NO `tenant` FIELD, AND THAT IS THE POINT. See the module note: the establishment is read off
    the credential. A model without the field cannot be talked into accepting one.
    """

    phone: str = Field(default="", max_length=32)
    name: str = Field(default="", max_length=128)
    plate: str = Field(default="", max_length=32)
    branch_id: str = Field(default="", max_length=64)
    operator_id: str = Field(default="", max_length=64)
    meter: int = Field(default=0, ge=0, le=10_000_000)
    note: str = Field(default="", max_length=1000)
    lines: list[TillLineIn] = Field(default_factory=list, max_length=50)
    # THEIR invoice number. The idempotency key derives from it, because the till is the only party
    # that knows whether two calls are the same sale — a key we generated would be new on every
    # retry, which is exactly the doubling this prevents.
    invoice_id: str = Field(default="", max_length=128)
    idempotency_key: str = Field(default="", max_length=128)
    # The device's clock, which may be days out. Kept alongside our receive time rather than
    # instead of it — reminders schedule from the visit, and a till running two days fast would
    # otherwise produce a reminder that arrives before it should.
    occurred_at: int = Field(default=0, ge=0)


class TillBatchIn(BaseModel):
    # Small on purpose: an SDK drains oldest-first in modest batches with a randomised gap, so a
    # city's network coming back does not put a thousand tills on us in the same second.
    visits: list[TillVisitIn] = Field(min_length=1, max_length=50)


@router.post("/visits", dependencies=[Depends(rate_limit)])
async def record_from_till(request: Request, body: TillBatchIn,
                           principal: Principal = Depends(_TILL)) -> Any:
    """Accept what the till already captured, and report the outcome PER ITEM.

    PER ITEM, NOT PER BATCH — the failure every hand-written offline queue walks into. An
    all-or-nothing batch holding one permanently-invalid visit fails, is retried, fails again,
    forever; everything behind it stops moving while the shop believes it is syncing. Nothing
    errors anywhere a human is looking.
    """
    if not principal.tenant:
        # A token with no tenant claim is REFUSED, never widened. A machine credential always
        # belongs to exactly one establishment; one that does not is not a till.
        return {"accepted": 0, "total": len(body.visits),
                "message": "هذا الاعتماد غير مرتبط بمنشأة."}

    from app.api.internal import BatchIn, BatchVisitIn, record_visits_batch

    # THE TENANT IS STAMPED ON EVERY ITEM FROM THE TOKEN, overwriting nothing because there was
    # nothing to overwrite — `TillVisitIn` has no such field. This is the single line the whole
    # module exists for.
    tenant = principal.tenant
    now = int(time.time())
    forwarded = BatchIn(visits=[
        BatchVisitIn(
            tenant=tenant,
            phone=v.phone, name=v.name, plate=v.plate,
            branch_id=v.branch_id, operator_id=v.operator_id,
            meter=v.meter, note=v.note,
            lines=[line.model_dump() for line in v.lines],
            invoice_id=v.invoice_id,
            # A batch is by definition a replay, and a replay without a stable key is how one lost
            # reply becomes two visits, two reminders and doubled revenue. The invoice number is
            # the till's own idea of "the same sale"; our fallback is only for a till that sends
            # neither, and it is per-request so at least a retry inside one call cannot double.
            idempotency_key=v.idempotency_key or (f"till:{tenant}:{v.invoice_id}"
                                                  if v.invoice_id else f"till:{tenant}:{now}:{i}"),
            occurred_at=v.occurred_at,
        )
        for i, v in enumerate(body.visits)
    ])

    # REUSED, NOT REIMPLEMENTED. The batch handler holds the per-item outcome reporting, the
    # invoice resolution, the integration detection and the seams; a second copy here would be a
    # second set of behaviour to keep in step, and the one that drifts is always the newer.
    return await record_visits_batch(request, forwarded)
