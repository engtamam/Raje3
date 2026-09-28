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
        # NO `id` FIELD — `Balance` is keyed by `key` (`f"{tenant}|{subject_ref}"`, see its own
        # `.key` property and `to_dict()`), never by an `id`. Found live (2026-09-28): with no
        # `key` template here, `import_archive`'s default `"{id}"` raised `KeyError('id')` on the
        # very first balance row, aborting the WHOLE restore — every customer's points balance was
        # silently unrestorable from any backup taken before this fix.
        {"name": "loyalty_balances", "tenant_scoped": True, "key": "{key}"},
        # The receipts. They carry the reward's name and cost AS THEY WERE, so losing them loses
        # the only record of what a customer was actually told.
        {"name": "loyalty_redemptions", "tenant_scoped": True},
        {"name": "loyalty_rewards", "tenant_scoped": True},
        # The earning tree and the mode switch. Restoring points without them means every future
        # visit earns the platform default, silently, in a shop that had configured otherwise.
        {"name": "loyalty_settings", "tenant_scoped": True},
        # The catch-up cursor (ج-2). Not data loss, but a restore without it re-reads every
        # visit an establishment ever had — bounded, and slow enough to miss its window.
        {"name": "loyalty_watermarks", "tenant_scoped": True},
        # THE OPERATOR SURFACE (core/runtime_config.py, pasted verbatim into every service) —
        # found live (2026-09-28), a 13-service audit: never declared here at all. Mixes a
        # platform-wide row and per-tenant overrides in the SAME collection — the same reasoning
        # portal's own identical entry is declared under — so `tenant_scoped: False`,
        # whole-collection restore only.
        {"name": "runtime_config", "tenant_scoped": False},
    ],
    "excluded": [],
}
