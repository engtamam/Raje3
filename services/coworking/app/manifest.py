# =============================================================================
# coworking — Self-describing service manifest
# -----------------------------------------------------------------------------
# A machine-readable descriptor so a gateway/platform can discover what this
# service is, what it exposes, which ports (adapters) it uses, and which events
# it emits/consumes. Served at GET /internal/manifest.
# =============================================================================
from __future__ import annotations

from typing import Any

from app.config import Settings


def _backup() -> dict:
    try:
        from app.backup_manifest import BACKUP
    except Exception:
        return {"object_prefix": "", "collections": [], "excluded": []}
    return BACKUP


def _admin_actions() -> list[dict[str, Any]]:
    try:
        from app.admin_actions import ADMIN_ACTIONS
    except Exception:
        return []
    return list(ADMIN_ACTIONS)


def _user_actions() -> list[dict[str, Any]]:
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
        "capabilities": ["platform.secrets", "platform.config",
                        # The one capability every shop owner/admin token holds to run THIS app
                        # for their own tenant — never a platform-operator capability.
                        "coworking.manage"],
        "endpoints": [
            {"path": "/healthz", "tier": "public", "method": "GET"},
            {"path": "/readyz", "tier": "public", "method": "GET"},
            {"path": "/metrics", "tier": "public", "method": "GET"},
            {"path": "/internal/health", "tier": "internal", "method": "GET"},
            {"path": "/internal/manifest", "tier": "internal", "method": "GET"},
            {"path": "/internal/backup/export", "tier": "internal", "method": "POST"},
            {"path": "/internal/backup/import", "tier": "internal", "method": "POST"},
            {"path": "/internal/backup/verify", "tier": "internal", "method": "POST"},
            {"path": "/internal/privacy/erase", "tier": "internal", "method": "POST",
             "erasure_category": "resource_bookings"},
            {"path": "/api/v1/coworking/whoami", "tier": "user", "method": "GET"},
            {"path": "/api/v1/coworking/admin/ping", "tier": "user", "method": "GET"},
            # ── resources (spec §1/§7) ──────────────────────────────────────────────────────
            {"path": "/api/v1/coworking/resources", "tier": "user", "method": "POST"},
            {"path": "/api/v1/coworking/resources", "tier": "user", "method": "GET"},
            {"path": "/api/v1/coworking/resources/{resource_id}", "tier": "user", "method": "PATCH"},
            {"path": "/api/v1/coworking/resources/{resource_id}/availability", "tier": "user",
             "method": "PUT"},
            {"path": "/api/v1/coworking/resources/{resource_id}/image", "tier": "user",
             "method": "POST"},
            {"path": "/api/v1/coworking/resources/{resource_id}/image", "tier": "user",
             "method": "GET"},
            # ── join requests / block list (spec §6/§7) ─────────────────────────────────────
            {"path": "/api/v1/coworking/joins", "tier": "user", "method": "GET"},
            {"path": "/api/v1/coworking/joins/{phone}/approve", "tier": "user", "method": "POST"},
            {"path": "/api/v1/coworking/joins/{phone}/reject", "tier": "user", "method": "POST"},
            {"path": "/api/v1/coworking/joins/{phone}/block", "tier": "user", "method": "POST"},
            {"path": "/api/v1/coworking/joins/{phone}/unblock", "tier": "user", "method": "POST"},
            # ── bookings (spec §7) ───────────────────────────────────────────────────────────
            {"path": "/api/v1/coworking/bookings", "tier": "user", "method": "GET"},
            {"path": "/api/v1/coworking/bookings/{booking_id}/cancel", "tier": "user",
             "method": "POST"},
            # ── tenant-level pause (spec §5) ─────────────────────────────────────────────────
            {"path": "/api/v1/coworking/pause", "tier": "user", "method": "GET"},
            {"path": "/api/v1/coworking/pause", "tier": "user", "method": "PUT"},
            # ── the operator surface (credentials/policy, inherited from _template) ──────────
            {"path": "/api/v1/coworking/operator/secrets", "tier": "user", "method": "GET"},
            {"path": "/api/v1/coworking/operator/secrets", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/coworking/operator/secrets/{name}", "tier": "user", "method": "DELETE"},
            {"path": "/api/v1/coworking/operator/config", "tier": "user", "method": "GET"},
            {"path": "/api/v1/coworking/operator/config", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/coworking/operator/config/{key}", "tier": "user", "method": "DELETE"},
            # ── the freelancer's own public door (spec §6) — see api/public.py's own docstring
            # for why this is served here rather than by portal, despite the `/p/*` prefix ─────
            {"path": "/p/coworking/{tenant}/resources", "tier": "public", "method": "GET"},
            {"path": "/p/coworking/{tenant}/slots", "tier": "public", "method": "GET"},
            {"path": "/p/coworking/{tenant}/status", "tier": "public", "method": "GET"},
            {"path": "/p/coworking/{tenant}/join", "tier": "public", "method": "POST"},
            {"path": "/p/coworking/{tenant}/bookings", "tier": "public", "method": "POST"},
            {"path": "/p/coworking/{tenant}/my-bookings", "tier": "public", "method": "GET"},
        ],
        "ports": ports or [],
        "events": {"emitted": [], "consumed": []},
        "admin_actions": _admin_actions(),
        "backup": _backup(),
        "user_actions": _user_actions(),
    }
