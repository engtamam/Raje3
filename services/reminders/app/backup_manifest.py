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
        # THE CONSENT HISTORY, and losing it is worse than losing a schedule. A restore without it
        # leaves every customer reading `never_asked`, so no marketing goes out at all — which is
        # the safe direction and still a shop silently unable to reach anybody who had agreed. And
        # it is the record we would be asked to produce, so a gap in it is a gap in the evidence.
        {"name": "marketing_consent", "tenant_scoped": True},
        {"name": "engagement", "tenant_scoped": True},
        # The owner's own configuration. Losing it silently reverts every service to the platform
        # default — messages keep going out, at the wrong intervals, and nothing says why.
        {"name": "reminder_settings", "tenant_scoped": True},
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
        # ── DECLARED AFTER ج-2 ──────────────────────────────────────────────────────────────
        # THE CRUELLEST ONE TO LOSE. A shop's own texts, some of them approved by Meta under a
        # name. Restore without these rows and the same name goes back to Meta carrying different
        # content — which Meta refuses for good, and the name is gone for that establishment.
        {"name": "custom_templates", "tenant_scoped": True},
        # The «ساعدوني» queue: a shop asked us to write it a text and is waiting.
        {"name": "template_help", "tenant_scoped": True},
        # The catch-up cursor for this service's own consumers, and the reasons an owner chose
        # from — both cheap and both confusing to lose.
        {"name": "reminders_watermarks", "tenant_scoped": True},
        {"name": "reason_choices", "tenant_scoped": True},
    ],
    # Nothing excluded. An exclusion is a judgement call, and the fewer of those a backup manifest
    # carries the better.
    "excluded": [
        # ALREADY-TOLD MARKERS, and both are about a moment that has passed.
        # `ceiling_notice` remembers that we told an owner his ceiling was reached; restoring it
        # would suppress the notice for a ceiling he is hitting NOW.
        {"name": "ceiling_notice", "reason": "a marker that we already told this owner; restoring "
                                             "it suppresses a notice about a live ceiling"},
        # `reached_24h` is the WhatsApp service-window clock — a 24-hour fact. Anything old enough
        # to be in an archive has expired, and a restored row would claim a window that is closed.
        {"name": "reached_24h", "reason": "a 24-hour service window; every archived row has "
                                          "already expired and would claim a window that is shut"},
    ],
}
