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
from app.core.apps import KEYS, licence_attr

# And when we could not ask. A DIFFERENT sentence from "you have not paid" on purpose — telling a
# paying shop it has not paid is a different wrong from telling an unpaid one the truth.
CANNOT_ASK = "تعذّر التحقق من اشتراكك الآن — حاول بعد قليل."

# NO SINGLE BUNDLE ANY MORE (الأساس retired 2026-09-10). Ordinary shop-management writes — staff,
# branches, services, redeeming an offer — are not any ONE app's business; they need SOME paid app,
# whichever it is.
#
# DERIVED FROM `core/apps.py::KEYS`, NOT RETYPED. This used to be its own hand-typed tuple of
# container attribute names, written the day the OR-gate first existed and never revisited when
# `feature.coupons`, `feature.insights.engine`, and `feature.mobile_requests` each later shipped as
# their own standalone app — a shop holding only one of those three, and nothing else, was
# wrongly refused this generic gate because its licence's attribute name was simply never added
# here. `KEYS` is the one place every sellable app is listed (the same list the console renders
# and `ci/check_listed_apps_are_wired.py` checks); `licence_attr` is the one rule that turns a key
# into the container attribute `container.py` wires it under. A future standalone app now joins
# this gate the moment it is added to `APPS` and wired onto the container — nothing here changes.
_ANY_APP = tuple(licence_attr(key) for key in KEYS)


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


# THE GENERIC GATE, and now the entire definition of "subscribed" — no bundle sits under it any
# more. Every ordinary shop-management write (staff, branches, services, an offer redeemed) needs
# SOME paid app; which one is irrelevant to routes that are not themselves app-specific.
subscribed_write = subscribed_write_or(
    *_ANY_APP,
    refusal="يحتاج هذا الإجراء اشتراكاً فعّالاً في تطبيق واحد على الأقل من تطبيقاتنا.")

# Connecting WhatsApp is specific to the one app that number belongs to — no OR needed any more
# now that `subscribed_write` itself already asks about `whatsapp_licence` as one of its options;
# kept as its own name only because `api/v1/connect.py` reads clearer naming the app it gates.
subscribed_write_or_whatsapp = subscribed_write_or(
    "whatsapp_licence",
    refusal="يحتاج ربط واتساب اشتراكاً فعّالاً بتطبيق واتساب الذكي.")

# Registering a customer — `/field/customers/ensure` — must be possible from any app that
# legitimately creates or first meets a customer relationship: `feature.contacts` ("جهات
# الاتصال", the free standalone app built to carry exactly this) or `feature.bookings`, because a
# booking can be how a shop meets a customer for the first time. A FUTURE app joins this OR by
# adding its own attribute name to this one line — nothing else in this file changes.
subscribed_write_or_customer_creating_app = subscribed_write_or(
    "contacts_licence", "bookings_licence",
    refusal="يحتاج تسجيل عميل اشتراكاً فعّالاً بتطبيق جهات الاتصال، أو بتطبيق الحجوزات.")

# Recording a visit — `/field/visits`, `/field/visits/{id}/offer`, and the till door that
# ultimately calls the same `Operations.record_visit` — needs the separately-priced `feature.visit`
# standalone app ("تسجيل زيارة").
subscribed_write_or_visit = subscribed_write_or(
    "visit_licence",
    refusal="يحتاج تسجيل الزيارة اشتراكاً فعّالاً بتطبيق تسجيل زيارة.")


async def no_subscription_needed() -> None:
    """A route that works whether or not the month is paid, and says so.

    Three kinds only, and each is a decision rather than an oversight:
      · paying us — subscribing, adding an app, reading the price list;
      · signing up, before there is anything to subscribe;
      · the CUSTOMER's rights under PDPL — erasure and privacy requests belong to the law.
    """
    return None
