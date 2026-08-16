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

import hashlib
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.auth import Principal
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.core.operations import OperationError

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


def content_key(*, tenant: str, visit: "TillVisitIn") -> str:
    """A key derived from the sale itself, for a till that sends no key and no invoice number.

    THE FALLBACK IT REPLACES WAS THE BUG. It was `till:{tenant}:{now}:{i}` — unique inside one
    request and new on the next, so a till that lost the reply and re-sent two seconds later
    recorded every visit a second time: doubled history, doubled reminders, doubled points, and
    an owner asking why a customer who came once shows twice.

    SO THE KEY COMES FROM THE CONTENT, and the same sale hashes to the same key however many times
    it is sent. `occurred_at` is part of it and is the till's own clock — ours moves between
    retries, which is precisely what broke the old one.

    TWO GENUINELY IDENTICAL SALES — same shop, same number, same second, same lines — collapse
    into one. That is the safer of the two errors by a wide margin: merging a real duplicate pair
    costs one visit; splitting a retried sale costs a customer's trust in every message we send
    him afterwards.
    """
    parts = [tenant, (visit.phone or "").strip(), str(visit.occurred_at),
             (visit.plate or "").strip(), str(visit.meter or 0)]
    # SORTED, because a till is free to reorder the lines of the same invoice between retries —
    # and an unsorted fingerprint would make the reorder look like a different sale.
    parts += sorted(f"{line.product_id}|{line.name}|{line.qty}|{line.amount_minor}"
                    for line in (visit.lines or []))
    digest = hashlib.sha256("".join(parts).encode()).hexdigest()[:32]
    return f"till:{tenant}:c:{digest}"


def _key_for(tenant: str, visit: "TillVisitIn") -> str:
    """Their key, else their invoice number, else the sale's own fingerprint."""
    if visit.idempotency_key:
        return visit.idempotency_key
    if visit.invoice_id:
        # NAMESPACED, so a till whose invoice numbers restart at 1 each day cannot collide with a
        # key some other integration chose.
        return f"till:{tenant}:{visit.invoice_id}"
    return content_key(tenant=tenant, visit=visit)


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

    # HAS THIS SHOP BOUGHT THE LINK AT ALL? `feature.api` was sold from the first price list and
    # checked by nothing — any shop on any plan could point a till at us. Refused only on a
    # DEFINITE no: an unreachable billing lets the sale through, because a fleet-wide hiccup must
    # never stop every counter in the country from recording its day (see core/licence.py).
    from app.core.licence import NOT_INCLUDED as API_NOT_INCLUDED, refuses_machine_writes

    if await refuses_machine_writes(
            getattr(request.app.state.container, "api_licence", None), principal.tenant):
        return {"accepted": 0, "total": len(body.visits), "message": API_NOT_INCLUDED}

    from app.api.internal import BatchIn, BatchVisitIn, record_visits_batch

    # THE TENANT IS STAMPED ON EVERY ITEM FROM THE TOKEN, overwriting nothing because there was
    # nothing to overwrite — `TillVisitIn` has no such field. This is the single line the whole
    # module exists for.
    tenant = principal.tenant
    # A SALE WITH NOTHING STABLE ON IT IS REFUSED, not accepted with a key that changes.
    #
    # Three things can make a retry recognisable: their own key, their invoice number, or the time
    # the sale happened by their clock. A till that sends none of the three has given us no way to
    # tell "the same sale again" from "another sale", and inventing one from OUR clock is what
    # doubled a shop's history. The refusal names all three, per item, so the rest of the batch
    # still lands and their engineer reads a sentence instead of guessing.
    unstable = [i for i, v in enumerate(body.visits)
                if not (v.idempotency_key or v.invoice_id or v.occurred_at)]
    if unstable:
        return {"accepted": 0, "total": len(body.visits),
                "results": [{"idempotency_key": "", "status": "rejected",
                             "reason": "send one of: idempotency_key, invoice_id, occurred_at — "
                                       "without one a retry cannot be told from a second sale",
                             "index": i} for i in unstable]}
    forwarded = BatchIn(visits=[
        BatchVisitIn(
            tenant=tenant,
            phone=v.phone, name=v.name, plate=v.plate,
            branch_id=v.branch_id, operator_id=v.operator_id,
            meter=v.meter, note=v.note,
            lines=[line.model_dump() for line in v.lines],
            invoice_id=v.invoice_id,
            # A batch is by definition a replay, and a replay without a stable key is how one
            # lost reply becomes two visits, two reminders and doubled revenue. `_key_for` picks
            # the most authoritative thing the till gave us, and every one of its answers is the
            # same on the second attempt — which the old fallback was not.
            idempotency_key=_key_for(tenant, v),
            occurred_at=v.occurred_at,
        )
        for v in body.visits
    ])

    # REUSED, NOT REIMPLEMENTED. The batch handler holds the per-item outcome reporting, the
    # invoice resolution, the integration detection and the seams; a second copy here would be a
    # second set of behaviour to keep in step, and the one that drifts is always the newer.
    out = await record_visits_batch(request, forwarded)

    # AND THE LINK'S PULSE IS WRITTEN HERE, where a till is known to be a till.
    #
    # A shop whose point-of-sale stops posting believes its visits are being recorded and we
    # believe the partner is healthy — every screen we own describes what arrived, not what
    # stopped arriving. One counter on the hot path is what lets a panel name the shop that went
    # quiet three weeks ago, instead of an owner discovering it in a month of missing reminders.
    #
    # NEVER AT THE COST OF THE SALE. The visits are already durable at this point; a health row
    # that cannot be written is a health row we do without.
    try:
        from app.core.till_health import TillHealth
        results = out.get("results") or []
        rejected = [r for r in results if r.get("status") == "rejected"]
        await TillHealth(request.app.state.container.datastore).record(
            tenant,
            accepted=int(out.get("accepted", 0)),
            rejected=len(rejected),
            duplicate=len([r for r in results if r.get("status") == "duplicate"]),
            reason=(rejected[0].get("reason") or "") if rejected else "")
    except Exception as exc:                                                    # noqa: BLE001
        request.app.state.container.telemetry.event("till_health_write_failed",
                                                    tenant=tenant, error=str(exc)[:200])
    return out


