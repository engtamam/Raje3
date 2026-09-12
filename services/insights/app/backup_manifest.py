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
        # FIXED 2026-09-12, a real gap a QA audit found: three collections the service actually
        # writes (app/api/v1/insights.py, app/core/rollup.py, app/core/runtime_config.py) were
        # declared nowhere — neither backed up nor excluded, the exact silent hole this file's own
        # docstring says must never exist.
        #
        # "Next step" suggestion state per tenant — losing it resets which suggestions an owner has
        # already dismissed, and nothing else records that.
        {"name": "insight_next_step_state", "tenant_scoped": True},
        # An operator's runtime policy overrides. NOT tenant_scoped, even though most rows carry a
        # real tenant: a platform-wide override lives in the SAME collection under tenant="" (see
        # core/runtime_config.py's own `set()`), and a per-tenant restore that only pulled one
        # tenant's rows would miss every platform-wide row that tenant's own resolution falls back
        # to — the same reasoning portal's identical runtime_config collection is declared under.
        {"name": "runtime_config", "tenant_scoped": False},
    ],
    "excluded": [
        # A single cross-tenant row, fully recomputed by the scheduled rollup (core/rollup.py) from
        # each tenant's own already-backed-up snapshot — losing it costs one rollup cycle, not data.
        {"name": "insight_platform_summary",
         "reason": "recomputed nightly from insight_snapshots; not a source of truth"},
    ],
}
