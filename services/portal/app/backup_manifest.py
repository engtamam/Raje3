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
    # No files. This service holds no blobs of its own; images and assets live elsewhere.
    "object_prefix": "",
    # This service is not the pure renderer its own comment used to claim — it writes exactly one
    # collection, runtime_config (app/core/runtime_config.py), the operator-editable overrides
    # behind the settings panel. A restore that skips it silently reverts every tenant's tuned
    # knob back to the compiled default, with nothing on screen saying so. fixed 2026-09-12, a
    # real gap a QA audit found: this manifest declared zero collections while the service was
    # actively writing one.
    #
    # Declared whole rather than per-tenant: a row's tenant field is "" for a platform-wide
    # override and a real tenant id for a tenant override, in the SAME collection. A per-tenant
    # restore that only pulled rows for one tenant would miss the platform-wide rows a tenant's
    # resolution falls back to, and could bring back a platform override an operator deliberately
    # cleared — the same reasoning reminders' own "limits" collection is declared under.
    "collections": [
        {"name": "runtime_config", "tenant_scoped": False},
    ],
    "excluded": [],
}
