"""What backup-service must capture to restore this service, and what it may skip.

See `services/affiliate-service/app/backup_manifest.py`'s own module doc for the full contract
this file answers to (the `safety:backup-coverage` gate reads it the same way here).
"""
from __future__ import annotations

from typing import Any

BACKUP: dict[str, Any] = {
    "object_prefix": "",        # this service stores no files in the object store
    "collections": [
        {"name": "coworking_resources", "tenant_scoped": True},
        {"name": "coworking_joins", "tenant_scoped": True},
        {"name": "coworking_bookings", "tenant_scoped": True},
        {"name": "coworking_settings", "tenant_scoped": True},
    ],
    "excluded": [
        {"name": "coworking_claims",
         "reason": "the double-booking lock's own advisory lanes (core/lock.py) — each one lives "
                   "for at most CLAIM_TTL_SECONDS and is released the instant its confirm "
                   "finishes; restoring one from a backup would only ever resurrect a stale lock "
                   "nobody is still holding, never a fact worth keeping"},
    ],
}