# ══════════════════════════════════════════════════════════════════════════════════════════════
#  THE OTHER DIRECTION — and it did not exist.
#
#  The till sent us sales and heard back «accepted: 3». Nothing else. Not the customer's points,
#  not what he could redeem, not the offer he is holding — at the one moment in the whole product
#  where the customer is standing in front of a person, paying, and can be told.
#
#  «عندك 120 نقطة، تبغى تستبدلها؟» is said there or it is never said. Our own field screen says
#  it; a shop whose till company integrated us got a silent version of the same product, and the
#  loyalty programme it pays for stopped at the counter.
#
#  ONE CALL, NOT THREE. The vendor sends a phone number and gets everything the counter needs.
#  Resolving a pseudonym, then calling a second host, then reconciling two error shapes is three
#  chances for an integration written once to get it wrong.
# ══════════════════════════════════════════════════════════════════════════════════════════════


@router.get("/customer", dependencies=[Depends(rate_limit)])
async def customer_at_the_counter(request: Request, phone: str = "", plate: str = "",
                                  principal: Principal = Depends(_TILL)) -> Any:
    """Who this is, what he has, and what he can take right now.

    ANSWERS `found: false` RATHER THAN 404. A new customer is the ordinary case at a till, not an
    error, and a vendor's HTTP layer treats a 404 as a fault to log and retry.

    NEVER THE PSEUDONYM. It is our join key between services, and a till has no use for it — it
    identifies its customer by the phone number it already holds. Handing it out would put a
    durable cross-service identifier into a third party's database for no purpose it has.
    """
    if not principal.tenant:
        return {"found": False, "message": "هذا الاعتماد غير مرتبط بمنشأة."}
    tenant = principal.tenant
    svc = request.app.state.container.operations

    c = None
    if phone.strip():
        c = await svc.customer_by_phone(tenant, phone.strip())
    if c is None and plate.strip():
        c = await svc.customer_by_plate(tenant, plate.strip())
    if c is None:
        return {"found": False}

    out: dict[str, Any] = {"found": True, "name": c.name or "", "visits": getattr(c, "visits", 0)}

    desk = getattr(request.app.state.container, "loyalty_desk", None)
    if desk is None or not desk.configured or not c.subject_ref:
        # SILENT, NOT ZERO. A shop without the loyalty feature has no points section at its
        # counter either (§9.9) — and a zero balance for a customer holding three hundred is a
        # grievance we handed over ourselves.
        return out

    bal = await desk.balance(tenant=tenant, subject_ref=c.subject_ref)
    if bal is None:
        # THE FAILURE IS NAMED. A cashier who is told "we could not check" asks the customer to
        # wait a moment; one shown 0 tells him he has nothing, and is believed.
        out["points_unavailable"] = True
        return out

    out["points"] = bal.get("points", 0)
    out["to_next_reward"] = bal.get("to_next_reward", 0)
    # ONLY WHAT HE CAN AFFORD, exactly as the field screen shows it: a list of things he cannot
    # have turns a moment of goodwill into a menu of refusals.
    out["rewards"] = [{"id": r.get("id"), "name": r.get("name"), "cost": r.get("cost")}
                      for r in (bal.get("rewards") or [])]
    return out


