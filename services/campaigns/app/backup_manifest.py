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
    "object_prefix": "",
    "collections": [
        {"name": "campaigns", "tenant_scoped": True},
        # THE RUNS, and they are not optional. They are the owner's answer to "why didn't my
        # customer get this?" — the only question this product generates — and losing them loses
        # every reason we recorded.
        {"name": "campaign_runs", "tenant_scoped": True},
        # WHO EACH CAMPAIGN ALREADY REACHED. Restoring without it makes every standing campaign
        # re-send to everyone it has ever reached, on the day of the recovery.
        {"name": "campaign_reached", "tenant_scoped": True},
        # Platform-scoped: one row per establishment under the reserved tenant. A per-tenant
        # restore must not be able to raise its own ceiling.
        {"name": "audience_caps", "tenant_scoped": False},
    ],
    "excluded": [],
}
