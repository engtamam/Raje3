# =============================================================================
# campaigns — Self-describing service manifest
# -----------------------------------------------------------------------------
# A machine-readable descriptor so a gateway/platform can discover what this
# service is, what it exposes, which ports (adapters) it uses, and which events
# it emits/consumes. Served at GET /internal/manifest. Phase 1: ports/events are
# empty; later phases populate them.
# =============================================================================
from __future__ import annotations

from typing import Any

from app.config import Settings


def _backup() -> dict:
    """This service's backup declaration (app/backup_manifest.py), or an empty one.

    Published in the manifest so the backup fan-out discovers what to capture the same way the DSAR
    fan-out discovers who holds a person — a holder nobody declares is one nobody backs up."""
    try:
        from app.backup_manifest import BACKUP
    except Exception:
        return {"object_prefix": "", "collections": [], "excluded": []}
    return BACKUP


def _admin_actions() -> list[dict[str, Any]]:
    """This service's declared admin actions (docs/contracts/admin-actions.schema.json), or [] if it
    declares none. Opt-in: a service with no app/admin_actions.py simply exposes nothing to the
    panel. The panel is a map — these decide what is SHOWN, never what an operator may DO."""
    try:
        from app.admin_actions import ADMIN_ACTIONS
    except Exception:
        return []
    return list(ADMIN_ACTIONS)


def _user_actions() -> list[dict[str, Any]]:
    """This service's declared end-user (self-service) actions
    (docs/contracts/user-actions.schema.json), or [] if it declares none. Opt-in: aggregated into
    GET /api/v1/app/catalog. The app is a map — these decide what is SHOWN, never what a user may DO."""
    try:
        from app.user_actions import USER_ACTIONS
    except Exception:
        return []
    return list(USER_ACTIONS)


def build_manifest(
    settings: Settings, ports: list[dict[str, str]] | None = None
) -> dict[str, Any]:
    return {
        "name": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "env": settings.ENV,
        # FILL THIS. An empty list is a CLAIM — "this service grants no capabilities" — that an
        # adopter's client app reads as fact and renders nothing from. A blank app is the usual
        # symptom of a service that shipped this untouched. If a service genuinely grants none,
        # leaving it empty is correct; the point is that it must be a decision, not a leftover.
        # Three, split by who is harmed. Reading answers "what did I send?"; managing decides
        # who receives a message under the shop's name; and the caps behind a campaign are ours.
        "capabilities": ["campaigns.read", "campaigns.manage", "platform.campaigns",
                         # WHAT api/v1/operator.py ACTUALLY ENFORCES. Advertised because they are
                         # enforced here — not because we grant them to a tenant: platform.* is
                         # ours, and authz denies the whole prefix to every establishment. The
                         # actions used to name platform.<service> instead, so the console rendered
                         # the credentials buttons for whoever held that and the service answered
                         # 403 to every one of them.
                         "platform.secrets", "platform.config"],  # e.g. ["files.upload", "files.read"] — atomic capability keys
        "endpoints": [
            # From the generated scaffold, and kept: what a client calls to confirm its token is
            # accepted at all, which is the first question asked when something else is failing.
            # Undeclared in every service until a guard compared the manifest with the app itself.
            {"path": "/api/v1/campaigns/admin/ping", "tier": "user", "method": "GET"},
            {"path": "/healthz", "tier": "public", "method": "GET"},
            {"path": "/readyz", "tier": "public", "method": "GET"},
            {"path": "/metrics", "tier": "public", "method": "GET"},
            {"path": "/internal/health", "tier": "internal", "method": "GET"},
            {"path": "/internal/manifest", "tier": "internal", "method": "GET"},
            {"path": "/internal/backup/export", "tier": "internal", "method": "POST"},
            {"path": "/internal/backup/import", "tier": "internal", "method": "POST"},
            {"path": "/internal/backup/verify", "tier": "internal", "method": "POST"},
            # THE HEARTBEAT. Without the cron this service is inert and looks healthy: campaigns
            # exist, every probe passes, and nothing ever fires.
            {"path": "/internal/campaigns/tick", "tier": "internal", "method": "POST"},
            {"path": "/internal/privacy/erase", "tier": "internal", "method": "POST",
             "erasure_category": "subject"},
            {"path": "/api/v1/campaigns/whoami", "tier": "user", "method": "GET"},
            # ── the owner's three screens ─────────────────────────────────────────────────
            {"path": "/api/v1/campaigns/goals", "tier": "user", "method": "GET"},
            {"path": "/api/v1/campaigns/preview", "tier": "user", "method": "POST"},
            {"path": "/api/v1/campaigns", "tier": "user", "method": "POST"},
            {"path": "/api/v1/campaigns", "tier": "user", "method": "GET"},
            {"path": "/api/v1/campaigns/{}/runs", "tier": "user", "method": "GET"},
            {"path": "/api/v1/campaigns/{}/pause", "tier": "user", "method": "POST"},
            # THE APP-STORE CARD'S OWN CONTENT (app/core/features.py) — no `campaigns.*`
            # capability, deliberately: a shop deciding whether to buy this app has to read what
            # it would get.
            {"path": "/api/v1/campaigns/features", "tier": "user", "method": "GET"},
            # OURS. The audience ceiling is not an establishment's to raise: a twenty-thousand
            # recipient burst is a volume signal Meta reads against every number we hold.
            {"path": "/api/v1/campaigns/platform/audience-cap", "tier": "user", "method": "GET"},
            {"path": "/api/v1/campaigns/platform/audience-cap", "tier": "user", "method": "PUT"},
            # The operator surface: policy an operator changes after launch. The credential-
            # management routes that used to sit here (a dead SecretStore nothing ever consumed)
            # were removed — see git history for the incident.
            {"path": "/api/v1/campaigns/operator/config", "tier": "user", "method": "GET"},
            {"path": "/api/v1/campaigns/operator/config", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/campaigns/operator/config/{}", "tier": "user", "method": "DELETE"},
        ],
        "ports": ports or [],  # port -> driver, from the composition root
        # FILL THIS too, or leave it empty deliberately. Same trap as capabilities: an empty
        # `emitted` reads as "this service publishes nothing", so a consumer wiring against it
        # subscribes to nothing and fails silently rather than at boot.
        # Emitted so insights can count what a campaign achieved without this service knowing
        # who counts it. Consumed: nothing — a campaign is started by a person or a clock.
        "events": {"emitted": ["campaigns.run.completed"], "consumed": []},  # e.g. {"emitted": ["wallet.credited"], ...}
        "admin_actions": _admin_actions(),
        "backup": _backup(),
        "user_actions": _user_actions(),
    }
