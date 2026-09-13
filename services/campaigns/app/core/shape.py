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

#: EVERY MARKETING TEXT THAT MAY SHOW A CAROUSEL, once the owner has actually attached more than
#: one service or package to feature (2026-09-13 — the owner's own instruction that a multi-select
#: offer should render as cards, "professionally", never a plain paragraph naming them all).
#: `mkt_loyalty_activation`/`mkt_announcement` JOIN THE THREE BOOKING TYPES here — neither ever
#: opens a booking (a reward, an announcement are not appointments), but each carries the SAME
#: "catalogue" blank a carousel card needs.
#:
#: `mkt_announcement` USED TO CARRY A FREE "owner" BLANK INSTEAD — a real bug, not a style choice:
#: Meta refuses free-typed promotional content inside an approved marketing template's own variable
#: (a variable is a value the template's own reviewed wording expects, not a place to write new
#: copy after approval), and "what's new" is always one of his own services or packages anyway. It
#: was switched to the same "catalogue" multi-select every other marketing goal already uses
#: (2026-09-13). `awr_care_tip` had the same fix applied and joined this set for the same reason —
#: then the goal itself was deleted (2026-09-13, the owner's own decision: its "tip" never carried
#: an actual tip, only a bare catalogue name, once free text was no longer an option).
CAROUSEL_TYPES = BOOKING_TYPES | frozenset({"mkt_loyalty_activation", "mkt_announcement"})

#: The Flow's own seed key, as whatsapp-assistant's FlowBookingBackend reads it. Declared empty
#: and filled with the resolved recipient inside reminders' sender — see the module docstring.
CUSTOMER_SEED = "customer"


@dataclass(frozen=True)
class Shape:
    """What one send carries beyond its text. Empty is today's message and is the default."""

    flow_token: str = ""
    flow_action_data: dict[str, Any] = field(default_factory=dict)
    # PHASE 2 — the carousel counterpart of the booking Flow, for a shop that does NOT own the
    # appointment book. A REQUEST, not a guarantee: reminders is the one place that knows whether a
    # carousel template actually exists (registered, approved, one of the three tones) for this
    # campaign type, and it falls back to plain text on its own if none does — see
    # rendering.choose_carousel. Threading the availability check through here would mean
    # campaigns re-learning a fact reminders already owns, the exact duplication core/shape.py's
    # own module docstring warns against for the booking Flow.
    carousel: bool = False
    # THE UNIFIED QUICK-REPLY BUTTON (2026-09-13) — for a single-item send on one of the two
    # NON-booking types (mkt_loyalty_activation, mkt_announcement): the owner attached
    # exactly one service or package, and a shop that can act on a tap gets the same
    # "carousel:{kind}:{id}" button its own carousel card would carry for the same item. See
    # `for_send`'s own docstring for why this is not a Flow (that mechanism stays reserved for the
    # three "come back" types) and not a carousel (Meta's own 2-card minimum forbids it for one
    # item). Empty means no button — the wire never grows a `button_payload` key for it.
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

    THE CAROUSEL TAKES PRIORITY OVER THE BOOKING FLOW (2026-09-13), where it used to be the
    opposite — a shop that owns the book got the Flow and one that did not got the carousel,
    mutually exclusive by construction. That rule answered a different question ("can this shop
    take a booking at all") than the one that now matters more: the OWNER explicitly attached
    several services or packages to this specific offer, which is a stronger, per-campaign signal
    than a shop-wide entitlement. Two or more cards (Meta's own carousel minimum — see
    `HttpSender._send_carousel_sync`) on an eligible type is shown as a carousel regardless of
    booking ownership; the Flow remains the answer for the ordinary case (0-1 items attached, one
    of the three "come back" types, a shop that owns the book).

    THE SINGLE-ITEM QUICK-REPLY BUTTON (2026-09-13, the owner's own instruction): a campaign of one
    of the two NON-booking types (`mkt_loyalty_activation`/`mkt_announcement`) that names exactly
    one service or package is not "asking for nothing" any more — the owner attached
    something bookable to it, and a shop that can act on a tap should get the same button its own
    carousel card would carry for the same item. Checked ONLY once the Flow and carousel branches
    above have both said no — a `BOOKING_TYPES` campaign with bookings owned keeps opening the
    Flow (the richer, owner-preferred experience), never this quick-reply instead.
    """
    if template_type in CAROUSEL_TYPES and card_count >= 2:
        return Shape(carousel=True)
    if opens_booking and idempotency_key:
        return Shape(flow_token=idempotency_key, flow_action_data={CUSTOMER_SEED: ""})
    if template_type in CAROUSEL_TYPES and card_count == 1 and item_id and card_button_allowed:
        return Shape(button_item_id=item_id, button_kind=kind)
    return PLAIN
