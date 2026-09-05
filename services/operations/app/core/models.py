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
PACKAGES = "packages"
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
    # WHERE THEY WERE LAST SEEN, and the customer FOLLOWS IT (spec 12.2).
    #
    # A customer belongs to the establishment, never to a branch — one balance, one opt-out, one
    # page. But a campaign aimed at Jeddah must reach the people who actually go to Jeddah, and the
    # honest answer to «which branch is this customer's» is the last one they walked into. Somebody
    # who moves city moves with it, on their first visit, with nobody configuring anything.
    #
    # Denormalised here for the same reason `last_visit` is: the alternative is scanning a year of
    # visits per customer while building an audience of 5000.
    last_branch_id: str = ""
    # THE LAST VISIT THESE COUNTERS HAVE ALREADY COUNTED (ز-6).
    #
    # `visit_count` and `last_visit` are derived numbers kept beside the customer so the recent-
    # customers strip is one read. Deriving them is a scan; incrementing them is a second write.
    # Two writes are two chances to be interrupted, and this field is what makes the second one
    # repeatable: the increment asks «have I already counted this visit?» rather than «is this my
    # first attempt?», which is a question no process can answer about itself after a crash.
    #
    # Empty on every customer written before this existed, and that is correct: it means «not
    # counted by id», and the very next visit stamps it. Nothing is recomputed retroactively —
    # the counters those customers carry are the ones they already had.
    counted_visit_id: str = ""

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "tenant": self.tenant, "phone": self.phone, "name": self.name,
                "created": self.created, "last_visit": self.last_visit,
                "visit_count": self.visit_count, "last_branch_id": self.last_branch_id}

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
    """A catalogue entry, written by the owner in «خدماتي» —
    an establishment that must build its own service list before recording a first visit will not
    record a first visit.

    `cycle_days` is what `reminders` will read to schedule the next visit; 0 means the service has
    no natural cycle (a one-off repair) and generates no reminder.

    `duration_minutes` is what bookings reads to derive availability (docs/خطة-تنفيذ-الحجوزات.md
    §2/§4). 0 means NOT CONFIGURED — not "instant" and not a guessed default. A shop that has not
    set it must not have a length silently invented for its services: bookings refuses to compute
    a slot for a service whose duration is 0, and the console prompts the owner to set a real one.
    Guessing here would be the same defect family as an unread config deciding policy.
    """
    id: str
    tenant: str
    name: str
    cycle_days: int = 0
    price_minor: int = 0             # minor units. No float ever touches an amount.
    duration_minutes: int = 0        # 0 = not configured. See docstring — never defaulted silently.
    active: bool = True
    sort: int = 0                    # the field screen's grid order; the adaptive re-sort (§4.4)
                                     # overlays this rather than rewriting it
    # THE CATCH-ALL. Exactly one per tenant, and the reason it exists is
    # that the alternative is losing the visit. A technician does something the catalogue does not
    # list, or a POS sends a service the owner never added — without this the operator cannot save,
    # and a lost visit is a lost customer: no reminder, no points, no metric, forever.
    #
    # Its cycle is necessarily 0. We do not know what was done, so we cannot say when it is due.
    catchall: bool = False
    # THE TILL'S OWN ID FOR THIS PRODUCT. Empty for anything the owner typed by hand; set when the
    # service came from — or was matched to — a POS line (core/invoices.py).
    #
    # It is what lets a renamed product stay ONE service instead of forking into two every time a
    # shop tidies its wording, and what lets a shop that went manual first ADOPT its till's id
    # rather than ending up with two identical rows and a visit history split across them.
    external_id: str = ""
    # WE PUT THIS ROW HERE, HE DID NOT. Nothing sets it any more — seeding is gone — and it is
    # what still makes the
    # catalogue tidy-up on integration safe: a seeded name the till never mentions and nobody ever
    # sold is a GUESS of ours, and retiring a guess is not the same as touching a shop's data.
    seeded: bool = False
    created: int = 0
    # WHO CAN ACTUALLY DO THIS — empty means EVERY active operator can, which is the safe default
    # a shop with one operator (or a shop where nobody has ever specialised) never has to touch.
    # A shop that DOES have staff who only do some of its services fills this in per service; the
    # reverse view ("what does this operator do") is derived by filtering services at read time,
    # never stored a second time on Operator — one direction of truth, so the two can never drift
    # apart from each other. Read by bookings-service over
    # `/internal/operations/service-durations` (extended to carry this alongside duration), never
    # duplicated into bookings' own store.
    eligible_staff_ids: list[str] = field(default_factory=list)

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "tenant": self.tenant, "name": self.name,
                "cycle_days": self.cycle_days, "price_minor": self.price_minor,
                "duration_minutes": self.duration_minutes,
                "active": self.active, "sort": self.sort, "catchall": self.catchall,
                "external_id": self.external_id, "seeded": self.seeded, "created": self.created,
                "eligible_staff_ids": list(self.eligible_staff_ids)}


