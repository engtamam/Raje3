"""Turn one inbound message from an IDENTIFIED STAFF SENDER into an opened visit-registration
Flow — the entry point for the second channel this session's own approved plan describes
(.claude/plans/stateless-wondering-fox.md; see services/operations' `api/internal.py::
internal_visit_from_whatsapp` for the write side).

SENT FROM THE SHOP'S OWN NUMBER, PER-SHOP LIKE `booking_flow` — unlike the subscription-renewal
Flow (`core/renewal_trigger.py`'s own `_PLATFORM` sending identity), this is staff talking to
their own employer's WhatsApp number about that employer's own operational data, so `tenant` here
is always the real shop tenant, never `_platform`.

THREE GATES, IN THE CHEAPEST-FIRST ORDER, BEFORE ANY PEER READ HAPPENS:
  1. `licence.allowed(tenant)` — the same subscription gate every WhatsApp feature in this
     product already holds (see core/conversation.py's own use of it). A lapsed/unsubscribed shop
     gets nothing from this trigger, same as it gets nothing from the AI channel.
  2. `whatsapp_visit_gate.enabled(tenant)` — the OWNER's own explicit opt-in (services/operations'
     core/whatsapp_visit_flag.py). Off by default for every shop; this trigger must never open a
     Flow a shop never asked for.
  3. `operator_identity.resolve(...)` — the actual, real two-peer-read WhatsApp-sender-to-operator
     match. Deliberately checked LAST: it is the only one of the three that costs a network round
     trip per message, and the first two already answer "no" for the overwhelming majority of
     inbound messages (most tenants have not opted in yet) without ever making it.

AN UNIDENTIFIED SENDER IS NOT AN ERROR. A customer texting the shop's number, or a staff member
whose phone changed and was never re-registered, both fall through here with `False` — the caller
(app/core/inbound_ingest.py) then continues into the ordinary customer conversation exactly as it
already does today. This trigger only ever intercepts, never refuses.
"""
from __future__ import annotations

from typing import Any

_TEMPLATE_NAME = "visit_flow"


async def maybe_open_visit_flow(*, container: Any, tenant: str, from_number: str,
                                idempotency_key: str) -> bool:
    """`True` iff a Flow-opening message was sent — the caller should stop and not continue into
    the ordinary conversation for this message. `False` for everything else: gated off, not
    opted in, or the sender is not (or no longer) a real operator here."""
    licence = getattr(container, "licence", None)
    if licence is not None and not await licence.allowed(tenant):
        return False
    gate = getattr(container, "whatsapp_visit_gate", None)
    if gate is None or not await gate.enabled(tenant):
        return False
    identity = getattr(container, "operator_identity", None)
    if identity is None:
        return False
    operator_id = await identity.resolve(tenant=tenant, from_number=from_number)
    if not operator_id:
        return False
    await container.sender.send_template(
        tenant=tenant, to=from_number, template_name=_TEMPLATE_NAME, variables=[],
        idempotency_key=idempotency_key, flow_token=idempotency_key,
        flow_action_data={"customer": from_number})
    return True
