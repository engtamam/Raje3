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
        "capabilities": ["whatsapp_assistant.converse", "platform.whatsapp_assistant"],
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
        ],
        "ports": ports or [],
        "events": {"emitted": [], "consumed": ["whatsapp.message", "whatsapp.status"]},
        "admin_actions": [],
        "user_actions": [],
    }
