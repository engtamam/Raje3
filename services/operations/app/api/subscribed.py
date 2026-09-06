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
from app.core.base_licence import LicenceError


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


async def subscribed_write_or_whatsapp(request: Request,
                                       principal: Principal = Depends(require_user)) -> Principal:
    """Refuse this write unless EITHER the base subscription OR a standalone `feature.whatsapp`
    plan is live.

    THE ONE DOOR TWO DIFFERENT BUYERS MUST BOTH OPEN. `subscribed_write` alone refuses "واتساب
    الذكي (مستقل)"'s own subscriber — he holds no base at all, by design (plans.json's own note
    on that row) — so the WhatsApp connect routes (api/v1/connect.py) use this instead of
    `subscribed_write`, everywhere else on this file unchanged.

    A shop holding NEITHER is still refused — this does not exempt WhatsApp from needing to be
    bought, it only widens WHICH purchase counts.
    """
    if not principal.tenant:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN")
    base = getattr(request.app.state.container, "base_licence", None)
    wa = getattr(request.app.state.container, "whatsapp_licence", None)
    if base is None or wa is None:
        return principal
    base_answer = await base.allowed(principal.tenant)
    if base_answer is True:
        return principal
    wa_answer = await wa.allowed(principal.tenant)
    if wa_answer is True:
        return principal
    # NEITHER IS A CLEAR YES. Fail closed on an outage the same way subscribed_write does —
    # "could not ask" from either check must not read as permission.
    if base_answer is None or wa_answer is None:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            detail="تعذّر التحقق من اشتراكك الآن — حاول بعد قليل.")
    raise HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail="يحتاج ربط واتساب اشتراكاً فعّالاً — بالأساس، أو بتطبيق واتساب الذكي المستقل.")


async def no_subscription_needed() -> None:
    """A route that works whether or not the month is paid, and says so.

    Three kinds only, and each is a decision rather than an oversight:
      · paying us — subscribing, adding an app, reading the price list;
      · signing up, before there is anything to subscribe;
      · the CUSTOMER's rights under PDPL — erasure and privacy requests belong to the law.
    """
    return None
