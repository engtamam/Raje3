"""Whether this shop works on cars — the one fact the plate page and the meter depend on.

WHAT THIS REPLACES. The product used to open sign-up with «نوع النشاط» and a list of trades, and
that answer decided four separate things: the service catalogue we seeded, the starting rewards we
seeded, whether «تسجيل زيارة» shows a plate page, and whether a meter is asked for. One question,
four consequences, none of them visible to the person answering it — and a shop that did tyres AND
detailing got a catalogue that was wrong on its first day.

Three of those four are gone: a shop now starts empty and its owner writes what he actually sells,
because a guess about a business we have never seen is worse than a blank page he fills in once.
What remains is the only part that was ever a real question, and it is asked as one:

    هل يتم العمل على السيارات؟

A checkbox on his own establishment. He can change it the day he starts doing cars, which the old
question could not — a trade was chosen once at sign-up and never again.

ABSENT MEANS NO, AND THE DEFAULT IS NOT WRITTEN. A row that exists only because somebody registered
records a decision nobody made. The first write is the first real choice, exactly as with
`shop_mode`.

AND IT FAILS TOWARD «NO». If we cannot read the row we do not know whether this shop does cars, and
the two mistakes are not equal: showing a plate page to a salon is a screen nobody can get past,
while omitting it from a tyre shop loses one optional field on a visit that still records.
"""
from __future__ import annotations

import time
from typing import Any

VEHICLES = "shop_vehicles"

#: The extra inputs «تسجيل زيارة» renders for a shop that works on cars. Names, not a boolean, so
#: the screen asks «is `plate` among my fields» rather than carrying its own idea of what a vehicle
#: shop needs — the same contract the sector fields used, minus the trade.
PLATE = "plate"
METER = "meter"
VEHICLE_FIELDS = (PLATE, METER)


class VehicleStore:
    """One row per establishment. Absent means «no cars», which is most shops."""

    def __init__(self, store: Any) -> None:
        self._s = store

    async def tracks_vehicle(self, tenant: str) -> bool:
        if not tenant:
            return False
        try:
            row = await self._s.get(VEHICLES, tenant)
        except Exception:                                                    # noqa: BLE001
            # UNREADABLE IS «NO», and it is written down rather than left to a bare `except` that
            # returns None somewhere upstream: see the module docstring for why the two mistakes
            # are not symmetric.
            return False
        return bool((row or {}).get("tracks_vehicle"))

    async def set(self, tenant: str, tracks: bool) -> dict[str, Any]:
        """Say it, either way. Turning it OFF is a real answer and is stored as one — a shop that
        stopped doing cars must not be left reading the absent row as «never asked»."""
        row = {"tenant": tenant, "tracks_vehicle": bool(tracks), "chosen_at": int(time.time())}
        await self._s.put(VEHICLES, tenant, row)
        return row


async def fields_for(store: Any, tenant: str) -> list[dict[str, str]]:
    """What «تسجيل زيارة» renders beyond the service itself.

    THE SCREEN ASKS FOR NAMES, NOT A FLAG. `Visit.tsx` decides on «is `plate` in my fields», which
    is what lets this answer change without a console release — and what stopped the console from
    carrying its own copy of which trades have plates.
    """
    if not await VehicleStore(store).tracks_vehicle(tenant):
        return []
    return [{"name": PLATE, "label": "رقم اللوحة"}, {"name": METER, "label": "العدّاد"}]
