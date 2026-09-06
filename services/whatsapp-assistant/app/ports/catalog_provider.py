"""CatalogProvider port — a shop's own sellable items, one card each, behind a port a shop with no
account on this platform at all (a standalone WhatsApp-bot customer, reading its OWN Meta/WhatsApp
catalog instead) can implement later without touching whichever feature ends up consuming it.

SAME SHAPE AS `ports/booking_provider.py`, DELIBERATELY: a `@runtime_checkable Protocol` carrying
`driver: str`, a frozen dataclass for the one value object it returns, and a driver string in
config picking one adapter in `app/container.py`'s own explicit if/elif — never a generic registry,
matching that port's own precedent exactly.

THIS PORT IS INFRASTRUCTURE ONLY, BUILT AHEAD OF ANY CONSUMER — a deliberate choice (owner's own
decision), not an oversight. `container.catalog_provider` is wired and tested, but nothing in
core/conversation.py or core/tools.py calls it yet: neither an actual WhatsApp carousel send (that
needs an approved Meta template plus notification-service's own media-upload step) nor a
`WhatsAppCatalogProvider` (a standalone shop's own linked Meta catalog) exist yet. Both are future
work this port is shaped to receive without a second migration.

`image_url` IS ABSENCE-DISCIPLINED, NEVER A PLACEHOLDER — an item with no photo carries `""`, the
same "do not render a card for what does not apply" rule `AiNotesCard`/`WalletPane`'s own cards
follow elsewhere in this product, not a stock image standing in for a real one.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class CatalogCard:
    id: str
    kind: str            # "service" | "package"
    name: str
    price_minor: int
    image_url: str = ""  # "" — no photo. Never a placeholder image.


@runtime_checkable
class CatalogProvider(Protocol):
    driver: str

    async def list_cards(self, *, tenant: str, limit: int = 10) -> list[CatalogCard]: ...
