"""operations — the entities the field screen writes and reads.

Six of them, and the boundaries between them are product decisions rather than modelling taste:

  Customer   a person, identified by a phone number, belonging to ONE establishment.
  Asset      a vehicle. THE ONLY asset (spec §13.2) — everything else the service cycle follows
             the customer, not a thing they own. A salon has no assets and must not be asked for
             one.
  Service    an entry in the establishment's catalogue: "oil change", "haircut".
  Visit      the record the operator creates: who, what, when, by which operator, at which branch.
             This is the product as far as the shop floor is concerned.
  Operator   the person who recorded it. Attribution, not a login.
  Branch     where.

Everything is tenant-scoped, and the tenant is never taken from a request body — it comes off the
verified token. A tenant sent by a caller is a tenant a caller can change.

──────────────────────────────────────────────────────────────────────────────────────────────
THE PHONE NUMBER: STORED READABLE HERE, PSEUDONYMOUS EVERYWHERE ELSE
──────────────────────────────────────────────────────────────────────────────────────────────
The platform's convention is to hold people as a salted `subject_ref` and never the raw
identifier. We deliberately depart from it inside this service, and the reason has to survive
anyone who reads this later and assumes it was an oversight:

  * The field screen searches by PREFIX. An operator types the first digits while the customer
    stands in front of him, and the matches must appear. A salted hash cannot be prefix-searched —
    that is the entire point of a salted hash.
  * The establishment already has the number. Their customer gave it to them, at their counter,
    for this purpose. Hiding it from the establishment protects nobody and breaks the one screen
    the product lives or dies by.

So: the number is stored and indexed here, readable, tenant-scoped. `subject_ref(PII_SALT, tenant,
phone)` is what we hand to every OTHER service — consent, audit, analytics, notifications — so no
peer ever holds a raw number, and an erasure request can be honoured by ref alone.

Two obligations follow from that choice, and neither is optional:
  * this service's rows are the ones a deletion request must actually clear (see core/erasure.py);
  * a leak here is a leak of phone numbers, so tenant isolation is enforced at the store and not
    merely in a handler.

──────────────────────────────────────────────────────────────────────────────────────────────
THE NAME IS OPTIONAL, AND BLANK IS A REAL VALUE
──────────────────────────────────────────────────────────────────────────────────────────────
Requiring a name does not produce names. It produces "عميل", ".", and "ااا" — which are worse than
blank, because blank is a state the system knows how to handle while an invented name becomes a
greeting in a real message. Messages fall back to a neutral form when it is absent (spec §8.4).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Collection names. Constants rather than literals at call sites: a typo in a string at one call
# site creates a second, silent collection that no backup manifest declares and no erasure clears.
CUSTOMERS = "customers"
ASSETS = "assets"
SERVICES = "services"
VISITS = "visits"
OPERATORS = "operators"
BRANCHES = "branches"


@dataclass
class Customer:
    id: str
    tenant: str
    phone: str                       # readable here by design — see the module docstring
    subject_ref: str                 # what every peer service sees instead
    name: str = ""                   # OPTIONAL. Blank is valid and expected.
    created: int = 0
    last_visit: int = 0              # denormalised: the recent-customers strip reads it on every
                                     # keystroke, and a join per keystroke is a join too many
    visit_count: int = 0

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "tenant": self.tenant, "phone": self.phone, "name": self.name,
                "created": self.created, "last_visit": self.last_visit,
                "visit_count": self.visit_count}

    def peer_view(self) -> dict[str, Any]:
        """What leaves this service toward another one: the ref, never the number."""
        return {"id": self.id, "tenant": self.tenant, "subject_ref": self.subject_ref}


@dataclass
class Asset:
    """A vehicle, and only a vehicle.

    `plate` is the identifier a Saudi workshop actually uses — a customer says "the white Camry,
    plate ABC 1234", never an internal id. It is NOT unique across tenants (two shops may serve the
    same car) and not even guaranteed unique within one: a plate is transcribed by a person in a
    hurry, and refusing a duplicate would block a real visit to protect a database invariant nobody
    asked for.
    """
    id: str
    tenant: str
    customer_id: str
    plate: str = ""
    make: str = ""
    model: str = ""
    year: str = ""
    created: int = 0

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "tenant": self.tenant, "customer_id": self.customer_id,
                "plate": self.plate, "make": self.make, "model": self.model, "year": self.year,
                "created": self.created}


@dataclass
class Service:
    """A catalogue entry. Seeded FULL from the sector defaults at tenant creation (spec §4.6) —
    an establishment that must build its own service list before recording a first visit will not
    record a first visit.

    `cycle_days` is what `reminders` will read to schedule the next visit; 0 means the service has
    no natural cycle (a one-off repair) and generates no reminder.
    """
    id: str
    tenant: str
    name: str
    cycle_days: int = 0
    price_minor: int = 0             # minor units. No float ever touches an amount.
    active: bool = True
    sort: int = 0                    # the field screen's grid order; the adaptive re-sort (§4.4)
                                     # overlays this rather than rewriting it
    created: int = 0

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "tenant": self.tenant, "name": self.name,
                "cycle_days": self.cycle_days, "price_minor": self.price_minor,
                "active": self.active, "sort": self.sort, "created": self.created}


@dataclass
class Visit:
    """One recorded service event — the product, from the shop floor.

    `idempotency_key` is CLIENT-generated, one per entry on the screen, and it is what makes a
    double tap harmless. A server-generated key could not tell a double tap from two genuine
    consecutive visits by the same customer, which is an ordinary thing in a tyre shop.
    """
    id: str
    tenant: str
    customer_id: str
    service_ids: list[str] = field(default_factory=list)
    asset_id: str = ""
    operator_id: str = ""
    branch_id: str = ""
    meter: int = 0                   # odometer where the sector has one; 0 = not captured
    note: str = ""
    idempotency_key: str = ""
    created: int = 0

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "tenant": self.tenant, "customer_id": self.customer_id,
                "service_ids": list(self.service_ids), "asset_id": self.asset_id,
                "operator_id": self.operator_id, "branch_id": self.branch_id,
                "meter": self.meter, "note": self.note, "created": self.created}


@dataclass
class Operator:
    """Who recorded the visit.

    `pin_hash` — never the PIN. A four-digit PIN is guessable by construction, so it is not a
    credential that protects data; it is an attribution check at the moment of saving, and the
    screen behind it is already inside an authenticated establishment session.
    """
    id: str
    tenant: str
    name: str
    pin_hash: str = ""
    role: str = "operator"
    branch_id: str = ""
    active: bool = True
    created: int = 0

    def public(self) -> dict[str, Any]:
        """No pin_hash. Not because it is readable, but because a hash that is never returned
        cannot be attacked offline by someone who reached a read endpoint."""
        return {"id": self.id, "tenant": self.tenant, "name": self.name, "role": self.role,
                "branch_id": self.branch_id, "active": self.active, "created": self.created}


@dataclass
class Branch:
    id: str
    tenant: str
    name: str
    active: bool = True
    created: int = 0

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "tenant": self.tenant, "name": self.name,
                "active": self.active, "created": self.created}
