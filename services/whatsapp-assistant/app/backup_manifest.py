"""What backup-service must capture to restore this service, and what it may skip.

A pure declaration, read as a literal — like admin_actions and auditable_actions. The
`safety:backup-coverage` gate checks this against the collections the code actually writes, so a
collection added later without a line here fails the build rather than being silently missing the
day a restore is needed. See services/loyalty/app/backup_manifest.py for the full convention this
mirrors, and app/core/backup.py (a verbatim copy of loyalty's — the seal/export/import/verify
logic is generic, this file is the only service-specific part).

Every collection app/core/models.py declares AND the code actually writes to (grep the datastore
calls, not just the constant) must appear either in `collections` (backed up) or `excluded`
(skipped, with a reason). `wa_cost_ledger` is deliberately absent from both: it is declared in
models.py for a future per-conversation cost ledger, but nothing in this service writes to it yet
(token counts currently live on the conversation row itself) — the backup-coverage gate only
reasons about writes, so an unwritten collection needs no entry.
"""
from __future__ import annotations

from typing import Any

BACKUP: dict[str, Any] = {
    "object_prefix": "",
    "collections": [
        # The wamid-keyed inbound dedup store. Losing it does not lose a conversation, but a
        # restore without it re-processes every message inside the platform's non-durable bus
        # retry window as if it were new — the exact double-reply this store exists to prevent.
        {"name": "wa_inbound_messages", "tenant_scoped": True},
        # The conversation state machine itself — summary, raw window, debounce/session timers,
        # the pending proposal id. This IS the product's memory of a customer; restoring without
        # it means every open conversation resets to a stranger the next message it answers.
        {"name": "wa_conversations", "tenant_scoped": True},
        # A model's tool call, server-validated, awaiting the button press that fires it. A
        # restore without this loses nothing irreversible (a stale proposal simply expires), but
        # dropping it silently would make a customer's still-live "confirm" button 404.
        {"name": "wa_pending_proposals", "tenant_scoped": True},
        # Confirmed bookings — the one write in this service with real business consequence.
        {"name": "wa_bookings", "tenant_scoped": True},
        {"name": "renewal_requests", "tenant_scoped": True},
        {"name": "wa_upsell_ledger", "tenant_scoped": True},
        {"name": "wa_pricing_pending", "tenant_scoped": False},
        {"name": "wa_coexistence_watermarks", "tenant_scoped": False},
        {"name": "wa_inbound_watermarks", "tenant_scoped": False},
        {"name": "operator_secrets", "tenant_scoped": False},
        {"name": "runtime_config", "tenant_scoped": False},
    ],
    "excluded": [
        {"name": "wa_owner_active", "reason": "a 30-minute human-reply cooldown "
                                              "(COEXISTENCE_HUMAN_COOLDOWN_SECONDS); any archived "
                                              "row has already expired"},
    ],
}
