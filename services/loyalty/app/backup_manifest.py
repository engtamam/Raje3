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
        # THE LEDGER FIRST, because it is the truth (see core/models.py). A restore that recovered
        # balances and not entries would produce totals nobody can explain and `reconcile` would
        # then "repair" every one of them to zero.
        {"name": "loyalty_entries", "tenant_scoped": True},
        {"name": "loyalty_balances", "tenant_scoped": True},
        # The receipts. They carry the reward's name and cost AS THEY WERE, so losing them loses
        # the only record of what a customer was actually told.
        {"name": "loyalty_redemptions", "tenant_scoped": True},
        {"name": "loyalty_rewards", "tenant_scoped": True},
        # The earning tree and the mode switch. Restoring points without them means every future
        # visit earns the platform default, silently, in a shop that had configured otherwise.
        {"name": "loyalty_settings", "tenant_scoped": True},
    ],
    "excluded": [],
}
