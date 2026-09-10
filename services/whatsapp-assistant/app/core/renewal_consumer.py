"""Turn one inbound `whatsapp.message` bus event into a delivered renewal pay-link, or nothing.

MIRRORS services/reminders' `rating_consumer.py` exactly, with one real difference: rating only
WRITES a record on a match (the rating itself is the end value); this must also SEND something
back — the Flow's own terminal screen already told the shop owner "a message is coming" (see
deploy/seed/subscription-renewal-flow.json's SUCCESS screen), and `extension_message_response`
alone is not a message a WhatsApp client is guaranteed to render as a readable, clickable link. So
`redeem`'s `reward_ref` (the real pay_url, created for real by billing when the shop owner
confirmed) is delivered as an ordinary approved-template send, to the SAME number the Flow was
opened on.

TEMPLATE NAME IS AN OPERATOR DECISION, NOT A CODE ONE. `_TEMPLATE_NAME` must be registered,
carrying one variable (the link), and submitted for Meta's approval through the admin console
(AdminWhatsAppTemplates.tsx — the ONE place templates are registered on this product) before this
consumer can actually deliver anything; until then `send_template` fails and this consumer's own
docstring on `handle` explains why that is a refusal, never a silent swallow.

AT-MOST-ONCE, same as `RatingConsumer`'s own documented gap — no catch-up path exists yet.
"""
from __future__ import annotations

from typing import Any

from app.core.renewal_reply import parse_renewal_reply
from app.core.renewal_request import RenewalRequestStore

_TEMPLATE_NAME = "subscription_renewal_link"
#: THE SENDING IDENTITY, always — this whole conversation happens on the platform's own number
#: (see renewal_trigger.py's own docstring), never `pending.tenant` (the real shop, kept on the
#: request row for audit only).
_PLATFORM = "_platform"


class RenewalConsumer:
    def __init__(self, *, requests: RenewalRequestStore, sender: Any) -> None:
        self._requests = requests
        self._sender = sender

    async def handle(self, message: dict[str, Any]) -> bool:
        """`True` iff a pay-link message was sent this call. `False` for everything else — not a
        renewal reply, an unknown or already-consumed flow_token — and NEVER raises: one malformed
        or unrelated inbound message must not stop this consumer from reading every message after
        it. A `send_template` failure (unregistered/unapproved template, peer unreachable) DOES
        raise past this method — the shop owner confirmed a real charge is coming and silently
        losing the link is worse than a retried/duplicate delivery on the next bus event.
        """
        reply = parse_renewal_reply(message)
        if reply is None:
            return False
        pending = await self._requests.resolve(reply.flow_token)
        if pending is None:
            return False
        await self._sender.send_template(
            tenant=_PLATFORM, to=pending.to, template_name=_TEMPLATE_NAME,
            variables=[reply.pay_url], idempotency_key=f"renewal_link:{reply.flow_token}")
        return True
