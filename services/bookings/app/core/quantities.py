"""How many of each service — the same small shape validator `operations` carries under the
identical name (`services/operations/app/core/quantities.py`), duplicated rather than imported:
these are independent services with independent deploys (see `pdf_convert.py`'s own header in
operations for this repo's established convention — one small file per service, not a shared
package across a service boundary).
"""
from __future__ import annotations

MAX_QUANTITY = 100_000


def check_quantities(v: dict[str, int]) -> dict[str, int]:
    for n in v.values():
        if not (0 < n <= MAX_QUANTITY):
            raise ValueError(f"quantities must be positive integers, {MAX_QUANTITY} or fewer")
    return v
