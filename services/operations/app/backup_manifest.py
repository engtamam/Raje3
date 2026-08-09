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
    # No files. operations records what happened; it stores no blobs.
    "object_prefix": "",
    # Every one of these is tenant-scoped, and that matters for a restore: an establishment that
    # loses its data can be restored ALONE, without touching anyone else's rows. A whole-service
    # restore to recover one tenant would be a second outage caused by the recovery.
    "collections": [
        {"name": "customers", "tenant_scoped": True},
        {"name": "assets", "tenant_scoped": True},
        {"name": "services", "tenant_scoped": True},
        {"name": "visits", "tenant_scoped": True},
        {"name": "operators", "tenant_scoped": True},
        {"name": "branches", "tenant_scoped": True},
        # WHO BROUGHT EACH SHOP. Losing this loses the commission history, and there is no way to
        # reconstruct it: the stamp is the only record that a partner ever introduced a customer.
        {"name": "partner_stamps", "tenant_scoped": True},
    ],
    # Nothing is excluded. The idempotency key lives ON the visit row rather than in a side table,
    # precisely so there is no collection anyone has to argue about — an excluded collection is a
    # judgement call, and the fewer of those a backup manifest carries the better.
    "excluded": [
        # The partner REGISTRY is platform-scoped, not tenant-scoped, and it holds hashed bearer
        # credentials. It is excluded from the per-tenant archive deliberately: a tenant restore
        # must never be able to write into it, and a tenant export must never carry it.
        {"name": "partners", "why": "platform-scoped credential registry; backed up with the "
                                    "platform, never inside a tenant archive"},
    ],
}
