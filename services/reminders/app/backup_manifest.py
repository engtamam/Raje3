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
    # No files. This service holds decisions and their evidence; it stores no blobs.
    "object_prefix": "",
    # ALL tenant-scoped, which is what makes a single-establishment restore possible. Restoring
    # the whole service to recover one shop would be a second outage caused by the recovery.
    "collections": [
        {"name": "schedules", "tenant_scoped": True},
        {"name": "rules", "tenant_scoped": True},
        # THE ONE PEOPLE WOULD BE TEMPTED TO SKIP, and the one that must not be. Every cap in
        # spec 8.4.2 is counted against this ledger. Restore without it and the caps reset to
        # zero: every customer becomes eligible for four fresh marketing messages on the day of
        # the recovery, which is how a restore turns into a wave of complaints.
        {"name": "send_log", "tenant_scoped": True},
        # The customer's own instruction about what may be sent to them. Losing it silently
        # re-enables what they switched off — the one data loss here we could not defend.
        {"name": "prefs", "tenant_scoped": True},
        {"name": "engagement", "tenant_scoped": True},
        # Platform-scoped, not tenant-scoped: one row per establishment under a reserved tenant,
        # plus the global default. A per-tenant restore must not bring back an override that was
        # deliberately removed, which is why this is declared whole rather than scoped.
        {"name": "limits", "tenant_scoped": False},
        # The catch-up cursor. Losing it is not data loss but it is an outage: the next tick would
        # re-read every visit an establishment ever had, which is bounded but slow enough to miss
        # its window on a large tenant.
        {"name": "watermarks", "tenant_scoped": True},
        # The tenant cache — catalogue, templates and profile, all copies of another service's
        # truth. EXCLUDED would be defensible; included because it is small and a cold cache after
        # a restore means the first tick renders every message with an empty establishment name.
        {"name": "tenant_cache", "tenant_scoped": True},
    ],
    # Nothing excluded. An exclusion is a judgement call, and the fewer of those a backup manifest
    # carries the better.
    "excluded": [],
}
