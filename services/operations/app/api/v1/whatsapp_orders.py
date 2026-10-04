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
