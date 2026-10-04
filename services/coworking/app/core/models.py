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

# ── join-request state machine (spec §6) ────────────────────────────────────────────────────────
JOIN_PENDING = "pending"
JOIN_APPROVED = "approved"
JOIN_BLOCKED = "blocked"

# ── booking status ──────────────────────────────────────────────────────────────────────────────
BOOKING_CONFIRMED = "confirmed"
BOOKING_CANCELLED = "cancelled"


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "tenant": self.tenant, "name": self.name, "active": self.active,
            "hourly_price_minor": self.hourly_price_minor, "weekly": self.weekly,
            "exceptions": self.exceptions, "created_at": self.created_at,
            "branch_id": self.branch_id, "description": self.description,
            "image_key": self.image_key,
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
        )
