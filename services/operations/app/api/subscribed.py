"""Every mutating route says, in its own signature, whether it needs a live subscription.

WHY A DEPENDENCY AND NOT A CHECK INSIDE THE HANDLER. The four licences that came before this one
are called from handler bodies, and the result is that «which routes are guarded» can only be
answered by reading every handler to the end. That is how the base came to be the only unguarded
product in the fleet without anyone noticing: nothing about a route's SIGNATURE said what it had
decided. Here the decision is on the decorator, where a gate can read it and a reviewer can see
it in one line.

TWO DEPENDENCIES, AND THE SECOND IS NOT DECORATION. `no_subscription_needed` does nothing at
runtime, on purpose: it is how a route declares that it deliberately works while the month is
lapsed — paying us, signing up, and the customer's own PDPL rights. Without it there is no
difference between «decided this must stay open» and «nobody thought about it», and an exceptions
table in the gate would put that decision somewhere other than the code it governs.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from app.api.auth import Principal, require_user
from app.core.base_licence import CANNOT_ASK, LicenceError


async def subscribed_write(request: Request,
                           principal: Principal = Depends(require_user)) -> Principal:
    """Refuse this write unless the base subscription (or its trial) is live.

    402 PAYMENT_REQUIRED, never 403: the owner is not forbidden, he is unsubscribed, and the two
    lead to different screens. `detail` carries the Arabic sentence the licence chose so the
    console never has to guess which of the two refusals it is showing.
    """
    if not principal.tenant:
        # NO ESTABLISHMENT ON THE CREDENTIAL IS NOT A SHOP, and asking billing about an empty
        # tenant asks about everybody. A platform token has no month to have paid, so it does not
        # reach a shop's write door — it has its own routes, and they declare themselves exempt.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN")
    licence = getattr(request.app.state.container, "base_licence", None)
    if licence is None:
        # A deployment with no licence wired is refused at boot; if one is somehow running,
        # refusing every write would take the whole product down for a configuration mistake.
        return principal
    try:
        await licence.require_write(principal.tenant)
    except LicenceError as exc:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            detail=exc.message) from exc
    return principal


def subscribed_write_or(*licence_attrs: str, refusal: str):
    """Build a write-gate dependency that passes if ANY of the named container licences answers
    True for this tenant — the generalisation of what used to be `subscribed_write_or_whatsapp`
    on its own.

    THE PROBLEM WITH THE THING THIS REPLACES. `subscribed_write_or_whatsapp` hardcoded exactly
    two attribute names ("base_licence", "whatsapp_licence") inside its own body. That was fine
    for the one app that needed an OR — it stopped being fine the moment registering a customer
    needed to accept `feature.base` OR `feature.contacts` OR `feature.bookings`, because the only
    way to reuse that shape was to copy the whole function a second time with different attribute
    names hardcoded in a different place, and a third time after that. Copy-pasted gates are
    exactly how one of them quietly drifts — a fixed sentence, a missed licence, a forgotten
    "could not ask" branch — and nothing before this file made that impossible.

    `licence_attrs` are `request.app.state.container` attribute names, each an object shaped like
    `base_licence`/`whatsapp_licence`/anything built by `core/feature_licence.py`: an async
    `.allowed(tenant) -> bool | None`. Joining the OR is one line at a call site below — no new
    function, no new file.

    SHORT-CIRCUITS ON THE FIRST YES, in the order given, so a licence that need not be asked
    (an HTTP round trip) is not asked. Fails closed exactly like `subscribed_write`: a tenant-less
    principal is 403, an unwired licence lets the write through (same "a deployment that cannot
    read entitlements is not this gate's problem to invent a refusal for" posture as
    `subscribed_write` above), and "could not ask" from EVERY licence that answered refuses with
    `CANNOT_ASK` rather than the caller-supplied `refusal` — telling a paying shop it has not paid
    is a different wrong from telling an unpaid one the truth, and the two sentences must never
    share a string.
    """
    async def _gate(request: Request,
                    principal: Principal = Depends(require_user)) -> Principal:
        if not principal.tenant:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN")
        container = request.app.state.container
        licences = [getattr(container, attr, None) for attr in licence_attrs]
        if any(l is None for l in licences):
            return principal
        saw_unreachable = False
        for licence in licences:
            answer = await licence.allowed(principal.tenant)
            if answer is True:
                return principal
            if answer is None:
                saw_unreachable = True
        if saw_unreachable:
            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=CANNOT_ASK)
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=refusal)
    return _gate


# "واتساب الذكي (مستقل)" holds no base at all, by design (plans.json's own note on that row) — so
# the WhatsApp connect routes (api/v1/connect.py) use this instead of `subscribed_write`,
# everywhere else on this file unchanged. Same dependency object as before this file was
# generalised — only its construction changed, not its behaviour or its identity as an import.
subscribed_write_or_whatsapp = subscribed_write_or(
    "base_licence", "whatsapp_licence",
    refusal="يحتاج ربط واتساب اشتراكاً فعّالاً — بالأساس، أو بتطبيق واتساب الذكي المستقل.")

# Registering a customer — `/field/customers/ensure` — must be possible from any app that
# legitimately creates or first meets a customer relationship, not gated to `feature.base` alone:
# `feature.base` for today's legacy bundle, `feature.contacts` for "بيانات التواصل" (the free
# standalone app built to carry exactly this), and `feature.bookings` because a booking can be how
# a shop meets a customer for the first time. A FUTURE app joins this OR by adding its own
# attribute name to this one line — nothing else in this file changes.
subscribed_write_or_customer_creating_app = subscribed_write_or(
    "base_licence", "contacts_licence", "bookings_licence",
    refusal="يحتاج تسجيل عميل اشتراكاً فعّالاً — بالأساس، أو بتطبيق بيانات التواصل، "
           "أو بتطبيق الحجوزات.")

# Recording a visit — `/field/visits`, `/field/visits/{id}/offer`, and the till door that
# ultimately calls the same `Operations.record_visit` — accepts `feature.base` (the legacy
# bundle, unchanged for existing subscribers) OR the new, separately-priced `feature.visit`
# standalone app ("تسجيل زيارة").
subscribed_write_or_visit = subscribed_write_or(
    "base_licence", "visit_licence",
    refusal="يحتاج تسجيل الزيارة اشتراكاً فعّالاً — بالأساس، أو بتطبيق تسجيل زيارة المستقل.")


async def no_subscription_needed() -> None:
    """A route that works whether or not the month is paid, and says so.

    Three kinds only, and each is a decision rather than an oversight:
      · paying us — subscribing, adding an app, reading the price list;
      · signing up, before there is anything to subscribe;
      · the CUSTOMER's rights under PDPL — erasure and privacy requests belong to the law.
    """
    return None
