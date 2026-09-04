# =============================================================================
# whatsapp-assistant — Self-describing service manifest
# =============================================================================
from __future__ import annotations

from typing import Any

from app.config import Settings


def _admin_actions() -> list[dict[str, Any]]:
    """This service's declared admin actions, or [] if it declares none — mirrors every sibling
    service's own manifest.py (e.g. services/reminders')."""
    try:
        from app.admin_actions import ADMIN_ACTIONS
    except Exception:
        return []
    return list(ADMIN_ACTIONS)


def build_manifest(settings: Settings, ports: list[dict[str, str]] | None = None) -> dict[str, Any]:
    return {
        "name": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "env": settings.ENV,
        # "platform.secrets" is real now — app/api/v1/operator.py's /operator/secrets routes
        # enforce it (Depends(require_capability("platform.secrets"))). Still no "admin" here for
        # the same reason as before (undeclared in loyalty/reminders' manifests too, per
        # ci/check_deploy_wiring.py step 10's own rule: only a capability a route enforces belongs
        # here — /admin/ping's "admin" cap is a platform-wide convention every sibling repeats
        # undeclared, not this service's own).
        "capabilities": ["platform.secrets"],
        "endpoints": [
            {"path": "/healthz", "tier": "public", "method": "GET"},
            {"path": "/readyz", "tier": "public", "method": "GET"},
            {"path": "/metrics", "tier": "public", "method": "GET"},
            {"path": "/internal/health", "tier": "internal", "method": "GET"},
            {"path": "/internal/manifest", "tier": "internal", "method": "GET"},
            # The scheduler (or an operator) drives the sweep — the bus subscription is the fast
            # path, this tick is the one that closes timed-out sessions and composes debounced
            # replies, matching reminders' /internal split between the event fast-path and the
            # cron-driven tick.
            {"path": "/internal/whatsapp_assistant/tick", "tier": "internal", "method": "POST"},
            # Privacy and backup — real routes in app/api/internal.py, previously implemented but
            # left off this list, which is the exact silent gap docs/adding-a-new-app.md §3b warns
            # about: the route works, and nothing that reads the manifest can see it.
            {"path": "/internal/privacy/erase", "tier": "internal", "method": "POST"},
            {"path": "/internal/backup/export", "tier": "internal", "method": "POST"},
            {"path": "/internal/backup/verify", "tier": "internal", "method": "POST"},
            {"path": "/internal/backup/import", "tier": "internal", "method": "POST"},
            {"path": "/internal/whatsapp_assistant/price", "tier": "internal", "method": "POST"},
            # The operator credential surface (app/api/v1/operator.py) — GEMINI_API_KEY is the one
            # runtime-tunable knob this service has: see that file's own note on why it exists now.
            {"path": "/api/v1/assistant/operator/secrets", "tier": "user", "method": "GET"},
            {"path": "/api/v1/assistant/operator/secrets", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/assistant/operator/secrets/{}", "tier": "user", "method": "DELETE"},
        ],
        "ports": ports or [],
        "events": {"emitted": [], "consumed": ["whatsapp.message", "whatsapp.status"]},
        "admin_actions": _admin_actions(),
        "user_actions": [],
    }
