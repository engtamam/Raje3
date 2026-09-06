# =============================================================================
# loyalty — Self-describing service manifest
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
        # Four, split by who is harmed. Reading a balance is harmless; REDEEMING spends something
        # the customer owns, which is why it is its own capability rather than folded into
        # `manage` — the field operator must be able to spend and must not be able to reprice the
        # rewards he is spending against. And `platform.loyalty` is ours.
        "capabilities": ["loyalty.read", "loyalty.redeem", "loyalty.manage", "platform.loyalty",
                         # WHAT api/v1/operator.py ACTUALLY ENFORCES. Advertised because they are
                         # enforced here — not because we grant them to a tenant: platform.* is
                         # ours, and authz denies the whole prefix to every establishment. The
                         # actions used to name platform.<service> instead, so the console rendered
                         # the credentials buttons for whoever held that and the service answered
                         # 403 to every one of them.
                         "platform.secrets", "platform.config"],
        "endpoints": [
            # From the generated scaffold, and kept: what a client calls to confirm its token is
            # accepted at all, which is the first question asked when something else is failing.
            # Undeclared in every service until a guard compared the manifest with the app itself.
            {"path": "/api/v1/loyalty/admin/ping", "tier": "user", "method": "GET"},
            {"path": "/healthz", "tier": "public", "method": "GET"},
            {"path": "/readyz", "tier": "public", "method": "GET"},
            {"path": "/metrics", "tier": "public", "method": "GET"},
            {"path": "/internal/health", "tier": "internal", "method": "GET"},
            {"path": "/internal/manifest", "tier": "internal", "method": "GET"},
            {"path": "/internal/backup/export", "tier": "internal", "method": "POST"},
            {"path": "/internal/backup/import", "tier": "internal", "method": "POST"},
            {"path": "/internal/backup/verify", "tier": "internal", "method": "POST"},
            # THE HEARTBEAT. Without its schedule this service is inert and looks healthy:
            # balances accumulate, every probe passes, and nothing ever expires (trap §4.1).
            {"path": "/internal/loyalty/tick", "tier": "internal", "method": "POST"},
            {"path": "/internal/loyalty/earn", "tier": "internal", "method": "POST"},
            {"path": "/internal/loyalty/portal/balance", "tier": "internal", "method": "GET"},
            # The integrated till redeems here (spec §9.8) — the SAME core path as the field.
            {"path": "/internal/loyalty/redeem", "tier": "internal", "method": "POST"},
            # The repair for a materialised total that drifted from its own ledger.
            # Aggregates for insights' weekly digest — totals only, never who.
            {"path": "/internal/loyalty/report", "tier": "internal", "method": "POST"},
            {"path": "/internal/loyalty/reconcile", "tier": "internal", "method": "POST"},
            {"path": "/internal/privacy/erase", "tier": "internal", "method": "POST",
             # DECLARED, because a data map built from manifests is how a DSAR fan-out
             # finds who holds a person. An undeclared holder is never asked, never acks,
             # and is therefore never MISSED — the request closes green on an erasure
             # that did not happen.
             "erasure_category": "subject"},
            # ── the field screen (spec §4.7, §9.5) ────────────────────────────────────────
            {"path": "/api/v1/loyalty/balance/{}", "tier": "user", "method": "GET"},
            {"path": "/api/v1/loyalty/redeem", "tier": "user", "method": "POST"},
            {"path": "/api/v1/loyalty/adjust", "tier": "user", "method": "POST"},
            {"path": "/api/v1/loyalty/history/{}", "tier": "user", "method": "GET"},
            # ── the rewards catalogue (spec §9.4) ─────────────────────────────────────────
            {"path": "/api/v1/loyalty/rewards", "tier": "user", "method": "GET"},
            {"path": "/api/v1/loyalty/rewards", "tier": "user", "method": "POST"},
            {"path": "/api/v1/loyalty/rewards/{}", "tier": "user", "method": "PATCH"},
            # ── the earning tree (spec §9.2, §9.3) ────────────────────────────────────────
            {"path": "/api/v1/loyalty/settings", "tier": "user", "method": "GET"},
            {"path": "/api/v1/loyalty/settings/general", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/loyalty/settings/group", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/loyalty/settings/service/{}", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/loyalty/settings/service/{}", "tier": "user", "method": "DELETE"},
            {"path": "/api/v1/loyalty/settings/package/{}", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/loyalty/settings/mode", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/loyalty/report", "tier": "user", "method": "GET"},
            # OURS: support repairing a balance for a shop that is not theirs.
            {"path": "/api/v1/loyalty/platform/reconcile", "tier": "user", "method": "POST"},
            {"path": "/api/v1/loyalty/whoami", "tier": "user", "method": "GET"},
            # The operator surface: credentials and policy an operator changes after launch.
            # The operator surface: policy an operator changes after launch. The credential-
            # management routes that used to sit here (a dead SecretStore nothing ever consumed)
            # were removed — see git history for the incident.
            {"path": "/api/v1/loyalty/operator/config", "tier": "user", "method": "GET"},
            {"path": "/api/v1/loyalty/operator/config", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/loyalty/operator/config/{}", "tier": "user", "method": "DELETE"},
        ],
        "ports": ports or [],  # port -> driver, from the composition root
        # FILL THIS too, or leave it empty deliberately. Same trap as capabilities: an empty
        # `emitted` reads as "this service publishes nothing", so a consumer wiring against it
        # subscribes to nothing and fails silently rather than at boot.
        # Consumed: a visit becomes points. Emitted: a redemption, so insights can count what the
        # programme achieved without this service knowing who counts it. The bus is at-most-once
        # by contract, which is why `/internal/loyalty/earn` also has a catch-up caller.
        "events": {"emitted": ["loyalty.redeemed"], "consumed": ["operations.visit.recorded"]},  # e.g. {"emitted": ["wallet.credited"], ...}
        "admin_actions": _admin_actions(),
        "backup": _backup(),
        "user_actions": _user_actions(),
    }
