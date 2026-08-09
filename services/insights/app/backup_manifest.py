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
        # THE DERIVED SEQUENCES ARE THE ONLY ROWS HERE THAT DESCRIBE A PERSON, and they are backed
        # up because losing them means the association engine restarts its learning from zero for
        # every shop on the product at once.
        {"name": "insight_sequences", "tenant_scoped": True},
        # Snapshots and pairs are recomputable from the peers within a day — but a restore that
        # brought back neither would leave every dashboard saying "أحسب الآن" until the next tick,
        # which is a recovery that looks like an outage.
        {"name": "insight_snapshots", "tenant_scoped": True},
        {"name": "insight_pairs", "tenant_scoped": True},
        # Who asked for the weekly report. Small, and impossible to reconstruct: nothing else
        # records that a manager subscribed.
        {"name": "insight_digest_subs", "tenant_scoped": True},
    ],
    "excluded": [],
}
