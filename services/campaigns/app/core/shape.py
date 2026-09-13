"""WHAT SHAPE one campaign message takes — today's plain text, or a booking Flow.

THE QUESTION THIS ANSWERS. Three marketing texts end in an intention the customer cannot act on
from inside WhatsApp: «وحشتنا — لك خصم», «كل عام وأنت بخير... لك خصم», «عندنا لك خصم على». He reads
it, he means to come, and the next step is a phone call at a time the shop is busy. A shop that
owns the appointment book can put the book itself under the message — the customer taps, picks a
service, a day and an hour, and the visit exists before he has put the phone down.

ONLY FOR A SHOP THAT OWNS THE BOOK. `feature.bookings` is a separately-priced app, and a booking
screen opened on a shop that has not bought it is a promise nothing behind it can keep: there is
no calendar to read, no staff to assign, and no row to write. So the shape is decided by the
entitlement and by nothing else — never by the goal, never by a per-campaign switch, because a
campaign is authored once and an entitlement changes on the day it is paid for.

AND «NO» IS TODAY'S MESSAGE, BYTE FOR BYTE. Every path that is not a definite yes — the shop does
not own bookings, billing could not be asked, no licence is wired at all, the template is not one
of the three — resolves to `PLAIN`, whose fields are empty, and `HttpSender.send` omits an empty
`flow_token` from the wire body entirely. A shop that gains nothing from this file must not be able
to tell it was added.

WHY THE TOKEN IS THE SEND'S OWN IDEMPOTENCY KEY, and not a fresh mint. It is already unique per
(campaign, recipient) and already stable across a retry — which is the whole of what a Flow token
has to be. insights' weekly-report Flow reuses its own key the same way and for the same reason
(services/insights/app/api/internal.py). A separately-minted token would need a store, a write on
the send path, and a reconciliation for the sends that never happened.

WHY `customer` TRAVELS EMPTY. The booking Flow is seeded with the customer's own phone number —
that is the identity every op in whatsapp-assistant's FlowBookingBackend keys on. This service
holds a PSEUDONYM and no phone number, deliberately, and neither does reminders: the number is
resolved for the length of one call inside reminders' message sender, beside the customer's name.
So the key is DECLARED here (a Flow's action data must carry every placeholder its screen
declares) and FILLED there — the same blank-filling the sender already does for the greeting,
in the same function, for the same reason.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: The entitlement that decides it. One string, one file — a second spelling is a feature that is
#: gated here and free everywhere else.
BOOKINGS_KEY = "feature.bookings"

#: The three marketing texts whose whole point is getting him back through the door, and the only
#: ones a booking screen belongs under. `mkt_announcement` asks for nothing at all — a booking
#: screen under an announcement would be advertising an action the message never asked for.
BOOKING_TYPES = frozenset({"mkt_winback", "mkt_personal_occasion", "mkt_offer"})

#: EVERY MARKETING TEXT WHOSE "attached item" MAY CARRY THE SINGLE-ITEM QUICK-REPLY BUTTON
#: (`for_send`'s third branch). The multi-item carousel counterpart that used to share this set
#: (Meta card rows, `card_count >= 2`) was deleted 2026-09-13 — every campaign carousel template
#: row sat `active: false` and reminders' fallback to `merged_service_text` already fired on
#: every send; this set now exists only for the button. `mkt_loyalty_activation`/`mkt_announcement`
#: JOIN THE THREE BOOKING TYPES here — neither ever opens a booking (a reward, an announcement are
#: not appointments), but each carries the SAME "catalogue" blank the button's item comes from.
BUTTON_TYPES = BOOKING_TYPES | frozenset({"mkt_loyalty_activation", "mkt_announcement"})

#: The Flow's own seed key, as whatsapp-assistant's FlowBookingBackend reads it. Declared empty
#: and filled with the resolved recipient inside reminders' sender — see the module docstring.
CUSTOMER_SEED = "customer"

#: THE FLOW'S FIRST-STEP PRE-SEED (2026-09-13), shipped by base-services-72 in booking_flow.py
#: v0.22.7: INIT now accepts a value under the dimension name of the Flow's OWN first
#: selection step and skips straight past it. Every one of our booking definitions puts "service"
#: first, so this is the one dimension we can ever pre-fill from a campaign — a message that
#: promised "your haircut" no longer makes the customer re-pick it before choosing staff/day/time.
#: Empty (omitted from `flow_action_data` entirely) when the campaign names more than one service —
#: nothing SINGLE to preselect, and the customer picks among them exactly as before.
SERVICE_SEED = "service"


@dataclass(frozen=True)
class Shape:
    """What one send carries beyond its text. Empty is today's message and is the default."""

    flow_token: str = ""
    flow_action_data: dict[str, Any] = field(default_factory=dict)
    # THE UNIFIED QUICK-REPLY BUTTON (2026-09-13) — for a single-item send on one of the two
    # NON-booking types (mkt_loyalty_activation, mkt_announcement): the owner attached
    # exactly one service or package, and a shop that can act on a tap gets a
    # "carousel:{kind}:{id}" button (the payload prefix whatsapp-assistant's own tap handler
    # already expects — see `for_send`'s own docstring for why this is not a Flow, that mechanism
    # stays reserved for the three "come back" types). Empty means no button — the wire never
    # grows a `button_payload` key for it.
    button_item_id: str = ""
    button_kind: str = "service"

    @property
    def opens_booking(self) -> bool:
        return bool(self.flow_token)


