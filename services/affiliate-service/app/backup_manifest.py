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
    "object_prefix": "",        # set if this service stores files in the object store
    "collections": [
        # NOT tenant-scoped: every row here lives under the ONE shared affiliate tenant (spec
        # §1/§12) — there is no per-tenant restore to isolate.
        {"name": "affiliate_applications", "tenant_scoped": False},
        {"name": "affiliates", "tenant_scoped": False},
        {"name": "affiliate_referrals", "tenant_scoped": False},
        {"name": "affiliate_commissions", "tenant_scoped": False},
        {"name": "affiliate_withdrawals", "tenant_scoped": False},
        {"name": "affiliate_wafa_requests", "tenant_scoped": False},
        {"name": "affiliate_employment_requests", "tenant_scoped": False},
        {"name": "affiliate_leads", "tenant_scoped": False},
        {"name": "affiliate_lead_search_jobs", "tenant_scoped": False},
    ],
    "excluded": [
        {"name": "affiliate_pending_secret",
         "reason": "an applicant's chosen password, held ONLY between apply() and the admin's "
                   "approve()/reject() — deleted the moment it is spent either way (see "
                   "core/onboarding.py). Restoring a backup would resurrect a plaintext "
                   "credential nothing should still hold; a genuinely pending applicant simply "
                   "re-applies."},
    ],
}
