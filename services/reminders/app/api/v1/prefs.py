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
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.ratelimit import rate_limit
from app.core.models import CLASSES, Preferences, as_row
from app.core.stores import PrefsStore

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
    row = await PrefsStore(request.app.state.container.datastore).get(tenant, subject) \
        if tenant and subject else None
    stopped = (row or {}).get("stopped") or {}
    return {"preferences": [
        {"class": c, "label": LABELS[c], "enabled": not stopped.get(c, False)}
        for c in CLASSES]}


class PrefsIn(BaseModel):
    # Which classes to STOP. The whole set is sent each time rather than one switch at a time: a
    # partial update from a page the customer had open for an hour would silently re-enable what
    # they turned off in another tab.
    stopped: list[str] = Field(default_factory=list, max_length=5)


@router.put("/{ref}", dependencies=[Depends(rate_limit)])
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
    store = PrefsStore(request.app.state.container.datastore)
    row = await store.get(tenant, subject) or as_row(Preferences(tenant=tenant,
                                                                subject_ref=subject))
    row["stopped"] = stopped
    await store.put(tenant, subject, row)
    await request.app.state.auditor.record(
        "reminders.preferences_changed", actor=subject, tenant=tenant,
        resource="notification_prefs", ip=request.client.host if request.client else "")
    return {"saved": True, "preferences": [
        {"class": c, "label": LABELS[c], "enabled": not stopped.get(c, False)} for c in CLASSES]}