#: Today's send, unchanged. A single shared instance so the ordinary path allocates nothing, and so
#: a test can assert identity rather than compare two empty objects.
PLAIN = Shape()


async def opens_booking_for(tenant: str, template_type: str, *, licence: Any) -> bool:
    """May THIS shop's sends of THIS template type open the booking Flow?

    ASKED ONCE PER CAMPAIGN PASS, not once per recipient: the answer is a property of the shop and
    the text, and a thousand-recipient run must not become a thousand billing calls.

    FAILS TO «NO», in every direction. `licence` is None on a deployment that never wired one, and
    every licence in this fleet already answers False rather than raising when billing cannot be
    reached — so an outage costs the booking button, never the message.
    """
    if template_type not in BOOKING_TYPES or licence is None:
        return False
    return bool(await licence.allowed(tenant))


def for_send(*, opens_booking: bool, idempotency_key: str, template_type: str = "",
            card_count: int = 0, item_id: str = "", kind: str = "service",
            card_button_allowed: bool = False) -> Shape:
    """The shape of ONE send. `opens_booking` is `opens_booking_for`'s answer, asked once above;
    `card_count` is how many services/packages THIS campaign actually has attached (its own
    `scope_service_ids`), also asked once — neither varies per recipient. `item_id`/`kind` are that
    single service/package's own id when `card_count == 1` (empty otherwise); `card_button_allowed`
    is `Dispatcher._card_button_allowed`'s own answer, asked once per pass exactly like
    `opens_booking`.

    NO KEY, NO FLOW. An empty idempotency key would mint an empty token, which `HttpSender.send`
    treats as «no Flow» anyway — answering PLAIN here says so out loud instead of relying on a
    falsy value three services away.

    THE SINGLE-ITEM QUICK-REPLY BUTTON (2026-09-13, the owner's own instruction): a campaign of one
    of the two NON-booking types (`mkt_loyalty_activation`/`mkt_announcement`) that names exactly
    one service or package is not "asking for nothing" any more — the owner attached
    something bookable to it, and a shop that can act on a tap should get a button for it. Checked
    ONLY once the Flow branch above has said no — a `BOOKING_TYPES` campaign with bookings owned
    keeps opening the Flow (the richer, owner-preferred experience), never this quick-reply
    instead.

    THE MULTI-ITEM CAROUSEL THAT USED TO SIT HERE (`card_count >= 2`, taking priority over the
    Flow) WAS DELETED 2026-09-13 — every carousel template row was `active: false`, so this
    branch never actually fired; reminders' `merged_service_text` fallback already carried every
    multi-item campaign in production.

    THE SERVICE PRE-SEED (2026-09-13, see `SERVICE_SEED`): only when `card_count == 1`, `item_id`
    is a real service (not a package — `kind == "service"`), and the Flow actually has one to open
    on (a package_offer's own `item_id` is a package id, meaningless to the booking Flow's own
    "service" dimension). A package campaign or a multi-service one still opens the Flow with only
    `customer` seeded, exactly as before.
    """
    if opens_booking and idempotency_key:
        data = {CUSTOMER_SEED: ""}
        if card_count == 1 and item_id and kind == "service":
            data[SERVICE_SEED] = item_id
        return Shape(flow_token=idempotency_key, flow_action_data=data)
    if template_type in BUTTON_TYPES and card_count == 1 and item_id and card_button_allowed:
        return Shape(button_item_id=item_id, button_kind=kind)
    return PLAIN
