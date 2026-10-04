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
        # THE CAMPAIGN CONFIGURATION ITSELF (core/campaigns.py, `CAMPAIGNS` constant imported from
        # core/models.py) — found live (2026-09-28), a 13-service audit: this manifest had never
        # declared a single real collection, only a commented-out placeholder. Losing this on
        # restore loses every shop's own referral-program setup (mode, reward shape, eligibility)
        # with nothing anywhere saying so.
        {"name": "referral_campaigns", "tenant_scoped": True},
        # THE PHONE<->CODE INDEX (core/referral_code.py) — GLOBAL, not tenant-scoped: a row is
        # `{"phone": ..., "code": ...}` with no `tenant` field at all (a referral code identifies a
        # PERSON across the whole platform, never one shop's own namespace — see that module's own
        # `.claim()`-based reservation for why two shops can never race the same phone or code).
        {"name": "referral_codes_by_phone", "tenant_scoped": False},
        {"name": "referral_phones_by_code", "tenant_scoped": False},
        # THE OPERATOR SURFACE (core/secret_store.py/core/runtime_config.py, pasted verbatim into
        # every service) — same gap, same fix as every sibling service.
        {"name": "operator_secrets", "tenant_scoped": False},
        {"name": "runtime_config", "tenant_scoped": False},
    ],
    "excluded": [
    ],
}
