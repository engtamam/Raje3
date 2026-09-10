"""Turn one inbound message from an IDENTIFIED STAFF SENDER into an opened visit-registration
Flow — the entry point for the second channel this session's own approved plan describes
(.claude/plans/stateless-wondering-fox.md; see services/operations' `api/internal.py::
internal_visit_from_whatsapp` for the write side).

SENT FROM THE SHOP'S OWN NUMBER, PER-SHOP LIKE `booking_flow` — unlike the subscription-renewal
Flow (`core/renewal_trigger.py`'s own `_PLATFORM` sending identity), this is staff talking to
their own employer's WhatsApp number about that employer's own operational data, so `tenant` here
is always the real shop tenant, never `_platform`.

NEVER FOR AN ORDINARY MESSAGE, EVEN FROM A REAL STAFF MEMBER — the owner's own correction
(2026-09-10): a staff member texting the shop's number usually wants to talk to the SHOP (the AI,
or the owner reading it himself), exactly like anyone else, and hijacking every one of his messages
into a Flow would break that. So this only ever fires on an EXPLICIT keyword (`_TRIGGER_WORD`),
never on plain conversation — the same "he chooses it, it is never forced on him" shape a Telegram
bot's own `/command` has, the closest WhatsApp gets to one being an interactive list message a
keyword opens (WhatsApp itself has no native slash-command system — checked). Chosen as the
FIRST, free check before anything else: a random customer typing the same word costs nothing
extra, since every gate after it still has to answer honestly for him too.

FOUR GATES, IN THE CHEAPEST-FIRST ORDER, BEFORE ANY PEER READ HAPPENS:
  1. The keyword itself — a bare string compare, no I/O. Anything else (including the exact same
     text as it, but from a customer, or as a button reply) never reaches gate 2.
  2. `licence.allowed(tenant)` — the same subscription gate every WhatsApp feature in this
     product already holds (see core/conversation.py's own use of it). A lapsed/unsubscribed shop
     gets nothing from this trigger, same as it gets nothing from the AI channel.
  3. `whatsapp_visit_gate.enabled(tenant)` — the OWNER's own explicit opt-in (services/operations'
     core/whatsapp_visit_flag.py). Off by default for every shop; this trigger must never open a
     Flow a shop never asked for.
  4. `operator_identity.resolve(...)` — the actual, real two-peer-read WhatsApp-sender-to-operator
     match. Deliberately checked LAST: it is the only one of the four that costs a network round
     trip, and the earlier three already answer "no" for almost every message (most text is not
     the keyword at all, and most tenants have not opted in) without ever making it.

AN UNIDENTIFIED SENDER IS NOT AN ERROR. A customer who happens to type the same keyword, or a
staff member whose phone changed and was never re-registered, both fall through here with `False`
— the caller (app/core/inbound_ingest.py) then continues into the ordinary customer conversation
exactly as it already does today, reading his message as ordinary text. This trigger only ever
intercepts, never refuses.

ONE FLOW TODAY, NAMED FOR MORE LATER. The keyword opens the visit-registration Flow directly
rather than a menu — the owner's own future direction ("نقدر نضيف اكثر من فلو مستقبلا") is a real
one, and the natural next step once a second internal Flow exists is an interactive LIST message
here instead of a direct open (WhatsApp's own closest thing to a command menu — up to 10 rows,
each a title + description). Not built now because there is only one Flow to list.
"""
from __future__ import annotations

from typing import Any

_TEMPLATE_NAME = "visit_flow"
#: A SYMBOL, NOT A WORD (owner decision, 2026-09-10) — a staff member who cannot type Arabic (or
#: any language reliably on a shared/borrowed device) can still type this. `##` sits on every
#: keypad including a bare feature phone's, and is not a sequence anyone types mid-sentence to a
#: customer or the owner by accident. Matched exactly, deliberately not a prefix/fuzzy match — the
#: same certainty a slash command gives.
_TRIGGER_WORD = "##"


async def maybe_open_visit_flow(*, container: Any, tenant: str, from_number: str, kind: str,
                                text: str, idempotency_key: str) -> bool:
    """`True` iff a Flow-opening message was sent — the caller should stop and not continue into
    the ordinary conversation for this message. `False` for everything else: not the keyword,
    gated off, not opted in, or the sender is not (or no longer) a real operator here."""
    if kind != "text" or text.strip() != _TRIGGER_WORD:
        return False
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
