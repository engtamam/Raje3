"""Re-apply the shipped sector seed onto sector rows that already exist.

WHY THIS IS NOT `seed_from_file`. That one applies ONLY when the table is empty, and it is right
to: re-applying on every boot would silently undo an operator's edits from the platform console —
the console appears to work and the change is gone by morning.

But a field ADDED to the seed after the table was populated has no other way in. The rewards table
(§10.8) is exactly that case: four sectors were seeded months before rewards existed, so every shop
opened since has been told its rewards "arrive filled for your sector" by a row that has none.

SO IT MERGES ONE KEY AND TOUCHES NOTHING ELSE. Names, services, fields and the active flag are
whatever the console last said. Only `rewards` is written, and only where the row has none — an
operator who has already curated a sector's rewards keeps them.

PIPED INTO THE POD RATHER THAN BAKED INTO THE IMAGE. It runs once per schema addition and is not
part of the service; shipping it would put a maintenance script inside every running container for
ever. The datastore and the seed file are both in there, so it goes to them:

    kubectl -n base-services exec -i deploy/operations -- python - < deploy/seed/refresh-sectors.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, "/app")

from app.container import build_container            # noqa: E402
from app.config import get_settings                  # noqa: E402
from app.core.sectors import PLATFORM, SECTORS       # noqa: E402


async def main() -> int:
    settings = get_settings()
    # NOT AWAITED — `build_container` is synchronous. Assuming otherwise cost one run
    # and a stack trace that named the wrong thing.
    container = build_container(settings)
    store = container.datastore

    path = settings.SECTORS_SEED_FILE or "/app/data/sectors.seed.json"
    if not os.path.isfile(path):
        print(f"no seed file at {path}")
        return 1
    seed = json.loads(open(path, encoding="utf-8").read())

    touched = 0
    for entry in seed.get("sectors", []):
        key = entry.get("key")
        rewards = entry.get("rewards") or []
        if not key or not rewards:
            continue
        row = await store.get(SECTORS, f"{PLATFORM}|{key}")
        if not row:
            print(f"{key}: no row — a sector the console has never seen; skipped")
            continue
        if row.get("rewards"):
            print(f"{key}: already has {len(row['rewards'])} rewards — left alone")
            continue
        row["rewards"] = rewards
        await store.put(SECTORS, f"{PLATFORM}|{key}", row)
        print(f"{key}: {len(rewards)} rewards written")
        touched += 1

    print(f"done — {touched} sector(s) updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
