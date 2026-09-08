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
    ],
    "excluded": [
        # NOT BACKED UP, AND THIS IS THE ONE ENTRY THAT NEEDED AN ARGUMENT RATHER THAN A HABIT.
        #
        # A backup is a SECOND COPY, and the whole privacy design of this store is that no copy of
        # it survives ten days. An archive would be exactly the copy the retention window exists to
        # prevent: it would outlive the reap, it would outlive an erasure (which cannot reach an
        # archive at all), and it would sit in an object store holding whatever a stack trace
        # happened to print. Backing this up would quietly convert a ten-day store into a
        # permanent one.
        #
        # AND NOTHING IS LOST BY SKIPPING IT. Restoring last week's errors serves nobody: an
        # incident is diagnosed while it is happening, and a signal older than the outage it
        # describes is not evidence, it is noise. This is the only collection on the product whose
        # correct disaster-recovery behaviour is to come back EMPTY.
        {"name": "signals", "reason": "a ten-day diagnostic buffer, deliberately not persisted. "
                                      "An archive would outlive both the retention purge and any "
                                      "erasure, turning a bounded store into a permanent copy of "
                                      "whatever a stack trace printed — and a restored error from "
                                      "last week diagnoses nothing"},
    ],
}
