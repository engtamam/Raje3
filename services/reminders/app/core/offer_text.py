"""The offer, said in one line — from the structured parts when the owner wrote none.

WHY THIS EXISTS (أ-6). The entitlement IS `offer_text` on the send log: everything downstream —
what the till offers, what `choose_offer` picks, what the customer's page shows — skips a row whose
text is blank. And that text was taken from ONE place: the owner's free line.

Then the offer templates were built without a free line at all. `mkt_offer`, `mkt_winback` and
`mkt_personal_occasion` declare `fills: [system, system, amount, catalogue, date]` — no `owner`
anywhere — because the sentence is composed from the typed parts and the wording is ours. So the
screen never asks for the text, the owner never writes one, and the log records an empty string.

The result is a campaign that WORKS at every visible step. Four hundred messages go out, each one
correct, each one naming a real discount. Then the customer walks in, the operator opens the till,
and it says «لا يوجد عرضٌ ساري». His own page says the same. The only trace that the offer ever
existed is the message in his phone, and the shop is arguing with a customer holding proof.

SO THE ENTITLEMENT IS BUILT FROM WHAT WAS SENT, and never invented: the discount, the services it
covers, and — when neither survives — a plain statement that an offer exists, because the expiry
alone is proof that one was granted. Silence here is the one answer that cannot be right.
"""
from __future__ import annotations

from app.core.rendering import merged_service_text


def compose(*, owner_text: str = "", value: str = "", service_names: list[str] | None = None,
            has_expiry: bool = False) -> str:
    """The line that IS the entitlement.

    `owner_text` wins whenever there is one: it is what the customer actually read, and a
    different sentence at the counter is how one offer becomes an argument about two.
    """
    if not has_expiry:
        # NOT AN OFFER AT ALL. An entitlement with no end is a price change nobody decided on, and
        # every reader of this field already refuses one.
        return ""
    said = (owner_text or "").strip()
    if said:
        return said

    amount = (value or "").strip()
    where = merged_service_text(list(service_names or []))
    if amount and where:
        return f"خصم {amount} على {where}"
    if amount:
        return f"خصم {amount}"
    if where:
        return f"عرض خاص على {where}"
    # THE LAST RESORT, AND IT IS STILL BETTER THAN BLANK. The shop granted something with an end
    # date; the operator needs to see that a valid offer exists even when we cannot restate it.
    return "عرض خاص"
