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

# And when we could not ask. A DIFFERENT sentence from "you have not paid" on purpose.
CANNOT_ASK = "تعذّر التحقق من اشتراكك الآن — حاول بعد قليل."

_REFUSAL = "يحتاج تعديل رسائلك اشتراكاً فعّالاً بتطبيق تسجيل زيارة أو تطبيق الحجوزات."


async def subscribed_write(request: Request,
                           principal: Principal = Depends(require_user)) -> Principal:
    """Refuse this write unless the shop owns AN EVENT-RECORDING APP (`feature.visit` or
    `feature.bookings`) right now — messaging is a FEATURE of one of those, not a product of its
    own (see `core/feature_licence.py`'s own docstring for the product reasoning, 2026-09-10).

    402 PAYMENT_REQUIRED, never 403: the owner is not forbidden, he is unsubscribed, and the two
    lead to different screens.
    """
    if not principal.tenant:
        # NO ESTABLISHMENT ON THE CREDENTIAL IS NOT A SHOP, and asking billing about an empty
        # tenant asks about everybody. A platform token has no month to have paid, so it does not
        # reach a shop's write door — it has its own routes, and they declare themselves exempt.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN")
    container = request.app.state.container
    licences = [getattr(container, "visit_licence", None), getattr(container, "bookings_licence", None)]
    if any(l is None for l in licences):
        # A deployment with no licences wired is refused at boot; if one is somehow running,
        # refusing every write would take the whole product down for a configuration mistake.
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
    raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=_REFUSAL)


async def no_subscription_needed() -> None:
    """A route that works whether or not the month is paid, and says so.

    Here that is: our own operator surface (secrets and policy, which are ours and not the shop's),
    and the CUSTOMER's own switches in `prefs.py` — a person turning our messages off must never
    be told to go and ask the shop to pay first. That one is the law, not a courtesy.
    """
    return None
