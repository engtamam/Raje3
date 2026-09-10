"""Turn one `wallet.balance_low` bus event into an owner-facing top-up notice — no polling, no
sweep. wallet-service (platform v0.19.14+) is the sensor: it measures the crossing itself on every
spend, dedupes/re-arms server-side (`_check_low_balance`), and fires this event AT MOST ONCE per
crossing, again once it recovers (`wallet.balance_recovered`, which this module ignores — a
recovery needs no message). That is deliberate, by owner decision (2026-09-10): the balance itself
carries the alarm, rather than this service (or any other) polling every tenant on a cron to ask
"are you low yet?" — the exact server-load tradeoff the owner asked to avoid.

SENT FROM OUR OWN NUMBER, NOT THE SHOP'S CONNECTED ONE — same posture as the subscription-renewal
Flow (core/renewal_trigger.py's own docstring): this is a bill about the AI assistant itself, true
for every conversation that tenant runs, not something any one customer conversation caused. A shop
with no WhatsApp number connected yet still has an AI wallet and still needs to hear this.

NO SPECIAL TOP-UP FLOW, NO AUTO-LOGIN LINK — a plain link to the platform (owner decision,
2026-09-10: "أسهل وأقل تكلفة"). The owner opens it, logs in the normal way, and tops up from the
wallet screen that already exists there; building a dedicated top-up page or a WhatsApp-native Flow
for this was explicitly rejected as unnecessary work for a reminder this simple.

NO RECIPIENT, NO SEND, NEVER A GUESS — identical posture to renewal_trigger.py: `OwnerPhone.resolve`
answering "" (no founding owner, an email-only signup, identity-service unreachable) means this
trigger sends nothing.

IDEMPOTENT ON (tenant, threshold), NOT ON TIME. wallet-service's own crossing-dedup is what
prevents a flood in the first place; the idempotency_key here only protects against the bus
occasionally redelivering the SAME event (still possible even on an at-most-once bus during a
retry inside notification-service) from sending the notice twice for what is, from the owner's
side, one and the same warning.
"""
from __future__ import annotations

from typing import Any

#: Must be a plain (non-Flow) template registered under the reserved "_platform" tenant — same
#: manual register-then-submit console flow as `subscription_renewal_flow` (services/operations/
#: app/core/flows.py's own PLATFORM constant), kept as each file's own local copy per this
#: codebase's convention rather than a shared import.
_TEMPLATE_NAME = "ai_wallet_low_balance"
_PLATFORM = "_platform"


class WalletLowBalanceTrigger:
    def __init__(self, *, owner_phone: Any, sender: Any, public_base_url: str) -> None:
        self._owner_phone = owner_phone
        self._sender = sender
        self._base_url = (public_base_url or "").rstrip("/")

    async def handle(self, event: dict[str, Any]) -> bool:
        """`True` iff a notice was sent this call. `False` for an event with no tenant, or a
        tenant with no reachable owner — never raises for those. A send failure past a real,
        reachable owner DOES raise (the balance really is low; silently dropping the notice is
        worse than a duplicate one on the next crossing), same posture RenewalTrigger.handle holds."""
        tenant = str(event.get("tenant") or "")
        if not tenant:
            return False
        threshold = event.get("threshold")
        to = await self._owner_phone.resolve(tenant)
        if not to:
            return False
        idempotency_key = f"walletlow:{tenant}:{threshold}"
        await self._sender.send_template(
            tenant=_PLATFORM, to=to, template_name=_TEMPLATE_NAME,
            variables=[self._base_url or "https://"], idempotency_key=idempotency_key)
        return True


def build(settings: Any, *, owner_phone: Any, sender: Any) -> WalletLowBalanceTrigger:
    return WalletLowBalanceTrigger(
        owner_phone=owner_phone, sender=sender, public_base_url=settings.PUBLIC_BASE_URL)
