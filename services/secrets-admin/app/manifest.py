# =============================================================================
# secrets-admin — Self-describing service manifest
# -----------------------------------------------------------------------------
# A machine-readable descriptor so a gateway/platform can discover what this
# service is, what it exposes, which ports (adapters) it uses, and which events
# it emits/consumes. Served at GET /internal/manifest.
# =============================================================================
from __future__ import annotations

from typing import Any

from app.config import Settings


def _admin_actions() -> list[dict[str, Any]]:
    """This service's declared admin actions (docs/contracts/admin-actions.schema.json).

    The panel is a map — these decide what is SHOWN, never what an operator may DO. Both actions
    below are re-checked against `platform.secrets_manage` at their own route on every call.
    """
    try:
        from app.admin_actions import ADMIN_ACTIONS
    except Exception:
        return []
    return list(ADMIN_ACTIONS)


def build_manifest(
    settings: Settings, ports: list[dict[str, str]] | None = None
) -> dict[str, Any]:
    return {
        "name": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "env": settings.ENV,
        # ONE CAPABILITY, AND IT IS DELIBERATELY NOT `platform.operations`.
        #
        # `platform.operations` already exists and already means "ours, not a tenant's" — reusing
        # it would have been one fewer thing to seed. It is refused because it is far wider than
        # this: it curates the message library and the partner ledger, and it is held by an
        # operator whose job is content. Replacing the credential every WhatsApp message in the
        # product is sent with is a different job, and the whole value of a narrow capability is
        # that it is held by fewer people.
        "capabilities": ["platform.secrets_manage"],
        "endpoints": [
            {"path": "/healthz", "tier": "public", "method": "GET"},
            {"path": "/readyz", "tier": "public", "method": "GET"},
            {"path": "/metrics", "tier": "public", "method": "GET"},
            {"path": "/internal/health", "tier": "internal", "method": "GET"},
            {"path": "/internal/manifest", "tier": "internal", "method": "GET"},
            # NO ERASURE ROUTE AND NO BACKUP ROUTES — see api/internal.py. Both
            # absences are decisions: there is no subject here to erase and nothing of ours to
            # export, and declaring either would put this service on a fan-out roster as a holder
            # that acks work it never did.
            {"path": "/api/v1/secrets/whoami", "tier": "user", "method": "GET"},
            # ── the whole product surface: read what is configured, replace one thing ─────────
            {"path": "/api/v1/secrets", "tier": "user", "method": "GET"},
            {"path": "/api/v1/secrets/{}", "tier": "user", "method": "POST"},
        ],
        "ports": ports or [],  # port -> driver, from the composition root
        # NEITHER, AND BOTH DELIBERATELY EMPTY. A credential change is not a fact other services
        # should learn by subscription: the one consumer that must react is the Deployment whose
        # pods read the value, and it is told by being restarted — synchronously, in the same
        # request, so the person who pressed the button learns whether it worked.
        "events": {"emitted": [], "consumed": []},
        "admin_actions": _admin_actions(),
        # NO BACKUP DECLARATION. An empty one would say "we hold collections and back up none of
        # them"; the truth is that we hold no collections, and the objects we patch belong to the
        # cluster's own etcd backup.
        "backup": {"object_prefix": "", "collections": [], "excluded": []},
        # NO USER ACTIONS. Every route here is an operator's, gated by a platform.* capability that
        # no tenant token carries — and the user catalogue is explicitly for a person acting on
        # their OWN data.
        "user_actions": [],
    }
