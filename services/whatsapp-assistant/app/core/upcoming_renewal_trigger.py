"""Turn one "this subscription renews soon" row into an opened subscription-renewal Flow, 2 days
BEFORE the real date — the owner's own explicit instruction (2026-09-15): the automatic billing
cycle must stay untouched, exactly on its own schedule ("ممنوع نفوتره قبلها... الافضل تكون في
وقتها كويس"), but a proactive WhatsApp heads-up should still go out early enough for the owner to
act, and — if he chooses to — pay ahead of time himself ("شحن يدوي، لا سحب تلقائي... زي كل
الشركات").

THE SAME FLOW AS renewal_trigger.py, SEEDED DIFFERENTLY. Rather than build a second Flow, a second
button-parsing consumer and a second pay-link path, this reuses the exact one
`subscription_renewal_flow` template and `LoyaltyEngine(name="subscription_renewal")` Flow
already built for the real, invoice-driven renewal — seeded with `"{tenant}:sub:{sub_id}"` instead
of `"{tenant}:{invoice_id}"` (operations' `RenewalProvider._split_early_customer` tells the two
apart). Balance/rewards show no invented amount (there is no invoice yet); redeem is the one
moment that actually forces the cycle, via `RenewalProvider.renew_now` — and only because the
owner just tapped confirm on this exact screen. See that module's own docstring for the full
reasoning; `renewal_reply.py`/`renewal_consumer.py` (the pay-link delivery) are unchanged and
serve both seedings identically, since redeem's own contract does not care which path built the
pay_url.

DEDUPED BY (subscription_id, period_end) (UpcomingRenewalTriggerStore) — a daily scan that finds
the same still-upcoming subscription on two consecutive days must open the heads-up exactly once
per real cycle, never once per day it happens to still be within the window.

NO RECIPIENT, NO SEND — NEVER A GUESS. Same posture as renewal_trigger.py: a tenant whose owner
phone cannot be resolved gets nothing sent, silently."""
from __future__ import annotations

from typing import Any

from app.core.upcoming_renewal_trigger_store import UpcomingRenewalTriggerStore

_TEMPLATE_NAME = "subscription_renewal_flow"
_PLATFORM = "_platform"


class UpcomingRenewalTrigger:
    def __init__(self, *, claims: UpcomingRenewalTriggerStore, owner_phone: Any, sender: Any) -> None:
        self._claims = claims
        self._owner_phone = owner_phone
        self._sender = sender

    async def handle(self, *, tenant: str, subscription_id: str, period_end: int, now: int) -> bool:
        """`True` iff a Flow-opening message was sent this call — a subscription/period_end
        already claimed, or a tenant with no reachable owner, answers `False`, never raises. A
        send failure past a real claim DOES raise, same reasoning as `RenewalTrigger.handle`'s own
        docstring: the renewal really is 2 days out, and silently dropping the notice is worse
        than a retried or duplicate one on tomorrow's scan."""
        if not tenant or not subscription_id:
            return False
        if not await self._claims.claim(subscription_id, period_end, now=now):
            return False
        to = await self._owner_phone.resolve(tenant)
        if not to:
            return False
        flow_token = f"renew_soon:{subscription_id}:{int(period_end)}"
        await self._sender.send_template(
            tenant=_PLATFORM, to=to, template_name=_TEMPLATE_NAME, variables=[],
            idempotency_key=flow_token, flow_token=flow_token,
            flow_action_data={"customer": f"{tenant}:sub:{subscription_id}"})
        return True


def build(*, store: Any, owner_phone: Any, sender: Any) -> UpcomingRenewalTrigger:
    return UpcomingRenewalTrigger(
        claims=UpcomingRenewalTriggerStore(store), owner_phone=owner_phone, sender=sender)