class TillRedeemIn(BaseModel):
    """Hand a reward over, from their screen (§9.8)."""

    phone: str = Field(default="", max_length=32)
    plate: str = Field(default="", max_length=32)
    reward_id: str = Field(min_length=1, max_length=128)
    # THEIR key, required — not defaulted. See the type's own note in loyalty: a key we mint is
    # new on every retry, and a doubled redemption spends a customer's points twice.
    idempotency_key: str = Field(min_length=1, max_length=128)
    actor: str = Field(default="", max_length=64)
    branch_id: str = Field(default="", max_length=64)


@router.post("/redeem", dependencies=[Depends(rate_limit)])
async def redeem_at_the_counter(request: Request, body: TillRedeemIn,
                                principal: Principal = Depends(_TILL)) -> Any:
    """Spend his points at their till, and answer with what the receipt must carry.

    THE ENGINE WAS ALREADY BUILT. `loyalty` has served `/internal/loyalty/redeem` — with its
    idempotency key, its cashier attribution, its branch and its customer receipt — since the
    programme was written, and nothing anywhere could reach it: the spec says redemption at an
    integrated till happens over the API (§9.8), and the API had no door. This is the door.

    STILL `operations.record`. The till does not gain a capability over the ledger: it asks us,
    and we ask loyalty with our own credential. What a third party holds must stay the smallest
    thing that does its job.
    """
    if not principal.tenant:
        return {"ok": False, "message": "هذا الاعتماد غير مرتبط بمنشأة."}
    tenant = principal.tenant
    svc = request.app.state.container.operations

    c = None
    if body.phone.strip():
        c = await svc.customer_by_phone(tenant, body.phone.strip())
    if c is None and body.plate.strip():
        c = await svc.customer_by_plate(tenant, body.plate.strip())
    if c is None or not c.subject_ref:
        return {"ok": False, "reason": "NOT_FOUND", "message": "لا يوجد عميل بهذا الرقم."}

    desk = getattr(request.app.state.container, "loyalty_desk", None)
    if desk is None or not desk.configured:
        return {"ok": False, "reason": "UNAVAILABLE", "message": "تعذّر الوصول إلى برنامج النقاط."}

    # AUDITED BEFORE IT HAPPENS, like every other write a machine makes. A redemption the log
    # could not record must not occur — it is a customer's balance being spent.
    await request.app.state.auditor.record(
        "loyalty.redeemed", actor=f"till:{body.actor or 'unknown'}", tenant=tenant,
        resource="redemption", ip=request.client.host if request.client else "")

    # THE BRANCH IS CHECKED HERE AND NOT IN LOYALTY, because the branch list is ours: loyalty
    # holds no places and would have to read our tables to know one. An id this shop does not have
    # is dropped rather than stamped onto a ledger entry nobody can ever attribute (§12.2).
    #
    # ASKED ONLY WHEN THERE IS SOMETHING TO ASK ABOUT. A till that sends no branch — most of them,
    # since the field is optional (§12.2) — must not pay for a branch list read on every sale.
    branch_id = await svc.resolve_branch(tenant, body.branch_id)
    out = await desk.redeem(tenant=tenant, subject_ref=c.subject_ref, reward_id=body.reward_id,
                            idempotency_key=body.idempotency_key, actor=body.actor,
                            branch_id=branch_id)
    if out is None:
        return {"ok": False, "reason": "UNAVAILABLE", "message": "تعذّر الوصول إلى برنامج النقاط."}
    if "_status" in out:
        # THE REFUSAL, IN THE WORDS THE LEDGER USED. «رصيده لا يكفي» is a sentence the cashier
        # reads to the customer; «409» is one he cannot.
        return {"ok": False, "reason": "REFUSED", "message": out.get("_reason") or "تعذّر الاستبدال."}
    return {"ok": True, **out}


