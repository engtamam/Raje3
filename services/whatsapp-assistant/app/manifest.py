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


def _user_actions() -> list[dict[str, Any]]:
    """This service's declared END-USER (shop) actions — the twin of `_admin_actions()`, read by
    api-gateway's own app_catalog.py to build a shop owner's console. Empty until 2026-09-07's
    pricing-card route was this service's first genuinely customer-facing endpoint."""
    try:
        from app.user_actions import USER_ACTIONS
    except Exception:
        return []
    return list(USER_ACTIONS)


def build_manifest(settings: Settings, ports: list[dict[str, str]] | None = None) -> dict[str, Any]:
    return {
        "name": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "env": settings.ENV,
        # "platform.secrets" and "platform.config" are both real — app/api/v1/operator.py's
        # /operator/secrets AND /operator/config routes each enforce one
        # (Depends(require_capability(...))). Still no "admin" here for the same reason as before
        # (undeclared in loyalty/reminders' manifests too, per ci/check_deploy_wiring.py step 10's
        # own rule: only a capability a route enforces belongs here — /admin/ping's "admin" cap is
        # a platform-wide convention every sibling repeats undeclared, not this service's own).
        # "whatsapp_assistant.pricing_read" joined 2026-09-07 — the FIRST real shop-facing
        # capability this service enforces (GET /api/v1/assistant/pricing/current, below);
        # granted to owner/manager in deploy/seed/roles.json + services/operations/data/
        # roles.seed.json, the same two roles that hold "billing.self".
        "capabilities": ["platform.secrets", "platform.config", "whatsapp_assistant.pricing_read"],
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
            # The operator credential surface (app/api/v1/operator.py) — ASSISTANT_MODEL_PROJECT/
            # ASSISTANT_MODEL_CREDENTIAL are the runtime-tunable knobs this service has: see that
            # file's own note on why it exists now.
            {"path": "/api/v1/assistant/operator/secrets", "tier": "user", "method": "GET"},
            {"path": "/api/v1/assistant/operator/secrets", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/assistant/operator/secrets/{}", "tier": "user", "method": "DELETE"},
            # /operator/config joined 2026-09-07 — app/runtime_policy.py's live-overridable knobs
            # (ASSISTANT_MODEL_NAME/SOFT_DECLINE_THRESHOLD/MAX_CAROUSEL_CARDS), same three-route
            # shape as reminders'/operations' own copy. persona-preview is read-only, no policy key.
            {"path": "/api/v1/assistant/operator/config", "tier": "user", "method": "GET"},
            {"path": "/api/v1/assistant/operator/config", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/assistant/operator/config/{}", "tier": "user", "method": "DELETE"},
            {"path": "/api/v1/assistant/operator/persona-preview", "tier": "user", "method": "GET"},
            # المحاسبة (the console's AI pricing calculator) — joined 2026-09-07. A pricing key
            # never applies instantly (core/pricing_schedule.py): /pricing/schedule is the only
            # door one can change through, always after a delay the caller sets.
            {"path": "/api/v1/assistant/operator/pricing/report", "tier": "user", "method": "GET"},
            {"path": "/api/v1/assistant/operator/pricing/pending", "tier": "user", "method": "GET"},
            {"path": "/api/v1/assistant/operator/pricing/schedule", "tier": "user", "method": "POST"},
            {"path": "/api/v1/assistant/operator/pricing/pending/{}", "tier": "user", "method": "DELETE"},
            # THE SHOP'S OWN READ — see this file's own note on "whatsapp_assistant.pricing_read"
            # above and app/api/v1/__init__.py's route docstring.
            # THE APP-STORE CARD'S OWN CONTENT (app/core/features.py) — same posture as pricing/
            # current right below: a shop reading a fact about their own subscription, never a
            # purchase check.
            {"path": "/api/v1/assistant/features", "tier": "user", "method": "GET"},
            {"path": "/api/v1/assistant/pricing/current", "tier": "user", "method": "GET"},
            # محلّي's own "أثر الذكاء الاصطناعي" card, joined 2026-09-07 — reuses the same
            # capability as the price read above (same "owner/manager reading their own AI
            # feature" family); ALWAYS tenant-scoped to the caller's own session, structurally —
            # see core/shop_impact_report.py's own module docstring for why.
            {"path": "/api/v1/assistant/growth/my-impact", "tier": "user", "method": "GET"},
            # المحاسبة's growth analytics half — real package-upsell offer/accept/decline off
            # wa_upsell_ledger (core/upsell_report.py), per branch. Operator-only, same
            # platform.config gate as the pricing routes above; not gateway-routed yet (no console
            # UI in this phase) — listed here anyway so /internal/manifest never silently omits a
            # route that already works, the exact gap docs/adding-a-new-app.md §3b warns about.
            {"path": "/api/v1/assistant/operator/growth/upsell-report", "tier": "user", "method": "GET"},
            # SAME growth/ family — average invoice value across every AI-made booking (package or
            # plain service), replacing the old avg_ticket_increase_minor that used to live inside
            # the upsell report above (core/invoice_report.py has the full reasoning).
            {"path": "/api/v1/assistant/operator/growth/invoice-report", "tier": "user", "method": "GET"},
        ],
        "ports": ports or [],
        "events": {"emitted": [], "consumed": ["whatsapp.message", "whatsapp.status"]},
        "admin_actions": _admin_actions(),
        "user_actions": _user_actions(),
    }