@dataclass
class Package:
    """A named, priced group of the owner's OWN services — sold as one thing, booked as one thing.

    NOT A DISCOUNT, NOT DERIVED. `price_minor` is entered by the owner and carries no relationship
    to the sum of its `service_ids`' own `price_minor` — the same "the platform never invents a
    price" doctrine campaigns' and insights' own docstrings already state for messages and
    suggestions. `services/insights/app/core/bundles.py` may SUGGEST which two services to combine
    (real, statistically-supported demand — never a discount), but the number typed here is always
    the owner's, from zero, every time.

    `service_ids` MUST hold at least two ids — a "package" of one service is just that service. No
    upper bound: the owner decides how many belong together, same as he decides for an ordinary
    visit's own `Visit.service_ids`. A service may sit in more than one active package at once —
    deliberately unrestricted, the owner's own call each time (§ decision, packages feature).

    `duration_minutes` is NEVER cached here — see bookings' own duration-lookup adapter for why:
    a component's own duration can change after the package was created, and a stale cached sum
    would silently mis-size a slot the owner never re-confirmed. Recomputed fresh, every booking
    attempt, by summing the CURRENT `Service.duration_minutes` of each live member — the same
    "never guessed, never stale" posture `Service.duration_minutes` itself already documents.

    Eligible staff are likewise never stored here — see the internal package-eligible-staff route:
    derived as the INTERSECTION of each component's own `eligible_staff_ids` at read time (an empty
    list on a component means "everyone", so intersecting naturally keeps the common "no
    restriction anywhere" case unrestricted too).
    """
    id: str
    tenant: str
    name: str
    service_ids: list[str] = field(default_factory=list)
    price_minor: int = 0             # minor units, owner-entered, independent of the components
    active: bool = True
    sort: int = 0
    # WHICH DOOR MADE IT — "manual" (owner picked services himself) or "suggested" (accepted from
    # محلّي's real-demand card). Telemetry only; both are the exact same entity from here on, and
    # neither is treated differently by bookings, visits, or loyalty.
    source: str = "manual"
    # THE PAIR THIS CAME FROM, if `source == "suggested"` — so محلّي can stop re-offering a pair the
    # owner already turned into a package. Empty otherwise.
    source_service_ids: list[str] = field(default_factory=list)
    created: int = 0

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "tenant": self.tenant, "name": self.name,
                "service_ids": list(self.service_ids), "price_minor": self.price_minor,
                "active": self.active, "sort": self.sort, "source": self.source,
                "source_service_ids": list(self.source_service_ids), "created": self.created}


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
    meter: int = 0                   # odometer where the shop works on cars; 0 = not captured
    note: str = ""
    # What it actually was, when the catch-all was used. Free text, typed by the operator or sent
    # by an integration. Kept because "خدمة أخرى" alone tells the owner nothing six months later,
    # and because a name appearing here repeatedly is exactly the signal that it should become a
    # real catalogue entry.
    custom_service: str = ""
    # HOW MANY OF EACH SERVICE THIS ONE VISIT HELD — empty for every visit recorded by hand, where
    # the screen records the act and not a count, and that emptiness is correct rather than missing.
    #
    # IT EXISTS FOR ONE READER: the group-basket test (§10.6.2). Two coffees on one bill is one
    # receipt and more than one person, and a receipt like that must be dropped from LEARNING while
    # still counting as the real visit and real money it was. Without it the association engine
    # learns «من طلب قهوة طلب قهوة» from a table of four.
    quantities: dict[str, int] = field(default_factory=dict)
    # PAID FOR WITH POINTS (ب-6). The visit is real — the work was done, the cycle restarts, the
    # history shows it — and it must not earn points of its own: a reward that pays the customer
    # for redeeming it is the shop giving the same thing away twice.
    free: bool = False
    # WHAT THIS VISIT WAS WORTH, in halalas, and only ever from an integrated till — the field
    # screen records no money. 0 means «not known», which is exactly what a field visit is.
    total_minor: int = 0
    idempotency_key: str = ""
    # TWO CLOCKS, kept separately and on purpose.
    #
    # `created` is OURS — when we received it. `occurred_at` is the device's — when it says the
    # visit happened. They are the same number for anything recorded on our own screen, and they
    # diverge for anything replayed by an integration after an outage.
    #
    # Not cosmetic: reminders schedule from when the visit HAPPENED, so a batch drained two days
    # late must not push every reminder two days out. And a cashier's clock can simply be wrong —
    # keeping ours means a device set to next month cannot schedule a reminder into next month.
    created: int = 0
    occurred_at: int = 0
    # WHEN THE WORK BEHIND THE VISIT FINISHED — indexing, and the event every other service
    # schedules and counts from (ز-7). 0 means «not yet», and it is the only way to tell that
    # apart from «done», which is what this whole field exists for.
    #
    # THE SEAMS RUN AFTER THE RESPONSE, deliberately: the operator has a customer in front of him
    # and must not wait on our fan-out. But «after the response» also means «after the process may
    # have gone away», and nothing recorded whether they had run. A pod evicted between the two
    # left a visit saved and a customer with no points, no reminder, and unfindable by the keypad —
    # and the retry made it permanent, because it saw a duplicate and skipped the seams entirely.
    #
    # Written by `Seams.after_visit` when it completes. Read by the retry, and by the sweep for
    # the visits no retry ever comes for.
    seamed_at: int = 0
    # THE OFFER THIS VISIT SPENT, and it lives HERE rather than on the send-log row (§5.6.2).
    #
    # «ويُسجَّل على الزيارة، لا على العرض» — because the send log is append-only and every cap in
    # 5.8 is counted against it, so a mutable flag inside it breaks the thing the limits are
    # counted on. The visit is also simply what happened at the counter.
    #
    # `offer_ref` is the send-log row id. The TEXT is copied rather than referenced: the message
    # said something specific to this customer, and an owner reading this visit a year later needs
    # what was promised, not a pointer into a log that retention may have pruned.
    offer_ref: str = ""
    offer_text: str = ""
    offer_used_at: int = 0
    # SET ONLY WHEN THIS VISIT FULFILLED A PACKAGE BOOKING — "" for an ordinary visit. `service_ids`
    # is STILL populated with the package's own components either way (never left empty), so every
    # existing reader (reminders' per-service cycle, the associations engine, loyalty's default
    # per-service sum) keeps working completely unmodified — this field exists purely so the
    # receipt/history UI can say «باقة: غيار + فحص» instead of two unrelated lines, and so loyalty
    # knows to look up the PACKAGE's own point value rather than summing the components' (see
    # services/loyalty/app/core/earning.py's package-level override).
    package_id: str = ""

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "tenant": self.tenant, "customer_id": self.customer_id,
                "service_ids": list(self.service_ids), "asset_id": self.asset_id,
                "operator_id": self.operator_id, "branch_id": self.branch_id,
                "meter": self.meter, "note": self.note, "custom_service": self.custom_service,
                "created": self.created,
                "free": self.free,
                "occurred_at": self.occurred_at or self.created,
                "offer_ref": self.offer_ref, "offer_text": self.offer_text,
                "offer_used_at": self.offer_used_at, "package_id": self.package_id}


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
    # WHO HE IS AT IDENTITY, when he has an account of his own. Empty for the PIN-only operators a
    # shared tablet attributes work to — they are a name and a rhythm, not a login.
    #
    # THIS FIELD IS WHAT MAKES A BRANCH SCOPE POSSIBLE. A token carries `sub`; a branch lives on
    # this row; nothing else in the product joins the two. Without it, "show this manager only his
    # branch" has no way to know which manager is asking.
    person_id: str = ""
    # WHAT HE MAY SEE, which is not where he WORKS. `branch_id` above is his station: it decides
    # where his visits are counted, and it is one place. This decides which branches' numbers,
    # messages and customers he may read, and an owner asks for more than one of those often — a
    # supervisor over the east side, an area manager over four. While both facts lived in
    # `branch_id` the only two settings were «this one branch» and «everything», and «everything»
    # was also what an unassigned new hire got.
    #
    # EMPTY MEANS «HIS OWN», which is the safe default and the common case: he sees where he works.
    # A non-empty list is exactly what the owner granted. The whole establishment is `visible_all`,
    # said out loud rather than inferred from a blank field — an emptiness that means «no limit» is
    # how و-1 happened.
    visible_branch_ids: list[str] = field(default_factory=list)
    visible_all: bool = False
    active: bool = True
    created: int = 0
    # `None` = INHERITS THE SHOP'S OWN WORKING HOURS, IN FULL — the default every operator has
    # until an owner explicitly narrows one. Same shape bookings-service's own tenant-wide
    # WORKING_HOURS row already uses (`{"weekly": {"0".."6": {"closed","start_minute",
    # "end_minute"}}}`), so nearest_slot/free_slots derivation code never has to learn a second
    # schedule shape — only a second SOURCE for the same one. Read by bookings-service over
    # `/internal/operations/staff-hours` (batch by operator id); validated at write time here to
    # never exceed the shop's own hours (bookings intersects defensively too, at read time).
    working_hours: dict[str, Any] | None = None
    # CURRENT SCOPE: the console's operator screens (Visit, Bookings, Services, ...). The owner's
    # own admin screens are Arabic-only for now too, but that is this phase's scope, not a
    # permanent split — do not assume it stays that way. Empty means "no preference set yet",
    # which the console reads as its own default (Arabic) rather than a language code — same
    # "empty means inherit" shape as `working_hours` above. Lives here, not in the browser,
    # because a hired operator has his OWN login (`person_id` above) and moves between devices; a
    # localStorage setting would reset every time he signs in somewhere new.
    locale: str = ""

    def public(self) -> dict[str, Any]:
        """No pin_hash. Not because it is readable, but because a hash that is never returned
        cannot be attacked offline by someone who reached a read endpoint."""
        return {"id": self.id, "tenant": self.tenant, "name": self.name, "role": self.role,
                "branch_id": self.branch_id, "active": self.active, "created": self.created,
                # WHAT HE MAY SEE, BESIDE WHERE HE WORKS. «فريقي» has to show both or the owner
                # cannot tell a branch employee from a supervisor over four, and cannot correct
                # either — a grant that is stored and never shown is a permission nobody can audit.
                "visible_branch_ids": list(self.visible_branch_ids),
                "visible_all": bool(self.visible_all),
                # `None` means "inherits the shop's hours" — said explicitly rather than an absent
                # key, so the console can tell "never customised" from "customised to look
                # identical to the shop's hours" (the owner might do that on purpose, then narrow
                # it later without losing the fact that it IS a customisation).
                "working_hours": self.working_hours,
                # A BOOLEAN, NEVER THE ID. The screen needs to know he can sign in; the identifier
                # itself is identity's and belongs in no response of ours.
                "has_login": bool(self.person_id),
                # ALSO A BOOLEAN, and for the field screen rather than for «فريقي»: the sheet that
                # asks «من يحفظ؟» must not offer a name that cannot answer. An operator with no PIN
                # listed there is a tap that ends in a refusal he has no way to satisfy, with a
                # customer waiting.
                "has_pin": bool(self.pin_hash),
                "locale": self.locale}


@dataclass
class Branch:
    id: str
    tenant: str
    name: str
    active: bool = True
    created: int = 0
    #: WHEN THIS BRANCH WAS LAST CLOSED — 0 while `active` is True. A convenience CACHE of the
    #: current state, not a history: the real open/close TIMELINE (every transition, who did it,
    #: and when) lives in audit-service's own `branch.updated` events, which now carry a real
    #: before/after diff (see app/api/v1/staff.py::update_branch's own note) — this field only
    #: answers "is it closed right now, and since when", the same "cache the current fact,
    #: audit carries the history" split every other status field in this product already follows.
    closed_at: int = 0
    #: Optional, set by the shop's own owner (never inferred) — the admin panel's own map of
    #: where shops actually are reads these, but this service never invents a location for a
    #: branch nobody located. 0.0/0.0 (the Gulf of Guinea) means "not set", not "at the equator".
    lat: float = 0.0
    lng: float = 0.0
    city: str = ""

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "tenant": self.tenant, "name": self.name,
                "active": self.active, "created": self.created, "closed_at": self.closed_at,
                "lat": self.lat, "lng": self.lng, "city": self.city}
