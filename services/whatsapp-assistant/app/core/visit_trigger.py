"""Turn one inbound message from an IDENTIFIED STAFF SENDER into an opened internal-management
menu — the entry point for the second channel this session's own approved plan describes
(.claude/plans/stateless-wondering-fox.md; see services/operations' `api/internal.py::
internal_visit_from_whatsapp` for the visit-registration Flow's own write side).

TWO STEPS, NOT ONE. `##` opens a real WhatsApp **Interactive List Message** — Meta's own native
menu component (a bottom-sheet list, up to 10 rows, each a short title + optional description; no
custom styling, the same list UI a customer sees in any other list this product already sends,
e.g. the mandatory triage gate) — never a Flow directly. Tapping a row is what opens the actual
Flow for whichever internal action it names. One row today ("تسجيل زيارة"); a second internal
Flow later is a second row, never a second trigger word or a restructure of this module.

SENT FROM THE SHOP'S OWN NUMBER, PER-SHOP LIKE `booking_flow` — unlike the subscription-renewal
Flow (`core/renewal_trigger.py`'s own `_PLATFORM` sending identity), this is staff talking to
their own employer's WhatsApp number about that employer's own operational data, so `tenant` here
is always the real shop tenant, never `_platform`.

NEVER FOR AN ORDINARY MESSAGE, EVEN FROM A REAL STAFF MEMBER — the owner's own correction
(2026-09-10): a staff member texting the shop's number usually wants to talk to the SHOP (the AI,
or the owner reading it himself), exactly like anyone else, and hijacking every one of his messages
into a menu would break that. So the menu only ever opens on an EXPLICIT symbol (`_TRIGGER_WORD`),
matched EXACTLY — never a substring of a real sentence — the same "he chooses it, it is never
forced on him" shape a Telegram bot's own `/command` has (WhatsApp itself has no native
slash-command system — checked; a list message opened by a chosen keyword is the closest official
equivalent). Chosen as the FIRST, free check before anything else: a random customer typing the
same symbol costs nothing extra, since every gate after it still has to answer honestly for him
too.

THE SYMBOL, NOT A WORD (a second owner decision, 2026-09-10): `##` instead of an Arabic keyword,
so a staff member who cannot type Arabic reliably (or at all, on a borrowed/shared device) can
still use it — sits on every keypad including a bare feature phone's.

NOT A SECURITY BOUNDARY, AND DELIBERATELY NOT MADE SECRET-PER-SHOP (owner's own question,
answered 2026-09-10): the symbol only signals INTENT ("I want the menu"), never proof of WHO is
asking — a stranger typing `##` learns nothing and gets nothing, because `operator_identity`
resolution is the real gate and answers honestly for him too (empty). Making the symbol itself a
secret would add real complexity (a new per-tenant setting, a forgot-my-code support path) for
zero additional protection, since the actual security already lives one layer down.

FOUR GATES BEFORE THE MENU EVER SENDS, CHEAPEST-FIRST — see `maybe_open_staff_menu`'s own
docstring. THE SAME THREE (minus the symbol match, which only applies to opening the menu) ARE
RE-CHECKED when a row is actually tapped (`maybe_handle_staff_menu_reply`) — the list itself
proves nothing extra: WhatsApp does not let anyone else forge a reply to a message they were never
sent, but re-checking costs one more cheap read and matches this codebase's own "the write
re-checks, never only the suggestion" discipline everywhere else (see core/flow_visit_backend.py's
own `reserve()`, which never trusts an `operator_id` handed to it either).
"""
from __future__ import annotations

from typing import Any

#: row id -> the template that opens that Flow. One entry today; a second internal Flow is a
#: second entry here and a second row in `_MENU_ROWS`, nothing else in this module changes.
_MENU_TEMPLATES: dict[str, str] = {
    "staffmenu:visit": "visit_flow",
}
_MENU_ROWS: list[dict[str, str]] = [
    {"id": "staffmenu:visit", "title": "تسجيل زيارة",
     "description": "سجّل زيارة عميل من هنا مباشرة"},
]
_MENU_ID_PREFIX = "staffmenu:"

#: A SYMBOL, NOT A WORD — see the module docstring.
_TRIGGER_WORD = "##"


async def _staff_operator_id(container: Any, *, tenant: str, from_number: str) -> str:
    """The three real gates, shared by both the menu-open and the row-tap paths: licence, owner
    opt-in, sender identity. `""` for anything that fails any of them — never a distinct error,
    same "an unidentified sender is not an error" posture the module docstring states."""
    licence = getattr(container, "licence", None)
    if licence is not None and not await licence.allowed(tenant):
        return ""
    gate = getattr(container, "whatsapp_visit_gate", None)
    if gate is None or not await gate.enabled(tenant):
        return ""
    identity = getattr(container, "operator_identity", None)
    if identity is None:
        return ""
    return await identity.resolve(tenant=tenant, from_number=from_number)


async def maybe_open_staff_menu(*, container: Any, tenant: str, from_number: str, kind: str,
                                text: str, idempotency_key: str) -> bool:
    """`True` iff the menu was sent — the caller should stop and not continue into the ordinary
    conversation for this message. `False` for everything else: not the symbol, gated off, not
    opted in, or the sender is not (or no longer) a real operator here."""
    if kind != "text" or text.strip() != _TRIGGER_WORD:
        return False
    operator_id = await _staff_operator_id(container, tenant=tenant, from_number=from_number)
    if not operator_id:
        return False
    await container.sender.send_list(
        tenant=tenant, to=from_number, body="اختر من القائمة:", button_text="القائمة",
        rows=_MENU_ROWS, idempotency_key=idempotency_key)
    return True


async def maybe_handle_staff_menu_reply(*, container: Any, tenant: str, from_number: str,
                                        kind: str, reply_id: str, idempotency_key: str) -> bool:
    """`True` iff a row tap opened its Flow — the caller should stop, same as
    `maybe_open_staff_menu`. `False` for a reply that is not one of this menu's own rows, or one
    whose sender can no longer be verified (re-checked here, never trusted from the tap alone —
    see module docstring)."""
    if kind != "list_reply" or not reply_id.startswith(_MENU_ID_PREFIX):
        return False
    template_name = _MENU_TEMPLATES.get(reply_id)
    if not template_name:
        return False
    operator_id = await _staff_operator_id(container, tenant=tenant, from_number=from_number)
    if not operator_id:
        return False
    await container.sender.send_template(
        tenant=tenant, to=from_number, template_name=template_name, variables=[],
        idempotency_key=idempotency_key, flow_token=idempotency_key,
        flow_action_data={"customer": from_number})
    return True
