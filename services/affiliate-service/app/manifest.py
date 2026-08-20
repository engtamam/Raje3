# =============================================================================
# affiliate-service — Self-describing service manifest
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
        # The two the scaffold's OWN operator routes already enforce (api/v1/operator.py:
        # require_capability("platform.secrets") / ("platform.config")) — pre-declared so a freshly
        # generated service's operator routes are grantable and reachable, not permanently dark until
        # someone remembers to advertise them. ADD this service's domain capabilities alongside them
        # (e.g. "files.upload", "files.read"); remove one only if you also remove the route that
        # enforces it. An advertised capability is what the admin panel and onboarding grant against.
        "capabilities": ["platform.secrets", "platform.config", "platform.affiliates",
                        "platform.affiliates_payouts"],
        "endpoints": [
            {"path": "/healthz", "tier": "public", "method": "GET"},
            {"path": "/readyz", "tier": "public", "method": "GET"},
            {"path": "/metrics", "tier": "public", "method": "GET"},
            {"path": "/internal/health", "tier": "internal", "method": "GET"},
            {"path": "/internal/manifest", "tier": "internal", "method": "GET"},
            {"path": "/internal/backup/export", "tier": "internal", "method": "POST"},
            {"path": "/internal/backup/import", "tier": "internal", "method": "POST"},
            {"path": "/internal/backup/verify", "tier": "internal", "method": "POST"},
            {"path": "/internal/referrals/stamp", "tier": "internal", "method": "POST"},
            {"path": "/internal/commissions/sync", "tier": "internal", "method": "POST"},
            {"path": "/internal/commissions/sweep", "tier": "internal", "method": "POST"},
            {"path": "/internal/privacy/erase", "tier": "internal", "method": "POST",
             # DECLARED, because a data map built from manifests is how a DSAR fan-out
             # finds who holds a person. An undeclared holder is never asked, never acks,
             # and is therefore never MISSED — the request closes green on an erasure
             # that did not happen.
             "erasure_category": "subject"},
            {"path": "/api/v1/admin/ping", "tier": "user", "method": "GET"},
            {"path": "/api/v1/whoami", "tier": "user", "method": "GET"},
            # «بوابة القبول» (spec §2) — no token yet, same tier as operations' own /signup.
            {"path": "/api/v1/affiliates/apply", "tier": "public", "method": "POST"},
            {"path": "/api/v1/affiliates/signin", "tier": "public", "method": "POST"},
            {"path": "/api/v1/affiliates/accept-invite", "tier": "public", "method": "POST"},
            # Who I am — his own id doubles as his referral code (spec §1).
            {"path": "/api/v1/affiliates/me", "tier": "user", "method": "GET"},
            # A manager naming somebody for his own team — still gated by the admin queue below.
            {"path": "/api/v1/affiliates/me/invite", "tier": "user", "method": "POST"},
            {"path": "/api/v1/affiliates/me/commissions", "tier": "user", "method": "GET"},
            # spec §10: a manager's own team, WITH what each of them actually earned.
            {"path": "/api/v1/affiliates/me/team", "tier": "user", "method": "GET"},
            {"path": "/api/v1/affiliates/me/payout-method", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/affiliates/me/balance", "tier": "user", "method": "GET"},
            {"path": "/api/v1/affiliates/me/withdrawals", "tier": "user", "method": "GET"},
            {"path": "/api/v1/affiliates/me/withdrawals", "tier": "user", "method": "POST"},
            {"path": "/api/v1/admin/withdrawals", "tier": "user", "method": "GET"},
            {"path": "/api/v1/admin/withdrawals/{}/receipt", "tier": "user", "method": "POST"},
            {"path": "/api/v1/admin/withdrawals/{}/receipt", "tier": "user", "method": "GET"},
            {"path": "/api/v1/admin/withdrawals/{}/complete", "tier": "user", "method": "POST"},
            {"path": "/api/v1/admin/withdrawals/{}/reject", "tier": "user", "method": "POST"},
            {"path": "/api/v1/affiliates/me/withdrawals/{}/receipt", "tier": "user", "method": "GET"},
            {"path": "/api/v1/admin/affiliates/{}/platform-revenue", "tier": "user", "method": "POST"},
            # «برنامج دعم الوفاء» (spec §8).
            {"path": "/api/v1/affiliates/me/wafa-requests", "tier": "user", "method": "POST"},
            {"path": "/api/v1/affiliates/me/wafa-requests", "tier": "user", "method": "GET"},
            {"path": "/api/v1/affiliates/me/team/wafa-requests", "tier": "user", "method": "GET"},
            {"path": "/api/v1/affiliates/me/team/wafa-requests/{}/decision", "tier": "user", "method": "POST"},
            {"path": "/api/v1/admin/wafa-requests", "tier": "user", "method": "GET"},
            {"path": "/api/v1/admin/wafa-requests/{}/decision", "tier": "user", "method": "POST"},
            # «رشّح نفسك لوظيفة» (spec §8).
            {"path": "/api/v1/affiliates/me/employment-requests", "tier": "user", "method": "POST"},
            {"path": "/api/v1/affiliates/me/employment-requests", "tier": "user", "method": "GET"},
            {"path": "/api/v1/admin/employment-requests", "tier": "user", "method": "GET"},
            {"path": "/api/v1/admin/employment-requests/{}/decision", "tier": "user", "method": "POST"},
            # §٦ Lead Sourcing — a manager's OWN Google Places API key (BYOK).
            {"path": "/api/v1/affiliates/me/places-api-key", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/affiliates/me/places-api-key", "tier": "user", "method": "GET"},
            {"path": "/api/v1/affiliates/me/places-api-key", "tier": "user", "method": "DELETE"},
            # §٦ Lead Sourcing — the search itself + assignment.
            {"path": "/api/v1/affiliates/me/leads/search", "tier": "user", "method": "POST"},
            {"path": "/api/v1/affiliates/me/leads/search", "tier": "user", "method": "GET"},
            {"path": "/api/v1/affiliates/me/leads/search/{}", "tier": "user", "method": "GET"},
            {"path": "/api/v1/affiliates/me/leads", "tier": "user", "method": "GET"},
            {"path": "/api/v1/affiliates/me/leads/{}/assign", "tier": "user", "method": "POST"},
            {"path": "/internal/leads/tick", "tier": "internal", "method": "POST"},
            # §١٣ — a shop's tickets, consent-scoped to the marketer who referred it.
            {"path": "/api/v1/affiliates/me/shops/{}/tickets", "tier": "user", "method": "GET"},
            {"path": "/api/v1/affiliates/me/shops/{}/tickets", "tier": "user", "method": "POST"},
            {"path": "/api/v1/affiliates/me/shops/{}/tickets/{}", "tier": "user", "method": "GET"},
            {"path": "/api/v1/affiliates/me/shops/{}/tickets/{}/replies", "tier": "user",
             "method": "POST"},
            # The admin's queue over that gate.
            {"path": "/api/v1/admin/affiliates", "tier": "user", "method": "GET"},
            {"path": "/api/v1/admin/affiliates/{}/approve", "tier": "user", "method": "POST"},
            {"path": "/api/v1/admin/affiliates/{}/reject", "tier": "user", "method": "POST"},
            {"path": "/api/v1/admin/affiliates/{}/suspend", "tier": "user", "method": "POST"},
            {"path": "/api/v1/admin/affiliates/{}/reactivate", "tier": "user", "method": "POST"},
            # The operator surface: credentials and policy an operator changes after launch.
            # Declared like anything else — a route table built from manifests that omits the
            # place credentials are set is a route table that hides the highest-privilege
            # surface the service has.
            {"path": "/api/v1/operator/secrets", "tier": "user", "method": "GET"},
            {"path": "/api/v1/operator/secrets", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/operator/secrets/{}", "tier": "user", "method": "DELETE"},
            {"path": "/api/v1/operator/config", "tier": "user", "method": "GET"},
            {"path": "/api/v1/operator/config", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/operator/config/{}", "tier": "user", "method": "DELETE"},
        ],
        "ports": ports or [],  # port -> driver, from the composition root
        # FILL THIS too, or leave it empty deliberately. Same trap as capabilities: an empty
        # `emitted` reads as "this service publishes nothing", so a consumer wiring against it
        # subscribes to nothing and fails silently rather than at boot.
        "events": {"emitted": [], "consumed": []},  # e.g. {"emitted": ["wallet.credited"], ...}
        "admin_actions": _admin_actions(),
        "backup": _backup(),
        "user_actions": _user_actions(),
    }
