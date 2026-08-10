# =============================================================================
# portal — Self-describing service manifest
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
        # NONE, AND THAT IS THE DECISION. Every route here is public by design: the page is opened
        # from a link in a WhatsApp message by a customer who has no account and never will. A
        # capability would imply a login this product deliberately does not have (spec 8.6.1).
        #
        # Left empty explicitly rather than left untouched — an empty list a reviewer can see was
        # decided is worth more than one they have to guess about.
        "capabilities": [
                         # WHAT api/v1/operator.py ACTUALLY ENFORCES. Advertised because they are
                         # enforced here — not because we grant them to a tenant: platform.* is
                         # ours, and authz denies the whole prefix to every establishment. The
                         # actions used to name platform.<service> instead, so the console rendered
                         # the credentials buttons for whoever held that and the service answered
                         # 403 to every one of them.
                         "platform.secrets", "platform.config"],  # e.g. ["files.upload", "files.read"] — atomic capability keys
        "endpoints": [
            # ── the operator surface: credentials and policy, changed after launch ────────
            # UNDECLARED UNTIL A GUARD COMPARED THE MANIFEST WITH THE APP. The route table this
            # feeds is where a reviewer looks for the highest-privilege surface a service has, and
            # secrets management was missing from it — not hidden, absent, which reads the same to
            # anyone consulting the table.
            {"path": "/api/v1/operator/secrets", "tier": "user", "method": "GET"},
            {"path": "/api/v1/operator/secrets", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/operator/secrets/{}", "tier": "user", "method": "DELETE"},
            {"path": "/api/v1/operator/config", "tier": "user", "method": "GET"},
            {"path": "/api/v1/operator/config", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/operator/config/{}", "tier": "user", "method": "DELETE"},
            # What a client calls to learn who it is talking as. Declared rather than deleted: a
            # route table that omits it describes a service that answers a question it does not.
            {"path": "/api/v1/whoami", "tier": "user", "method": "GET"},
            # From the generated scaffold, and kept: what a client calls to confirm its token is
            # accepted at all, which is the first question asked when something else is failing.
            # Undeclared in every service until a guard compared the manifest with the app itself.
            {"path": "/api/v1/admin/ping", "tier": "user", "method": "GET"},
            {"path": "/healthz", "tier": "public", "method": "GET"},
            {"path": "/readyz", "tier": "public", "method": "GET"},
            {"path": "/metrics", "tier": "public", "method": "GET"},
            {"path": "/internal/health", "tier": "internal", "method": "GET"},
            {"path": "/internal/manifest", "tier": "internal", "method": "GET"},
            {"path": "/internal/privacy/erase", "tier": "internal", "method": "POST",
             # Declared even though this service holds nothing. "Holds nothing" and "was never
             # asked" look identical from outside, and only one of them is a decision.
             "erasure_category": "presentation"},
            # ── the page, and the only routes a customer ever reaches ──────────────────────
            # PUBLIC. No token, no capability, no session — the link lands in a chat that gets
            # forwarded, and whoever opens it must learn nothing about whose it is.
            {"path": "/p/{}", "tier": "public", "method": "GET"},
            {"path": "/p/{}/prefs", "tier": "public", "method": "POST"},
            {"path": "/p/{}/stop", "tier": "public", "method": "GET"},
        ],
        "ports": ports or [],  # port -> driver, from the composition root
        # FILL THIS too, or leave it empty deliberately. Same trap as capabilities: an empty
        # `emitted` reads as "this service publishes nothing", so a consumer wiring against it
        # subscribes to nothing and fails silently rather than at boot.
        # Neither. A page that emitted events would be a page with opinions; this one renders.
        "events": {"emitted": [], "consumed": []},  # e.g. {"emitted": ["wallet.credited"], ...}
        "admin_actions": _admin_actions(),
        "backup": _backup(),
        "user_actions": _user_actions(),
    }
