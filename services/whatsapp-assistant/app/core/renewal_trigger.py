"""Turn one `subscription.renewed` bus event into an opened subscription-renewal Flow, or nothing.

THE LAST PIECE of the renewal build: `renewal_provider.py` (services/operations) answers the
Flow's screens once opened; `renewal_consumer.py` (this service) delivers the pay-link once
confirmed; this is what actually OPENS it — sends the approved Flow-button template to the shop
owner's own number the moment billing tells us a renewal invoice exists.

ONE PLATFORM-OWNED FLOW, NOT CLONED PER SHOP (owner's decision, 2026-09-10) — sent from OUR OWN
WhatsApp number, same category as the `auth_otp` template, never a shop's own connected number.
So every send here uses `tenant=PLATFORM` (the sending identity), and the REAL shop tenant travels
inside the Flow's own seed data instead: `customer` = `"{tenant}:{invoice_id}"` (billing exposes
no "list this tenant's open invoices" read, only "read ONE invoice by id", so both pieces have to
be carried forward from the one place they are genuinely known together — this event). Read back
and split apart by `renewal_provider.py` on the operations side; see that module's own docstring.

DEDUPED BY INVOICE (RenewalTriggerStore), because a consolidated invoice (platform v0.19.11) fires
this event once PER SUBSCRIPTION it covers, all carrying the same invoice_id — without the claim a
shop renewing three apps together would get three copies of the same Flow-opening message.

NO RECIPIENT, NO SEND — NEVER A GUESS. A tenant identity cannot resolve to a phone (no founding
owner, an email-only signup, identity-service unreachable) answers `""` from `OwnerPhone.resolve`
and this trigger sends nothing, silently, the same "cannot read = cannot act" posture every other
peer-backed piece of this service already holds."""
from __future__ import annotations

from typing import Any

from app.core.renewal_request import RenewalRequestStore
from app.core.renewal_trigger_store import RenewalTriggerStore

#: Must be a template registered (AdminWhatsAppTemplates.tsx) with a flow_button naming the
#: "subscription_renewal" flow — the send only carries the template name; the Flow name itself is
#: fixed at template-registration time on notification-service's own side.
_TEMPLATE_NAME = "subscription_renewal_flow"
#: THE SENDING IDENTITY — never the real shop's tenant. Same reserved account
#: AdminWhatsAppTemplates.tsx registers `auth_otp` on; see services/operations/app/core/flows.py's
#: own `PLATFORM` constant (kept as each file's own local copy, matching this codebase's
#: convention rather than a shared import).
_PLATFORM = "_platform"


class RenewalTrigger:
    def __init__(self, *, claims: RenewalTriggerStore, requests: RenewalRequestStore,
                owner_phone: Any, sender: Any) -> None:
        self._claims = claims
        self._requests = requests
        self._owner_phone = owner_phone
        self._sender = sender

    async def handle(self, event: dict[str, Any], *, now: int) -> bool:
        """`True` iff a Flow-opening message was sent this call. `False` for everything else — an
        event with no tenant/invoice_id, an invoice already claimed, or a tenant with no
        reachable owner. NEVER raises for those; a send failure past a real claim DOES raise (the
        owner's renewal is genuinely due — silently dropping the notice is worse than a retried
        or duplicate one on the next event), same posture `RenewalConsumer.handle` holds."""
        tenant = str(event.get("tenant") or "")
        invoice_id = str(event.get("invoice_id") or "")
        if not tenant or not invoice_id:
            return False
        if not await self._claims.claim(invoice_id, now=now):
            return False
        to = await self._owner_phone.resolve(tenant)
        if not to:
            return False
        # DETERMINISTIC, NOT RANDOM — the claim above already guarantees exactly one open attempt
        # per invoice, so the token needs no extra entropy, same "rate:{visit_id}" shape
        # reminders' own rating_request.py uses for the identical reason.
        flow_token = f"renew:{invoice_id}"
        # `tenant` REMEMBERED HERE IS THE REAL SHOP — kept for audit/traceability even though the
        # send itself always goes out under `_PLATFORM` (see module docstring); the completion
        # consumer (renewal_consumer.py) never needed this real tenant anyway, only `to`.
        await self._requests.remember(flow_token=flow_token, tenant=tenant, to=to, now=now)
        await self._sender.send_template(
            tenant=_PLATFORM, to=to, template_name=_TEMPLATE_NAME, variables=[],
            idempotency_key=flow_token, flow_token=flow_token,
            flow_action_data={"customer": f"{tenant}:{invoice_id}"})
        return True


def build(settings: Any, *, store: Any, owner_phone: Any, sender: Any) -> RenewalTrigger:
    return RenewalTrigger(
        claims=RenewalTriggerStore(store), requests=RenewalRequestStore(store),
        owner_phone=owner_phone, sender=sender)
