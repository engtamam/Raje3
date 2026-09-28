"""What backup-service must capture to restore this service, and what it may skip.

A pure declaration, read as a literal — like admin_actions and auditable_actions. The
`safety:backup-coverage` gate checks this against the collections the code actually writes, so a
collection added later without a line here fails the build rather than being silently missing the
day a restore is needed.

FILL THIS as the generated service grows a datastore. Every collection the code writes must appear
either in `collections` (backed up) or `excluded` (skipped, with a reason a person can challenge).
There is no third state — the third state is a silent hole, which is the one thing a backup system
must never have. A brand-new service that writes nothing yet declares nothing yet, and that is
correct; the gate reports it as "not onboarded" rather than failing.

`tenant_scoped` on each collection tells a restore whether it may be restored for one tenant in
isolation, or only whole. Get it wrong toward False and a per-tenant restore refuses; wrong toward
True and it may restore rows that were never tenant-partitioned.
"""
from __future__ import annotations

from typing import Any

BACKUP: dict[str, Any] = {
    "object_prefix": "",        # this service stores no files in the object store
    "collections": [
        {"name": "bookings", "tenant_scoped": True},
        # DERIVED FROM `bookings` BY `save()`, BUT BACKED UP ANYWAY: `import_archive` writes rows
        # straight to the datastore under each collection's own key template — it never calls
        # `BookingStore.save()` — so excluding this index on the assumption a restore of
        # `bookings` alone regenerates it would be exactly the "note explaining a defect mistaken
        # for a fix" family. Backed up as its own collection instead: correct, and no restore-time
        # re-derivation step to keep honest.
        {"name": "booking_slots", "tenant_scoped": True,
         "key": "{tenant}|{branch_id}|{bucket}|{booking_id}"},
        # THE OPERATOR SURFACE (core/runtime_config.py, pasted verbatim into every service) —
        # found live (2026-09-28), a 13-service audit: never declared here at all. Mixes a
        # platform-wide row (tenant "") and per-tenant overrides in the SAME collection — the
        # same reasoning portal's own identical entry is declared under — so `tenant_scoped:
        # False`, whole-collection restore only.
        {"name": "runtime_config", "tenant_scoped": False},
    ],
    "excluded": [
        {"name": "booking_claims", "reason": "sub-15-second lock lanes, never worth a day-old "
                                             "backup — TTL clears any left over on its own"},
    ],
}