class TillOfferIn(BaseModel):
    """Apply the offer this customer is holding, to the visit just recorded at the counter."""

    # THE VISIT IS THE SUBJECT, exactly as on the field screen: the used-mark lives on the visit
    # and nowhere else (§5.6.2), so a till that has not recorded one has nothing to mark.
    visit_id: str = Field(min_length=1, max_length=128)
    phone: str = Field(default="", max_length=32)
    plate: str = Field(default="", max_length=32)
    actor: str = Field(default="", max_length=64)


@router.post("/offer/apply", dependencies=[Depends(rate_limit)])
async def apply_offer_at_the_counter(request: Request, body: TillOfferIn,
                                     principal: Principal = Depends(_TILL)) -> Any:
    """Spend the customer's offer at their till — the door that did not exist.

    THE GAP THIS CLOSES. An exclusive offer is the reason a customer came back, and the counter is
    where it is honoured. The integrated till could read his points and his rewards and could not
    see, let alone apply, the one thing the message he received had promised him. So a shop on a
    cashier integration ran offers it could not redeem: the customer arrives holding it, the
    cashier has no way to apply it, and the shop either gives the discount off the books or refuses
    a customer it invited.

    THE SAME RULES AS THE FIELD SCREEN, because they are the shop's rules and not the surface's:
    reminders judges WHICH offer applies (only it knows what was sent, its scope and its expiry),
    one offer per visit, and a second tap returns the same offer and spends nothing more.

    NEVER THE PSEUDONYM, IN OR OUT. The till identifies its customer the way it always does — by
    the phone number it already holds — and `subject_ref` is resolved here.
    """
    if not principal.tenant:
        return {"applied": False, "reason": "هذا الاعتماد غير مرتبط بمنشأة."}
    tenant = principal.tenant
    svc = request.app.state.container.operations

    c = None
    if body.phone.strip():
        c = await svc.customer_by_phone(tenant, body.phone.strip())
    if c is None and body.plate.strip():
        c = await svc.customer_by_plate(tenant, body.plate.strip())
    if c is None or not c.subject_ref:
        return {"applied": False, "reason": "لا يوجد عميل بهذا الرقم."}

    await request.app.state.auditor.record(
        "offer.applied", actor=f"till:{body.actor or 'unknown'}", tenant=tenant,
        resource=f"visit:{body.visit_id}", ip=request.client.host if request.client else "")

    try:
        applied = await svc.apply_offer(tenant=tenant, visit_id=body.visit_id,
                                        subject_ref=c.subject_ref)
    except OperationError as e:
        # RETURNED, NEVER RAISED — the platform strips a raised detail, and this sentence is read
        # aloud to a customer standing at the counter.
        return {"applied": False, "reason": str(e)}

    if applied is None:
        return {"applied": False, "reason": "لا يوجد عرضٌ ساري يشمل هذه الزيارة"}
    return {"applied": True, "offer": applied}
