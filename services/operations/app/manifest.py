# =============================================================================
# operations — Self-describing service manifest
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
        # Three, and the split is a product decision rather than a modelling one. Recording a
        # visit is what every operator does all day. Reading the customer book is a different
        # privilege — a shop that hires seasonal help should grant the first without the second.
        # Managing the catalogue, the staff and the branches is the owner's.
        "capabilities": ["operations.record", "operations.read", "operations.manage",
                         # OURS. No tenant token carries it: a tyre shop must not be able to
                         # rename "بنشر" for every other tyre shop on the product.
                         "platform.operations"],
        "endpoints": [
            {"path": "/healthz", "tier": "public", "method": "GET"},
            {"path": "/readyz", "tier": "public", "method": "GET"},
            {"path": "/metrics", "tier": "public", "method": "GET"},
            {"path": "/internal/health", "tier": "internal", "method": "GET"},
            {"path": "/internal/manifest", "tier": "internal", "method": "GET"},
            {"path": "/internal/backup/export", "tier": "internal", "method": "POST"},
            {"path": "/internal/backup/import", "tier": "internal", "method": "POST"},
            {"path": "/internal/backup/verify", "tier": "internal", "method": "POST"},
            {"path": "/internal/operations/visits/batch", "tier": "internal", "method": "POST"},
            {"path": "/internal/operations/seed-tenant", "tier": "internal", "method": "POST"},
            {"path": "/internal/operations/sectors", "tier": "internal", "method": "GET"},
            # The most sensitive surface this service has: it turns a pseudonym back into a phone
            # number for a peer that is about to send. One subject per call, never a list.
            {"path": "/internal/operations/recipient", "tier": "internal", "method": "POST"},
            # The read that makes the visit event self-healing. The bus is at-most-once, so a
            # consumer that misses an event must be able to catch up by reading — see the route.
            {"path": "/internal/operations/visits/since", "tier": "internal", "method": "POST"},
            {"path": "/internal/privacy/erase", "tier": "internal", "method": "POST",
             # DECLARED, because a data map built from manifests is how a DSAR fan-out
             # finds who holds a person. An undeclared holder is never asked, never acks,
             # and is therefore never MISSED — the request closes green on an erasure
             # that did not happen.
             "erasure_category": "subject"},
            {"path": "/api/v1/whoami", "tier": "user", "method": "GET"},
            # ── the field screen — the product, as far as the shop floor is concerned ──────
            {"path": "/api/v1/field/visits", "tier": "user", "method": "POST"},
            {"path": "/api/v1/field/customers/recent", "tier": "user", "method": "GET"},
            {"path": "/api/v1/field/customers/by-phone", "tier": "user", "method": "GET"},
            {"path": "/api/v1/field/customers/{}", "tier": "user", "method": "GET"},
            {"path": "/api/v1/field/catalogue", "tier": "user", "method": "GET"},
            # ── the back office ───────────────────────────────────────────────────────────
            {"path": "/api/v1/staff/operators", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/operators", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/operators/verify-pin", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/branches", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/branches", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/services", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/services/{}", "tier": "user", "method": "PATCH"},
            # ── the platform console: OURS, not an establishment's ────────────────────────
            {"path": "/api/v1/platform/sectors", "tier": "user", "method": "GET"},
            {"path": "/api/v1/platform/sectors/{}", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/platform/sectors/{}", "tier": "user", "method": "DELETE"},
            {"path": "/api/v1/platform/sector-fields", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/platform/templates", "tier": "user", "method": "GET"},
            {"path": "/api/v1/platform/templates/{}", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/platform/templates/{}", "tier": "user", "method": "DELETE"},
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
        # ONE event, and it is the spine of the product: reminders schedules from it, insights
        # counts it, loyalty will award from it. Published rather than called, so this service
        # stays ignorant of who consumes a visit — a service that knows its consumers has to be
        # changed every time one is added. The payload carries subject_ref, never the phone.
        "events": {"emitted": ["operations.visit.recorded"], "consumed": []},
        "admin_actions": _admin_actions(),
        "backup": _backup(),
        "user_actions": _user_actions(),
    }
