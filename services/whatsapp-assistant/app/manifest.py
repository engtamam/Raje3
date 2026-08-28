# =============================================================================
# whatsapp-assistant — Self-describing service manifest
# =============================================================================
from __future__ import annotations

from typing import Any

from app.config import Settings


def build_manifest(settings: Settings, ports: list[dict[str, str]] | None = None) -> dict[str, Any]:
    return {
        "name": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "env": settings.ENV,
        # Empty, deliberately — was `["whatsapp_assistant.converse", "platform.whatsapp_assistant"]`,
        # the _template default, and NEITHER was ever enforced by a real route: this service's own
        # `/api/v1/*` surface is just `/whoami` (no capability) and `/admin/ping` (gated on the
        # platform-wide "admin" cap every sibling's admin/ping route also uses, undeclared here for
        # the same reason it is undeclared in loyalty/reminders' manifests). ci/check_deploy_wiring.py
        # step 10 caught it: an advertised-but-unenforced capability is grantable and does nothing —
        # worse than no capability, because it LOOKS like access. Add a real entry here the day a
        # route actually requires one (mirroring loyalty's owner/platform capability split), not
        # before.
        "capabilities": [],
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
        ],
        "ports": ports or [],
        "events": {"emitted": [], "consumed": ["whatsapp.message", "whatsapp.status"]},
        # Empty on purpose: this service exposes no operator-panel routes (no api/v1/operator.py),
        # so it has nothing for the admin panel to call. See app/api/v1/__init__.py's own note —
        # the operator surface (platform.secrets / platform.config credential+config editing) is a
        # real capability every sibling service carries, but nothing in this service's config is
        # operator-tunable yet (every knob is deploy-time env, not a per-tenant/runtime override),
        # so declaring routes and capabilities for it now would be dead surface. Add it the day a
        # real operator-tunable setting exists here, mirroring services/reminders/app/api/v1/
        # operator.py and app/admin_actions.py — do not invent one to satisfy this comment.
        "admin_actions": [],
        "user_actions": [],
    }
