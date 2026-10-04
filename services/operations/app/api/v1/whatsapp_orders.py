"""WhatsApp Direct Ordering — Step 7, the shop's own door to move an order through its lifecycle
(`core/orders.py::OrderService`'s own state machine). Every transition method there already fires
the matching WhatsApp status message on success (`_emit()` -> `operations.order.changed` ->
services/reminders' own live, tested subscriber — see whatsapp-catalog-ordering-execution-plan.md's
Step 7); this file is only the HTTP door that lets a human actually call one.

CAPABILITY = `operations.record`, THE SAME ONE RECORDING TODAY'S VISIT USES — the owner's own
decision (whatsapp-ordering-app-gap-analysis.md's own note): the order screen itself (view/update
status/share) is every role that can record a visit, not a manager-only action. Connection SETTINGS
(delivery radius, payment gateway) are the manager/owner-only `operations.manage` door instead — a
different concern, not this file's.

NO BRANCH SCOPE ON THESE WRITES — `app/api/scope.py`'s own module docstring states the rule this
mirrors: branch scope narrows READS, never WRITES. A staff member covering a shift at another
branch must still be able to mark an order ready or out for delivery in front of them, same
reasoning `record_visit` already holds for a visit. A branch-scoped LIST of orders (the console
screen itself) is Step 8's own concern, not this file's.

FORWARD-ONLY, NO SKIPPING — every method below is `OrderService`'s own, and each already refuses
(`OrderError`) a transition attempted from the wrong current status; this file relays that refusal
verbatim, never invents its own validation."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.auth import Principal
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.api import scope as SCOPE
from app.api.scope import branch_scope
from app.core.orders import OrderError

router = APIRouter(prefix="/staff/whatsapp-orders", tags=["whatsapp-orders"])

_RECORD = require_capability("operations.record")


def _tenant(p: Principal) -> str:
    if not p.tenant:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "NO_TENANT")
    return p.tenant


def _refuse(exc: OrderError) -> None:
    """Every action below shares the same shape: the engine's own refusal, verbatim, never a bare
    500 — same posture `MobileRequestError`/`CouponError` get from their own staff routes."""
    raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get("", dependencies=[Depends(rate_limit)])
async def list_whatsapp_orders(request: Request, status_filter: str = "", branch_id: str = "",
                               principal: Principal = Depends(_RECORD)) -> dict:
    """The console's own order queue (Step 8) — a real gap found in a 2026-10-05 backend audit:
    `OrderService.list()` already existed, filterable by status/branch, with nothing exposing it
    to a staff member at all.

    `status_filter`: one of `Order`'s own status constants ("" = every status, newest first).

    BRANCH-SCOPED ON READ, NEVER ON WRITE — same rule this module's own docstring already states
    for the status-change actions below, and the exact `branch_scope()`/`SCOPE.visible()` pair
    `field.py`'s own reads already use: an order with no branch (should not happen in practice,
    but never assumed) stays visible to everyone, same posture every other unbranched row in this
    service takes.
    """
    tenant = _tenant(principal)
    svc = request.app.state.container.orders
    rows = await svc.list(tenant, status=status_filter)
    scope = await branch_scope(request.app.state.container.datastore, principal)
    kept = SCOPE.visible([r.public() for r in rows], SCOPE.narrow(scope, branch_id),
                         field="branch_id")
    return {"orders": kept}


class SetOrderPauseIn(BaseModel):
    branch_id: str = Field(min_length=1, max_length=64)
    paused: bool
    reason: str = Field(default="", max_length=300)


@router.get("/pause", dependencies=[Depends(rate_limit)])
async def get_order_pause(request: Request, branch_id: str,
                          principal: Principal = Depends(_RECORD)) -> dict:
    """Whether this branch is currently refusing new WhatsApp orders — `core/order_pause.py`'s
    own «الكاشير الموقف مؤقت»، found with no door of its own in the same 2026-10-05 audit: the
    mechanism was built and already enforced inside `OrderService.create()`, with no route
    anywhere letting a cashier actually press the button."""
    tenant = _tenant(principal)
    paused, reason = await request.app.state.container.order_pauses.get(tenant, branch_id)
    return {"branch_id": branch_id, "paused": paused, "reason": reason}


@router.post("/pause", dependencies=[Depends(rate_limit)])
async def set_order_pause(request: Request, body: SetOrderPauseIn,
                          principal: Principal = Depends(_RECORD)) -> dict:
    """Flip the switch — same `operations.record` capability as every other action in this file
    (module docstring's own reasoning: the order screen is every role that can record a visit,
    never a manager-only action), since this is exactly the kind of floor decision ("we're
    swamped, stop new orders for twenty minutes") a cashier makes in the moment, not a policy a
    manager sets in advance."""
    tenant = _tenant(principal)
    row = await request.app.state.container.order_pauses.set(
        tenant, body.branch_id, paused=body.paused, reason=body.reason,
        actor=principal.subject)
    await _audit(request, "whatsapp_order.pause_set", tenant, body.branch_id, principal)
    return row


class SetOrderShareToggleIn(BaseModel):
    enabled: bool


@router.get("/share-toggle", dependencies=[Depends(rate_limit)])
async def get_order_share_toggle(request: Request,
                                 principal: Principal = Depends(_RECORD)) -> dict:
    """Step 9's own on/off switch — `core/order_share_toggle.py`'s own «مشاركة الطلب مع
    المندوب» preference. Per tenant, not per branch — see that module's own docstring."""
    tenant = _tenant(principal)
    enabled = await request.app.state.container.order_share_toggle.get(tenant)
    return {"enabled": enabled}


@router.post("/share-toggle", dependencies=[Depends(rate_limit)])
async def set_order_share_toggle(request: Request, body: SetOrderShareToggleIn,
                                 principal: Principal = Depends(_RECORD)) -> dict:
    """Same `operations.record` capability as every other action in this file — a cashier deciding
    whether this shop uses an external delivery rep at all is not a manager-only call."""
    tenant = _tenant(principal)
    row = await request.app.state.container.order_share_toggle.set(tenant, body.enabled)
    await request.app.state.auditor.record(
        "whatsapp_order.share_toggle_set", actor=principal.subject, tenant=tenant,
        resource=f"tenant:{tenant}", ip=request.client.host if request.client else "")
    return row


@router.get("/{order_id}", dependencies=[Depends(rate_limit)])
async def get_whatsapp_order(request: Request, order_id: str,
                             principal: Principal = Depends(_RECORD)) -> dict:
    tenant = _tenant(principal)
    svc = request.app.state.container.orders
    row = await svc.get(tenant, order_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    return row.public()


async def _audit(request: Request, action: str, tenant: str, order_id: str,
                 principal: Principal) -> None:
    await request.app.state.auditor.record(
        action, actor=principal.subject, tenant=tenant, resource=f"whatsapp_order:{order_id}",
        ip=request.client.host if request.client else "")


@router.post("/{order_id}/preparing", dependencies=[Depends(rate_limit)])
async def start_preparing_whatsapp_order(request: Request, order_id: str,
                                         principal: Principal = Depends(_RECORD)) -> dict:
    """تأكيد الطلب فعليًا دخل التجهيز — only valid from `CONFIRMED` (a payment already landed);
    `OrderService.start_preparing`'s own refusal explains anything else."""
    tenant = _tenant(principal)
    svc = request.app.state.container.orders
    try:
        row = await svc.start_preparing(tenant, order_id)
    except OrderError as exc:
        _refuse(exc)
    await _audit(request, "whatsapp_order.preparing", tenant, order_id, principal)
    return row.public()


@router.post("/{order_id}/ready", dependencies=[Depends(rate_limit)])
async def mark_ready_whatsapp_order(request: Request, order_id: str,
                                    principal: Principal = Depends(_RECORD)) -> dict:
    tenant = _tenant(principal)
    svc = request.app.state.container.orders
    try:
        row = await svc.mark_ready(tenant, order_id)
    except OrderError as exc:
        _refuse(exc)
    await _audit(request, "whatsapp_order.ready", tenant, order_id, principal)
    return row.public()


@router.post("/{order_id}/out-for-delivery", dependencies=[Depends(rate_limit)])
async def start_delivery_whatsapp_order(request: Request, order_id: str,
                                        principal: Principal = Depends(_RECORD)) -> dict:
    tenant = _tenant(principal)
    svc = request.app.state.container.orders
    try:
        row = await svc.start_delivery(tenant, order_id)
    except OrderError as exc:
        _refuse(exc)
    await _audit(request, "whatsapp_order.out_for_delivery", tenant, order_id, principal)
    return row.public()


@router.post("/{order_id}/delivered", dependencies=[Depends(rate_limit)])
async def complete_whatsapp_order(request: Request, order_id: str,
                                  principal: Principal = Depends(_RECORD)) -> dict:
    """تم التسليم — `OrderService.complete`'s own docstring: this is the one transition that also
    records a real Visit, so loyalty points/insights/reminders all follow automatically from here,
    exactly as any other visit."""
    tenant = _tenant(principal)
    svc = request.app.state.container.orders
    try:
        row = await svc.complete(tenant, order_id)
    except OrderError as exc:
        _refuse(exc)
    await _audit(request, "whatsapp_order.delivered", tenant, order_id, principal)
    return row.public()


class CancelOrderIn(BaseModel):
    reason: str = Field(default="", max_length=300)


@router.post("/{order_id}/cancel", dependencies=[Depends(rate_limit)])
async def cancel_whatsapp_order(request: Request, order_id: str, body: CancelOrderIn,
                                principal: Principal = Depends(_RECORD)) -> dict:
    """Only before preparation has actually started (`OrderService.CANCELLABLE_FROM`) — once the
    shop has begun fulfilling it, cancelling is a conversation with the customer, not a button."""
    tenant = _tenant(principal)
    svc = request.app.state.container.orders
    try:
        row = await svc.cancel(tenant, order_id, reason=body.reason, actor=principal.subject)
    except OrderError as exc:
        _refuse(exc)
    await _audit(request, "whatsapp_order.cancelled", tenant, order_id, principal)
    return row.public()


@router.post("/{order_id}/resolve-mismatch", dependencies=[Depends(rate_limit)])
async def resolve_mismatch_whatsapp_order(request: Request, order_id: str,
                                          principal: Principal = Depends(_RECORD)) -> dict:
    """A human's own recovery action for `PAYMENT_MISMATCH` (`OrderService.resolve_mismatch`'s own
    docstring) — the shop confirmed by other means (bank statement, a call to the customer) that
    the payment is in fact good, and moves the order on manually rather than leaving it stuck."""
    tenant = _tenant(principal)
    svc = request.app.state.container.orders
    try:
        row = await svc.resolve_mismatch(tenant, order_id, actor=principal.subject)
    except OrderError as exc:
        _refuse(exc)
    await _audit(request, "whatsapp_order.mismatch_resolved", tenant, order_id, principal)
    return row.public()
