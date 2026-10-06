"""Shapes and collection names — the whole domain in one small file, deliberately.

WHY THIS IS SMALL. Every other domain this fleet books through (bookings' own `Booking`) carries a
`customer_id`, `service_ids`, a `visit_id` and a loyalty-redeem intent that this app has no use for
(spec: the freelancer's own end-customer is INVISIBLE to us — no visit, no customer row, nothing).
Building `ResourceBooking` on top of that model would mean fighting a state machine built for a
different lifecycle just to get two fields (`resource_id`, `freelancer_phone`) it does not have.
This is its own small, independent model instead.

NO MONEY MOVES THROUGH THIS SERVICE (spec §3). `hourly_price_minor` is a stored FACT — what the
shop and the freelancer agreed the rate was, at the moment the booking was made — never a
transaction, never a balance, never anything billing-service or wallet-service is asked about.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

RESOURCES = "coworking_resources"
JOINS = "coworking_joins"
BOOKINGS = "coworking_bookings"
SETTINGS = "coworking_settings"
MEMBERSHIPS = "coworking_memberships"

# ── join-request state machine (spec §6) ────────────────────────────────────────────────────────
JOIN_PENDING = "pending"
JOIN_APPROVED = "approved"
JOIN_BLOCKED = "blocked"

# ── booking status ──────────────────────────────────────────────────────────────────────────────
BOOKING_CONFIRMED = "confirmed"
BOOKING_CANCELLED = "cancelled"

# ── a resource's own rental shape (owner decision, 2026-10-06) ─────────────────────────────────
# "hourly" is every resource this app has ever had — a time-of-day schedule (`weekly`/
# `exceptions`), booked in hours, `hourly_price_minor` the stamped rate. "month"/"year" are new: a
# SEAT MEMBERSHIP, never a specific desk (owner's own explicit call — "ما يهم أي مقعد، نبغى الأمور
# الميدانية عليهم"), gated on the SAME `quantity` capacity below but counted in whole periods, not
# hours, and carrying no time-of-day schedule at all — `core/memberships.py` is the engine for this
# shape; `core/bookings.py`/`core/availability.py` stay exactly what they always were, for "hourly".
RENTAL_HOURLY = "hourly"
RENTAL_MONTH = "month"
RENTAL_YEAR = "year"
RENTAL_PERIODS = (RENTAL_HOURLY, RENTAL_MONTH, RENTAL_YEAR)
# Fixed, derived lengths — NOT a real calendar month/year (no billing ever runs against this, see
# `core/memberships.py`'s own module doc: tracking only, nothing charged). A stable, testable
# number beats a calendar library's own month-length edge cases for a field nobody is billed by.
RENTAL_PERIOD_SECONDS = {RENTAL_MONTH: 30 * 86400, RENTAL_YEAR: 365 * 86400}

# ── membership state machine (owner decision, 2026-10-06) ──────────────────────────────────────
MEMBERSHIP_ACTIVE = "active"
MEMBERSHIP_ENDED = "ended"
# WHY a membership ended — never guessed from `auto_renew` alone after the fact, because the one
# case the owner was explicit about (force-ending mid-period) must stay distinguishable from an
# ordinary lapse forever, for exactly the dispute it exists to prevent.
MEMBERSHIP_END_EXPIRED = "expired"            # renewal was off, the period simply ran out
MEMBERSHIP_END_FORCE_ENDED = "force_ended"    # ended mid-period, with the explicit acknowledgment
                                              # `core/memberships.py::force_end` requires


@dataclass(frozen=True)
class Window:
    """One open stretch on one weekday, in minutes since midnight — the JSON-safe twin of
    `availability.Window`, stored as a plain `[start, end]` pair rather than a dataclass so it
    round-trips through the datastore's own dict-of-JSON-values shape with no custom codec."""
    start_minute: int
    end_minute: int

    def to_list(self) -> list[int]:
        return [self.start_minute, self.end_minute]

    @staticmethod
    def from_list(pair: Any) -> "Window":
        return Window(int(pair[0]), int(pair[1]))


def weekly_to_storage(weekly: dict[int, list[tuple[int, int]]]) -> dict[str, list[list[int]]]:
    """`{0: [(540, 780)]}` -> `{"0": [[540, 780]]}` — dict keys must be strings to survive a JSON
    round-trip through every datastore driver (postgres' own jsonb column included)."""
    return {str(day): [[int(s), int(e)] for s, e in windows] for day, windows in weekly.items()}


def weekly_from_storage(raw: dict[str, Any]) -> dict[int, tuple[tuple[int, int], ...]]:
    return {int(day): tuple((int(w[0]), int(w[1])) for w in windows)
            for day, windows in (raw or {}).items()}


