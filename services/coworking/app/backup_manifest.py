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
        {"name": "coworking_memberships", "tenant_scoped": True},
        {"name": "coworking_settings", "tenant_scoped": True},
        # THE OPERATOR SURFACE (core/secret_store.py/core/runtime_config.py, pasted verbatim into
        # every service) — found live (2026-09-28), a 13-service audit: neither was declared here
        # at all. Both mix a platform-wide row and per-tenant overrides in the SAME collection —
        # the same reasoning portal's own `runtime_config` entry is declared under — so
        # `tenant_scoped: False`, whole-collection restore only.
        {"name": "operator_secrets", "tenant_scoped": False},
        {"name": "runtime_config", "tenant_scoped": False},
    ],
    "excluded": [
        {"name": "coworking_claims",
         "reason": "the double-booking lock's own advisory lanes (core/lock.py) — each one lives "
                   "for at most CLAIM_TTL_SECONDS and is released the instant its confirm "
                   "finishes; restoring one from a backup would only ever resurrect a stale lock "
                   "nobody is still holding, never a fact worth keeping"},
    ],
}
