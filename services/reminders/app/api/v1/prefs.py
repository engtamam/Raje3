"""The customer's own switches — five, one per class (spec 8.4.2 section 5, 8.6.1).

REACHED FROM A LINK AT THE END OF A MESSAGE, AND THE LINK CARRIES NO TOKEN. That is the whole
security design of this surface, and it inverts the usual one: the link is forwardable, it lands in
a WhatsApp chat that gets screenshotted and shared, and anyone who opens it must NOT learn whose it
is. So the reference in the URL is opaque, this endpoint returns no name, no phone and no history,
and the page it feeds shows switches and nothing else.

WHAT THE REFERENCE IS. The `subject_ref` — already an HMAC of the tenant and the identifier under
a salt only our services hold. It cannot be reversed to a phone number, it is scoped to one
establishment (the same person at two shops has two of them), and it is the same value peers
already exchange. Minting a second secret for this page would be a second thing to rotate.

WHAT SOMEONE WHO GUESSES ONE GETS: the ability to switch off messages for a stranger. That is the
honest worst case and it is acceptable — the reference is 128 bits of HMAC output, guessing is not
a threat model, and the failure direction is fewer messages rather than more. The alternative, a
one-time token per message, means a customer who reopens yesterday's link finds it dead and
concludes we ignored them.

RATE LIMITED HARD. It is the one route on this service reachable without a token, and an
unthrottled unauthenticated write is an invitation regardless of what it writes.
"""
# gateway: auth none
#
# THE MARKER THE GATEWAY IS CHECKED AGAINST (ط-6). Everything above is prose, and prose and a YAML
# route table drifted: this module was written token-free on purpose and the gateway had it as
# `"auth":"required"` — so the customer tapping «إيقاف الرسائل» in WhatsApp met a login screen for
# an account he does not have, and PDPL's right to object was a dead button. The direction is the
# safe one, which is exactly why nobody noticed for months.
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.ratelimit import rate_limit
from app.core.consent import Consent, GRANTED, WITHDRAWN
from app.core.models import SendLog, CLASSES, Preferences, as_row
from app.core.stores import PrefsStore, SendLogStore
from app.api.subscribed import no_subscription_needed, subscribed_write

router = APIRouter(prefix="/prefs", tags=["prefs"])

# What each class is called on the customer's own page. Their words, not ours — "خدمية" is a
# regulatory term and means nothing to the person reading it on their phone.
LABELS = {
    "service": "رسائل الخدمة — تأكيد الزيارة والتذكير بموعد صيانتك",
    "personal": "رسائل تخصّك — رصيد نقاطك وإشعارات حسابك",
    "awareness": "نصائح ومعلومات",
    "warning": "تنبيهات السلامة",
    "marketing": "العروض والخصومات",
}


def _tenant_and_subject(ref: str) -> tuple[str, str]:
    """Split the opaque reference into its parts.

    The link carries `{tenant}.{subject_ref}` because the subject_ref alone is not unique across
    establishments in the datastore key — and a lookup that had to scan every tenant to find one
    reference would be a cross-tenant read on an unauthenticated route, which is the one thing this
    file must not contain.
    """
    if "." not in ref:
        return "", ""
    tenant, _, subject = ref.partition(".")
    return tenant, subject


@router.get("/{ref}", dependencies=[Depends(rate_limit)])
async def get_prefs(request: Request, ref: str) -> dict:
    """The five switches and their current state.

    NO NAME, NO PHONE, NO HISTORY, AND NO 404. An unknown reference returns the default switches,
    exactly like a known one: a 404 here answers "is this a real customer of this shop?" to anyone
    holding a forwarded link, which is the leak this design exists to prevent.
    """
    tenant, subject = _tenant_and_subject(ref)
    ds = request.app.state.container.datastore
    row = await PrefsStore(ds).get(tenant, subject) if tenant and subject else None
    stopped = (row or {}).get("stopped") or {}
    enabled = {c: not stopped.get(c, False) for c in CLASSES}

    # ── MARKETING IS DRAWN FROM THE CONSENT, NOT FROM THE ABSENCE OF A REFUSAL (د-1) ───────────
    # Every other class here is opt-OUT: it runs until the customer stops it, which is right for a
    # service reminder he asked for by buying something. Marketing is opt-IN — §8.5 and the PDPL's
    # prior-consent rule — so «he never stopped it» is not «he agreed to it».
    #
    # Rendered from the stopped map, the box showed TICKED to a customer who had never granted
    # anything, because he had never refused anything either. He opened his page to switch off one
    # reminder, saved, and the tick he never made was read as a grant and written as one.
    #
    # Reading it from the consent record makes the first tick a real act — which is what the write
    # side now requires before it records anything.
    if tenant and subject:
        enabled["marketing"] = await Consent(ds).state(tenant, subject) == GRANTED

    return {"preferences": [
        {"class": c, "label": LABELS[c], "enabled": enabled[c]} for c in CLASSES]}


class PrefsIn(BaseModel):
    # Which classes to STOP. The whole set is sent each time rather than one switch at a time: a
    # partial update from a page the customer had open for an hour would silently re-enable what
    # they turned off in another tab.
    stopped: list[str] = Field(default_factory=list, max_length=5)


