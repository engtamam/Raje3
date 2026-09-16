"""How many of each service — one small, shared shape validator for every route that accepts a
`quantities: dict[str, int]` body field (`api/v1/field.py`'s `VisitIn`, `api/internal.py`'s
`VisitFromCustomerIn`/`ServiceDurationsIn`). One place for the bound, so the field screen, the
booking->visit gateway, and the booking duration lookup can never quietly drift onto three
different ceilings for the same kind of number.

SAME CEILING `TillLineIn.qty` ALREADY HOLDS (till.py) — a quantity typed by hand or sent by a
device should never reach a catalogue-priced sum, or a slot-duration search, as something absurd
enough to print a fictional total or ask for a fictional block of time.
"""
from __future__ import annotations

MAX_QUANTITY = 100_000


def check_quantities(v: dict[str, int]) -> dict[str, int]:
    for n in v.values():
        if not (0 < n <= MAX_QUANTITY):
            raise ValueError(f"quantities must be positive integers, {MAX_QUANTITY} or fewer")
    return v