def exceptions_to_storage(exceptions: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for date, exc in (exceptions or {}).items():
        out[date] = {"closed": bool(exc.get("closed", True)),
                    "windows": [[int(w[0]), int(w[1])] for w in exc.get("windows") or []]}
    return out


@dataclass(frozen=True)
class Resource:
    id: str
    tenant: str
    name: str
    active: bool = True
    hourly_price_minor: int = 0
    # Stored exactly like `weekly_to_storage`'s own shape — see availability.py's own `Schedule`
    # for what these become once read back for a real search.
    weekly: dict[str, list[list[int]]] = field(default_factory=dict)
    exceptions: dict[str, dict[str, Any]] = field(default_factory=dict)
    created_at: int = 0
    # "" MEANS UNASSIGNED, A REAL, VISIBLE-TO-EVERYONE STATE (owner decision, 2026-09-27) — the
    # same "a row with no branch is kept for everyone" rule `app/api/scope.py::visible()` already
    # holds fleet-wide, never a resource silently hidden because nobody picked a branch for it yet.
    branch_id: str = ""
    # THE FREELANCER'S OWN "WHAT AM I BOOKING" ANSWER (owner decision, 2026-09-27) — free text, the
    # shop's own words, never validated beyond a length ceiling; empty is a real, common answer for
    # a resource nobody has described yet.
    description: str = ""
    # OPAQUE — see `core/catalogue_image.py`'s own module doc for why this is a KEY, never bytes or
    # a URL. ONE photo per resource, by explicit owner decision — never a gallery.
    image_key: str = ""
    # «hourly» (default — every resource before 2026-10-06 reads this, unchanged behaviour) or
    # «month»/«year» — see RENTAL_PERIODS' own note above.
    rental_period: str = RENTAL_HOURLY
    # HOW MANY CAN HOLD THIS RESOURCE AT ONCE — the capacity this whole feature exists for. 1 is
    # the OLD behaviour exactly (one booking excludes every other), so every resource created
    # before this field existed reads as 1 and nothing about it changes. For «hourly» this counts
    # overlapping CONFIRMED bookings; for «month»/«year» it counts ACTIVE memberships.
    quantity: int = 1
    # ONLY MEANINGFUL FOR month/year — a stamped-at-join-time rate, same "historical fact, never
    # silently changes under an existing member" discipline `hourly_price_minor` already holds for
    # a booking. 0 and unused for «hourly» resources.
    period_price_minor: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "tenant": self.tenant, "name": self.name, "active": self.active,
            "hourly_price_minor": self.hourly_price_minor, "weekly": self.weekly,
            "exceptions": self.exceptions, "created_at": self.created_at,
            "branch_id": self.branch_id, "description": self.description,
            "image_key": self.image_key, "rental_period": self.rental_period,
            "quantity": self.quantity, "period_price_minor": self.period_price_minor,
        }

    def public(self) -> dict[str, Any]:
        """The same shape `to_dict()` gives an owner, minus the one internal reference nobody
        outside this service should ever read directly — see `core/catalogue_image.py`'s own
        module doc on why `image_key` itself never leaves this process."""
        row = self.to_dict()
        row.pop("image_key", None)
        row["has_image"] = bool(self.image_key)
        return row

    @staticmethod
    def from_dict(row: dict[str, Any]) -> "Resource":
        return Resource(
            id=row["id"], tenant=row["tenant"], name=row.get("name", ""),
            active=bool(row.get("active", True)),
            hourly_price_minor=int(row.get("hourly_price_minor") or 0),
            weekly=row.get("weekly") or {}, exceptions=row.get("exceptions") or {},
            created_at=int(row.get("created_at") or 0),
            branch_id=str(row.get("branch_id") or ""),
            description=str(row.get("description") or ""),
            image_key=str(row.get("image_key") or ""),
            # ABSENT ON ANY ROW WRITTEN BEFORE THIS FIELD EXISTED -> "hourly"/1/0, which is
            # byte-for-byte the behaviour that row already had. Never a migration to run.
            rental_period=str(row.get("rental_period") or RENTAL_HOURLY),
            quantity=int(row.get("quantity") or 1),
            period_price_minor=int(row.get("period_price_minor") or 0),
        )


@dataclass(frozen=True)
class Membership:
    """One freelancer's seat membership on one «month»/«year» resource — `core/memberships.py`'s
    own record. NEVER A SPECIFIC DESK (owner's own explicit call) — this row is proof of a slot
    held against `resource.quantity`, nothing about WHICH physical seat."""
    id: str
    tenant: str
    resource_id: str
    freelancer_phone: str
    started_at: int
    period_end: int
    auto_renew: bool
    status: str                 # MEMBERSHIP_ACTIVE | MEMBERSHIP_ENDED
    period_price_minor: int     # stamped at join — see Resource.period_price_minor's own doc
    created_at: int
    ended_at: int = 0
    end_reason: str = ""        # "" while active; MEMBERSHIP_END_EXPIRED | _FORCE_ENDED once ended
    # THE RECORD THE OWNER ASKED FOR — set ONLY by `force_end`, never implied by anything else, so
    # "this membership ended" can never be read as "both sides agreed to end it early" by accident.
    force_ack_by: str = ""      # the actor (phone, or an operator's own subject) who acknowledged
    force_ack_note: str = ""    # free text — what was actually agreed, for the record

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "tenant": self.tenant, "resource_id": self.resource_id,
            "freelancer_phone": self.freelancer_phone, "started_at": self.started_at,
            "period_end": self.period_end, "auto_renew": self.auto_renew,
            "status": self.status, "period_price_minor": self.period_price_minor,
            "created_at": self.created_at, "ended_at": self.ended_at,
            "end_reason": self.end_reason, "force_ack_by": self.force_ack_by,
            "force_ack_note": self.force_ack_note,
        }

    @staticmethod
    def from_dict(row: dict[str, Any]) -> "Membership":
        return Membership(
            id=row["id"], tenant=row["tenant"], resource_id=row["resource_id"],
            freelancer_phone=row.get("freelancer_phone", ""),
            started_at=int(row.get("started_at") or 0),
            period_end=int(row.get("period_end") or 0),
            auto_renew=bool(row.get("auto_renew", True)),
            status=row.get("status", MEMBERSHIP_ACTIVE),
            period_price_minor=int(row.get("period_price_minor") or 0),
            created_at=int(row.get("created_at") or 0),
            ended_at=int(row.get("ended_at") or 0),
            end_reason=str(row.get("end_reason") or ""),
            force_ack_by=str(row.get("force_ack_by") or ""),
            force_ack_note=str(row.get("force_ack_note") or ""),
        )