@router.put("/{ref}", dependencies=[Depends(no_subscription_needed), Depends(rate_limit)])
async def set_prefs(request: Request, ref: str, body: PrefsIn) -> dict:
    """Switch classes off, or back on.

    AUDITED, and this is one of the few user-sourced actions that is. If we cannot prove when a
    customer said stop, we cannot defend the message we sent after they did.
    """
    tenant, subject = _tenant_and_subject(ref)
    if not tenant or not subject:
        # Still not a 404 or a 400 naming the problem — a malformed reference gets the same shape
        # of answer as a valid one that changed nothing.
        return {"saved": False}
    stopped = {c: True for c in body.stopped if c in CLASSES}
    ds = request.app.state.container.datastore
    store = PrefsStore(ds)
    row = await store.get(tenant, subject) or as_row(Preferences(tenant=tenant,
                                                                subject_ref=subject))
    was_stopped = dict((row or {}).get("stopped") or {})
    row["stopped"] = stopped
    await store.put(tenant, subject, row)

    # ── THE STOP IS AN EVENT, NOT ONLY A FLAG (proof 4) ────────────────────────────────────────
    # The preference row says who is switched off; nothing said WHEN, so «هل ارتفع الإزعاج بعد
    # حملة الخميس؟» had no answer anywhere in the product. A rate needs a moment.
    #
    # Written into the SEND LOG rather than a table of its own: that ledger already exists, is
    # already append-only, already trimmed by the same retention, and already keyed by customer.
    # A second store for the same fact is a second thing to erase on a deletion request and a
    # second place for a count to drift.
    #
    # ONLY THE NEWLY-STOPPED CLASSES. Saving the page without touching anything must not append a
    # row — a history of identical refusals would inflate the very number it is meant to warn
    # about, and the warning would then fire on nothing.
    newly = [c for c in stopped if not was_stopped.get(c, False)]
    if newly:
        log = SendLogStore(ds)
        now = int(time.time())
        for c in newly:
            await log.append(tenant, as_row(SendLog(
                tenant=tenant, subject_ref=subject, cls=c, at=now,
                outcome="opt_out", reason="العميل أوقف هذا النوع من صفحته")))
    await request.app.state.auditor.record(
        "reminders.preferences_changed", actor=subject, tenant=tenant,
        resource="notification_prefs", ip=request.client.host if request.client else "")

    # ── the marketing switch is ALSO a consent decision ────────────────────────────────────────
    # Ticking the box used to do one thing: clear a refusal. But "no longer refusing" is not
    # agreeing, and the difference is the whole of §8.5 and of PDPL's prior-consent requirement —
    # so the same tap now writes a consent RECORD, with the sentence they were shown and its
    # version (core/consent.py).
    #
    # ONLY ON A CHANGE. Saving the page without touching the box must not append a row: a history
    # of identical grants is not evidence of anything, and it would inflate the owner's count.
    consent = Consent(ds)
    now_on = "marketing" not in stopped
    state = await consent.state(tenant, subject)
    # FROM THE RECORD, NOT FROM THE STOPPED MAP. `"marketing" not in was_stopped` was true for
    # everybody who had never touched the page, so «was on» meant «never said anything» — and a
    # transition measured against it could never be real.
    was_on = state == GRANTED
    shop = await _shop_name(request, tenant)
    # WHAT MAKES THIS A REAL TICK IS THE READ SIDE, NOT A CONDITION HERE (د-1).
    #
    # `now_on` is only «marketing is absent from the stopped list». It used to be absent for every
    # customer who had never touched this page — the box rendered TICKED because he had never
    # refused — so saving the page for any other reason wrote a consent record, with a shop name
    # and a statement version, against somebody who had agreed to nothing.
    #
    # No condition here can tell those apart: «he ticked it» and «it was never off» arrive as the
    # same request. `get_prefs` now draws this one switch from the CONSENT record, so a customer
    # who has not granted sees it off, sends it stopped, and only a deliberate tick clears it.
    if now_on and state != GRANTED:
        # AUDITED SEPARATELY from the preference change, and write-ahead. A consent we cannot
        # prove is a consent we did not have, and the message that followed it is then unlawful
        # rather than merely unrecorded.
        await request.app.state.auditor.record(
            "reminders.marketing_consent", actor=subject, tenant=tenant,
            resource="marketing_consent", ip=request.client.host if request.client else "")
        await consent.record(tenant, subject, state=GRANTED, source="customer_page", shop=shop)
    elif not now_on and was_on and state == GRANTED:
        # THE ONE-TAP WITHDRAWAL WRITES A ROW, not only a gate flag. Otherwise the message stops
        # and the record still says they agreed — which is the worst of the two failures, because
        # it is the one we would be asked to produce.
        await request.app.state.auditor.record(
            "reminders.marketing_consent", actor=subject, tenant=tenant,
            resource="marketing_consent", ip=request.client.host if request.client else "")
        await consent.record(tenant, subject, state=WITHDRAWN, source="customer_page")

    return {"saved": True, "preferences": [
        {"class": c, "label": LABELS[c], "enabled": not stopped.get(c, False)} for c in CLASSES]}


async def _shop_name(request: Request, tenant: str) -> str:
    """The establishment's own name, for the sentence stored with the grant.

    Empty on failure rather than raising: a consent that cannot be recorded because a peer was
    slow is a consent lost, and the statement degrades to "the establishment" — which the customer
    page itself does in the same situation (spec §8.6.1).
    """
    try:
        shop = await request.app.state.container.identity.get(tenant)
        return getattr(shop, "name", "") or ""
    except Exception:                                                   # noqa: BLE001
        return ""
